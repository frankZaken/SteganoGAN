# backend/training_queue.py
# GPU slot semaphore — allows multiple training jobs to be submitted at once
# while ensuring only one occupies the GPU at a time.
#
# Jobs submitted while the GPU is busy queue up automatically (OS-scheduled).
# Increase GPU_SLOTS to 2 only if your VRAM can hold two models simultaneously.

import threading

GPU_SLOTS = 1

_semaphore = threading.Semaphore(GPU_SLOTS)


class GPUSlot:
    """Context manager: acquires a GPU slot on enter, releases on exit."""

    def __init__(self, on_queued=None):
        self._on_queued = on_queued

    def __enter__(self):
        if not _semaphore.acquire(blocking=False):
            # Slot busy — notify the caller and block until one is free
            if self._on_queued:
                self._on_queued()
            _semaphore.acquire()
        return self

    def __exit__(self, *_):
        _semaphore.release()


def queued_count() -> int:
    """Approximate number of jobs waiting for a GPU slot."""
    return max(0, -_semaphore._value)
