# security/crypto/aes.py
# AES-128 core + CBC mode â€” in the style of your AES assignment.
# Implements: bytes_to_state, state_to_bytes, add_round_key, expand_key,
# substitute_bytes, shift_rows, mix_columns, aes128_encrypt, aes128_decrypt,
# and the AES_CBC class used by the app.

from dataclasses import dataclass


Row   = list[int]      # 4 integers (bytes)
State = list[Row]      # 4Ã—4 matrix of bytes


SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]

INV_SBOX = [0] * 256
for i, v in enumerate(SBOX):
    INV_SBOX[v] = i

RCON = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]



def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff

def _gmul(a: int, b: int) -> int:
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xff
        if hi:
            a ^= 0x1b
        b >>= 1
    return p



def bytes_to_state(data: bytes) -> State:
    return [[data[r + 4*c] for c in range(4)] for r in range(4)]

def state_to_bytes(state: State) -> bytes:
    return bytes(state[r][c] for c in range(4) for r in range(4))



def add_round_key(key: State, state: State):
    for r in range(4):
        for c in range(4):
            state[r][c] ^= key[r][c]


def substitute_bytes(state: State):
    for r in range(4):
        for c in range(4):
            state[r][c] = SBOX[state[r][c]]

def inverse_substitute_bytes(state: State):
    for r in range(4):
        for c in range(4):
            state[r][c] = INV_SBOX[state[r][c]]


def shift_rows(state: State):
    for r in range(1, 4):
        state[r] = state[r][r:] + state[r][:r]

def inverse_shift_rows(state: State):
    for r in range(1, 4):
        state[r] = state[r][4-r:] + state[r][:4-r]


def mix_columns(state: State):
    for c in range(4):
        s0, s1, s2, s3 = state[0][c], state[1][c], state[2][c], state[3][c]
        state[0][c] = _gmul(s0,2) ^ _gmul(s1,3) ^ s2 ^ s3
        state[1][c] = s0 ^ _gmul(s1,2) ^ _gmul(s2,3) ^ s3
        state[2][c] = s0 ^ s1 ^ _gmul(s2,2) ^ _gmul(s3,3)
        state[3][c] = _gmul(s0,3) ^ s1 ^ s2 ^ _gmul(s3,2)

def inverse_mix_columns(state: State):
    for c in range(4):
        s0, s1, s2, s3 = state[0][c], state[1][c], state[2][c], state[3][c]
        state[0][c] = _gmul(s0,0x0e) ^ _gmul(s1,0x0b) ^ _gmul(s2,0x0d) ^ _gmul(s3,0x09)
        state[1][c] = _gmul(s0,0x09) ^ _gmul(s1,0x0e) ^ _gmul(s2,0x0b) ^ _gmul(s3,0x0d)
        state[2][c] = _gmul(s0,0x0d) ^ _gmul(s1,0x09) ^ _gmul(s2,0x0e) ^ _gmul(s3,0x0b)
        state[3][c] = _gmul(s0,0x0b) ^ _gmul(s1,0x0d) ^ _gmul(s2,0x09) ^ _gmul(s3,0x0e)


def expand_key(key: State) -> list[State]:
    # Flatten key to list of words (each word = 4 bytes = one column)
    words = [[key[r][c] for r in range(4)] for c in range(4)]

    for i in range(4, 44):
        w = words[i-1][:]
        if i % 4 == 0:
            # RotWord
            w = w[1:] + w[:1]
            # SubWord
            w = [SBOX[b] for b in w]
            # XOR with Rcon
            w[0] ^= RCON[i // 4 - 1]
        words.append([words[i-4][j] ^ w[j] for j in range(4)])

    # Build 11 round key States
    round_keys = []
    for rk in range(11):
        state = [[words[rk*4 + c][r] for c in range(4)] for r in range(4)]
        round_keys.append(state)
    return round_keys


def aes128_encrypt(key: bytes, plaintext: bytes) -> bytes:
    assert len(key) == 16 and len(plaintext) == 16
    state     = bytes_to_state(plaintext)
    key_state = bytes_to_state(key)
    round_keys = expand_key(key_state)

    add_round_key(round_keys[0], state)
    for rnd in range(1, 10):
        substitute_bytes(state)
        shift_rows(state)
        mix_columns(state)
        add_round_key(round_keys[rnd], state)
    substitute_bytes(state)
    shift_rows(state)
    add_round_key(round_keys[10], state)
    return state_to_bytes(state)


def aes128_decrypt(key: bytes, ciphertext: bytes) -> bytes:
    assert len(key) == 16 and len(ciphertext) == 16
    state      = bytes_to_state(ciphertext)
    key_state  = bytes_to_state(key)
    round_keys = expand_key(key_state)

    add_round_key(round_keys[10], state)
    for rnd in range(9, 0, -1):
        inverse_shift_rows(state)
        inverse_substitute_bytes(state)
        add_round_key(round_keys[rnd], state)
        inverse_mix_columns(state)
    inverse_shift_rows(state)
    inverse_substitute_bytes(state)
    add_round_key(round_keys[0], state)
    return state_to_bytes(state)



class PKCS7:
    @staticmethod
    def pad(data: bytes, size: int = 16) -> bytes:
        pad_len = size - (len(data) % size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def unpad(data: bytes, size: int = 16) -> bytes:
        pad_len = data[-1]
        if pad_len < 1 or pad_len > size:
            raise ValueError(f"Invalid PKCS7 padding: {pad_len}")
        return data[:-pad_len]



@dataclass
class AES_CBC:
    """
    AES-128-CBC encryption/decryption.
    Used by aes_manager.py â€” see that file for IV prepending convention.
    """
    key: bytes   # 16-byte AES-128 key
    iv:  bytes   # 16-byte initialization vector

    def _xor_blocks(self, a: bytes, b: bytes) -> bytes:
        return bytes(x ^ y for x, y in zip(a, b))

    def encrypt(self, plaintext: bytes) -> bytes:
        """
        Encrypt with AES-128-CBC + PKCS7 padding.
        Returns ciphertext only (no IV â€” aes_manager prepends it).
        """
        padded     = PKCS7.pad(plaintext)
        ciphertext = b""
        prev       = self.iv

        for i in range(0, len(padded), 16):
            block = padded[i:i+16]
            block = self._xor_blocks(block, prev)
            block = aes128_encrypt(self.key, block)
            ciphertext += block
            prev        = block

        return ciphertext

    def decrypt(self, ciphertext: bytes) -> bytes:
        """
        Decrypt AES-128-CBC + remove PKCS7 padding.
        Receives raw ciphertext (no IV â€” aes_manager strips it).
        """
        plaintext = b""
        prev      = self.iv

        for i in range(0, len(ciphertext), 16):
            block     = ciphertext[i:i+16]
            decrypted = aes128_decrypt(self.key, block)
            plaintext += self._xor_blocks(decrypted, prev)
            prev       = block

        return PKCS7.unpad(plaintext)



def main():
    import os
    key = os.urandom(16)
    iv  = os.urandom(16)
    msg = b"Hello AES-128-CBC! This tests the implementation."

    aes = AES_CBC(key=key, iv=iv)
    enc = aes.encrypt(msg)
    dec = aes.decrypt(enc)

    assert dec == msg, f"Mismatch: {dec!r} != {msg!r}"
    print(f"âœ“ AES-128-CBC round-trip: {len(msg)} bytes â†’ {len(enc)} bytes â†’ {len(dec)} bytes")

    # Also test core AES-128 with a known test vector
    test_key   = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    test_plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    expected   = bytes.fromhex("69c4e0d86a7b04300d8a8f4b5a63305c")
    result     = aes128_encrypt(test_key, test_plain)
    assert result == expected, f"AES core test failed: {result.hex()}"
    print("âœ“ AES-128 core test vector passes!")


if __name__ == "__main__":
    main()