# old_db_tools/client_demo.py
# Interactive client demo — run AFTER starting the old_server with:
#   python SteganoGAN2/old_server.py
#
# Usage:
#   python SteganoGAN2/old_db_tools/client_demo.py
#
# What it does:
#   1. Checks old_server connection
#   2. Shows current DB state
#   3. Submits a training job and polls status live
#   4. Shows DB diff after each status change (new rows highlighted)
#   5. Reports final result

import sys
import time
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from SteganoGAN2.app.backend.api_client import APIClient
from SteganoGAN2.app.database.db        import get_engine
from SteganoGAN2.app.database.schema    import USERS_TABLE, MODELS_TABLE

# ── Config ────────────────────────────────────────────────────────────────────

SERVER      = ("127.0.0.1", 8765)
POLL_SECS   = 3
MAX_POLLS   = 200   # ~10 minutes before giving up

# ── Helpers ───────────────────────────────────────────────────────────────────

W = 64

def header(title: str):
    pad = (W - len(title) - 2) // 2
    print(f"\n{'─' * pad} {title} {'─' * (W - pad - len(title) - 2)}")

def divider():
    print("─" * W)

def _fetch(table) -> list[dict]:
    eng  = get_engine()
    rows = list(eng.execute(__import__(
        'SteganoGAN2.app.database.sql.query', fromlist=['Select']
    ).Select(table)))
    eng.close()
    return rows

def show_table(table, title: str):
    rows = _fetch(table)
    print(f"\n  {title} ({len(rows)} row{'s' if len(rows) != 1 else ''}):")
    if not rows:
        print("    (empty)")
        return rows
    cols  = list(rows[0].keys())
    widths = {c: max(len(c), max(len(str(r.get(c, ''))) for r in rows)) for c in cols}
    header_line = "  " + "  ".join(c.ljust(widths[c]) for c in cols)
    print(header_line)
    print("  " + "  ".join("─" * widths[c] for c in cols))
    for row in rows:
        print("  " + "  ".join(str(row.get(c, '')).ljust(widths[c]) for c in cols))
    return rows

def db_snapshot() -> dict:
    """Return {table_name: [rows]} and also print them."""
    header("DATABASE STATE")
    snap = {}
    snap["users"]  = show_table(USERS_TABLE,  "users")
    snap["models"] = show_table(MODELS_TABLE, "models")
    return snap

def db_diff(before: dict, after: dict):
    """Print rows that are new since the last snapshot."""
    changed = False
    for name in before:
        old_ids = {r.get("id") for r in before[name]}
        new_rows = [r for r in after[name] if r.get("id") not in old_ids]
        if new_rows:
            if not changed:
                header("NEW DB ROWS")
                changed = True
            print(f"\n  + {name}:")
            for row in new_rows:
                print(f"    {dict(row)}")
    if not changed:
        print("  (no new rows)")

def progress_bar(pct: int, width: int = 24) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)

# ── Steps ─────────────────────────────────────────────────────────────────────

def step_connection(client: APIClient) -> bool:
    header("1 / CONNECTION TEST")
    try:
        jobs = client.active_jobs()
        print(f"  ✓ Server reachable at {SERVER[0]}:{SERVER[1]}")
        print(f"  Active jobs on server: {len(jobs)}")
        return True
    except Exception as e:
        print(f"  ✗ Cannot reach server: {e}")
        print(f"  Make sure it's running:  python SteganoGAN2/server.py")
        return False


def step_list_models(client: APIClient, user_id: int):
    header("2 / MODELS FOR USER")
    try:
        models = client.list_models(user_id)
        if models:
            for m in models:
                print(f"  [{m['id']}] {m['name']}  —  {m.get('description') or 'no description'}")
        else:
            print(f"  (no models yet for user {user_id})")
        return models
    except Exception as e:
        print(f"  Error: {e}")
        return []


def step_train(client: APIClient, user_id: int, name: str, desc: str, image_path: str) -> str | None:
    header("3 / SUBMIT TRAINING JOB")
    if not Path(image_path).exists():
        print(f"  ✗ Image not found: {image_path}")
        print(f"  Edit IMAGE_PATH at the bottom of this file to point to a real JPG/PNG.")
        return None
    try:
        job_id = client.train(user_id, name, desc, image_path)
        print(f"  ✓ Job submitted — id: {job_id}")
        print(f"  Model name : {name}")
        print(f"  Image      : {image_path}")
        return job_id
    except Exception as e:
        print(f"  ✗ Server error: {e}")
        return None


def step_poll(client: APIClient, job_id: str, before_snap: dict):
    header("4 / TRAINING PROGRESS  (Ctrl-C to stop polling)")
    print()
    last_step  = ""
    after_snap = before_snap

    for i in range(MAX_POLLS):
        try:
            status = client.train_status(job_id)
        except Exception as e:
            print(f"\n  Poll error: {e}")
            break

        pct  = status.get("percent", 0)
        step = status.get("step", "")

        print(f"\r  [{progress_bar(pct)}] {pct:3d}%  {step:<45}", end="", flush=True)

        if status.get("done"):
            print()
            if status.get("error"):
                print(f"\n  ✗ Training failed: {status['error']}")
            else:
                print(f"\n  ✓ Training complete!")
                # show DB diff now that a model record exists
                after_snap = db_snapshot()
                db_diff(before_snap, after_snap)
            return status, after_snap

        if step != last_step:
            # snapshot DB each time a new training phase starts
            after_snap = db_snapshot()
            db_diff(before_snap, after_snap)
            before_snap = after_snap
            last_step   = step

        time.sleep(POLL_SECS)

    print("\n  (polling stopped)")
    return None, after_snap


# ── Entry point ───────────────────────────────────────────────────────────────

# ↓↓  Edit these before running  ↓↓
USER_ID    = 1
MODEL_NAME = "demo_model"
MODEL_DESC = "Trained via client_demo.py"
IMAGE_PATH = str(Path(__file__).parent.parent / "input" / "photo.jpg")
# ↑↑  Edit these before running  ↑↑


def main():
    divider()
    print(" SteganoGAN — Client Demo")
    divider()

    client = APIClient(SERVER)

    # 1. Connection
    if not step_connection(client):
        return

    # 2. Initial DB snapshot
    snap = db_snapshot()

    # 3. List existing models
    step_list_models(client, USER_ID)

    # 4. Submit training
    job_id = step_train(client, USER_ID, MODEL_NAME, MODEL_DESC, IMAGE_PATH)
    if job_id is None:
        return

    # 5. Poll + live DB updates
    step_poll(client, job_id, snap)

    header("DONE")
    print(f"  Run  python SteganoGAN2/tools/db_repl.py  for an interactive DB explorer.")
    print()


if __name__ == "__main__":
    main()
