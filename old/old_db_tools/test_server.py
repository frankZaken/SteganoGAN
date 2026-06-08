# old_db_tools/test_server.py
# Quick connection test — run AFTER starting the old_server with:
#   python SteganoGAN2/old_server.py
#
# Run this script:
#   python SteganoGAN2/old_db_tools/test_server.py

import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from SteganoGAN2.httpio.client  import HTTPClient
from SteganoGAN2.httpio.request import HTTPRequest


SERVER = ("127.0.0.1", 8765)


def post(uri: str, body: dict) -> dict:
    raw = json.dumps(body).encode()
    req = HTTPRequest(
        method="POST",
        uri=uri,
        headers={"Content-Type": "application/json", "Content-Length": str(len(raw))},
        body=raw,
    )
    client = HTTPClient(server_address=SERVER, buffer=65536)
    resp   = client.open(req)
    print(f"  {resp.status} {resp.message}  →  {resp.body[:120].decode(errors='replace')}")
    return json.loads(resp.body) if resp.body else {}


if __name__ == "__main__":
    print(f"Connecting to {SERVER[0]}:{SERVER[1]} …\n")

    # 1. unknown route → 404
    print("GET /unknown (expect 404):")
    post("/unknown", {})

    # 2. list models for user 1 (may be empty, but old_server should respond)
    print("\nPOST /model/list {user_id: 1} (expect 200):")
    result = post("/model/list", {"user_id": 1})
    print(f"  models returned: {len(result.get('models', []))}")

    # 3. active jobs (expect empty list)
    print("\nPOST /jobs/active (expect 200):")
    result = post("/jobs/active", {})
    print(f"  active jobs: {result.get('jobs', [])}")

    print("\nDone — old_server is responding correctly.")
