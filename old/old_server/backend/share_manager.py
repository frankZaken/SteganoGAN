# backend/share_manager.py
# Direct model sharing — no room required.

from SteganoGAN2.app.database.direct_shares_table import (
    create_share, get_received_shares, delete_share as db_delete_share,
)
from SteganoGAN2.app.database.users_table  import get_user_by_username, get_user_by_id
from SteganoGAN2.app.database.models_table import get_model_by_id, model_belongs_to_user


def send_model_to_user(
    sender_id:          int,
    recipient_username: str,
    model_id:           int,
) -> tuple[bool, str]:
    """Share one of the sender's models directly with another user by username."""
    recipient = get_user_by_username(recipient_username.strip())
    if recipient is None:
        return False, f"User '{recipient_username}' not found"

    if recipient["id"] == sender_id:
        return False, "You cannot share a model with yourself"

    if not model_belongs_to_user(model_id, sender_id):
        return False, "Model not found in your library"

    create_share(sender_id, recipient["id"], model_id)
    return True, ""


def get_shared_with_me(user_id: int) -> list[dict]:
    """Return shares addressed to this user, enriched with sender info and model data."""
    shares = get_received_shares(user_id)
    result = []
    for s in shares:
        model  = get_model_by_id(s["model_id"])
        sender = get_user_by_id(s["sender_id"])
        if model and sender:
            result.append({
                **s,
                "sender_username": sender["username"],
                "model":           model,
            })
    return result


def remove_share(share_id: int):
    db_delete_share(share_id)
