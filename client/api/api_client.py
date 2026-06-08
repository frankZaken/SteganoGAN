# client/api/api_client.py

import base64
import json
from pathlib import Path

from httpio.client import HTTPClient
from httpio.request import HTTPRequest


class APIClient:
    def __init__(self, address: tuple[str, int]):
        self._address    = address
        self._session_id: str   = ""
        self._http_client = HTTPClient(address)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def _post(self, uri: str, data: dict[str, ...]) -> dict[str, ...]:
        request_body = json.dumps(data).encode()
        post = HTTPRequest(uri=uri, body=request_body, method="POST")

        response = self._http_client.open(post)
        status = response.status

        if status != 200:
            try:
                msg = json.loads(response.body).get("error", f"Server error {status}")
            except Exception:
                msg = f"Server error {status}"
            raise RuntimeError(msg)

        return json.loads(response.body)

    def signup(self, username: str, password_hash: str, pub_key: str) -> int:
        return self._post("/auth/signup", {
            "username": username, "password_hash": password_hash, "pub_key": pub_key,
        })["user_id"]

    def login(self, username: str, password: str) -> dict:
        return self._post("/auth/login", {"username": username, "password": password})

    def update_pubkey(self, user_id: int, pub_key: str) -> None:
        self._post("/auth/update_pubkey", {"user_id": user_id, "pub_key": pub_key})

    def change_password(self, user_id: int, new_password_hash: str) -> None:
        self._post("/auth/change_password", {
            "user_id": user_id, "new_password_hash": new_password_hash,
        })

    def delete_account(self, user_id: int) -> None:
        self._post("/auth/delete_account", {"user_id": user_id})

    # ── File transfer ─────────────────────────────────────────────────────────

    def upload_file(self, local_path: str) -> str:
        data = Path(local_path).read_bytes()
        return self._post("/file/upload", {
            "filename": Path(local_path).name,
            "data":     base64.b64encode(data).decode(),
        })["server_path"]

    def download_file(self, server_path: str, local_path: str) -> None:
        resp = self._post("/file/download", {"server_path": server_path})
        data = base64.b64decode(resp["data"])
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(data)

    # ── ML operations ─────────────────────────────────────────────────────────

    def train(self, user_id: int, name: str, description: str, image_path: str) -> str:
        return self._post("/model/train", {
            "user_id": user_id, "name": name,
            "description": description, "image_path": image_path,
        })["job_id"]

    def train_status(self, job_id: str, user_id: int) -> dict:
        return self._post("/model/train/status", {"job_id": job_id, "user_id": user_id})

    def encode(self, model_id: int, image_path: str, message: str,
               output_path: str = "") -> str:
        return self._post("/model/encode", {
            "model_id": model_id, "image_path": image_path,
            "message": message, "output_path": output_path,
        })["output_path"]

    def decode(self, model_id: int, image_path: str) -> str:
        return self._post("/model/decode", {
            "model_id": model_id, "image_path": image_path,
        })["message"]

    def list_models(self, user_id: int) -> list[dict]:
        return self._post("/model/list", {"user_id": user_id})["models"]

    def delete_model(self, model_id: int, user_id: int) -> bool:
        return self._post("/model/delete", {
            "model_id": model_id, "user_id": user_id,
        })["ok"]

    def active_jobs(self) -> list[dict]:
        return self._post("/jobs/active", {})["jobs"]

    # ── User lookup ───────────────────────────────────────────────────────────

    def get_user_by_id(self, user_id: int) -> dict | None:
        try:
            return self._post("/user/get", {"user_id": user_id})
        except RuntimeError:
            return None

    def get_user_by_username(self, username: str) -> dict | None:
        try:
            return self._post("/user/get", {"username": username})
        except RuntimeError:
            return None

    # ── Rooms ─────────────────────────────────────────────────────────────────

    def room_create(self, owner_id: int, name: str) -> tuple[int, str, str]:
        r = self._post("/room/create", {"owner_id": owner_id, "name": name})
        return r["room_id"], r["auth_key"], r.get("seed", "")

    def room_join(self, user_id: int, room_id: int, auth_key: str) -> tuple[bool, str]:
        r = self._post("/room/join", {
            "user_id": user_id, "room_id": room_id, "auth_key": auth_key,
        })
        return r["ok"], r.get("seed", "")

    def room_list(self, user_id: int) -> dict:
        return self._post("/room/list", {"user_id": user_id})

    def room_get(self, room_id: int) -> dict | None:
        try:
            return self._post("/room/get", {"room_id": room_id})["room"]
        except RuntimeError:
            return None

    def room_model_add(self, room_id: int, model_id: int, user_id: int) -> int:
        return self._post("/room/model/add", {
            "room_id": room_id, "model_id": model_id, "user_id": user_id,
        })["entry_id"]

    def room_model_remove(self, entry_id: int) -> None:
        self._post("/room/model/remove", {"entry_id": entry_id})

    def room_models(self, room_id: int) -> list[dict]:
        return self._post("/room/models", {"room_id": room_id})["entries"]

    def room_setting_get(self, room_id: int) -> bool:
        return self._post("/room/setting/get", {"room_id": room_id})["allow_member_models"]

    def room_setting_set(self, room_id: int, allow: bool) -> None:
        self._post("/room/setting/set", {"room_id": room_id, "allow": allow})

    def room_message_send(self, room_id: int, sender_id: int,
                          msg_type: str, payload: str) -> None:
        self._post("/room/message/send", {
            "room_id": room_id, "sender_id": sender_id,
            "type": msg_type, "payload": payload,
        })

    def room_message_list(self, room_id: int) -> list[dict]:
        return self._post("/room/message/list", {"room_id": room_id})["messages"]

    # ── Direct shares ─────────────────────────────────────────────────────────

    def share_send(self, sender_id: int, recipient_username: str,
                   model_id: int) -> tuple[bool, str]:
        try:
            self._post("/share/send", {
                "sender_id": sender_id,
                "recipient_username": recipient_username,
                "model_id": model_id,
            })
            return True, ""
        except RuntimeError as e:
            return False, str(e)

    def share_list(self, user_id: int) -> list[dict]:
        return self._post("/share/list", {"user_id": user_id})["shares"]

    def share_delete(self, share_id: int) -> None:
        self._post("/share/delete", {"share_id": share_id})

    # ── Creations ─────────────────────────────────────────────────────────────

    def creation_add(self, user_id: int, model_id: int | None,
                     original_path: str, stego_path: str) -> int:
        return self._post("/creation/add", {
            "user_id": user_id, "model_id": model_id,
            "original_path": original_path, "stego_path": stego_path,
        })["id"]

    def creation_list(self, user_id: int) -> list[dict]:
        return self._post("/creation/list", {"user_id": user_id})["creations"]

    def creation_delete(self, creation_id: int) -> None:
        self._post("/creation/delete", {"creation_id": creation_id})
