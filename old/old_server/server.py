# old_server/old_server.py
# SteganoGAN API old_server.  Run this on the old_server machine:
#
#   python SteganoGAN2/old_server/old_server.py

import base64
import json
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).parent   # SteganoGAN2/old_server/
sys.path.insert(0, str(_ROOT))

from httpio.request  import HTTPRequest
from httpio.response import HTTPResponse
from httpio.endpoint import HTTPEndpoint
from httpio.server   import HTTPServer

from database.db import initialize

UPLOADS_DIR   = _ROOT / "data" / "uploads"
DOWNLOADS_DIR = _ROOT / "data"



def _ok(data: dict) -> HTTPResponse:
    body = json.dumps(data).encode()
    return HTTPResponse(
        status=200, message="OK",
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        body=body,
    )


def _err(message: str, status: int = 400) -> HTTPResponse:
    body = json.dumps({"error": message}).encode()
    return HTTPResponse(
        status=status, message="Error",
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
        body=body,
    )


def _parse(request: HTTPRequest) -> dict:
    return json.loads(request.body.decode())



def ep_auth_signup(request: HTTPRequest) -> HTTPResponse:
    body          = _parse(request)
    username      = body["username"]
    password_hash = body["password_hash"]
    pub_key       = body["pub_key"]

    from database.users_table import create_user, username_exists
    if username_exists(username):
        return _err("Username already taken")
    user_id = create_user(username, password_hash, pub_key)
    return _ok({"user_id": user_id})


def ep_auth_login(request: HTTPRequest) -> HTTPResponse:
    body     = _parse(request)
    username = body["username"]
    password = body["password"]

    from database.users_table import get_user_by_username
    from security.hashing    import verify_password

    user = get_user_by_username(username)
    if user is None or not verify_password(password, user["password"]):
        return _err("Wrong username or password", 401)

    return _ok({
        "user_id":  user["id"],
        "username": user["username"],
        "pub_key":  user.get("rsa_public_key") or "",
    })


def ep_auth_update_pubkey(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.users_table import update_public_key
    update_public_key(body["user_id"], body["pub_key"])
    return _ok({"ok": True})


def ep_auth_change_password(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.users_table import update_password
    update_password(body["user_id"], body["new_password_hash"])
    return _ok({"ok": True})


def ep_auth_delete_account(request: HTTPRequest) -> HTTPResponse:
    body    = _parse(request)
    user_id = body["user_id"]

    from database.db     import get_engine
    from database.schema import (
        MODELS_TABLE, MODEL_USER_ID,
        CREATIONS_TABLE, CREATION_USER_ID,
        ROOM_MEMBERS_TABLE, MEMBER_USER_ID,
    )
    from sql.query import Delete
    from database.users_table import delete_user

    engine = get_engine()
    engine.execute(Delete(MODELS_TABLE).where(MODEL_USER_ID       == user_id))
    engine.execute(Delete(CREATIONS_TABLE).where(CREATION_USER_ID == user_id))
    engine.execute(Delete(ROOM_MEMBERS_TABLE).where(MEMBER_USER_ID == user_id))
    engine.commit()
    engine.close()
    delete_user(user_id)
    return _ok({"ok": True})



def ep_file_upload(request: HTTPRequest) -> HTTPResponse:
    body     = _parse(request)
    filename = ""
    data     = base64.b64decode(body["data"])
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    ext = Path(filename).suffix or ".jpg"
    dst = UPLOADS_DIR / f"{uid}{ext}"
    dst.write_bytes(data)
    return _ok({"server_path": str(dst)})


def ep_file_download(request: HTTPRequest) -> HTTPResponse:
    body        = _parse(request)
    server_path = Path(body["server_path"])
    try:
        server_path.resolve().relative_to(DOWNLOADS_DIR.resolve())
    except ValueError:
        return _err("Access denied", 403)
    if not server_path.exists():
        return _err("File not found", 404)
    return _ok({"data": base64.b64encode(server_path.read_bytes()).decode()})



def ep_train(request: HTTPRequest) -> HTTPResponse:
    body        = _parse(request)
    user_id     = body["user_id"]
    name        = body["name"]
    description = body.get("description", "")
    image_path  = body["image_path"]

    from backend import jobs
    from backend.model_manager import train_model_async

    job_id = jobs.start(name, user_id)
    train_model_async(
        user_id=     user_id,
        name=        name,
        description= description,
        image_path=  image_path,
        on_progress= lambda step, pct: jobs.update(job_id, step, pct),
        on_done=     lambda mid: jobs.finish(job_id, mid),
        on_error=    lambda err: jobs.fail(job_id, err),
    )
    return _ok({"job_id": job_id})


def ep_train_status(request: HTTPRequest) -> HTTPResponse:
    body    = _parse(request)
    job_id  = body["job_id"]
    user_id = body["user_id"]

    from backend import jobs as _jobs
    state = _jobs.get_job(job_id)

    if state is None:
        return _err(f"Job '{job_id}' not found", 404)
    if state.get("user_id") != user_id:
        return _err("Access denied", 403)

    safe = {k: v for k, v in state.items() if k != "user_id"}
    return _ok(safe)


def ep_encode(request: HTTPRequest) -> HTTPResponse:
    body        = _parse(request)
    model_id    = body["model_id"]
    image_path  = body["image_path"]
    message     = body["message"]
    output_path = body.get("output_path") or ""

    if not output_path:
        from backend.model_manager import CREATIONS_DIR
        CREATIONS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(CREATIONS_DIR / f"{uuid.uuid4().hex}.png")

    from backend.model_manager import encode_with_model
    result = encode_with_model(model_id, image_path, message, output_path)
    return _ok({"output_path": result})


def ep_decode(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from backend.model_manager import decode_with_model
    message = decode_with_model(body["model_id"], body["image_path"])
    return _ok({"message": message})


def ep_models(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from backend.model_manager import get_user_models
    return _ok({"models": get_user_models(body["user_id"])})


def ep_model_delete(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from backend.model_manager import delete_model
    ok = delete_model(body["model_id"], body["user_id"])
    return _ok({"ok": ok})


def ep_jobs_active(request: HTTPRequest) -> HTTPResponse:
    from backend import jobs
    return _ok({"jobs": jobs.active()})



def ep_user_get(request: HTTPRequest) -> HTTPResponse:
    body     = _parse(request)
    user_id  = body.get("user_id")
    username = body.get("username")

    from database.users_table import get_user_by_id, get_user_by_username
    if user_id is not None:
        user = get_user_by_id(user_id)
    elif username:
        user = get_user_by_username(username)
    else:
        return _err("Provide user_id or username")

    if user is None:
        return _err("User not found", 404)

    return _ok({
        "id":       user["id"],
        "username": user["username"],
        "pub_key":  user.get("rsa_public_key") or "",
    })



def ep_room_create(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.rooms_table import create_room
    room_id, auth_key, seed = create_room(body["owner_id"], body["name"])
    return _ok({"room_id": room_id, "auth_key": auth_key, "seed": seed})


def ep_room_join(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.rooms_table import join_room
    ok, seed = join_room(body["room_id"], body["user_id"], body["auth_key"])
    return _ok({"ok": ok, "seed": seed})


def ep_room_list(request: HTTPRequest) -> HTTPResponse:
    body    = _parse(request)
    user_id = body["user_id"]
    from database.rooms_table import get_rooms_by_owner, get_rooms_by_member
    owned  = get_rooms_by_owner(user_id)
    joined = [r for r in get_rooms_by_member(user_id) if r["owner_id"] != user_id]
    return _ok({"owned": owned, "joined": joined})


def ep_room_get(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.rooms_table import get_room_by_id
    room = get_room_by_id(body["room_id"])
    if room is None:
        return _err("Room not found", 404)
    return _ok({"room": room})


def ep_room_model_add(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.room_models_table import add_model_to_room
    entry_id = add_model_to_room(body["room_id"], body["model_id"], body["user_id"])
    return _ok({"entry_id": entry_id})


def ep_room_model_remove(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.room_models_table import remove_model_from_room
    remove_model_from_room(body["entry_id"])
    return _ok({"ok": True})


def ep_room_models(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.room_models_table import get_room_models
    from database.models_table      import get_model_by_id
    result = []
    for entry in get_room_models(body["room_id"]):
        model = get_model_by_id(entry["model_id"])
        if model:
            result.append({**entry, "model": model})
    return _ok({"entries": result})


def ep_room_setting_get(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.room_models_table import get_room_setting
    return _ok({"allow_member_models": get_room_setting(body["room_id"])})


def ep_room_setting_set(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.room_models_table import set_room_setting
    set_room_setting(body["room_id"], body["allow"])
    return _ok({"ok": True})


def ep_room_message_send(request: HTTPRequest) -> HTTPResponse:
    """Only 'text' (OTP-encrypted by client) and 'image' (stego PNG) are allowed."""
    body = _parse(request)
    from database.rooms_table import send_to_room
    try:
        send_to_room(body["room_id"], body["sender_id"], body["type"], body["payload"])
    except ValueError as e:
        return _err(str(e))
    return _ok({"ok": True})


def ep_room_message_list(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.rooms_table import get_room_messages
    return _ok({"messages": get_room_messages(body["room_id"])})



def ep_share_send(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.users_table         import get_user_by_username
    from database.models_table        import model_belongs_to_user
    from database.direct_shares_table import create_share

    recipient = get_user_by_username(body["recipient_username"].strip())
    if recipient is None:
        return _err(f"User '{body['recipient_username']}' not found")
    if recipient["id"] == body["sender_id"]:
        return _err("You cannot share a model with yourself")
    if not model_belongs_to_user(body["model_id"], body["sender_id"]):
        return _err("Model not found in your library")

    create_share(body["sender_id"], recipient["id"], body["model_id"])
    return _ok({"ok": True})


def ep_share_list(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.direct_shares_table import get_received_shares
    from database.models_table        import get_model_by_id
    from database.users_table         import get_user_by_id

    result = []
    for s in get_received_shares(body["user_id"]):
        model  = get_model_by_id(s["model_id"])
        sender = get_user_by_id(s["sender_id"])
        if model and sender:
            result.append({**s, "sender_username": sender["username"], "model": model})
    return _ok({"shares": result})


def ep_share_delete(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.direct_shares_table import delete_share
    delete_share(body["share_id"])
    return _ok({"ok": True})



def ep_creation_add(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.creations_table import create_creation
    cid = create_creation(
        body["user_id"], body.get("model_id"),
        body["original_path"], body["stego_path"],
    )
    return _ok({"id": cid})


def ep_creation_list(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.creations_table import get_creations_by_user
    return _ok({"creations": get_creations_by_user(body["user_id"])})


def ep_creation_delete(request: HTTPRequest) -> HTTPResponse:
    body = _parse(request)
    from database.creations_table import delete_creation
    delete_creation(body["creation_id"])
    return _ok({"ok": True})



HOST = "0.0.0.0"
PORT = 8765

ENDPOINTS = [
    HTTPEndpoint("/auth/signup",            "POST", ep_auth_signup),
    HTTPEndpoint("/auth/login",             "POST", ep_auth_login),
    HTTPEndpoint("/auth/update_pubkey",     "POST", ep_auth_update_pubkey),
    HTTPEndpoint("/auth/change_password",   "POST", ep_auth_change_password),
    HTTPEndpoint("/auth/delete_account",    "POST", ep_auth_delete_account),
    HTTPEndpoint("/user/get",               "POST", ep_user_get),
    HTTPEndpoint("/file/upload",            "POST", ep_file_upload),
    HTTPEndpoint("/file/download",          "POST", ep_file_download),
    HTTPEndpoint("/model/train",            "POST", ep_train),
    HTTPEndpoint("/model/train/status",     "POST", ep_train_status),
    HTTPEndpoint("/model/encode",           "POST", ep_encode),
    HTTPEndpoint("/model/decode",           "POST", ep_decode),
    HTTPEndpoint("/model/list",             "POST", ep_models),
    HTTPEndpoint("/model/delete",           "POST", ep_model_delete),
    HTTPEndpoint("/jobs/active",            "POST", ep_jobs_active),
    HTTPEndpoint("/room/create",            "POST", ep_room_create),
    HTTPEndpoint("/room/join",              "POST", ep_room_join),
    HTTPEndpoint("/room/list",              "POST", ep_room_list),
    HTTPEndpoint("/room/get",               "POST", ep_room_get),
    HTTPEndpoint("/room/model/add",         "POST", ep_room_model_add),
    HTTPEndpoint("/room/model/remove",      "POST", ep_room_model_remove),
    HTTPEndpoint("/room/models",            "POST", ep_room_models),
    HTTPEndpoint("/room/setting/get",       "POST", ep_room_setting_get),
    HTTPEndpoint("/room/setting/set",       "POST", ep_room_setting_set),
    HTTPEndpoint("/room/message/send",      "POST", ep_room_message_send),
    HTTPEndpoint("/room/message/list",      "POST", ep_room_message_list),
    HTTPEndpoint("/share/send",             "POST", ep_share_send),
    HTTPEndpoint("/share/list",             "POST", ep_share_list),
    HTTPEndpoint("/share/delete",           "POST", ep_share_delete),
    HTTPEndpoint("/creation/add",           "POST", ep_creation_add),
    HTTPEndpoint("/creation/list",          "POST", ep_creation_list),
    HTTPEndpoint("/creation/delete",        "POST", ep_creation_delete),
]

HEADERS = {
    "Server":     "SteganoGAN/1.0",
    "Connection": "close",
}

if __name__ == "__main__":
    initialize()
    server = HTTPServer(ENDPOINTS, HEADERS)
    print(f"[old_server] Listening on {HOST}:{PORT}")
    server.serve_forever((HOST, PORT))
