# client/backend/auth.py
# Authentication â€” all account data lives on the old_server.
# RSA private key is stored locally (never sent to old_server).

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from security.hashing import hash_password
from security import (
    generate_keypair, save_private_key, load_private_key,
    serialize_public_key, deserialize_public_key,
)
from security.crypto import PrivateKey, PublicKey


def _client():
    from api.api_client    import APIClient
    from api.server_config import get_server
    return APIClient(get_server())


@dataclass
class Session:
    user_id:         int
    username:        str
    rsa_private_key: Optional[PrivateKey]
    rsa_public_key:  Optional[PublicKey]


def sign_up(username: str, password: str) -> tuple[bool, str]:
    username = username.strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(password) < 6:
        return False, "Password must be at least 6 characters"

    password_hash  = hash_password(password)
    private_key, public_key = generate_keypair()
    pub_serialized = serialize_public_key(public_key)

    try:
        client  = _client()
        user_id = client.signup(username, password_hash, pub_serialized)
    except RuntimeError as e:
        return False, str(e)

    save_private_key(user_id, private_key)
    return True, ""


def log_in(username: str, password: str) -> tuple[bool, Optional[Session]]:
    username = username.strip()
    try:
        result = _client().login(username, password)
    except RuntimeError:
        return False, None

    user_id = result["user_id"]
    pub_raw = result.get("pub_key", "")

    private_key = load_private_key(user_id)
    if private_key is None:
        private_key, public_key = generate_keypair()
        save_private_key(user_id, private_key)
        pub_serialized = serialize_public_key(public_key)
        try:
            _client().update_pubkey(user_id, pub_serialized)
            pub_raw = pub_serialized
        except Exception:
            pass

    public_key = deserialize_public_key(pub_raw) if pub_raw else None

    return True, Session(
        user_id=user_id,
        username=result["username"],
        rsa_private_key=private_key,
        rsa_public_key=public_key,
    )


def log_out(session: Session):
    session.rsa_private_key = None
    session.rsa_public_key  = None


def change_password(session: Session, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 6:
        return False, "Password must be at least 6 characters"
    try:
        _client().change_password(session.user_id, hash_password(new_password))
        return True, ""
    except RuntimeError as e:
        return False, str(e)


def delete_account(session: Session):
    try:
        _client().delete_account(session.user_id)
    except Exception:
        pass
    log_out(session)
