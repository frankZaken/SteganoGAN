# stegano2/pipeline/decoder.py

import torch
from pathlib import Path

from stegano.core.image    import StegoImage, load_stego
from stegano.core.message  import unpack_message
from stegano.gan.generator import InvertibleGenerator
from stegano.pipeline.model_cache    import get_generator


def decode(image_path: str, checkpoint_path: str) -> str:
    """Reveal the hidden message from a stego image."""
    generator, device = get_generator(checkpoint_path)

    stego_tensor = load_stego(image_path).to(device)

    H, W     = stego_tensor.shape[2], stego_tensor.shape[3]
    capacity = generator.capacity(H, W)

    with torch.no_grad():
        bits = generator.decode(stego_tensor, capacity)

    message = unpack_message(bits.squeeze(0))
    print(f"✓ Decoded from: {image_path}")
    print(f"  Hidden message: {repr(message)}")

    return message


def main():
    base = Path(__file__).parent.parent.parent   # SteganoGAN2/
    decode(
        image_path=      str(base / "old_testing_output" / "stego.png"),
        checkpoint_path= str(base / "stegano2" / "training" / "checkpoints" / "checkpoint_epoch_0030.pt"),
    )

if __name__ == "__main__":
    main()
