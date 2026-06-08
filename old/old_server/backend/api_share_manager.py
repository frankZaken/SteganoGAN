# client/backend/api_share_manager.py

from api import _client


def send_model_to_user(sender_id: int, recipient_username: str,
                       model_id: int) -> tuple[bool, str]:
    return _client().share_send(sender_id, recipient_username, model_id)


def get_shared_with_me(user_id: int) -> list[dict]:
    return _client().share_list(user_id)


def remove_share(share_id: int) -> None:
    _client().share_delete(share_id)
