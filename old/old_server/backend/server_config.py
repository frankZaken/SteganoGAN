# client/backend/server_config.py

import json
from pathlib import Path

_CONFIG = Path(__file__).parent.parent.parent / "data" / "server_config.json"

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8765


def get_server() -> tuple[str, int]:
    if _CONFIG.exists():
        data = json.loads(_CONFIG.read_text())
        return data.get("host", _DEFAULT_HOST), data.get("port", _DEFAULT_PORT)
    return _DEFAULT_HOST, _DEFAULT_PORT


def set_server(host: str, port: int = _DEFAULT_PORT) -> None:
    _CONFIG.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG.write_text(json.dumps({"host": host, "port": port}))


def is_configured() -> bool:
    return _CONFIG.exists()
