# client/backend/api_room_manager.py
# Client-side room operations.
#
# OTP encryption:
#   Each room has a cryptographic seed (32 bytes) generated old_server-side on creation.
#   Text messages are encrypted client-side with HMAC-SHA256-based OTP before being
#   stored on the old_server.  The old_server only sees the ciphertext â€” it cannot read messages.
#
# Images:
#   Stego images are sent as base64-encoded PNG data (type="image").
#   They are already visually opaque (the hidden message is embedded in pixel data).

import base64
from pathlib import Path

from api.api_model_manager import _client

# room_id â†’ seed bytes (in-memory cache, populated on create/join/get)
_room_seeds: dict[int, bytes] = {}


def _store_seed(room_id: int, seed_hex: str):
    if seed_hex:
        _room_seeds[room_id] = bytes.fromhex(seed_hex)


# â”€â”€ Room management â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def create_room(owner_id: int, name: str) -> tuple[int, str]:
    room_id, auth_key, seed_hex = _client().room_create(owner_id, name)
    _store_seed(room_id, seed_hex)
    return room_id, auth_key


def join_room(user_id: int, room_id: int, auth_key: str) -> bool:
    ok, seed_hex = _client().room_join(user_id, room_id, auth_key)
    if ok:
        _store_seed(room_id, seed_hex)
    return ok


def get_my_rooms(user_id: int) -> dict:
    data = _client().room_list(user_id)
    for room in data.get("owned", []) + data.get("joined", []):
        _store_seed(room["id"], room.get("seed", ""))
    return data


def get_room_by_id(room_id: int) -> dict | None:
    room = _client().room_get(room_id)
    if room:
        _store_seed(room["id"], room.get("seed", ""))
    return room


def get_room_models_detailed(room_id: int) -> list[dict]:
    return _client().room_models(room_id)


def add_model_to_room(room_id: int, model_id: int, user_id: int) -> int:
    return _client().room_model_add(room_id, model_id, user_id)


def remove_model_from_room(entry_id: int) -> None:
    _client().room_model_remove(entry_id)


def get_room_setting(room_id: int) -> bool:
    return _client().room_setting_get(room_id)


def set_room_setting(room_id: int, allow: bool) -> None:
    _client().room_setting_set(room_id, allow)


# â”€â”€ Messaging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def send_text_message(room_id: int, sender_id: int, text: str) -> None:
    """OTP-encrypt the text with the room seed, then post to the old_server."""
    seed = _room_seeds.get(room_id)
    if seed:
        from security.otp import otp_encrypt
        raw     = text.encode("utf-8")
        payload = base64.b64encode(otp_encrypt(raw, seed)).decode()
    else:
        payload = base64.b64encode(text.encode("utf-8")).decode()
    _client().room_message_send(room_id, sender_id, "text", payload)


def send_image_message(room_id: int, sender_id: int, image_path: str) -> None:
    """Send a stego PNG image as a room message (base64-encoded)."""
    data    = Path(image_path).read_bytes()
    payload = base64.b64encode(data).decode()
    _client().room_message_send(room_id, sender_id, "image", payload)


def get_inbox(room_id: int) -> list[dict]:
    """
    Fetch and decode all messages in a room.
    Text messages are OTP-decrypted; image messages stay as base64.
    Adds 'decoded_text' or 'image_bytes' key to each message.
    """
    messages = _client().room_message_list(room_id)
    seed     = _room_seeds.get(room_id)
    result   = []

    for msg in messages:
        if msg["type"] == "text":
            try:
                raw = base64.b64decode(msg["payload"])
                if seed:
                    from security.otp import otp_decrypt
                    text = otp_decrypt(raw, seed).decode("utf-8")
                else:
                    text = raw.decode("utf-8")
            except Exception:
                text = "[decryption failed]"
            result.append({**msg, "decoded_text": text})

        elif msg["type"] == "image":
            result.append({**msg, "image_bytes": msg["payload"]})

        else:
            result.append(msg)

    return result
