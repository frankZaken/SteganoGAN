# client/api/jobs.py
# Client-side training job tracker — UI only, no old_server state.

import threading
import uuid

_lock = threading.Lock()
_jobs: dict[str, dict] = {}

_DONE_TTL = 10


def start(name: str) -> str:
    job_id = uuid.uuid4().hex[:8]
    with _lock:
        _jobs[job_id] = {"name": name, "step": "Starting…", "percent": 0,
                         "done": False, "error": None, "_ttl": None}
    return job_id


def update(job_id: str, step: str, percent: int):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["step"]    = step
            _jobs[job_id]["percent"] = percent


def finish(job_id: str, model_id=None):
    import time
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["done"]     = True
            _jobs[job_id]["model_id"] = model_id
            _jobs[job_id]["_ttl"]     = time.time() + _DONE_TTL


def fail(job_id: str, error: str):
    import time
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["done"]  = True
            _jobs[job_id]["error"] = error
            _jobs[job_id]["_ttl"]  = time.time() + _DONE_TTL


def active() -> list[dict]:
    with _lock:
        return [
            {k: v for k, v in j.items() if not k.startswith("_")}
            for j in _jobs.values()
            if not j["done"]
        ]


def cleanup():
    import time
    now = time.time()
    with _lock:
        expired = [jid for jid, j in _jobs.items()
                   if j["done"] and j["_ttl"] is not None and now > j["_ttl"]]
        for jid in expired:
            del _jobs[jid]
