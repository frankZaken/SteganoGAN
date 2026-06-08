# shared/security/hashing.py

import os
from security.crypto.kdf import PBKDF2HMAC

SALT_SIZE  = 16
KEY_SIZE   = 32
ITERATIONS = 100_000
ALGORITHM  = "sha256"
SEPARATOR  = ":"


def hash_password(plain: str) -> str:
    salt   = os.urandom(SALT_SIZE)
    kdf    = PBKDF2HMAC(
        algorithm=  ALGORITHM,
        key=        plain.encode("utf-8"),
        size=       KEY_SIZE,
        salt=       salt,
        iterations= ITERATIONS,
    )
    digest = kdf.digest()
    return salt.hex() + SEPARATOR + digest.hex()


def verify_password(plain: str, stored: str) -> bool:
    salt_hex, hash_hex = stored.split(SEPARATOR, 1)
    salt     = bytes.fromhex(salt_hex)
    kdf      = PBKDF2HMAC(
        algorithm=  ALGORITHM,
        key=        plain.encode("utf-8"),
        size=       KEY_SIZE,
        salt=       salt,
        iterations= ITERATIONS,
    )
    computed = kdf.digest()
    return computed == bytes.fromhex(hash_hex)
