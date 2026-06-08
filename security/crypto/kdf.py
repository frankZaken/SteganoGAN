# shared/security/crypto/kdf.py

import hashlib
from dataclasses import dataclass
from os import urandom
from security.crypto.utils import xor


@dataclass
class KDF:
    algorithm: str
    key:       bytes
    size:      int

    def hash(self, data: bytes) -> bytes:
        gen = hashlib.new(self.algorithm, data)
        return gen.digest()

    def derive(self, counter: int) -> bytes:
        return self.hash(self.key)

    def digest(self) -> bytes:
        blocks = []
        counter, total_size = 1, 0
        while total_size < self.size:
            blocks.append(self.derive(counter))
            total_size += len(blocks[-1])
            counter    += 1
        return b"".join(blocks)[:self.size]


@dataclass
class KDF2(KDF):
    def derive(self, counter: int) -> bytes:
        return self.hash(self.key + counter.to_bytes(8, byteorder="big"))


@dataclass
class PBKDF2(KDF2):
    salt:       bytes = b""
    iterations: int   = 100_000

    def derive(self, counter: int) -> bytes:
        first = second = self.hash(
            self.key + self.salt + counter.to_bytes(8, byteorder="big")
        )
        for _ in range(self.iterations):
            first  = self.hash(first)
            second = xor(first, second)
        return second


@dataclass
class PBKDF2HMAC(PBKDF2):
    def hash(self, data: bytes) -> bytes:
        from security.crypto.hmac import HMAC
        gen = HMAC(algorithm=self.algorithm, data=data, key=self.salt)
        return gen.derive()
