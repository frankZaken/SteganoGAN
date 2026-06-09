# server_endpoints

import base64
import json
import hashlib
import secrets
import zlib
from pathlib import Path

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

MODELS_TABLE = Table(
    name="models",
    fields=(
        MODELS_MODEL_PATH,
        MODELS_CREATOR,
        MODELS_MODEL_NAME,
        MODELS_MODEL_DESCRIPTION,
        MODELS_ORIGINAL_IMAGE_PATH
    )
)

ROOMS_NAME = Field("name", str, primary=False, unique=False, nullable=False)
ROOMS_ADMIN = Field("admin", str, primary=False, unique=False, nullable=False)
ROOMS_MEMBERS = Field("members", str, primary=False, unique=False, nullable=False)
ROOMS_MODEL_NAMES = Field("model_names", str, primary=False, unique=False, nullable=False)

ROOMS_TABLE = Table(
    name="rooms",
    fields=(
        ROOMS_NAME,
        ROOMS_ADMIN,
        ROOMS_MEMBERS,
        ROOMS_MODEL_NAMES
    )
)

DB_PATH = "../db.sqlite3"
ENGINE = Engine(path=DB_PATH).open()

ENGINE.execute(Create(table=USERS_TABLE, exists_ok=True))
ENGINE.execute(Create(table=MODELS_TABLE, exists_ok=True))
ENGINE.execute(Create(table=ROOMS_TABLE, exists_ok=True))

# migration: add model_description column if it was created before this field existed
try:
    ENGINE.conn.execute("ALTER TABLE models ADD COLUMN model_description TEXT NOT NULL DEFAULT ''")
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



def compress(image: bytes) -> str:
    compressed = zlib.compress(image, level=9)

    if len(compressed) < len(image):
        payload = b"Z" + compressed
    else:
        payload = b"R" + image

    return base64.b64encode(payload).decode()


def decompress(data: str) -> bytes:
    payload = base64.b64decode(data)

    mode = payload[:1]
    content = payload[1:]

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

def get_model_names(request: HTTPRequest) -> HTTPResponse:
    """
    Returns the list of model names accessible by the user.

    request body:
        token: JWT token

    response body:
        model_names: list[str]
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")


    select_user_auth = (
        Select(table=MODELS_TABLE).where(MODELS_CREATOR == value(username))
    )

    model_names = []

    for row in ENGINE.execute(select_user_auth):
        model_names.append(
            row.get(MODELS_MODEL_NAME.name)
        )

    return HTTPResponse(
        body=json.dumps({"model_names": model_names}).encode(),
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
                ROOMS_MODEL_NAMES: json.dumps([])
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
        model_names: list[str] | None
        members: list[str] | None  # other user names.
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    room_name = request_body["name"]
    new_members: list[str] = request_body.get("members")

    for member in new_members:
        select_member = Select(
            table=USERS_TABLE,
            statement=USERS_USERNAME == value(member)
        )

        for _ in ENGINE.execute(select_member):
            break

        else:
            return HTTPResponse(status=404, message="member not found.")

    new_model_names = request_body.get("model_names")
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

    if new_model_names is not None:
        admin_models = set(json.loads(get_model_names(request).body))
        new_models = set(new_model_names)

        if not admin_models.issubset(new_models):
            return HTTPResponse(status=404, message="invalid models list.")

        updated_fields[ROOMS_MODEL_NAMES] = json.dumps(new_model_names)

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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE = Path(__file__).parent

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
    image_data = decompress(request_body["image_data"])

    existing = next(iter(
            ENGINE.execute(
                Select(table=MODELS_TABLE)
                .where((MODELS_CREATOR == value(username)) & (MODELS_MODEL_NAME == value(model_name)))
            )
        ), None
    )

    if existing:
        return HTTPResponse(status=404, message="model already exists.")

    original_images_dir = BASE / "original_images" / username
    original_images_dir.mkdir(parents=True, exist_ok=True)

    original_image_path = str(original_images_dir / f"{model_name}_original_image.jpg")
    Path(original_image_path).write_bytes(image_data)

    datasets_dir = BASE / "finetune_datasets" / username / model_name
    datasets_dir.mkdir(parents=True, exist_ok=True)

    prepare_dataset(
        image_path=original_image_path,
        output_dir=datasets_dir
    )

    finetuned_model_path = str(BASE / "finetuned_models" / username / f"{model_name}.pt")

    finetune(
        dataset_dir=str(datasets_dir),
        base_checkpoint = str(PROJECT_ROOT / "stegano" / "training" / "checkpoints" / "checkpoint_epoch_0050.pt"),
        target_image=str(original_image_path),
        output_path=finetuned_model_path
     )

    insert_model = Insert(
        table=MODELS_TABLE
    ).values(
        [
            {
                MODELS_MODEL_PATH: finetuned_model_path,
                MODELS_CREATOR: username,
                MODELS_MODEL_NAME: model_name,
                MODELS_MODEL_DESCRIPTION: model_description,
                MODELS_ORIGINAL_IMAGE_PATH: original_image_path
            }
        ]
    )

    ENGINE.execute(insert_model)
    ENGINE.commit()

    return HTTPResponse(status=200, message="OK")


def stego_encode(request: HTTPRequest) -> HTTPResponse:
    """
    Encodes a hidden message inside the original image of the model.

    request body:
        token: JWT token

        model_name: str
        model_creator: str
        message: str

    response body:
        stego_image: str  (bytes of png)
    """

    try:
        username = auth_token(request)

    except:
        return HTTPResponse(status=404, message="invalid token/token not found.")

    request_body = json.loads(request.body)

    model_name = request_body["model_name"]
    creator = request_body["model_creator"]
    message = request_body["message"]

    if creator != username:
        return HTTPResponse(status=404, message="creator must be the user.")

    select_model = (
        Select(table=MODELS_TABLE)
        .where((MODELS_CREATOR == value(creator)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    selected_model_data: dict[str, str] | None = next(iter(ENGINE.execute(select_model)), None)

    if selected_model_data is None:
        return HTTPResponse(status=404, message="model doesn't exist.")

    selected_model_data: dict[str, str]
    model_path = selected_model_data[MODELS_MODEL_PATH.name]
    original_image_path = selected_model_data[MODELS_ORIGINAL_IMAGE_PATH.name]

    stego_images_dir = BASE / "stego_images" / username
    stego_image_path = stego_images_dir / model_name / f"{model_name}_stego_image.png"
    stego_image_path.parent.mkdir(parents=True, exist_ok=True)

    encode(
        image_path=original_image_path,
        message=message,
        checkpoint_path=model_path,
        output_path=str(stego_image_path),
    )

    return HTTPResponse(
        body=json.dumps({"stego_image": compress(stego_image_path.read_bytes())}).encode(),
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

    image_data = decompress(request_body["stego_image"])
    model_name = request_body["model_name"]
    creator = request_body["model_creator"]

    if creator != username:
        return HTTPResponse(status=404, message="creator must be the user.")

    select_model = (
        Select(table=MODELS_TABLE)
        .where((MODELS_CREATOR == value(creator)) & (MODELS_MODEL_NAME == value(model_name)))
    )

    selected_model_data = next(iter(ENGINE.execute(select_model)), None)

    if selected_model_data is None:
        return HTTPResponse(status=404, message="model doesn't exist.")

    model_path = selected_model_data[MODELS_MODEL_PATH.name]

    stego_images_dir = BASE / "stego_images" / username
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

    new_model = {
        "model_path": "path",
        "creator": "peleg",
        "model_name": "the model",
        "original_image_path": "image"
    }

    model_exist: bool = False

    select_model = Select(
        table=MODELS_TABLE,
        statement=MODELS_CREATOR == value("peleg")
    )

    for _ in ENGINE.execute(select_model):
        model_exist = True
        break

    if not model_exist:
        insert_user = Insert(table=MODELS_TABLE).values(
            [
                {
                    MODELS_MODEL_PATH: new_model["model_path"],
                    MODELS_CREATOR: new_model["creator"],
                    MODELS_MODEL_NAME: new_model["model_name"],
                    MODELS_ORIGINAL_IMAGE_PATH: new_model["original_image_path"]
                }
            ]
        )

        ENGINE.execute(insert_user)
        ENGINE.commit()

    else:
        request = HTTPRequest(headers={"token": token})
        response = get_model_names(request)

        print(json.loads(response.body))


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
        "image_data": compress(image_data)
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

    stego_image = (BASE / "stego_images/peleg/test_model_stego_image.png").read_bytes()

    body = {
        "stego_image": compress(stego_image),
        "model_name": "test_model",
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
    # test_signin()
    # test_login()
    #
    # test_create_room()
    # test_update_room()
    #
    # test_get_model_names()
    #
    # test_train_model()
    test_stego_encode()
    test_stego_decode()

if __name__ == '__main__':
    main()
