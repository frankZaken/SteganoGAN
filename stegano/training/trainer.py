# stegano2/training/trainer.py

import torch
import torch.nn as nn
import torch.optim as optim
from torch import Tensor
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from pathlib import Path
from PIL import Image, ImageDraw
import torchvision

from stegano.gan.generator     import InvertibleGenerator
from stegano.gan.discriminator import Discriminator
from stegano.core.message      import pack_message, unpack_message


# ── Configuration ─────────────────────────────────────────────────────────────

IMAGE_SIZE       = 256
BATCH_SIZE       = 8
NUM_EPOCHS       = 50
LR_GEN           = 2e-4
LR_DISC          = 5e-5
LAMBDA_ADV       = 0.01
LAMBDA_IMG       = 10.0
DISC_TRAIN_EVERY = 5
LOG_EVERY        = 50
SAVE_EVERY       = 5
TEST_MESSAGE     = "hello stego"



def get_dataloader() -> DataLoader:
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5]),
    ])
    dataset = datasets.CIFAR10(root="./data", train=True, download=True, transform=transform)
    return DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True, num_workers=2, drop_last=True)



def compute_psnr(cover: Tensor, stego: Tensor) -> float:
    mse = nn.functional.mse_loss(cover, stego).item()
    if mse == 0:
        return float("inf")
    return 10 * torch.log10(torch.tensor(1.0 / mse)).item()



def save_samples(generator, covers, device, epoch, sample_dir):
    generator.eval()
    with torch.no_grad():
        n = min(8, covers.shape[0])
        H, W = covers.shape[2], covers.shape[3]
        capacity = generator.capacity(H, W)

        test_bits = pack_message(TEST_MESSAGE, capacity).unsqueeze(0).to(device)
        test_stego = generator.encode(covers[:1], test_bits)
        test_bits_recovered = generator.decode(test_stego, capacity)
        decoded = unpack_message(test_bits_recovered.squeeze(0))

        rand_bits = torch.randint(0, 2, (n, capacity)).float().to(device)
        stegos = generator.encode(covers[:n], rand_bits)

        def denorm(t):
            return (t * 0.5 + 0.5).clamp(0, 1)

        grid = torch.cat([denorm(covers[:n]), denorm(stegos)], dim=0)
        grid_img = torchvision.utils.make_grid(grid, nrow=n)
        grid_pil = torchvision.transforms.functional.to_pil_image(grid_img)

        scale = 4
        grid_pil = grid_pil.resize((grid_pil.width * scale, grid_pil.height * scale), Image.NEAREST)

        draw  = ImageDraw.Draw(grid_pil)
        row_h = grid_pil.height // 2
        for i, (label, color) in enumerate([("Cover", (100, 220, 100)), ("Stego", (100, 180, 255))]):
            draw.text((4, i * row_h + 4), label, fill=(0, 0, 0))
            draw.text((3, i * row_h + 3), label, fill=color)

        match = "✓" if decoded == TEST_MESSAGE else "✗"
        banner = f"Epoch {epoch}  |  '{TEST_MESSAGE}' → '{decoded}'  {match}"
        banner_h = 22
        combined = Image.new("RGB", (grid_pil.width, grid_pil.height + banner_h))
        combined.paste(grid_pil, (0, 0))
        combined.paste(Image.new("RGB", (grid_pil.width, banner_h), (20, 20, 20)), (0, grid_pil.height))
        ImageDraw.Draw(combined).text((6, grid_pil.height + 4), banner, fill=(220, 220, 220))
        combined.save(sample_dir / f"epoch_{epoch:04d}.png")

        print(f"  Test message: '{TEST_MESSAGE}' → '{decoded}'  {match}")
    generator.train()



def train():
    device = torch.device(
        "cuda" if torch.cuda.is_available() else
        "mps"  if torch.backends.mps.is_available() else
        "cpu"
    )
    print(f"Training on: {device}")

    base       = Path(__file__).parent.parent.parent   # project root
    ckpt_dir   = base / "stegano" / "training" / "checkpoints"
    sample_dir = base / "stegano" / "training" / "samples"
    ckpt_dir.mkdir(exist_ok=True)
    sample_dir.mkdir(exist_ok=True)

    generator     = InvertibleGenerator(hidden_channels=64, num_layers=8).to(device)
    discriminator = Discriminator(image_channels=3).to(device)

    opt_gen  = optim.Adam(generator.parameters(),     lr=LR_GEN,  betas=(0.5, 0.999))
    opt_disc = optim.Adam(discriminator.parameters(), lr=LR_DISC, betas=(0.5, 0.999))

    bce = nn.BCEWithLogitsLoss()
    mse = nn.MSELoss()
    l1  = nn.L1Loss()


    loader = get_dataloader()
    print(f"Dataset: CIFAR-10 | Batches per epoch: {len(loader)}")

    last_disc_loss = 0.0

    for epoch in range(1, NUM_EPOCHS + 1):
        generator.train()
        discriminator.train()

        epoch_g = epoch_d = epoch_psnr = 0.0

        for batch_idx, (covers, _) in enumerate(loader):
            covers   = covers.to(device)
            H, W     = covers.shape[2], covers.shape[3]
            capacity = generator.capacity(H, W)
            bits     = torch.randint(0, 2, (BATCH_SIZE, capacity)).float().to(device)

            stegos = generator.encode(covers, bits)

            if batch_idx % DISC_TRAIN_EVERY == 0:
                opt_disc.zero_grad()
                real_scores = discriminator(covers)
                fake_scores = discriminator(stegos.detach())
                loss_disc = (
                    bce(real_scores, torch.ones_like(real_scores)  * 0.9) +
                    bce(fake_scores, torch.zeros_like(fake_scores) + 0.1)
                ) * 0.5
                loss_disc.backward()
                opt_disc.step()
                last_disc_loss = loss_disc.item()

            opt_gen.zero_grad()
            stegos    = generator.encode(covers, bits)
            loss_adv  = bce(discriminator(stegos), torch.ones_like(discriminator(stegos)))
            loss_img  = mse(stegos, covers) + 0.5 * l1(stegos, covers)
            loss_gen  = LAMBDA_ADV * loss_adv + LAMBDA_IMG * loss_img
            loss_gen.backward()
            opt_gen.step()

            with torch.no_grad():
                stegos_check = generator.encode(covers, bits)
                bits_rec     = generator.decode(stegos_check, capacity)
                bit_acc      = (bits_rec == bits).float().mean().item()
                psnr         = compute_psnr(covers, stegos_check)

            epoch_g    += loss_gen.item()
            epoch_d    += last_disc_loss
            epoch_psnr += psnr

            if (batch_idx + 1) % LOG_EVERY == 0:
                print(
                    f"Epoch [{epoch:3d}/{NUM_EPOCHS}] "
                    f"Batch [{batch_idx+1:4d}/{len(loader)}] | "
                    f"G: {loss_gen.item():.4f}  D: {last_disc_loss:.4f}  "
                    f"PSNR: {psnr:.1f} dB  BitAcc: {bit_acc*100:.1f}%"
                )

        n = len(loader)
        print(f"\n=== Epoch {epoch}/{NUM_EPOCHS} === G: {epoch_g/n:.4f}  D: {epoch_d/n:.4f}  PSNR: {epoch_psnr/n:.1f} dB\n")

        covers_sample, _ = next(iter(loader))
        save_samples(generator, covers_sample.to(device), device, epoch, sample_dir)

        if epoch % SAVE_EVERY == 0:
            torch.save({
                "epoch": epoch,
                "generator": generator.state_dict(),
                "discriminator": discriminator.state_dict(),
            }, ckpt_dir / f"checkpoint_epoch_{epoch:04d}.pt")
            print(f"Checkpoint saved: checkpoint_epoch_{epoch:04d}.pt")


if __name__ == "__main__":
    train()
