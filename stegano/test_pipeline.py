# test_pipeline.py

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from pipeline.encoder import encode
from pipeline.decoder import decode


# ── Settings — change these ───────────────────────────────────────────────────

MESSAGE = "this is my secret message!"
DIFF_AMPLIFY = 10      # how much to amplify the difference image (try 5, 10, 20, 50)
FIGURE_SIZE = (18, 6)  # width × height of the plot in inches
SAVE_COMPARISON = True
SHOW_PLOT = True


# ── Paths — change these ──────────────────────────────────────────────────────

from pathlib import Path

base = Path(__file__).parent.parent  # project root

CHECKPOINT = str(base / "stegano" / "training" / "checkpoints" / "finetuned.pt")

COVER = str(base / "cat_original.jpg")
STEGO = str(base / "stegano" / "training" / "checkpoints" / "finetune_samples" / "epoch_020.png")

COMPARISON = base / "stegano" / "old_testing_output" / "comparison1.png"


# ── Plot function ─────────────────────────────────────────────────────────────

def plot_comparison(
        cover_path: str,
        stego_path: str,
        diff_amplify: int = DIFF_AMPLIFY,
        figure_size: tuple = FIGURE_SIZE,
        out_path: Path = COMPARISON,
        show: bool = SHOW_PLOT,
):
    orig  = np.array(Image.open(cover_path).convert("RGB"), dtype=np.float32) / 255.0
    stego = np.array(Image.open(stego_path).convert("RGB"), dtype=np.float32) / 255.0

    if orig.shape != stego.shape:
        h, w = stego.shape[:2]
        orig = np.array(Image.fromarray((orig * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS), dtype=np.float32) / 255.0

    diff = stego - orig
    print(f"diff  min={diff.min():.5f}  max={diff.max():.5f}  mean_abs={np.abs(diff).mean():.5f}")

    vis = np.clip(np.abs(diff) * diff_amplify, 0, 1)

    fig, axes = plt.subplots(1, 3, figsize=figure_size)
    for ax, img, title in zip(axes, [orig, stego, vis], ["Original", "Stego", f"Diff ×{diff_amplify}"]):
        ax.imshow(img)
        ax.set_title(title)
        ax.axis("off")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    print(f"  Saved → {out_path}")

    if show:
        plt.show()

    plt.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def test_encode_decode():
    encode(
        image_path=str(COVER),
        message=MESSAGE,
        checkpoint_path=str(CHECKPOINT),
        output_path=str(STEGO),
    )

    recovered = decode(
        image_path=str(STEGO),
        checkpoint_path=str(CHECKPOINT),
    )

    assert recovered == MESSAGE, f"Got: {repr(recovered)}"
    print(f"\n✓ Message recovered: {repr(recovered)}")


def main():
    plot_comparison(str(COVER), str(STEGO))


if __name__ == "__main__":
    main()