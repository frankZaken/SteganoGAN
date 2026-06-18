# security/channel.py

# Encrypted, authenticated transport: per-connection DHE key agreement
# (server authenticated with RSA), keys expanded with KDF2, records sealed
# with AES-128-CTR + HMAC-SHA256 (encrypt-then-MAC).

import secrets

from security.asymmetric.dhe        import DHE
from security.asymmetric.rsa        import sign_bytes, verify_bytes, PrivateKey, PublicKey
from security.protocols.dhe         import DHESKE, TCPKeyEstablishing, send_msg, recv_msg
from security.symmetric.kdf         import KDF2
from security.symmetric.aes.aes128  import AES128
from security.symmetric.aes.modes   import CTR
from security.integrity.hmac        import HMAC
from security.utils                 import int_to_bytes, bytes_to_int

from Crypto.Cipher import AES as _LibAES   # fast (C) AES for bulk record traffic


USE_FAST_AES = True

TAG_LEN   = 32          # HMAC-SHA256 output
AES_LEN   = 16          # AES-128 key
NONCE_LEN = 8           # CTR nonce = block_size(16) - 8
BUFFER    = 4096


class SecurityError(Exception):
    pass


# ── key expansion (KDF2) ─────────────────────────────────────────────────────
def _derive_keys(shared: bytes):
    def k(label: bytes, size: int) -> bytes:
        return KDF2("sha256", shared + label, size).digest()

    s2c = {"aes": k(b"S2C|AES", AES_LEN), "mac": k(b"S2C|MAC", TAG_LEN), "nonce": k(b"S2C|NONCE", NONCE_LEN)}
    c2s = {"aes": k(b"C2S|AES", AES_LEN), "mac": k(b"C2S|MAC", TAG_LEN), "nonce": k(b"C2S|NONCE", NONCE_LEN)}
    return s2c, c2s


def handshake(sock, role: str, server_private: PrivateKey | None = None, server_public: PublicKey | None = None):

    transport = TCPKeyEstablishing(connection=sock, buffer=BUFFER)
    ske = DHESKE(send=transport.send, receive=transport.receive, auto=True)
    ske.initialize()
    my_dh = ske.dhe.send()

    if role == "server":
        # Server proves identity: signs its DH value with the hardcoded private key.
        send_msg(sock, int_to_bytes(my_dh))
        send_msg(sock, sign_bytes(int_to_bytes(my_dh), server_private))
        peer_dh = bytes_to_int(recv_msg(sock))

    else:  # client
        peer_dh = bytes_to_int(recv_msg(sock))
        signature = recv_msg(sock)

        if not verify_bytes(int_to_bytes(peer_dh), signature, server_public):
            raise SecurityError("server identity could not be verified (possible MITM)")

        send_msg(sock, int_to_bytes(my_dh))

    shared = ske.dhe.receive(peer_dh)

    return _derive_keys(int_to_bytes(shared))


def _ctr_crypt(key: bytes, nonce: bytes, data: bytes) -> bytes:
    # CTR is symmetric — the same operation encrypts and decrypts.
    if USE_FAST_AES:
        return _LibAES.new(key, _LibAES.MODE_CTR, nonce=nonce).encrypt(data)
    return b"".join(CTR(AES128(key), nonce).encrypt(data))

def seal(plaintext: bytes, ks: dict) -> bytes:
    ciphertext = _ctr_crypt(ks["aes"], ks["nonce"], plaintext)   # CTR: no padding needed
    tag = HMAC("sha256", ciphertext, ks["mac"]).derive()

    return tag + ciphertext

def open_(frame: bytes, ks: dict) -> bytes:
    tag, ciphertext = frame[:TAG_LEN], frame[TAG_LEN:]
    expected = HMAC("sha256", ciphertext, ks["mac"]).derive()

    if not secrets.compare_digest(tag, expected):
        raise SecurityError("HMAC check failed (tampered, or wrong key)")

    return _ctr_crypt(ks["aes"], ks["nonce"], ciphertext)        # CTR decrypt == encrypt