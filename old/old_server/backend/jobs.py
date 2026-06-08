# old_server/backend/jobs.py
# Server-side in-memory tracker for background training jobs.

import threading
import uuid

_lock = threading.Lock()
_jobs: dict[str, dict] = {}


def start(name: str, user_id: int) -> str:
    job_id = uuid.uuid4().hex[:8]
    with _lock:
        _jobs[job_id] = {
            "id":      job_id,
            "name":    name,
            "user_id": user_id,
            "step":    "Starting…",
            "percent": 0,
            "done":    False,
            "error":   None,
            "model_id": None,
        }
    return job_id


def update(job_id: str, step: str, percent: int):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["step"]    = step
            _jobs[job_id]["percent"] = percent


def finish(job_id: str, model_id: int = None):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["done"]     = True
            _jobs[job_id]["percent"]  = 100
            _jobs[job_id]["step"]     = "Done!"
            _jobs[job_id]["model_id"] = model_id


def fail(job_id: str, error: str):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["done"]  = True
            _jobs[job_id]["error"] = error


def get_job(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs[job_id]) if job_id in _jobs else None


def active() -> list[dict]:
    with _lock:
        return [
            {k: v for k, v in j.items() if k != "user_id"}
            for j in _jobs.values()
            if not j["done"]
        ]
