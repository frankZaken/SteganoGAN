# client/backend/api_model_manager.py
# Client-side model operations â€” all ML requests go through the old_server API.

import threading
import time
import uuid
from pathlib import Path
from typing import Callable

from api.api_client    import APIClient
from api.server_config import get_server

APP_DIR       = Path(__file__).parent.parent   # SteganoGAN2/client/
CREATIONS_DIR = APP_DIR / "data" / "creations"

_client_lock   = threading.Lock()
_cached_client: APIClient | None = None


def _client() -> APIClient:
    global _cached_client
    with _client_lock:
        if _cached_client is None:
            _cached_client = APIClient(get_server())
        return _cached_client


def _reset_client():
    global _cached_client
    with _client_lock:
        _cached_client = None


def encode_with_model(model_id: int, image_path: str,
                      message: str, output_path: str) -> str:
    client = _client()
    server_image = client.upload_file(image_path)
    server_stego = client.encode(model_id, server_image, message)
    if not output_path:
        CREATIONS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(CREATIONS_DIR / f"{uuid.uuid4().hex}.png")
    client.download_file(server_stego, output_path)
    return output_path


def decode_with_model(model_id: int, image_path: str) -> str:
    client = _client()
    server_image = client.upload_file(image_path)
    return client.decode(model_id, server_image)


def get_user_models(user_id: int) -> list[dict]:
    return _client().list_models(user_id)


def delete_model(model_id: int, user_id: int) -> bool:
    return _client().delete_model(model_id, user_id)


def train_model_async(
    user_id:     int,
    name:        str,
    description: str,
    image_path:  str,
    on_progress: Callable[[str, int], None],
    on_done:     Callable[[int | None], None],
    on_error:    Callable[[str], None],
):
    def run():
        try:
            client = _client()

            on_progress("Uploading image to serverâ€¦", 2)
            server_image  = client.upload_file(image_path)
            server_job_id = client.train(user_id, name, description, server_image)
            on_progress("Submitted to serverâ€¦", 5)

            last_step    = ""
            last_percent = 0

            while True:
                time.sleep(2)
                status = client.train_status(server_job_id, user_id)

                step    = status.get("step", "")
                percent = status.get("percent", 0)

                if step != last_step or percent != last_percent:
                    on_progress(step, percent)
                    last_step    = step
                    last_percent = percent

                if status.get("done"):
                    if status.get("error"):
                        on_error(status["error"])
                    else:
                        on_done(status.get("model_id"))
                    return

        except Exception as ex:
            on_error(str(ex))

    threading.Thread(target=run, daemon=True).start()
