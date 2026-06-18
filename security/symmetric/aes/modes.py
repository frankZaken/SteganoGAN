from os import urandom
from dataclasses import dataclass, field
from typing import Generator

from security.symmetric.aes.aes128 import AES128
from security.symmetric.aes.padding import PKCS7, split_chunks

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


@dataclass
class ECB:
    block_cipher: AES128

    def encrypt(self, plaintext: bytes) -> Generator[bytes, None, None]:
        for chunk in split_chunks(PKCS7.pad(plaintext)):
            yield self.block_cipher.encrypt(chunk)

    def decrypt(self, ciphertext: bytes) -> Generator[bytes, None, None]:

        last_index = len(ciphertext) // 16 - 1

        for i, chunk in enumerate(split_chunks(ciphertext)):
            decrypted = self.block_cipher.decrypt(chunk)

            if i == last_index:
                decrypted = PKCS7.unpad(decrypted)

            yield decrypted

@dataclass
class CBC:
    block_cipher: AES128
    iv: bytes
    last_block: bytes = field(init=False)

    def __post_init__(self):
        block_size = self.block_cipher.block_size

        if len(self.iv) != self.block_cipher.block_size:
            raise ValueError(f"IV must be the size of CBC.block_cipher.block_size ({block_size}).")

        self.last_block = self.iv

    def encrypt(self, plaintext: bytes) -> Generator[bytes, None, None]:
        for chunk in split_chunks(PKCS7.pad(plaintext)):

            last = self.last_block
            self.last_block = self.block_cipher.encrypt(xor_bytes(last, chunk))

            yield self.last_block

    def decrypt(self, ciphertext: bytes) -> Generator[bytes, None, None]:

        last_index = len(ciphertext) // 16 - 1

        for i, chunk in enumerate(split_chunks(ciphertext)):
            decrypted = xor_bytes(self.block_cipher.decrypt(chunk), self.last_block)
            self.last_block = chunk

            if i == last_index:
                decrypted = PKCS7.unpad(decrypted)

            yield decrypted

@dataclass
class CFB:
    block_cipher: AES128
    iv: bytes
    last_block: bytes = field(init=False)

    def __post_init__(self):
        block_size = self.block_cipher.block_size

        if len(self.iv) != self.block_cipher.block_size:
            raise ValueError(f"IV must be the size of CBC.block_cipher.block_size ({block_size}).")

        self.last_block = self.iv

    def encrypt(self, plaintext: bytes) -> Generator[bytes, None, None]:
        for chunk in split_chunks(PKCS7.pad(plaintext)):

            self.last_block = xor_bytes(self.block_cipher.encrypt(self.last_block), chunk)

            yield self.last_block

    def decrypt(self, ciphertext: bytes) -> Generator[bytes, None, None]:

        last_index = len(ciphertext) // 16 - 1

        for i, chunk in enumerate(split_chunks(ciphertext)):
            decrypted = xor_bytes(self.block_cipher.encrypt(self.last_block), chunk)
            self.last_block = chunk

            if i == last_index:
                decrypted = PKCS7.unpad(decrypted)

            yield decrypted

@dataclass
class OFB:
    block_cipher: AES128
    iv: bytes
    last_block: bytes = field(init=False)

    def __post_init__(self):
        block_size = self.block_cipher.block_size

        if len(self.iv) != self.block_cipher.block_size:
            raise ValueError(f"IV must be the size of CBC.block_cipher.block_size ({block_size}).")

        self.last_block = self.iv

    def encrypt(self, plaintext: bytes) -> Generator[bytes, None, None]:
        for chunk in split_chunks(PKCS7.pad(plaintext)):

            self.last_block = self.block_cipher.encrypt(self.last_block)
            yield xor_bytes(self.last_block, chunk)

    def decrypt(self, ciphertext: bytes) -> Generator[bytes, None, None]:
        last_index = len(ciphertext) // 16 - 1

        for i, chunk in enumerate(split_chunks(ciphertext)):

            self.last_block = self.block_cipher.encrypt(self.last_block)
            decrypted = xor_bytes(self.last_block, chunk)

            if i == last_index:
                decrypted = PKCS7.unpad(decrypted)

            yield decrypted

@dataclass
class CTR:
    block_cipher: AES128
    nonce: bytes

    def __post_init__(self):
        if len(self.nonce) != self.block_cipher.block_size - 8:
            raise ValueError(f"IV must be the size of CBC.block_cipher.block_size - 8 ({self.block_cipher.block_size - 8}).")

    def encrypt(self, plaintext: bytes) -> Generator[bytes, None, None]:
        for i, chunk in enumerate(split_chunks(PKCS7.pad(plaintext))):
            yield xor_bytes(self.block_cipher.encrypt(self.nonce + i.to_bytes(8, "big")), chunk)

    def decrypt(self, ciphertext: bytes) -> Generator[bytes, None, None]:
        last_index = len(ciphertext) // 16 - 1

        for i, chunk in enumerate(split_chunks(ciphertext)):
            decrypted = xor_bytes(self.block_cipher.encrypt(self.nonce + i.to_bytes(8, "big")), chunk)

            if i == last_index:
                decrypted = PKCS7.unpad(decrypted)

            yield decrypted


def xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def main():
    key = urandom(16)
    aes128 = AES128(key)
    block_size = 16

    modes = [
        ("ECB", lambda: ECB(aes128), lambda: AES.new(key, AES.MODE_ECB)),
        ("CBC", lambda iv: CBC(aes128, iv), lambda iv: AES.new(key, AES.MODE_CBC, iv)),
        ("CFB", lambda iv: CFB(aes128, iv), lambda iv: AES.new(key, AES.MODE_CFB, iv, segment_size=128)),
        ("OFB", lambda iv: OFB(aes128, iv), lambda iv: AES.new(key, AES.MODE_OFB, iv)),
        ("CTR", lambda nonce: CTR(aes128, nonce), lambda nonce: AES.new(key, AES.MODE_CTR, nonce=nonce))
    ]

    for name, my_ctor, lib_ctor in modes:
        plaintext = urandom(12)

        if name == "ECB":
            encryptor = my_ctor()
            decryptor = my_ctor()
            lib_cipher = lib_ctor()

        elif name == "CTR":
            nonce = urandom(8)
            encryptor = my_ctor(nonce)
            decryptor = my_ctor(nonce)
            lib_cipher = lib_ctor(nonce)

        else:
            iv = urandom(16)
            encryptor = my_ctor(iv)
            decryptor = my_ctor(iv)
            lib_cipher = lib_ctor(iv)

        encrypted = b"".join(encryptor.encrypt(plaintext))
        decrypted = b"".join(decryptor.decrypt(encrypted))

        if name in ("ECB", "CBC"):
            lib_encrypted = lib_cipher.encrypt(pad(plaintext, block_size))

        else:
            lib_encrypted = lib_cipher.encrypt(pad(plaintext, block_size))

        print(f" - {name} -\n"
              f"plaintext:   {plaintext.hex()}\n"
              f"lib enc:     {lib_encrypted.hex()}\n"
              f"my enc:      {encrypted.hex()}\t{'✅' if lib_encrypted == encrypted else '❌'}\n"
              f"decrypted:   {decrypted.hex()}\t{'✅' if decrypted == plaintext else '❌'}\n")


if __name__ == '__main__':
    main()