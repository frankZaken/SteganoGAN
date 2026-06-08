# shared/security/aes_manager.py

import os
from security.crypto.aes import AES_CBC

KEY_SIZE = 16
IV_SIZE  = 16


def generate_aes_key() -> bytes:
    return os.urandom(KEY_SIZE)


def encrypt(data: bytes, key: bytes) -> bytes:
    assert len(key) == KEY_SIZE
    iv  = os.urandom(IV_SIZE)
    aes = AES_CBC(key=key, iv=iv)
    return iv + aes.encrypt(data)


def decrypt(ciphertext: bytes, key: bytes) -> bytes:
    assert len(key) == KEY_SIZE
    assert len(ciphertext) > IV_SIZE
    iv            = ciphertext[:IV_SIZE]
    actual_cipher = ciphertext[IV_SIZE:]
    aes = AES_CBC(key=key, iv=iv)
    return aes.decrypt(actual_cipher)
