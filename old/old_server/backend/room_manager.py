# backend/room_manager.py
# Rooms: creation, joining, and secure message passing using YOUR RSA+AES.

import base64
from SteganoGAN2.app.database.rooms_table  import (
    create_room as db_create_room,
    join_room as db_join_room,
    send_to_room, get_room_messages,
    get_rooms_by_owner, get_rooms_by_member, is_member,
    get_room_by_id as db_get_room_by_id,
)
from SteganoGAN2.app.database.users_table  import get_user_by_id
from SteganoGAN2.app.security.rsa_manager  import (
    encrypt_for_recipient, decrypt_from_sender, deserialize_public_key,
)
from SteganoGAN2.app.backend.auth          import Session


def create_room(owner_id: int, name: str) -> tuple[int, str]:
    """Create a room. Returns (room_id, auth_key)."""
    return db_create_room(owner_id, name)


def join_room(user_id: int, room_id: int, auth_key: str) -> bool:
    """Join a room with the auth key. Returns True on success."""
    return db_join_room(room_id, user_id, auth_key)


def get_my_rooms(user_id: int) -> dict[str, list[dict]]:
    """Return rooms owned by and rooms joined by this user."""
    return {
        "owned":  get_rooms_by_owner(user_id),
        "joined": [r for r in get_rooms_by_member(user_id)
                   if r["owner_id"] != user_id],
    }


def send_model_to_room(
    sender:            Session,
    room_id:           int,
    model_path:        str,
    recipient_user_id: int,
):
    """
    Securely send a trained model file through a room.

    Uses hybrid RSA+AES:
      1. AES encrypts the large model file
      2. RSA wraps the AES key (only recipient's private key can unwrap it)
      3. Both stored as base64 in the room message
    """
    recipient = get_user_by_id(recipient_user_id)
    if recipient is None or not recipient.get("rsa_public_key"):
        raise ValueError("Recipient has no RSA key — cannot encrypt for them")

    model_bytes   = open(model_path, "rb").read()
    recipient_pub = deserialize_public_key(recipient["rsa_public_key"])
    encrypted     = encrypt_for_recipient(model_bytes, recipient_pub)
    payload       = base64.b64encode(encrypted).decode()

    send_to_room(room_id, sender.user_id, "model", payload)


def receive_model_from_room(
    receiver:    Session,
    message:     dict,
    output_path: str,
):
    """Decrypt and save a model received from a room."""
    payload     = base64.b64decode(message["payload"])
    model_bytes = decrypt_from_sender(payload, receiver.rsa_private_key)
    with open(output_path, "wb") as f:
        f.write(model_bytes)


def send_key_to_room(
    sender:            Session,
    room_id:           int,
    key_data:          bytes,
    recipient_user_id: int,
):
    """Securely send a stego key through a room."""
    recipient = get_user_by_id(recipient_user_id)
    if recipient is None or not recipient.get("rsa_public_key"):
        raise ValueError("Recipient has no RSA key")

    recipient_pub = deserialize_public_key(recipient["rsa_public_key"])
    encrypted     = encrypt_for_recipient(key_data, recipient_pub)
    payload       = base64.b64encode(encrypted).decode()

    send_to_room(room_id, sender.user_id, "key", payload)


def get_inbox(room_id: int) -> list[dict]:
    """Get all messages in a room."""
    return get_room_messages(room_id)


def get_room_by_id(room_id: int) -> dict | None:
    """Fetch room info by ID."""
    return db_get_room_by_id(room_id)


def add_model_to_room(room_id: int, model_id: int, user_id: int) -> int:
    from SteganoGAN2.app.database.room_models_table import add_model_to_room as db_add
    return db_add(room_id, model_id, user_id)


def remove_model_from_room(entry_id: int):
    from SteganoGAN2.app.database.room_models_table import remove_model_from_room as db_remove
    db_remove(entry_id)


def get_room_models_detailed(room_id: int) -> list[dict]:
    """Room model entries enriched with full model data."""
    from SteganoGAN2.app.database.room_models_table import get_room_models
    from SteganoGAN2.app.database.models_table      import get_model_by_id
    result = []
    for entry in get_room_models(room_id):
        model = get_model_by_id(entry["model_id"])
        if model:
            result.append({**entry, "model": model})
    return result


def get_room_setting(room_id: int) -> bool:
    from SteganoGAN2.app.database.room_models_table import get_room_setting as db_get
    return db_get(room_id)


def set_room_setting(room_id: int, allow: bool):
    from SteganoGAN2.app.database.room_models_table import set_room_setting as db_set
    db_set(room_id, allow)