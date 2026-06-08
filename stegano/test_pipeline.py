# test_pipeline.py

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from core.image import load_image, load_16bit_png
from pipeline.encoder import encode
from pipeline.decoder import decode


# ── Settings — change these ───────────────────────────────────────────────────

MESSAGE = "this is my secret message!"
DIFF_AMPLIFY = 10      # how much to amplify the difference image (try 5, 10, 20, 50)
FIGURE_SIZE = (18, 6)  # width × height of the plot in inches
SAVE_COMPARISON = True
SHOW_PLOT = False


# ── Paths — change these ──────────────────────────────────────────────────────

BASE = Path(__file__).parent
from pathlib import Path

CHECKPOINT = BASE / "training" / "checkpoints" / "finetuned.pt"

COVER = BASE.parent / "server/original_images/peleg/test_model_original_image.jpg"

STEGO = BASE / "old_testing_output" / "stego300.png"
COMPARISON = BASE / "old_testing_output" / "comparison.png"


# ── Plot function ─────────────────────────────────────────────────────────────

def plot_comparison(
        cover_path: str,
        stego_path: str,
        diff_amplify: int = DIFF_AMPLIFY,
        figure_size: tuple = FIGURE_SIZE,
        out_path: Path = COMPARISON,
        show: bool = SHOW_PLOT,
):
    cover, _ = load_image(cover_path)  # (1, 3, H, W)
    stego = load_16bit_png(stego_path)  # (1, 3, H, W)

    def to_np(t):
        return (t.squeeze(0) * 0.5 + 0.5).clamp(0, 1).permute(1, 2, 0).cpu().numpy()

    cover_np = to_np(cover)
    stego_np = to_np(stego)

    # 1. Pure mathematical subtraction (stego - cover)
    # This results in a matrix of positive and negative float values
    diff_raw = stego_np - cover_np

    # 2. Amplify the raw difference
    diff_amp = diff_raw * diff_amplify

    # 3. Shift the result to middle gray (0.5) so negative values become visible
    # 0.5 + 0.0 = Gray (No change)
    # 0.5 + 0.2 = Brighter (Positive change)
    # 0.5 - 0.2 = Darker (Negative change)
    diff_visual = np.clip(diff_amp + 0.5, 0, 1)

    # 4. Compute stats for the plot title (using absolute mean for metrics)
    mse = (diff_raw ** 2).mean()
    psnr = 10 * np.log10(1.0 / mse) if mse > 0 else float("inf")
    max_diff = np.abs(diff_raw).max()
    mean_diff = np.abs(diff_raw).mean()

    # 5. Setup the plot
    fig, axes = plt.subplots(1, 3, figsize=figure_size)

    axes[0].imshow(cover_np)
    axes[0].set_title("Cover (original)", fontsize=13)
    axes[0].axis("off")

    axes[1].imshow(stego_np)
    axes[1].set_title(f"Stego (hidden message)\nPSNR: {psnr:.2f} dB", fontsize=13)
    axes[1].axis("off")

    # 6. Show the shifted subtraction vector
    axes[2].imshow(diff_visual)
    axes[2].set_title(
        f"Pure Subtraction (Gray=0) ×{diff_amplify}\n"
        f"max: {max_diff:.5f}  mean: {mean_diff:.5f}",
        fontsize=13,
    )
    axes[2].axis("off")

    plt.suptitle("StegoFusion — Visual Comparison", fontsize=15, fontweight="bold")
    plt.tight_layout()

    out = out_path
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"  Saved → {out}")

    if show:
        plt.show()

    plt.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    encode(
        image_path=      str(COVER),
        message=         MESSAGE,
        checkpoint_path= str(CHECKPOINT),
        output_path=     str(STEGO),
    )

    recovered = decode(
        image_path=      str(STEGO),
        checkpoint_path= str(CHECKPOINT),
    )

    assert recovered == MESSAGE, f"Got: {repr(recovered)}"
    print(f"\n✓ Message recovered: {repr(recovered)}")

    plot_comparison(str(COVER), str(STEGO))


if __name__ == "__main__":
    main()