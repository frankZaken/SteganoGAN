# gan/coupling_layer.py

import torch
import torch.nn as nn


class ScaleAndTranslateNetwork(nn.Module):
    """
    Takes half the channels → outputs scale (s) and translation (t).

    in_channels  = half the total channels  (e.g. 6 if total is 12)
    out_channels = full total channels      (e.g. 12 — first half=s, second=t)
    """

    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int):
        super().__init__()

        self.network = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size=3, padding=1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(hidden_channels, hidden_channels, kernel_size=3, padding=1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(hidden_channels, out_channels, kernel_size=3, padding=1),
        )

        nn.init.zeros_(self.network[-1].weight)
        nn.init.zeros_(self.network[-1].bias)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        output = self.network(x)

        s, t = output.chunk(2, dim=1)
        s = 2.0 * torch.tanh(s / 2.0)

        return s, t


class AffineCouplingLayer(nn.Module):
    """
    One invertible coupling layer.

    Forward:  [x1, x2] → [x1, x2 * exp(s(x1)) + t(x1)]
    Inverse:  [y1, y2] → [y1, (y2 - t(y1)) / exp(s(y1))]
    """

    def __init__(self, channels: int, hidden_channels: int = 64):
        super().__init__()
        assert channels % 2 == 0, "channels must be even to split in half"

        self.half = channels // 2

        self.net = ScaleAndTranslateNetwork(
            in_channels=self.half,
            hidden_channels=hidden_channels,
            out_channels=self.half * 2,  # half for s + half for t
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = x[:, :self.half]  # first half of channels
        x2 = x[:, self.half:]  # second half of channels

        s, t = self.net(x1)

        y2 = x2 * torch.exp(s) + t
        y = torch.cat([x1, y2], dim=1)

        return y

    def inverse(self, y: torch.Tensor) -> torch.Tensor:
        y1 = y[:, :self.half]
        y2 = y[:, self.half:]

        s, t = self.net(y1)

        x2 = (y2 - t) * torch.exp(-s)
        x = torch.cat([y1, x2], dim=1)

        return x


def main():
    layer = AffineCouplingLayer(channels=12, hidden_channels=32)

    x = torch.randn(2, 12, 16, 16)

    y = layer(x)
    print(f"Input shape:  {x.shape}")
    print(f"Output shape: {y.shape}")

    x_recovered = layer.inverse(y)

    error = (x - x_recovered).abs().max().item()
    print(f"\nMax recovery error: {error:.2e}")
    assert error < 1e-5, "Not invertible!"
    print("✓ Coupling layer is perfectly invertible!")


if __name__ == "__main__":
    main()