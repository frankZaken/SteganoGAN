# shared/security/otp.py
# Deterministic OTP using HMAC-SHA256 keystream.
#
# Design:
#   key    = room seed (32 bytes, generated once per room with secrets.token_bytes)
#   nonce  = 16 random bytes prepended to each ciphertext (unique per message)
#   stream = HMAC-SHA256(key=seed, msg=nonce + counter_bytes)  repeated until length met
#   cipher = plaintext XOR stream
#
# The old_server never sees plaintext â€” it only stores: nonce + XOR(plaintext, stream).
# Security: as long as the nonce is unique, this is as secure as the HMAC PRF.

import hmac as _hmac
import hashlib
import secrets


def _keystream(seed: bytes, nonce: bytes, length: int) -> bytes:
    stream: list[int] = []
    counter = 0
    while len(stream) < length:
        msg   = nonce + counter.to_bytes(4, "big")
        block = _hmac.new(seed, msg, hashlib.sha256).digest()
        stream.extend(block)
        counter += 1
    return bytes(stream[:length])


def otp_encrypt(plaintext: bytes, seed: bytes) -> bytes:
    """Encrypt plaintext bytes; returns nonce (16 B) + ciphertext."""
    nonce      = secrets.token_bytes(16)
    ks         = _keystream(seed, nonce, len(plaintext))
    ciphertext = bytes(a ^ b for a, b in zip(plaintext, ks))
    return nonce + ciphertext


def otp_decrypt(data: bytes, seed: bytes) -> bytes:
    """Decrypt bytes produced by otp_encrypt; returns plaintext."""
    if len(data) < 16:
        raise ValueError("Data too short to contain nonce")
    nonce      = data[:16]
    ciphertext = data[16:]
    ks         = _keystream(seed, nonce, len(ciphertext))
    return bytes(a ^ b for a, b in zip(ciphertext, ks))
