# shared/security/crypto/hmac.py

import hashlib
from dataclasses import dataclass
from security.crypto.utils import xor


@dataclass
class HMAC:
    algorithm: str
    data:      bytes
    key:       bytes
    size:      int = 64

    def hash(self, data: bytes) -> bytes:
        gen = hashlib.new(self.algorithm, data)
        return gen.digest()

    def sized_key(self) -> bytes:
        key = self.key
        if len(key) > self.size:
            key = self.hash(key)
        if len(key) < self.size:
            key += bytes([0x00] * (self.size - len(key)))
        return key

    def derive(self) -> bytes:
        key = self.sized_key()
        k1  = xor(key, bytes([0x36] * len(key)))
        k2  = xor(key, bytes([0x5c] * len(key)))
        return self.hash(k2 + self.hash(k1 + self.data))
