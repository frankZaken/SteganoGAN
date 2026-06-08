# core/image.py

import numpy as np
import torch
from torch import Tensor
import struct
import zlib
from PIL import Image
import torchvision.transforms as T

ImageSize = tuple[int, int]


def load_image(path) -> tuple[Tensor, ImageSize]:
    img = Image.open(path).convert("RGB")
    original_size = img.size  # (W, H)

    to_tensor = T.ToTensor()
    tensor = to_tensor(img)  # [C, H, W], range [0, 1]

    # scale to [-1, 1]
    tensor = tensor * 2.0 - 1.0

    c, h, w = tensor.shape

    # ensure even dimensions (required for squeeze/pixel shuffle later)
    if h % 2 == 1:
        tensor = tensor[:, :h - 1, :]
        h -= 1

    if w % 2 == 1:
        tensor = tensor[:, :, :w - 1]
        w -= 1

    return tensor.unsqueeze(0), original_size


def save_stego(tensor: Tensor, path: str):
    """
    Save stego as a valid 16-bit PNG (viewable) with exact float32 data
    embedded in a private PNG chunk (ftNs). Image viewers display the
    16-bit visuals and ignore the unknown chunk; the decoder reads exact
    float32 from the chunk — no rounding in the decode path.
    """
    if tensor.ndim == 4:
        tensor = tensor.squeeze(0)
    assert tensor.ndim == 3 and tensor.shape[0] == 3

    x_np = ((tensor + 1.0) * 0.5 * 65535.0).clamp(0, 65535)
    x_np = x_np.cpu().numpy().astype(np.uint16).transpose(1, 2, 0)
    h, w = x_np.shape[:2]

    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw.extend(x_np[y].byteswap().tobytes())
    compressed_idat = zlib.compress(bytes(raw), level=9)

    float_bytes = tensor.cpu().numpy().astype(np.float32).tobytes()
    compressed_float = zlib.compress(float_bytes, level=9)

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data)) +
            tag +
            data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 16, 2, 0, 0, 0)
    png  = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", compressed_idat)
    png += chunk(b"ftNs", compressed_float)  # private ancillary: exact float32
    png += chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(png)


def load_stego(path: str) -> Tensor:
    """
    Load a stego PNG saved by save_stego.
    Reads exact float32 from the ftNs chunk — zero quantization error.
    """
    raw = open(path, "rb").read()
    pos = 8
    width = height = 0
    float_data = None

    while pos < len(raw):
        length              = struct.unpack(">I", raw[pos:pos+4])[0]
        tag                 = raw[pos+4:pos+8]
        data                = raw[pos+8:pos+8+length]
        pos                += 12 + length

        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[:8])
        elif tag == b"ftNs":
            float_data = zlib.decompress(data)
        elif tag == b"IEND":
            break

    if float_data is None:
        return load_16bit_png(path)

    arr    = np.frombuffer(float_data, dtype=np.float32).reshape(3, height, width)
    tensor = torch.from_numpy(arr.copy())
    return tensor.unsqueeze(0)


def save_16bit_png(tensor: Tensor, path: str):
    if tensor.ndim == 4:
        tensor = tensor.squeeze(0)
    assert tensor.ndim == 3 and tensor.shape[0] == 3

    x_np = ((tensor + 1.0) * 0.5 * 65535.0).clamp(0, 65535)
    x_np = x_np.cpu().numpy().astype(np.uint16).transpose(1, 2, 0)  # (H, W, 3)

    h, w = x_np.shape[:2]   # get h, w from numpy array directly

    raw = bytearray()

    for y in range(h):
        raw.append(0)  # filter byte
        row_be = x_np[y].byteswap().tobytes()  # big-endian uint16
        raw.extend(row_be)

    compressed = zlib.compress(bytes(raw), level=9)

    # -------------------------
    # PNG file construction
    # -------------------------

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data)) +
            tag +
            data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        )

    # PNG signature
    png = b"\x89PNG\r\n\x1a\n"

    # IHDR (16-bit RGB)
    ihdr = struct.pack(">IIBBBBB",
        w, h,
        16,  # bit depth
        2,   # color type: RGB
        0,   # compression
        0,   # filter
        0    # interlace
    )

    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")

    with open(path, "wb") as f:
        f.write(png)

def load_16bit_png(path: str) -> Tensor:
    import numpy as np

    raw = open(path, "rb").read()

    # Walk the chunks
    pos    = 8
    idat   = b""
    width  = height = 0

    while pos < len(raw):
        length = struct.unpack(">I", raw[pos:pos+4])[0]
        tag    = raw[pos+4:pos+8]
        data   = raw[pos+8:pos+8+length]
        pos   += 12 + length

        if tag == b"IHDR":
            width, height = struct.unpack(">II", data[:8])

        elif tag == b"IDAT":
            idat += data          # can be multiple IDAT chunks — concatenate

        elif tag == b"IEND":
            break

    # Decompress
    decompressed = zlib.decompress(idat)

    # Parse rows
    row_stride = 1 + width * 6   # 1 filter byte + W × 3 channels × 2 bytes
    arr = np.zeros((height, width, 3), dtype=np.uint16)

    for y in range(height):
        row_start = y * row_stride + 1     # +1 to skip filter byte
        row_data  = decompressed[row_start : row_start + width * 6]
        arr[y]    = np.frombuffer(row_data, dtype=">u2").reshape(width, 3)

    # uint16 [0, 65535] → float [-1, 1]
    tensor = torch.from_numpy(arr.astype(np.float32) / 65535.0)  # (H, W, 3)
    tensor = tensor.permute(2, 0, 1)    # (3, H, W)
    tensor = tensor * 2.0 - 1.0        # [-1, 1]

    return tensor.unsqueeze(0)          # (1, 3, H, W)


class CoverImage:
    def __init__(self, path):
        self.tensor, _  = load_image(path)
        self.height     = self.tensor.shape[2]
        self.width      = self.tensor.shape[3]

    @property
    def capacity(self):
        return self.height * self.width


class StegoImage:
    def __init__(self, tensor):
        self.tensor = tensor

    def save(self, path):
        save_stego(self.tensor, path)

    @classmethod
    def load(cls, path):
        return cls(load_stego(path))


from pathlib import Path

def main():
    # Get the directory of this file (core/), then go up to SteganoGAN2/
    base = Path(__file__).parent.parent

    # Test round-trip
    tensor = torch.rand(1, 3, 64, 64) * 2 - 1
    save_16bit_png(tensor, str(base / "test_output.png"))
    loaded = load_16bit_png(str(base / "test_output.png"))

    error = (tensor - loaded).abs().max().item()
    assert error < 1e-4, f"Round-trip error too large: {error}"
    print(f"✓ 16-bit PNG round-trip error: {error:.2e}")

    # Test CoverImage
    cover = CoverImage(str(base / "input" / "photo.jpg"))
    print(f"✓ Loaded: {cover.width}×{cover.height}, capacity={cover.capacity} bits")

if __name__ == '__main__':
    main()