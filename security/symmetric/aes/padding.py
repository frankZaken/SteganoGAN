from typing import Generator

def split_chunks(data: bytes, size: int = 16) -> Generator[bytes, None, None]:
    for i in range(0, len(data), size):
        yield data[i:i + size]

class PKCS7:

    @staticmethod
    def pad(data: bytes, size: int = 16) -> bytes:
        pad_num = size - (len(data) % size)
        return data + bytes([pad_num] * pad_num)

    @staticmethod
    def unpad(data: bytes, size: int = 16) -> bytes:
        if not data or len(data) % size != 0:
            raise ValueError("Invalid padded data length.")

        pad_len = data[-1]

        if pad_len < 1 or pad_len > size:
            raise ValueError("Invalid padding length.")

        if data[-pad_len:] != bytes([pad_len] * pad_len):
            raise ValueError("Invalid PKCS#7 padding.")

        return data[:-pad_len]

def main():
    work_on = b"hellohellohelloguys!!"

    print("Original Data (split into chunks of 5 bytes):")
    for chunk in split_chunks(work_on, 5):
        print([bytes([byte]) for byte in chunk])

    print()

    padded_data = PKCS7.pad(work_on, 5)
    print("Padded Data (split into chunks of 5 bytes):")
    for chunk in split_chunks(padded_data, 5):
        print([bytes([byte]) for byte in chunk])

    print()

    unpadded_data = PKCS7.unpad(padded_data, 5)
    print("Unpadded Data (split into chunks of 5 bytes):")
    for chunk in split_chunks(unpadded_data, 5):
        print([bytes([byte]) for byte in chunk])

if __name__ == '__main__':
    main()
