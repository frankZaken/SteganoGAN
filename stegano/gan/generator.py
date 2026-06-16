# stegano2/gan/generator.py

import torch
from torch import Tensor, nn

from ..core.message    import pack_message, unpack_message
from .coupling_layer   import AffineCouplingLayer

MSG_SCALE    = 5.0
MSG_CH_START = 8
MSG_CH_END   = 12


# def squeeze(x: Tensor) -> Tensor:
#     B, C, H, W = x.shape
#
#     x = x.reshape(B, C, H//2, 2, W//2, 2)
#     x = x.permute(0, 1, 3, 5, 2, 4)
#     x = x.reshape(B, C*4, H//2, W//2)
#
#     return x
#
# def unsqueeze(x: Tensor) -> Tensor:
#     B, C4, Hs, Ws = x.shape
#     C = C4 // 4
#
#     x = x.reshape(B, C, 2, 2, Hs, Ws)
#     x = x.permute(0, 1, 4, 2, 5, 3)
#     x = x.reshape(B, C, Hs*2, Ws*2)
#
#     return x

_PERM     = torch.tensor([0, 4, 8, 1, 5, 9, 2, 6, 10, 3, 7, 11])
_INV_PERM = torch.argsort(_PERM)


def squeeze(x: Tensor) -> Tensor:
    B, C, H, W = x.shape

    x = x.reshape(B, C, H // 2, 2, W // 2, 2)
    x = x.permute(0, 1, 3, 5, 2, 4)
    x = x.reshape(B, C * 4, H // 2, W // 2)

    return x[:, _PERM.to(x.device)]            # shuffle channels


def unsqueeze(x: Tensor) -> Tensor:
    x = x[:, _INV_PERM.to(x.device)]           # de-shuffle first

    B, C4, Hs, Ws = x.shape
    C = C4 // 4

    x = x.reshape(B, C, 2, 2, Hs, Ws)
    x = x.permute(0, 1, 4, 2, 5, 3)
    x = x.reshape(B, C, Hs * 2, Ws * 2)

    return x

def inject_message(latent: Tensor, bits: Tensor) -> Tensor:
    B, C, Hs, Ws = latent.shape
    msg_channels = MSG_CH_END - MSG_CH_START   # = 4

    signal = bits * (2.0 * MSG_SCALE) - MSG_SCALE   # {-5, +5}
    signal = signal.reshape(B, msg_channels, Hs, Ws)

    latent = latent.clone()
    latent[:, MSG_CH_START:MSG_CH_END] = signal

    return latent

def extract_message(latent: Tensor, num_bits: int) -> Tensor:
    B = latent.shape[0]
    msg_channels = latent[:, MSG_CH_START:MSG_CH_END]   # (B, 4, Hs, Ws)

    flat = msg_channels.reshape(B, -1)
    flat = flat[:, :num_bits]

    bits = (flat > 0).float()

    return bits


class InvertibleGenerator(nn.Module):

    def __init__(self, hidden_channels: int = 64, num_layers: int = 8):
        super().__init__()

        latent_channels = MSG_CH_END
        self.coupling_layers = nn.ModuleList(
            [
                AffineCouplingLayer(
                    channels=latent_channels,
                    hidden_channels=hidden_channels,
                )

                for _ in range(num_layers)
            ]
        )

    def capacity(self, H: int, W: int) -> int:
        msg_channels = MSG_CH_END - MSG_CH_START   # 4
        return msg_channels * (H // 2) * (W // 2)  # = H×W

    def encode(self, cover: torch.Tensor, bits: torch.Tensor) -> torch.Tensor:
        latent = squeeze(cover)
        latent = inject_message(latent, bits)

        for layer in self.coupling_layers:
            latent = layer(latent)

        return unsqueeze(latent)

    def decode(self, stego: torch.Tensor, num_bits: int) -> torch.Tensor:
        latent = squeeze(stego)

        for layer in reversed(self.coupling_layers):
            latent = layer.inverse(latent)

        return extract_message(latent, num_bits)


def main():
    generator = InvertibleGenerator(hidden_channels=64, num_layers=8)

    x = torch.randn(1, 3, 32, 32)
    assert (x - unsqueeze(squeeze(x))).abs().max() == 0.0
    print("✓ Squeeze round-trip: perfect")

    cover    = torch.randn(1, 3, 32, 32)
    capacity = generator.capacity(32, 32)
    bits_in  = pack_message("hello!", capacity).unsqueeze(0)

    stego    = generator.encode(cover, bits_in)
    bits_out = generator.decode(stego, capacity)

    message = unpack_message(bits_out.squeeze(0))
    assert message == "hello!", f"Got: {repr(message)}"
    print(f"✓ Message recovered: {repr(message)}")

    accuracy = (bits_out == bits_in).float().mean().item()
    print(f"✓ Bit accuracy: {accuracy * 100:.1f}%")
    print(f"✓ Cover shape: {cover.shape}")
    print(f"✓ Stego shape: {stego.shape}")
    print(f"✓ Capacity:    {capacity} bits = {capacity // 8} bytes")


if __name__ == '__main__':
    main()
