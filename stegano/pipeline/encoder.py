# stegano2/pipeline/encoder.py

import torch
from pathlib import Path

from PIL.Image import Image
import torchvision.transforms.functional as F
from stegano.core.image    import CoverImage, StegoImage
from stegano.core.message  import pack_message
from stegano.gan.generator import InvertibleGenerator
from stegano.pipeline.model_cache    import get_generator


def encode(image_path: str, message: str, checkpoint_path: str, output_path: str):
    """Hide a text message inside an image."""
    generator, device = get_generator(checkpoint_path)

    cover = CoverImage(image_path)
    cover_tensor = cover.tensor.to(device)

    H, W     = cover.height, cover.width
    capacity = generator.capacity(H, W)

    bits = pack_message(message, capacity).unsqueeze(0).to(device)

    with torch.no_grad():
        stego_tensor = generator.encode(cover_tensor, bits)

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    """
    F.to_pil_image(stego_tensor).save(str(out_path), format='PNG')
    """

    stego = StegoImage(stego_tensor)
    stego.save(str(out_path))

    bits_used = len(message.encode("utf-8")) * 8
    print(f"✓ Encoded → {out_path}")
    print(f"  Image size : {W}×{H}")
    print(f"  Capacity   : {capacity} bits = {capacity // 8} bytes")
    print(f"  Used       : {bits_used} bits ({bits_used / capacity * 100:.2f}%)")


def main():
    base = Path(__file__).parent.parent.parent   # SteganoGAN2/
    encode(
        image_path=      str(base / "input" / "photo.jpg"),
        message=         "hello world",
        checkpoint_path= str(base / "stegano2" / "training" / "checkpoints" / "checkpoint_epoch_0040.pt"),
        output_path=     str(base / "old_testing_output" / "stego.png"),
    )

if __name__ == "__main__":
    main()
