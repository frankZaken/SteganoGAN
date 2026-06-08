# security/crypto/utils.py
# From your utils.py â€” removed gmpy2 dependency, replaced with sympy.isprime

import os
from sympy import isprime


def xor(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("both byte streams must have the same length.")
    return bytes([a[i] ^ b[i] for i in range(len(a))])


def int_to_bytes(data: int) -> bytes:
    length = (data.bit_length() + 7) // 8
    return data.to_bytes(length, "big")


def bytes_to_int(data: bytes) -> int:
    return int.from_bytes(data, "big")


def random_prime(size: int) -> int:
    while True:
        candidate = bytes_to_int(os.urandom(size // 8))
        if isprime(candidate):
            return candidate