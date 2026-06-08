# security/crypto/dhe.py
# Your DHE implementation â€” the simple version without networking.

from dataclasses import dataclass, field
from random import randint


@dataclass(slots=True)
class DHE:
    """
    Diffie-Hellman Key Exchange.
    Both parties compute the same shared secret without transmitting it.

    n: the shared prime modulus
    g: the generator (default 5)
    e: the private exponent (random if not given)
    """
    n: int
    g: int = 5
    e: int = None

    _send_output_cache:       int                  = field(init=False, default=None)
    _send_input_cache:        tuple[int, int, int] = field(init=False, default=None)
    _receive_send_output_cache: int                = field(init=False, default=None)
    _receive_send_input_cache: tuple[int, int, int] = field(init=False, default=None)

    def __post_init__(self):
        if self.e is None:
            self.e = randint(2, self.n - 2)

    def send(self) -> int:
        """Compute g^e mod n â€” the public value to send to the other party."""
        if self._send_input_cache != (inputs := (self.n, self.g, self.e)):
            self._send_output_cache = pow(self.g, self.e, self.n)
            self._send_input_cache  = inputs
        return self._send_output_cache

    def receive(self, value: int) -> int:
        """Compute value^e mod n â€” the shared secret from their public value."""
        if self._receive_send_input_cache != (inputs := (value, self.e, self.n)):
            self._receive_send_output_cache = pow(value, self.e, self.n)
            self._receive_send_input_cache  = inputs
        return self._receive_send_output_cache