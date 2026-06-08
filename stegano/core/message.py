# core/message.py

import torch

UTF8 = "utf-8"
Bit  = int
Bits = list[Bit]


def byte_to_bits(byte: int) -> Bits:
    bits = []

    for i in range(7, -1, -1):
        bit = (byte >> i) & 1
        bits.append(bit)

    return bits

def bits_to_byte(bits: Bits) -> int:
    byte = 0

    for bit in bits:
        byte = (byte << 1) | bit

    return byte

def text_to_bits(text: str) -> Bits:
    bits = []

    for byte in text.encode(UTF8):
        bits.extend(byte_to_bits(byte))

    return bits

def bits_to_text(bits: Bits) -> str:
    byte_array = bytearray()

    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i + 8]
        if len(byte_bits) < 8:
            break
        byte = bits_to_byte(byte_bits)
        if byte == 0:
            break
        byte_array.append(byte)

    try:
        return byte_array.decode(UTF8)

    except UnicodeDecodeError:
        return "(corrupted)"     # ← instead of crashing

def pack_message(text: str, capacity: int) -> torch.Tensor:

    message_bits = text_to_bits(text)
    message_len = len(message_bits)

    # 16-bit header = number of message bits
    if message_len >= (1 << 16):
        raise ValueError("Message too large to encode in 16-bit length header")

    if message_len + 16 > capacity:
        raise ValueError("Message does not fit in given capacity")

    header = [(message_len >> (15 - i)) & 1 for i in range(16)]

    payload_len = capacity - 16 - message_len

    # IMPORTANT: random padding (Bernoulli(0.5), not zeros)
    padding = torch.randint(0, 2, (payload_len,)).tolist()

    packed = header + message_bits + padding

    return torch.tensor(packed, dtype=torch.float32)

def unpack_message(bits: torch.Tensor) -> str:
    bits = bits.int().tolist()

    # read 16-bit header (message bit-length)
    header_bits = bits[:16]
    message_len = 0

    for b in header_bits:
        message_len = (message_len << 1) | b

    # extract message region
    message_start = 16
    message_end = 16 + message_len

    message_bits = bits[message_start:message_end]

    return bits_to_text(message_bits)


def main():
    byte = 65
    print(f"\n----------\nTest byte {65}:\n")

    bits = byte_to_bits(byte)
    print(f"byte_to_bits: {bits}")

    byte = bits_to_byte(bits)
    print(f"bits_to_byte: {byte}")

    message = "Hi"
    print(f"\n----------\nTest text '{message}':\n")

    message_bits = text_to_bits(message)
    print(f"text_to_bits: {message_bits}")

    message = bits_to_text(message_bits)
    print(f"bits_to_text: {message}")

    print("\n----------\n")
    text = "hello steganography!"
    capacity = 1024

    packed = pack_message(text, capacity)
    assert packed.shape == (1024,)
    assert packed.sum() > 0  # should not be all zeros

    recovered = unpack_message(packed)
    assert recovered == text, f"Got: {repr(recovered)}"
    print("✓ Message round-trip works!")

if __name__ == '__main__':
    main()