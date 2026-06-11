# stegano2/training/finetuner.py
from collections.abc import Callable

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from pathlib import Path
from PIL import Image
from tqdm import tqdm

from ..gan.generator     import InvertibleGenerator, MSG_CH_START, MSG_CH_END, squeeze as gen_squeeze
from ..gan.discriminator import Discriminator
from ..core.message      import pack_message, unpack_message
from ..core.image import save_16bit_png, load_image

# ── Configuration ──────────────────────────────────────────────────────────────

IMAGE_SIZE   = 154
BATCH_SIZE   = 2
NUM_EPOCHS   = 20
LR           = 5e-5
LAMBDA_ADV   = 0.01
LAMBDA_IMG   = 10.0
LAMBDA_MSG   = 0.5    # message fidelity through quantization
LAMBDA_COLOR = 20.0   # penalise per-channel mean shift (global colour cast)
LAMBDA_FREQ  = 5.0    # penalise low-frequency content in the stego−cover diff
TEST_MESSAGE = "Iti is dumb!"


# ── Dataset ────────────────────────────────────────────────────────────────────

class ImageFolderWithBits(Dataset):
    EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

    def __init__(self, folder: str, image_size: int):
        self.paths = sorted(
            [p for p in Path(folder).iterdir() if p.suffix.lower() in self.EXTENSIONS]
        )
        self.capacity = image_size * image_size
        self.transform = transforms.Compose([
            transforms.Resize(image_size),
            transforms.RandomCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
        ])
        print(f"  Dataset: {len(self.paths)} images from {folder}")

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        img  = Image.open(self.paths[idx]).convert("RGB")
        img  = self.transform(img)
        bits = torch.randint(0, 2, (self.capacity,)).float()
        return img, bits


# ── Metrics ────────────────────────────────────────────────────────────────────

def compute_psnr(cover: torch.Tensor, stego: torch.Tensor) -> float:
    mse = nn.functional.mse_loss(cover, stego).item()
    if mse == 0:
        return float("inf")
    return 10 * torch.log10(torch.tensor(1.0 / mse)).item()


# ── Frequency loss ────────────────────────────────────────────────────────────

def low_freq_energy(diff: torch.Tensor, pool: int = 16) -> torch.Tensor:
    """
    Penalise low-frequency content in the stego−cover difference.
    Average-pool collapses high-frequency noise but keeps color shifts / blobs.
    We want that residual to be zero — pushing the coupling layers to route
    the message energy into grain rather than into visible tonal changes.
    """
    return torch.nn.functional.avg_pool2d(diff.abs(), kernel_size=pool, stride=pool).mean()


# ── Quantization simulation ────────────────────────────────────────────────────

def quantize_like_16bit_png(stego: torch.Tensor) -> torch.Tensor:
    display   = (stego * 0.5 + 0.5).clamp(0, 1)
    quantized = (display * 65535.0).round() / 65535.0
    return quantized * 2.0 - 1.0


# ── Fine-tuning loop ───────────────────────────────────────────────────────────

def get_status(epoch: int, num_epochs: int) -> int:
    return round((epoch / num_epochs) * 100)

def finetune(
    dataset_dir: str,
    base_checkpoint: str,
    output_path: str,
    target_image: str | None = None,
    on_epoch: Callable[[int, int], int] | None = get_status
):
    device = torch.device(
        "cuda" if torch.cuda.is_available() else
        "mps"  if torch.backends.mps.is_available() else
        "cpu"
    )
    print(f"\nFine-tuning on: {device}")
    print(f"Dataset      : {dataset_dir}")
    print(f"Base model   : {base_checkpoint}")
    print(f"Output       : {output_path}")

    generator     = InvertibleGenerator(hidden_channels=64, num_layers=8).to(device)
    discriminator = Discriminator(image_channels=3).to(device)

    ckpt = torch.load(base_checkpoint, map_location=device, weights_only=True)
    generator.load_state_dict(ckpt["generator"])
    discriminator.load_state_dict(ckpt["discriminator"])
    print(f"  Loaded checkpoint (epoch {ckpt['epoch']})")

    dataset = ImageFolderWithBits(dataset_dir, IMAGE_SIZE)
    loader  = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, drop_last=True)

    opt_gen  = optim.Adam(generator.parameters(),     lr=LR,       betas=(0.5, 0.999))
    opt_disc = optim.Adam(discriminator.parameters(), lr=LR * 0.1, betas=(0.5, 0.999))
    scheduler = optim.lr_scheduler.CosineAnnealingLR(opt_gen, T_max=NUM_EPOCHS, eta_min=LR * 0.1)

    bce = nn.BCEWithLogitsLoss()
    mse = nn.MSELoss()
    l1  = nn.L1Loss()

    target_tensor = None

    if target_image:
        target_tensor, _ = load_image(target_image)
        target_tensor = target_tensor.to(device)

    out_path   = Path(output_path)
    sample_dir = out_path.parent / "finetune_samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    best_psnr = 0.0

    for epoch in range(1, NUM_EPOCHS + 1):
        generator.train()
        discriminator.train()

        epoch_psnr   = 0.0
        last_bit_acc = 0.0
        last_d_loss  = 0.0
        last_msg_loss = 0.0

        for batch_idx, (covers, bits) in enumerate(tqdm(loader, desc=f"Epoch {epoch}/{NUM_EPOCHS}")):
            covers = covers.to(device)
            bits   = bits.to(device)

            stegos = generator.encode(covers, bits)

            if batch_idx % 5 == 0:
                opt_disc.zero_grad()
                loss_disc = (
                    bce(discriminator(covers), torch.ones_like(discriminator(covers))  * 0.9) +
                    bce(discriminator(stegos.detach()), torch.zeros_like(discriminator(stegos.detach())) + 0.1)
                ) * 0.5
                loss_disc.backward()
                opt_disc.step()
                last_d_loss = loss_disc.item()

            opt_gen.zero_grad()
            stegos   = generator.encode(covers, bits)
            loss_adv = bce(discriminator(stegos), torch.ones_like(discriminator(stegos)))
            loss_img = mse(stegos, covers) + 0.5 * l1(stegos, covers)

            # Message fidelity: exact decode (lossless storage, no quantization noise)
            lat = gen_squeeze(stegos)
            for lyr in reversed(generator.coupling_layers):
                lat = lyr.inverse(lat)
            msg_logits = lat[:, MSG_CH_START:MSG_CH_END].reshape(covers.shape[0], -1)[:, :bits.shape[1]]
            loss_msg = bce(msg_logits, bits)
            last_msg_loss = loss_msg.item()

            # Per-channel mean — penalises global colour cast
            loss_color = mse(
                stegos.mean(dim=[2, 3], keepdim=True),
                covers.mean(dim=[2, 3], keepdim=True),
            )

            # Low-frequency diff — pushes perturbation into grain, not tonal shifts
            loss_freq = low_freq_energy(stegos - covers)

            loss_gen = (LAMBDA_ADV   * loss_adv
                      + LAMBDA_IMG   * loss_img
                      + LAMBDA_MSG   * loss_msg
                      + LAMBDA_COLOR * loss_color
                      + LAMBDA_FREQ  * loss_freq)
            loss_gen.backward()
            opt_gen.step()

            with torch.no_grad():
                stegos_q     = quantize_like_16bit_png(stegos.detach())
                bits_rec     = generator.decode(stegos_q, bits.shape[1])
                last_bit_acc = (bits_rec == bits).float().mean().item()
                epoch_psnr  += compute_psnr(covers, stegos.detach())

        scheduler.step()

        avg_psnr = epoch_psnr / len(loader)
        print(
            f"\nEpoch {epoch}/{NUM_EPOCHS} | "
            f"PSNR: {avg_psnr:.2f} dB  "
            f"BitAcc(PNG): {last_bit_acc*100:.1f}%  "
            f"MsgLoss: {last_msg_loss:.4f}  "
            f"D: {last_d_loss:.4f}  "
            f"LR: {scheduler.get_last_lr()[0]:.2e}"
        )

        if target_tensor is not None:
            generator.eval()
            with torch.no_grad():
                cap            = generator.capacity(target_tensor.shape[2], target_tensor.shape[3])
                test_bits      = pack_message(TEST_MESSAGE, cap).unsqueeze(0).to(device)
                test_stego     = generator.encode(target_tensor, test_bits)
                test_bits_rec  = generator.decode(test_stego, cap)
                decoded        = unpack_message(test_bits_rec.squeeze(0))
                psnr_t         = compute_psnr(target_tensor, test_stego)
                match          = "✓" if decoded == TEST_MESSAGE else "✗"

            print(f"  Target image PSNR: {psnr_t:.2f} dB  Message: '{decoded}'  {match}")

            def denorm(t): return (t * 0.5 + 0.5).clamp(0, 1)
            import torchvision
            grid = torch.cat([denorm(target_tensor), denorm(test_stego)], dim=0)
            grid_img = torchvision.utils.make_grid(grid, nrow=2)
            torchvision.transforms.functional.to_pil_image(grid_img).save(
                sample_dir / f"epoch_{epoch:03d}.png"
            )

            if psnr_t > best_psnr:
                best_psnr = psnr_t
                torch.save({
                    "epoch":         epoch,
                    "generator":     generator.state_dict(),
                    "discriminator": discriminator.state_dict(),
                    "psnr":          psnr_t,
                }, out_path)
                print(f"  ✓ New best! Saved → {out_path} (PSNR: {psnr_t:.2f} dB)")
        else:
            torch.save({
                "epoch":         epoch,
                "generator":     generator.state_dict(),
                "discriminator": discriminator.state_dict(),
            }, out_path)

        if on_epoch:
            yield on_epoch(epoch, NUM_EPOCHS)

    print(f"\n✓ Fine-tuning complete. Best PSNR: {best_psnr:.2f} dB")
    print(f"  Fine-tuned model: {out_path}")


# ── Run ────────────────────────────────────────────────────────────────────────

def main():
    base = Path(__file__).parent.parent.parent   # SteganoGAN2/
    finetune(
        dataset_dir=     str(base / "input" / "variations"),
        base_checkpoint= str(base / "stegano2" / "training" / "checkpoints" / "checkpoint_epoch_0015.pt"),
        output_path=     str(base / "stegano2" / "training" / "checkpoints" / "finetuned.pt"),
        target_image=    str(base / "input" / "photo.jpg"),
    )


if __name__ == "__main__":
    main()
