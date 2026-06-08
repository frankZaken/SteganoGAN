# gan/discriminator.py

import torch
import torch.nn as nn


class DiscriminatorBlock(nn.Module):
    """
    One step of the discriminator:
    Conv2d (stride 2, halves spatial size) → BatchNorm → LeakyReLU
    """

    def __init__(
        self,
        in_channels:  int,
        out_channels: int,
        use_norm:     bool = True,
    ):
        super().__init__()

        layers = [
            nn.Conv2d(
                in_channels, out_channels,
                kernel_size=4, stride=2, padding=1,
                bias=not use_norm,
            )
        ]

        if use_norm:
            layers.append(nn.BatchNorm2d(out_channels))

        layers.append(nn.LeakyReLU(0.2, inplace=True))

        self.block = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class Discriminator(nn.Module):
    """
    PatchGAN discriminator.
    Judges whether an image is a real cover or a stego image.
    Outputs a grid of scores — one per local patch.
    """

    def __init__(
        self,
        image_channels: int = 3,
        base_features:  int = 32,
        num_blocks:     int = 3,
    ):
        super().__init__()

        blocks = [
            # First block: no BatchNorm (standard GAN practice)
            DiscriminatorBlock(image_channels, base_features, use_norm=False)
        ]

        in_ch = base_features
        for i in range(1, num_blocks):
            out_ch = min(base_features * (2 ** i), 256)  # double each block, cap at 256
            blocks.append(DiscriminatorBlock(in_ch, out_ch, use_norm=True))
            in_ch = out_ch

        # Final layer: old_testing_output one score per patch
        blocks.append(
            nn.Conv2d(in_ch, 1, kernel_size=4, stride=1, padding=1)
        )

        self.model = nn.Sequential(*blocks)
        self._init_weights()

    def _init_weights(self):

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, mean=0.0, std=0.02)

                if m.bias is not None:
                    nn.init.zeros_(m.bias)

            elif isinstance(m, nn.BatchNorm2d):
                nn.init.normal_(m.weight, mean=1.0, std=0.02)
                nn.init.zeros_(m.bias)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        """
        Judge an image.
        Returns raw logits (not passed through sigmoid).
        Use BCEWithLogitsLoss during training.
        """
        return self.model(image)


def main():
    disc = Discriminator(
        image_channels=3,
        base_features=32,
        num_blocks=3,
    )

    # batch of 4 images, 3 channels, 32×32
    images = torch.randn(4, 3, 32, 32)

    scores = disc(images)

    print(f"Input shape:  {images.shape}")
    print(f"Output shape: {scores.shape}")   # (4, 1, H', W')

    # scores should be different for different images
    print(f"Score range:  {scores.min().item():.3f} to {scores.max().item():.3f}")
    print("✓ Discriminator works!")


if __name__ == "__main__":
    main()