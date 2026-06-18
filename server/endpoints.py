# server_endpoints

import base64
import json
import hashlib
import secrets
import zlib
from pathlib import Path
import threading

from httpio import HTTPRequest, HTTPResponse

from datetime import datetime, timedelta, timezone
import jwt

from sql.engine import Engine
from sql.components import Field, value
from sql.query import Select, Insert, Create, Update
from sql.table import Table
from stegano.pipeline.decoder import decode
from stegano.pipeline.encoder import encode
from stegano.pipeline.prepare_dataset import prepare_dataset
from stegano.training.finetuner import finetune

"""

DB
________________

    USERS table:
        username: str  (PK)
        email: str
        salt: str
        digest: str
        
    MODELS table:
        creator: str  (USER.username)
        model_name: str
        model_description: str
        model_path: str
        original_image_path: str
    
    ROOMS table:
        name: str
        admin: str  (USERS.username)
        members: json[list[str]]  (list[USERS.username])
        model_names: json[list[str]]  (list[MODELS.model_name])
    

files
_________________

    MODELS directory:
        <model_path>.pt  <-->  DB.MODELS.model_path
        ...
    
    ORIGINAL_IMAGES directory:
        <original_image_path>.png  <-->  DB.MODELS.original_image_path
        
"""


USERS_USERNAME = Field("username", str, primary=True, unique=True,  nullable=False)
USERS_EMAIL = Field("email", str, primary=False, unique=False, nullable=False)
USERS_SALT = Field("salt", str, primary=False, unique=False, nullable=False)
USERS_DIGEST = Field("digest", str, primary=False, unique=False, nullable=False)

USERS_TABLE = Table(
    name="users",
    fields=(
        USERS_USERNAME,
        USERS_EMAIL,
        USERS_SALT,
        USERS_DIGEST
    )
)

MODELS_MODEL_PATH = Field("model_path", str, primary=True, unique=True,  nullable=False)
MODELS_CREATOR = Field("creator", str, primary=False, unique=False, nullable=False)
MODELS_MODEL_NAME = Field("model_name", str, primary=False, unique=False, nullable=False)
MODELS_MODEL_DESCRIPTION = Field("model_description", str, primary=False, unique=False, nullable=False)
MODELS_ORIGINAL_IMAGE_PATH = Field("original_image_path", str, primary=False, unique=False, nullable=False)
MODELS_MODEL_STATUS = Field("model_status", str, primary=False, unique=False, nullable=False)

MODELS_TABLE = Table(
    name="models",
    fields=(
        MODELS_MODEL_PATH,
        MODELS_CREATOR,
        MODELS_MODEL_NAME,
        MODELS_MODEL_DESCRIPTION,
        MODELS_ORIGINAL_IMAGE_PATH,
        MODELS_MODEL_STATUS
    )
)

ROOMS_NAME = Field("name", str, primary=False, unique=False, nullable=False)
ROOMS_ADMIN = Field("admin", str, primary=False, unique=False, nullable=False)
ROOMS_MEMBERS = Field("members", str, primary=False, unique=False, nullable=False)
ROOMS_MODELS = Field("model_names", str, primary=False, unique=False, nullable=False)

ROOMS_TABLE = Table(
    name="rooms",
    fields=(
        ROOMS_NAME,
        ROOMS_ADMIN,
        ROOMS_MEMBERS,
        ROOMS_MODELS
    )
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_DATA_ROOT = PROJECT_ROOT / "data"
DB_PATH = SERVER_DATA_ROOT / "db.sqlite3"

SERVER_DATA_ROOT.mkdir(parents=True, exist_ok=True)

ENGINE = Engine(path=str(DB_PATH)).open()

ENGINE.execute(Create(table=USERS_TABLE, exists_ok=True))
ENGINE.execute(Create(table=MODELS_TABLE, exists_ok=True))
ENGINE.execute(Create(table=ROOMS_TABLE, exists_ok=True))

# migration: add model_description column if it was created before this field existed
try:
    ENGINE.conn.execute("ALTER TABLE models ADD COLUMN model_description TEXT NOT NULL DEFAULT ''")
    ENGINE.commit()
except Exception:
    pass  # column already exists

try:
    ENGINE.conn.execute("ALTER TABLE models ADD COLUMN model_status TEXT NOT NULL DEFAULT '0'")
    ENGINE.commit()
except Exception:
    pass  # column already exists


PEPPER = b'B\x88\x0e\x8f]\x11\x8d\x07^\t\x8f\x05E\x86x\xfc'


def password_digest(password: str, salt: bytes, pepper: bytes) -> str:
    return hashlib.sha256(password.encode() + salt + pepper).digest().hex()


ALGORITHM = "HS256"
SECRET_KEY = b'\x1d\x8e\xf1\xa5\xf4\x9c\xc5\x1d\x08\xfa\xbd\xf0\x89\x03\xa2\x8cM\xbaB\xef\xae\x11M+\xca\x8b\x99\xa6\xa1\x97\xdf\xa1Y\x82X\x14\xd4\xf6\xe1\x84\t\x1c\xd4\xea\xfd\xcc\x86C5\xd9\xcb\xa0\xc5\x00\xeaU\xe5\xe4{\xe9\x83;#\xed'


def generate_token(username: str):
    payload = {
        "user_id": username,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=15)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def token_to_username(token: str) -> str:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["user_id"]


def auth_token(request: HTTPRequest) -> str:

    request_headers = request.headers
    if "token" not in request_headers:
        raise KeyError("token not found.")

    token = request_headers["token"]

    return token_to_username(token)


def compress(image: bytes) -> bytes:
    compressed = zlib.compress(image, level=9)

    if len(compressed) < len(image):
        payload = b"Z" + compressed

    else:
        payload = b"R" + image

    return payload


def decompress(data: bytes) -> bytes:

    mode = data[:1]
    content = data[1:]

    if mode == b"Z":
        return zlib.decompress(content)

    if mode == b"R":
        return content

    raise ValueError("Invalid compressed data")


def login(request: HTTPRequest) -> HTTPResponse:
    """
    Verifies the user credentials with the users database.

    request body:
        username: str
        password: str

    response body:
        token: JWT token
    """

    request_body = json.loads(request.body)
    username = request_body["username"]
    password = request_body["password"]

    select_username = Select(
        table=USERS_TABLE,
        statement=USERS_USERNAME == value(username)
    )

    for _ in ENGINE.execute(select_username):
        select_user_auth = (
            Select(table=USERS_TABLE, fields=(USERS_DIGEST, USERS_SALT))
            .where(USERS_USERNAME == value(username))
        )

        selected_user_data = next(iter(ENGINE.execute(select_user_auth)))

        selected_digest = selected_user_data.get(USERS_DIGEST.name)
        salt = selected_user_data.get(USERS_SALT.name)

        if secrets.compare_digest(selected_digest, password_digest(password, salt=salt, pepper=PEPPER)):

            token = generate_token(username)
            headers = {"token": token}

            return HTTPResponse(status=200, headers=headers, message="OK")
        break

    return HTTPResponse(status=404, message="wrong password")


def signup(request: HTTPRequest) -> HTTPResponse:
    """
    Verifies the user is new and saved it in the database.


    request body:
        username: str
        email: str
        password: str

    response body:
        token: JWT token
    """

    request_body = json.loads(request.body)
    username = request_body["username"]
    password = request_body["password"]
    email = request_body["email"]

    select_username = Select(
        table=USERS_TABLE,
        statement=USERS_USERNAME == value(username)
    )

    for _ in ENGINE.execute(select_username):
        return HTTPResponse(status=404, message='username taken')

    salt = secrets.token_bytes(16)
    digest = password_digest(password, salt=salt, pepper=PEPPER)

    insert_user = Insert(table=USERS_TABLE).values(
        [
            {
                USERS_USERNAME: username,
                USERS_EMAIL: email,
                USERS_SALT: salt,
                USERS_DIGEST: digest
            }
        ]
    )

    ENGINE.execute(insert_user)
    ENGINE.commit()

    return HTTPResponse(status=200, message="OK")

def get_models_info(request: HTTPRequest) -> HTTPResponse:
    """
    Returns the dict of models info accessible by the user.

    request body:
        token: JWT token

    response body:
        models_info: list[str]
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")


    select_user_auth = (
        Select(table=MODELS_TABLE).where(MODELS_CREATOR == value(username))
    )

    models: dict[str, list[str]] = {}

    for row in ENGINE.execute(select_user_auth):
        models[row.get(MODELS_MODEL_NAME.name)] = [
            row.get(MODELS_MODEL_DESCRIPTION.name),
            row.get(MODELS_CREATOR.name)
        ]

    return HTTPResponse(
        body=json.dumps({"models_info": models}).encode(),
        status=200,
        message="OK"
    )


def create_room(request: HTTPRequest) -> HTTPResponse:
    """
    Creates a row of a room in the rooms table of the database.

    request body:
        token: JWT token

        name: str
        members: list[str]  # other user names.
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    room_name = request_body["name"]
    members = request_body["members"]

    room_exists = False

    select_room = Select(
        table=ROOMS_TABLE,
        statement=ROOMS_NAME == value(room_name)
    )

    for _ in ENGINE.execute(select_room):
        room_exists = True
        break

    if room_exists:
        return HTTPResponse(
            status=404,
            message="room already exists"
        )

    room_members = list(set([username] + members))

    insert_room = Insert(
        table=ROOMS_TABLE
    ).values(
        [
            {
                ROOMS_NAME: room_name,
                ROOMS_ADMIN: username,
                ROOMS_MEMBERS: json.dumps(room_members),
                ROOMS_MODELS: json.dumps({})
            }
        ]
    )

    ENGINE.execute(insert_room)
    ENGINE.commit()

    return HTTPResponse(
        status=200,
        message="OK"
    )


def update_room(request: HTTPRequest) -> HTTPResponse:
    """
    Changes the list of members in the room.

    request body:
        token: JWT token

        name: str
        models_info: dict[str, (str, str)] | None
        members: list[str] | None  # other usernames.
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    room_name = request_body["name"]
    new_members: list[str] = request_body.get("members")

    if new_members is not None:
        for member in new_members:
            select_member = Select(
                table=USERS_TABLE,
                statement=USERS_USERNAME == value(member)
            )

            for _ in ENGINE.execute(select_member):
                break

            else:
                return HTTPResponse(status=404, message="member not found.")

    new_models: dict[str, tuple[str, str]] = request_body.get("models_info")
    admin_rooms_statement = (ROOMS_NAME == value(room_name)) & (ROOMS_ADMIN == value(username))

    select_room = (
        Select(table=ROOMS_TABLE)
        .where(admin_rooms_statement)
    )

    room_data = None

    for row in ENGINE.execute(select_room):
        room_data = row
        break

    if room_data is None:
        return HTTPResponse(status=404, message="room not found.")

    updated_fields = {}

    if new_members is not None:
        updated_fields[ROOMS_MEMBERS] = json.dumps(new_members)

    if new_models is not None:
        admin_models_info: dict = json.loads(get_models_info(request).body)["models_info"]

        if not set(new_models).issubset(admin_models_info.keys()):
            return HTTPResponse(status=404, message="invalid models list.")

        models_dict = {name: admin_models_info[name] for name in new_models}
        updated_fields[ROOMS_MODELS] = json.dumps(models_dict)

    if not updated_fields:
        return HTTPResponse(status=400, message="nothing to update")

    update_query = (
        Update(table=ROOMS_TABLE)
        .set(updated_fields)
        .where(admin_rooms_statement)
    )

    ENGINE.execute(update_query)
    ENGINE.commit()

    return HTTPResponse(status=200, message="OK")


def get_rooms(request: HTTPRequest) -> HTTPResponse:
    """
    Returns all rooms the authenticated user is a member of.

    request headers:
        token: JWT token

    response body:
        rooms: list of {name, admin, members, models}
    """
    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    all_rooms = ENGINE.execute(Select(table=ROOMS_TABLE))
    user_rooms = [
        {
            "name": row[ROOMS_NAME.name],
            "admin": row[ROOMS_ADMIN.name],
            "members": json.loads(row[ROOMS_MEMBERS.name]),
            "models": json.loads(row[ROOMS_MODELS.name]),
        }

        for row in all_rooms
        if username in json.loads(row[ROOMS_MEMBERS.name])
    ]

    return HTTPResponse(
        body=json.dumps({"rooms": user_rooms}).encode(),
        status=200,
        message="OK"
    )


def get_room_models(request: HTTPRequest) -> HTTPResponse:
    """
    Returns the models of a room the authenticated user is a member of.

    request headers:
        token: JWT token

    request body:
        room_name: str

    response body:
        models: dict[model_name, [description, creator]]
    """
    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)
    room_name = request_body["room_name"]
    admin = request_body["admin"]

    room_row = next(iter(ENGINE.execute(
        Select(table=ROOMS_TABLE)
        .where((ROOMS_NAME == value(room_name)) & (ROOMS_ADMIN == value(admin)))
    )), None)

    if room_row is None:
        return HTTPResponse(status=404, message="room not found.")

    if username not in json.loads(room_row[ROOMS_MEMBERS.name]):
        return HTTPResponse(status=404, message="room not found.")

    models: dict = json.loads(room_row[ROOMS_MODELS.name])

    return HTTPResponse(
        body=json.dumps({"models_info": models}).encode(),
        status=200,
        message="OK"
    )


def _finetune_endpoint(
    username: str,
    model_name: str,
    dataset_dir: str,
    output_path: str,
    target_image: str,
):
    yield from finetune(
        dataset_dir=dataset_dir,
        base_checkpoint=str(PROJECT_ROOT / "stegano" / "training" / "checkpoints" / "checkpoint_epoch_0010.pt"),
        target_image=target_image,
        output_path=output_path
    )

    update_model = (
        Update(table=MODELS_TABLE)
        .set({MODELS_MODEL_PATH: output_path})
        .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    ENGINE.execute(update_model)
    ENGINE.commit()


class StatusTracker:
    def __init__(self):
        self.status: int | None = None

status_tracker = StatusTracker()

def run_and_track(generator, tracker_obj, username: str, model_name: str):

    try:
        for s in generator:
            tracker_obj.status = s

            update_status = (
                Update(table=MODELS_TABLE)
                .set({MODELS_MODEL_STATUS: tracker_obj.status})
                .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name)))
            )

            ENGINE.execute(update_status)
            ENGINE.commit()

            print(f"[TRACKER] Live Status Updated: {tracker_obj.status}")

        update_status = (
            Update(table=MODELS_TABLE)
            .set({MODELS_MODEL_STATUS: 100})
            .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name))
            )
        )

        ENGINE.execute(update_status)
        ENGINE.commit()

    except Exception:
        import traceback
        print(f"[TRACKER] training thread crashed for {username}/{model_name}:")
        traceback.print_exc()


def train_model(request: HTTPRequest) -> HTTPResponse:
    """
    Gets a base image from the user and trains a model on it.

    request body:
        token: JWT token

        model_name: str
        model_description: str
        image_data: bytes
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    model_name = request_body["model_name"]
    model_description = request_body["model_description"]
    image_data = decompress(base64.b64decode(request_body["image_data"].encode()))

    existing = next(iter(
            ENGINE.execute(
                Select(table=MODELS_TABLE)
                .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name)))
            )
        ), None
    )

    if existing:
        return HTTPResponse(status=404, message="model already exists.")

    original_images_dir = SERVER_DATA_ROOT / "original_images" / username
    original_images_dir.mkdir(parents=True, exist_ok=True)

    original_image_path = str(original_images_dir / f"{model_name}_original_image.jpg")
    Path(original_image_path).write_bytes(image_data)

    datasets_dir = SERVER_DATA_ROOT / "finetune_datasets" / username / model_name
    datasets_dir.mkdir(parents=True, exist_ok=True)

    prepare_dataset(
        image_path=original_image_path,
        output_dir=datasets_dir,
        num_images=50,
        num_real_crops=100
    )

    finetuned_model_path = str(SERVER_DATA_ROOT / "finetuned_models" / username / f"{model_name}.pt")

    insert_model = Insert(
        table=MODELS_TABLE
    ).values(
        [
            {
                MODELS_MODEL_PATH: finetuned_model_path,
                MODELS_CREATOR: username,
                MODELS_MODEL_NAME: model_name,
                MODELS_MODEL_DESCRIPTION: model_description,
                MODELS_ORIGINAL_IMAGE_PATH: str(original_image_path),
                MODELS_MODEL_STATUS: 0
            }
        ]
    )

    ENGINE.execute(insert_model)
    ENGINE.commit()

    generator_instance = _finetune_endpoint(
        username=username,
        model_name=model_name,
        dataset_dir=str(datasets_dir),
        target_image=str(original_image_path),
        output_path=finetuned_model_path,
    )

    threading.Thread(
        target=run_and_track,
        args=(generator_instance, status_tracker, username, model_name),
        daemon=True
    ).start()

    return HTTPResponse(status=200, message="OK")


def model_exists(request: HTTPRequest) -> HTTPResponse:
    """
    Returns a boolean flag for the existence of the model, as a model created by the user.

    request body:
        token: JWT token
        model_name: str

    response body:
        status: bool

    :return:
    """


def get_model_status(request: HTTPRequest) -> HTTPResponse:
    """
    Returns the training progress (0-100) of a model owned by the authenticated user.

    request body:
        token: JWT token  (in headers)
        model_name: str

    response body:
        status: int  (0-100)
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)
    model_name = request_body["model_name"]

    select_model = (
        Select(table=MODELS_TABLE)
        .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    selected_model_data = next(iter(ENGINE.execute(select_model)), None)

    if selected_model_data is None:
        return HTTPResponse(status=404, message="model doesn't exist.")

    status = selected_model_data[MODELS_MODEL_STATUS.name]

    return HTTPResponse(body=json.dumps({"status": status}).encode(), status=200, message="OK")


def model_training_done(request: HTTPRequest) -> HTTPResponse:
    """
    Returns whether the model has finished training.

    request body:
        model_name: str  (in body)

    request headers:
        token: JWT token

    response body:
        status: bool
    """

    try:
        username = auth_token(request)
    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)
    model_name = request_body["model_name"]

    select_model = (
        Select(table=MODELS_TABLE)
        .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    selected_model_data = next(iter(ENGINE.execute(select_model)), None)

    if selected_model_data is None:
        return HTTPResponse(status=404, message="model doesn't exist.")

    done = int(selected_model_data[MODELS_MODEL_STATUS.name]) == 100

    return HTTPResponse(body=json.dumps({"status": done}).encode(), status=200, message="OK")


def stego_encode(request: HTTPRequest) -> HTTPResponse:
    """
    Encodes a hidden message inside the provided image using the selected model.

    request body:
        token: JWT token

        image_data: str  (base64 of compressed image bytes)
        model_name: str
        model_creator: str
        room_name: str
        message: str

    response body:
        stego_image: str  (base64 of compressed png bytes)
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    image_data = decompress(base64.b64decode(request_body["image_data"].encode()))
    model_name = request_body["model_name"]
    creator = request_body["model_creator"]
    room_name = request_body["room_name"]
    message = request_body["message"]


    if room_name is not None:
        find_model_in_room = (
            Select(table=ROOMS_TABLE)
            .where((ROOMS_NAME == value(room_name)) & (ROOMS_ADMIN == value(creator)))
        )

        found_room: dict[str, str] | None = next(iter(ENGINE.execute(find_model_in_room)), None)

        if found_room is None:
            return HTTPResponse(status=404, message="room doesn't exist.")

        for current_model_name in json.loads(found_room[ROOMS_MODELS.name]):
            if current_model_name == model_name:
                break

        else:
            return HTTPResponse(status=404, message="model was not found in this room.")

    elif creator != username:
        return HTTPResponse(status=404, message="creator must be the user.")

    select_model = (
        Select(table=MODELS_TABLE)
        .where((MODELS_CREATOR == value(creator)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    selected_model_data: dict[str, str] | None = next(iter(ENGINE.execute(select_model)), None)

    if selected_model_data is None:
        return HTTPResponse(status=404, message="model doesn't exist.")

    model_path = selected_model_data[MODELS_MODEL_PATH.name]

    stego_images_dir = SERVER_DATA_ROOT / "stego_images" / username / model_name
    stego_images_dir.mkdir(parents=True, exist_ok=True)

    cover_image_path = stego_images_dir / f"{model_name}_cover_image.png"
    cover_image_path.write_bytes(image_data)

    stego_image_path = stego_images_dir / f"{model_name}_stego_image.png"

    encode(
        image_path=str(cover_image_path),
        message=message,
        checkpoint_path=model_path,
        output_path=str(stego_image_path),
    )

    return HTTPResponse(
        body=json.dumps(
            {
                "stego_image": base64.b64encode(compress(stego_image_path.read_bytes())).decode()
            }
        ).encode(),
        status=200,
        message="OK"
    )


def stego_decode(request: HTTPRequest) -> HTTPResponse:
    """
    Decodes a given stego image using the selected model, and returns the recovered message.

    request body:
        token: JWT token

        stego_image: str  (bytes of png)
        model_name: str
        model_creator: str

    response body:
        message: str
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    image_data = decompress(base64.b64decode(request_body["stego_image"].encode()))
    model_name = request_body["model_name"]
    room_name = request_body["room_name"]
    creator = request_body["model_creator"]

    if room_name is not None:
        find_model_in_room = (
            Select(table=ROOMS_TABLE)
            .where((ROOMS_NAME == value(room_name)) & (ROOMS_ADMIN == value(creator)))
        )

        found_room: dict[str, str] | None = next(iter(ENGINE.execute(find_model_in_room)), None)

        if found_room is None:
            return HTTPResponse(status=404, message="room doesn't exist.")

        for current_model_name in json.loads(found_room[ROOMS_MODELS.name]):
            if current_model_name == model_name:
                break

        else:
            return HTTPResponse(status=404, message="model was not found in this room.")

    elif creator != username:
        return HTTPResponse(status=404, message="creator must be the user.")

    select_model = (
        Select(table=MODELS_TABLE)
        .where((MODELS_CREATOR == value(creator)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    selected_model_data: dict[str, str] | None = next(iter(ENGINE.execute(select_model)), None)

    if selected_model_data is None:
        return HTTPResponse(status=404, message="model doesn't exist.")

    model_path = selected_model_data[MODELS_MODEL_PATH.name]

    stego_images_dir = SERVER_DATA_ROOT / "stego_images" / username
    stego_image_path = stego_images_dir / model_name / f"{model_name}_stego_image.png"
    stego_image_path.parent.mkdir(parents=True, exist_ok=True)

    stego_image_path.write_bytes(image_data)

    message = decode(
        image_path=str(stego_image_path),
        checkpoint_path=model_path
    )

    return HTTPResponse(
        body=json.dumps({"message": message}).encode(),
        status=200,
        message="OK"
    )


def test_signin():
    print("signin")

    body = {"username": "peleg", "password": "123", "email": "pelegfrs@gmail.com"}
    request = HTTPRequest(body=json.dumps(body).encode())

    response = signup(request)
    print(response)


def test_login():
    print("\nlogin")

    body = {"username": "peleg", "password": "123"}
    request = HTTPRequest(body=json.dumps(body).encode())

    response = login(request)
    print(response)


def test_get_model_names():
    print("\nget_model_names")

    body = {"username": "peleg", "password": "123"}
    login_request = HTTPRequest(body=json.dumps(body).encode())

    login_response = login(login_request)
    token = login_response.headers["token"]

    # TODO: build the correct request
    # get_model_names()

def test_create_room():
    print("\ncreate room")

    body = {"username": "peleg", "password": "123"}
    login_request = HTTPRequest(body=json.dumps(body).encode())

    login_response = login(login_request)
    token = login_response.headers["token"]

    body = {
        "name": "friends",
        "members": ["alice", "bob"]
    }

    request = HTTPRequest(body=json.dumps(body).encode(), headers={"token": token})
    response = create_room(request)

    print(response)


def test_update_room():
    print("\nupdate room")

    body = {"username": "peleg", "password": "123"}
    login_request = HTTPRequest(body=json.dumps(body).encode())

    login_response = login(login_request)
    token = login_response.headers["token"]

    body = {
        "name": "friends",
        "members": [
            "shepeg"
        ],
        "model_names": [
            "the model"
        ]
    }

    request = HTTPRequest(
        body=json.dumps(body).encode(),
        headers={"token": token}
    )

    response = update_room(request)

    print(response)

def test_train_model():
    print("\ntrain_model")

    body = {
        "username": "peleg",
        "password": "123"
    }

    login_request = HTTPRequest(
        body=json.dumps(body).encode()
    )

    login_response = login(login_request)
    token = login_response.headers["token"]

    image_path = PROJECT_ROOT / "original.png"

    if not image_path.exists():
        print(f"CRITICAL: Could not find '{image_path}'. Please place it in the project root.")
        return

    image_data = image_path.read_bytes()

    body = {
        "model_name": "test_model",
        "model_description": "test description",
        "image_data": base64.b64encode(compress(image_data)).decode(),
    }

    request = HTTPRequest(
        body=json.dumps(body).encode(),
        headers={"token": token}
    )

    response = train_model(request)

    print(response)

def test_stego_encode():
    print("\nstego_encode")

    body = {
        "username": "peleg",
        "password": "123"
    }

    login_request = HTTPRequest(
        body=json.dumps(body).encode()
    )

    login_response = login(login_request)

    token = login_response.headers["token"]

    body = {
        "model_name": "test_model",
        "model_creator": "peleg",
        "message": "אופק גבר רצח דודל לא!!!"
    }

    request = HTTPRequest(
        body=json.dumps(body).encode(),
        headers={"token": token}
    )

    response = stego_encode(request)

    print(response)

def test_stego_decode():
    print("\nstego_decode")

    body = {
        "username": "peleg",
        "password": "123"
    }

    login_request = HTTPRequest(
        body=json.dumps(body).encode()
    )

    login_response = login(login_request)

    token = login_response.headers["token"]

    model_name = "test_model"

    stego_image = (SERVER_DATA_ROOT / f"stego_images/peleg/{model_name}/{model_name}_stego_image.png").read_bytes()

    body = {
        "stego_image": base64.b64encode(compress(stego_image)).decode(),
        "model_name": model_name,
        "model_creator": "peleg"
    }

    request = HTTPRequest(
        body=json.dumps(body).encode(),
        headers={"token": token}
    )

    response = stego_decode(request)

    print(response)

    if response.body:
        print(response.body.decode())


def main():
    test_signin()
    test_login()

    test_create_room()
    test_update_room()

    test_get_model_names()

    test_train_model()
    test_stego_encode()
    test_stego_decode()

if __name__ == '__main__':
    main()
