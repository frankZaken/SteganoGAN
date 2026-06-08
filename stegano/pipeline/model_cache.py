# pipeline/model_cache.py
# Thread-safe LRU cache for loaded generator checkpoints.
# Avoids reloading .pt files from disk on every encode/decode call.
# Safe for concurrent reads — PyTorch eval-mode inference is thread-safe.

import threading
from collections import OrderedDict

import torch

_lock: threading.Lock       = threading.Lock()
_cache: OrderedDict         = OrderedDict()
CACHE_SIZE: int             = 3   # max models kept in memory simultaneously


def get_generator(checkpoint_path: str):
    """
    Return a (generator, device) pair for checkpoint_path.
    Loads from disk on first call; returns the cached instance on subsequent calls.
    """
    from stegano.gan.generator import InvertibleGenerator   # relative import — same package

    with _lock:
        if checkpoint_path in _cache:
            _cache.move_to_end(checkpoint_path)
            return _cache[checkpoint_path]

    # Load outside the lock so other threads aren't blocked during disk I/O
    device = torch.device(
        "cuda" if torch.cuda.is_available() else
        "mps"  if torch.backends.mps.is_available() else
        "cpu"
    )
    gen = InvertibleGenerator(hidden_channels=64, num_layers=8).to(device)
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)
    gen.load_state_dict(ckpt["generator"])
    gen.eval()

    with _lock:
        # Another thread may have loaded the same path while we were loading —
        # keep theirs so we don't stomp a reference already in use.
        if checkpoint_path not in _cache:
            _cache[checkpoint_path] = (gen, device)
            if len(_cache) > CACHE_SIZE:
                _cache.popitem(last=False)

    return _cache[checkpoint_path]


def invalidate(checkpoint_path: str) -> None:
    """Remove a checkpoint from the cache (call after a model is deleted or replaced)."""
    with _lock:
        _cache.pop(checkpoint_path, None)
