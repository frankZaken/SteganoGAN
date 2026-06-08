# shared/security/rsa_manager.py

import json
import base64
from pathlib import Path

from security.crypto.rsa import (
    rsa_keys, distant_random_primes,
    dump_public_key, load_public_key,
    encrypt_bytes, decrypt_bytes,
    PublicKey, PrivateKey,
)
from security.aes_manager import generate_aes_key, encrypt as aes_encrypt, decrypt as aes_decrypt

KEYS_DIR     = Path(__file__).parent.parent / "data" / "keys"
KEY_BITS     = 512
AES_KEY_SIZE = 16


def generate_keypair() -> tuple[PrivateKey, PublicKey]:
    primes = distant_random_primes(KEY_BITS)
    return rsa_keys(primes)


def save_private_key(user_id: int, private_key: PrivateKey):
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    path = KEYS_DIR / f"{user_id}.json"
    path.write_text(json.dumps({"n": private_key.n, "d": private_key.d}))


def load_private_key(user_id: int) -> PrivateKey | None:
    path = KEYS_DIR / f"{user_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return PrivateKey(n=data["n"], d=data["d"])


def serialize_public_key(pub: PublicKey) -> str:
    return dump_public_key(pub).decode()


def deserialize_public_key(serialized: str) -> PublicKey:
    return load_public_key(serialized.encode())


def encrypt_for_recipient(data: bytes, recipient_public_key: PublicKey) -> bytes:
    aes_key        = generate_aes_key()
    encrypted_key  = encrypt_bytes(aes_key, recipient_public_key)
    encrypted_data = aes_encrypt(data, aes_key)
    payload = {
        "key":  base64.b64encode(encrypted_key).decode(),
        "data": base64.b64encode(encrypted_data).decode(),
    }
    return json.dumps(payload).encode()


def decrypt_from_sender(payload: bytes, my_private_key: PrivateKey) -> bytes:
    obj            = json.loads(payload.decode())
    encrypted_key  = base64.b64decode(obj["key"])
    encrypted_data = base64.b64decode(obj["data"])
    aes_key = decrypt_bytes(encrypted_key, my_private_key)
    aes_key = aes_key.rjust(AES_KEY_SIZE, b'\x00')
    return aes_decrypt(encrypted_data, aes_key)
