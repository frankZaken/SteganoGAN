import hashlib
from dataclasses import dataclass
from os import urandom
from security.utils import xor
from security.integrity.hmac import HMAC


@dataclass
class KDF:
    algorithm: str
    key: bytes
    size: int

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
            counter += 1

        return b"".join(blocks)[:self.size]

class KDF2(KDF):
    def derive(self, counter: int) -> bytes:
        return self.hash(self.key + counter.to_bytes(8, byteorder="big"))

class PBKDF2(KDF2):
    salt: bytes
    iterations: int

    def derive(self, counter: int) -> bytes:
        first = second = self.hash(self.key + self.salt + counter.to_bytes(8, byteorder="big"))

        for i in range (self.iterations):
            first = self.hash(first)
            second = xor(first, second)

        return second

class PBKDF2HMAC(PBKDF2):
    def hash(self, data: bytes) -> bytes:
        gen = HMAC(algorithm=self.algorithm, data=data, key=self.salt)
        return gen.derive()


def main():
    kdf = KDF("sha256", urandom(16), 12)
    print(kdf.digest())

if __name__ == '__main__':
    main()