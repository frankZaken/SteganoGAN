# security/crypto/rsa.py
# Your RSA implementation â€” import path updated for project structure.

import math
import secrets
import base64
import json
from dataclasses import dataclass
from sympy import nextprime


# â”€â”€ Prime helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def rand_prime_bits_size(size: int) -> int:
    prime = int(nextprime(secrets.randbits(size)))
    if prime.bit_length() <= size:
        return prime
    return prime - 2


def distant_random_prime(small_prime: int, big_prime: int, size: int) -> tuple[int, int]:
    first_digits = small_prime // pow(10, len(str(small_prime)) // 2)
    small_len    = len(str(small_prime))
    big_len      = len(str(big_prime))

    while big_prime // pow(10, small_len // 2 + big_len - small_len) == first_digits:
        new_prime = rand_prime_bits_size(size)
        if small_prime < new_prime:
            small_prime, big_prime = small_prime, new_prime
        else:
            small_prime, big_prime = new_prime, small_prime
        first_digits = small_prime // pow(10, small_len // 2)

    return small_prime, big_prime


def distant_random_primes(size: int) -> tuple[int, int]:
    p = rand_prime_bits_size(size)
    q = rand_prime_bits_size(size)
    if p < q:
        return distant_random_prime(p, q, size)
    return distant_random_prime(q, p, size)


# â”€â”€ Key dataclasses â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class PublicKey:
    n: int
    e: int


@dataclass
class PrivateKey:
    n: int
    d: int


# â”€â”€ RSA core â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def rsa_keys(primes: tuple[int, int]) -> tuple[PrivateKey, PublicKey]:
    p, q  = primes
    n     = p * q
    e     = 65537
    phi   = (p - 1) * (q - 1)

    if math.gcd(phi, e) != 1:
        e = 3
        while math.gcd(phi, e) != 1:
            e += 2

    d = pow(e, -1, phi)
    return PrivateKey(n, d), PublicKey(n, e)


def encrypt(data: int, key: PublicKey) -> int:
    return pow(data, key.e, key.n)


def decrypt(data: int, key: PrivateKey) -> int:
    return pow(data, key.d, key.n)


def sign(data: int, key: PrivateKey) -> int:
    return pow(data, key.d, key.n)


def verify(data: int, signature: int, key: PublicKey) -> bool:
    return data == pow(signature, key.e, key.n)


# â”€â”€ Bytes API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _chunk_size_for_n(n: int) -> int:
    return (n.bit_length() - 1) // 8


def _bytes_to_numbers(data: bytes, n: int) -> list[int]:
    size = _chunk_size_for_n(n)
    if size <= 0:
        raise ValueError("Modulus too small for byte operations.")
    numbers = []
    for i in range(0, len(data), size):
        block = data[i:i + size]
        numbers.append(int.from_bytes(block, "big"))
    return numbers


def _numbers_to_bytes(numbers: list[int], n: int) -> bytes:
    size = _chunk_size_for_n(n)
    out  = b""
    for num in numbers:
        out += num.to_bytes(size, "big").lstrip(b"\x00")
    return out


def encrypt_bytes(data: bytes, key: PublicKey) -> bytes:
    numbers      = _bytes_to_numbers(data, key.n)
    encrypted    = [encrypt(m, key) for m in numbers]
    payload_json = json.dumps(encrypted, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload_json)


def sign_bytes(data: bytes, key: PrivateKey) -> bytes:
    numbers      = _bytes_to_numbers(data, key.n)
    signed       = [sign(m, key) for m in numbers]
    payload_json = json.dumps(signed, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload_json)


def decrypt_bytes(payload: bytes, key: PrivateKey) -> bytes:
    encrypted = json.loads(base64.urlsafe_b64decode(payload).decode())
    numbers   = [decrypt(c, key) for c in encrypted]
    return _numbers_to_bytes(numbers, key.n)


def verify_bytes(data: bytes, signature_payload: bytes, key: PublicKey) -> bool:
    signed  = json.loads(base64.urlsafe_b64decode(signature_payload).decode())
    numbers = _bytes_to_numbers(data, key.n)
    if len(numbers) != len(signed):
        return False
    for m, s in zip(numbers, signed):
        if not verify(m, s, key):
            return False
    return True


def dump_public_key(pub: PublicKey) -> bytes:
    n_bytes = pub.n.to_bytes((pub.n.bit_length() + 7) // 8, "big")
    e_bytes = pub.e.to_bytes((pub.e.bit_length() + 7) // 8, "big")
    obj = {
        "n": base64.urlsafe_b64encode(n_bytes).decode(),
        "e": base64.urlsafe_b64encode(e_bytes).decode(),
    }
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode())


def load_public_key(payload: bytes) -> PublicKey:
    obj = json.loads(base64.urlsafe_b64decode(payload).decode())
    n   = int.from_bytes(base64.urlsafe_b64decode(obj["n"]), "big")
    e   = int.from_bytes(base64.urlsafe_b64decode(obj["e"]), "big")
    return PublicKey(n, e)


# â”€â”€ RSA communication class â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@dataclass
class RSA:
    my_public_key:   PublicKey
    my_private_key:  PrivateKey
    peer_public_key: PublicKey = None

    def dump_my_public_key(self) -> bytes:
        return dump_public_key(self.my_public_key)

    def load_peer_public_key(self, payload: bytes):
        self.peer_public_key = load_public_key(payload)

    def send(self, data: bytes, sign_data: bytes = None) -> bytes:
        if self.peer_public_key is None:
            raise ValueError("Peer public key not loaded.")
        enc_payload = encrypt_bytes(data, self.peer_public_key)
        obj = {"enc": enc_payload.decode()}
        if sign_data is not None:
            sig_payload  = sign_bytes(sign_data, self.my_private_key)
            obj["sig"]   = sig_payload.decode()
        return base64.urlsafe_b64encode(json.dumps(obj, separators=(",", ":")).encode())

    def receive(self, payload: bytes, sign_data: bytes = None, verify: bool = True) -> bytes:
        obj         = json.loads(base64.urlsafe_b64decode(payload).decode())
        enc_payload = obj["enc"].encode()
        message     = decrypt_bytes(enc_payload, self.my_private_key)
        if verify and sign_data is not None:
            if "sig" not in obj:
                raise ValueError("Signature expected but not provided.")
            if not verify_bytes(sign_data, obj["sig"].encode(), self.peer_public_key):
                raise ValueError("Signature verification failed.")
        return message