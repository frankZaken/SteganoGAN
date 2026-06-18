from dataclasses import dataclass, field
from os import urandom
from typing import ClassVar

S_BOX = [
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5,
    0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0,
    0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC,
    0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A,
    0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0,
    0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B,
    0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85,
    0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5,
    0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17,
    0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88,
    0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C,
    0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9,
    0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6,
    0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E,
    0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94,
    0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68,
    0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16
]

INV_S_BOX = [0] * 256
for I in range(256):
    INV_S_BOX[S_BOX[I]] = I

RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]

Row = list[int]
State = list[Row]

def add_round_key(key: State, state: State):
    for i in range(4):
        for j in range(4):
            state[i][j] = state[i][j] ^ key[i][j]

def rotate_word(word: Row) ->Row:
    return word[1:] + [word[0]]

def substitute_word(word: Row) -> Row:
    return [S_BOX[x] for x in word]

def substitute_bytes(state: State):
    for i in range(4):
        for j in range(4):
            state[i][j] = S_BOX[state[i][j]]

def inverse_substitute_bytes(state: State):
    for i in range(4):
        for j in range(4):
            state[i][j] = INV_S_BOX[state[i][j]]

def xor_word(a: list[int], b: list[int]) -> list[int]:
    return [x ^ y for x, y in zip(a, b)]

def expand_key(key: State) -> list[State]:

    key_bytes = flatten_state(key)
    words = [list(key_bytes[i:i + 4]) for i in range(0, 16, 4)]

    for i in range(4, 44):
        temp = words[i - 1][:]

        if i % 4 == 0:
            temp = substitute_word(rotate_word(temp))
            temp[0] ^= RCON[(i // 4) - 1]

        words.append(xor_word(words[i - 4], temp))

    round_keys = []

    for i in range(0, 44, 4):
        round_key_bytes = b''.join(bytes(words[i + j]) for j in range(4))
        round_keys.append(build_state(round_key_bytes))

    return round_keys

def shift_rows(state: State):
    for i in range(1, 4):
        for j in range(i):
            state[i].append(state[i].pop(0))

def inverse_shift_rows(state: State):
    for i in range(1, 4):
        for j in range(i):
            state[i].insert(0, state[i].pop())

def gmul(a: int, b: int) -> int:
    res = 0
    for _ in range(8):
        if b & 1:
            res ^= a
        hi_bit = a & 0x80
        a = (a << 1) & 0xFF
        if hi_bit:
            a ^= 0x1B
        b >>= 1

    return res

def mix_columns(state: State):
    for i in range(4):
        a = [state[row][i] for row in range(4)]

        state[0][i] = gmul(a[0], 2) ^ gmul(a[1], 3) ^ a[2] ^ a[3]
        state[1][i] = a[0] ^ gmul(a[1], 2) ^ gmul(a[2], 3) ^ a[3]
        state[2][i] = a[0] ^ a[1] ^ gmul(a[2], 2) ^ gmul(a[3], 3)
        state[3][i] = gmul(a[0], 3) ^ a[1] ^ a[2] ^ gmul(a[3], 2)

def inverse_mix_columns(state: State):
    for i in range(4):
        a = [state[row][i] for row in range(4)]

        state[0][i] = gmul(a[0], 14) ^ gmul(a[1], 11) ^ gmul(a[2], 13) ^ gmul(a[3], 9)
        state[1][i] = gmul(a[0], 9)  ^ gmul(a[1], 14) ^ gmul(a[2], 11) ^ gmul(a[3], 13)
        state[2][i] = gmul(a[0], 13) ^ gmul(a[1], 9)  ^ gmul(a[2], 14) ^ gmul(a[3], 11)
        state[3][i] = gmul(a[0], 11) ^ gmul(a[1], 13) ^ gmul(a[2], 9)  ^ gmul(a[3], 14)


def build_state(data: bytes) -> State:
    if len(data) != 16:
        raise ValueError("Input data must be exactly 16 bytes for AES-128.")

    state = [[0] * 4 for _ in range(4)]

    for row in range(4):
        for col in range(4):
            state[row][col] = data[row + 4 * col]

    return state

def flatten_state(state: State) -> bytes:
    data = bytearray()

    for col in range(4):
        for row in range(4):
            data.append(state[row][col])

    return bytes(data)

def aes128_encrypt(key: bytes, plaintext: bytes) -> bytes:

    if len(key) != 16:
        raise ValueError("AES-128 requires a 16-byte key.")

    state:State = build_state(plaintext)
    key:State = build_state(key)
    expanded_keys: list[State] = expand_key(key)

    add_round_key(expanded_keys[0], state)

    for i in range(1, 10):
        substitute_bytes(state)
        shift_rows(state)
        mix_columns(state)
        add_round_key(expanded_keys[i], state)

    substitute_bytes(state)
    shift_rows(state)
    add_round_key(expanded_keys[10], state)

    return flatten_state(state)

def aes128_decrypt(key: bytes, ciphertext: bytes) -> bytes:

    if len(key) != 16:
        raise ValueError("AES-128 requires a 16-byte key.")

    state: State = build_state(ciphertext)
    key: State = build_state(key)
    expanded_keys: list[State] = expand_key(key)

    add_round_key(expanded_keys[10], state)

    for i in range(9, 0, -1):
        inverse_shift_rows(state)
        inverse_substitute_bytes(state)
        add_round_key(expanded_keys[i], state)
        inverse_mix_columns(state)

    inverse_shift_rows(state)
    inverse_substitute_bytes(state)
    add_round_key(expanded_keys[0], state)

    return flatten_state(state)


@dataclass(slots=True, frozen=True)
class AES128:

    block_size: ClassVar[int] = 16

    key: bytes
    _round_keys: list[State] = field(init=False, default_factory=list)

    def __post_init__(self):
        if len(self.key) != 16:
            raise ValueError("Key size must be 16.")

    def _expand_key(self):
        if not self._round_keys:
            key: State = build_state(self.key)
            self._round_keys.extend(expand_key(key))

    def encrypt(self, plaintext: bytes) -> bytes:

        state: State = build_state(plaintext)
        self._expand_key()

        add_round_key(self._round_keys[0], state)

        for i in range(1, 10):
            substitute_bytes(state)
            shift_rows(state)
            mix_columns(state)
            add_round_key(self._round_keys[i], state)

        substitute_bytes(state)
        shift_rows(state)
        add_round_key(self._round_keys[10], state)

        return flatten_state(state)


    def decrypt(self, ciphertext: bytes) -> bytes:

        state: State = build_state(ciphertext)
        self._expand_key()

        add_round_key(self._round_keys[10], state)

        for i in range(9, 0, -1):
            inverse_shift_rows(state)
            inverse_substitute_bytes(state)
            add_round_key(self._round_keys[i], state)
            inverse_mix_columns(state)

        inverse_shift_rows(state)
        inverse_substitute_bytes(state)
        add_round_key(self._round_keys[0], state)

        return flatten_state(state)


def main():
    key = urandom(16)
    plaintext = urandom(16)

    aes128 = AES128(key)

    print("Original plaintext:")
    print(plaintext)

    print("\nEncrypted (hex):")

    # ciphertext = aes128_encrypt(key, plaintext)
    ciphertext = aes128.encrypt(plaintext)
    print(ciphertext.hex())

    print("\nDecrypted plaintext:")

    # decrypted = aes128_decrypt(key, ciphertext)
    decrypted = aes128.decrypt(ciphertext)
    print(decrypted)

    if decrypted == plaintext:
        print("\n✅ Success: Decrypted output matches original plaintext.")

    else:
        print("\n❌ Failure: Decrypted output does not match original plaintext.")


    print(expand_key([[1, 2, 3, 4], [5, 6, 7, 8], [9, 0, 1, 2], [3, 4, 5, 6]]))

if __name__ == '__main__':
    main()