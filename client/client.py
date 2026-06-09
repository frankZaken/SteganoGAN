# client/client.py

import base64
import json
import zlib
from pathlib import Path

from httpio import HTTPClient, HTTPRequest


def _compress(image: bytes) -> str:
    compressed = zlib.compress(image, level=9)

    if len(compressed) < len(image):
        payload = b"Z" + compressed
    else:
        payload = b"R" + image

    return base64.b64encode(payload).decode()


def _decompress(data: str) -> bytes:
    payload = base64.b64decode(data)

    mode = payload[:1]
    content = payload[1:]

    if mode == b"Z":
        return zlib.decompress(content)

    if mode == b"R":
        return content

    raise ValueError("Invalid compressed data")


class SteganoClient:

    def __init__(self, server_address: tuple[str, int]):
        self.server_address = server_address
        self.http_client    = HTTPClient(server_address)
        self.token:    str | None = None
        self.username: str | None = None


    def _check_token(self):
        if self.token is None:
            raise RuntimeError("must login first.")


    def signup(self, username: str, email: str, password: str):

        body = {
            "username": username,
            "email": email,
            "password": password
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST",
                uri="/signup",
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"signup failed: {response.message}")


    def login(self, username: str, password: str):

        body = {
            "username": username,
            "password": password
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST",
                uri="/login",
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"login failed: {response.message}")

        self.token = response.headers["token"]
        self.username = username


    def get_model_names(self) -> list[str]:
        self._check_token()

        response = self.http_client.open(
            HTTPRequest(
                method="POST",
                uri="/models",
                headers={"token": self.token}
            )
        )

        if response.status != 200:
            raise RuntimeError(f"get model names failed: {response.message}")

        return json.loads(response.body)["model_names"]


    def create_room(self, name: str, members: list[str]):
        self._check_token()

        body = {
            "name": name,
            "members": members
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST", uri="/room/create",
                headers={"token": self.token},
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"room creation failed: {response.message}")


    def update_room(self, name: str, model_names: list[str] | None, members: list[str] | None):
        self._check_token()

        body = {
            "name": name,
            "model_names": model_names,
            "members": members
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST",
                uri="/room/update",
                headers={"token": self.token},
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"room update failed: {response.message}")


    def train_model(self, model_name: str, model_description: str, image_data: bytes):
        self._check_token()

        body = {
            "model_name":  model_name,
            "model_description": model_description,
            "image_data": _compress(image_data),
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST", uri="/model/train",
                headers={"token": self.token},
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"model training failed: {response.message}")


    def stego_encode(self, model_name: str, model_creator: str, message: str) -> bytes:
        self._check_token()

        body = {
            "model_name": model_name,
            "model_creator": model_creator,
            "message": message
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST", uri="/model/encode",
                headers={"token": self.token},
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"encode failed: {response.message}")

        return _decompress(json.loads(response.body)["stego_image"])


    def stego_decode(self, stego_image: str, model_name: str, model_creator: str) -> str:
        self._check_token()

        body = {
            "stego_image": stego_image,
            "model_name": model_name,
            "model_creator": model_creator
        }

        response = self.http_client.open(
            HTTPRequest(
                method="POST",
                uri="/model/decode",
                headers={"token": self.token},
                body=json.dumps(body).encode()
            )
        )

        if response.status != 200:
            raise RuntimeError(f"decode failed: {response.message}")

        return json.loads(response.body)["message"]



def _prompt(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    answer = input(f"  {label}{hint}: ").strip()

    return answer if answer else default


def _header(logged_in_as: str = ""):
    suffix = f"  |  logged in as: {logged_in_as}" if logged_in_as else ""
    print(f"\n=== StegoGAN ==={suffix}\n")


def _menu(options: list[str]) -> int:

    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")

    while True:
        raw = input("\n  Choice: ").strip()

        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)

        print(f"  Enter a number between 1 and {len(options)}.")


PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main():
    addr_raw = input("Server address [127.0.0.1:8080]: ").strip() or "127.0.0.1:8080"
    ip, port = addr_raw.rsplit(":", 1) if ":" in addr_raw else (addr_raw, "8080")
    client = SteganoClient((ip, int(port)))

    state: str | None = None
    stego_buffer = None   # last encoded stego image (for quick decode)

    while True:

        if state is None:
            _header()
            choice = _menu(
                [
                    "Sign up",
                    "Log in"
                ]
            )

            if choice == 1:
                print()
                username = _prompt("username")
                password = _prompt("password")
                email = _prompt("email")

                try:
                    client.signup(username, email, password)
                    print("  [✓] account created — you can now log in")
                    state = "login"

                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 2:
                print()
                username = _prompt("username")
                password = _prompt("password")

                try:
                    client.login(username, password)
                    print(f"  [✓] logged in as {client.username}")
                    state = "menu"

                except RuntimeError as e:
                    print(f"  [✗] {e}")

        elif state == "login":
            _header()
            choice = _menu(["Log in"])

            if choice == 1:
                print()
                username = _prompt("username")
                password = _prompt("password")

                try:
                    client.login(username, password)
                    print(f"  [✓] logged in as {client.username}")
                    state = "menu"

                except RuntimeError as e:
                    print(f"  [✗] {e}")

        elif state == "menu":
            _header(client.username)
            choice = _menu(
                [
                    "List my models",
                    "Train a new model",
                    "Create a room",
                    "Update a room",
                    "Encode a message",
                    "Decode a message",
                    "Log out",
                    "Sign up another account",
                ]
            )

            if choice == 1:
                try:
                    names = client.get_model_names()
                    if names:
                        print("\n  Your models:")
                        for n in names:
                            print(f"    - {n}")
                    else:
                        print("\n  No models yet.")
                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 2:
                print()
                model_name = _prompt("model name")
                desc = _prompt("description")
                img_path = _prompt("path to cover image", PROJECT_ROOT / "original.png")

                try:
                    with open(img_path, "rb") as f:
                        image_data = f.read()

                    print("  [→] training — this takes several minutes...")
                    client.train_model(model_name, desc, image_data)

                    print("  [✓] training complete")

                except FileNotFoundError:
                    print(f"  [✗] file not found: {img_path}")

                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 3:
                print()

                room_name = _prompt("room name")
                members_raw = _prompt("members (comma-separated, blank for none)", "")
                members = [m.strip() for m in members_raw.split(",") if m.strip()]

                try:
                    client.create_room(room_name, members)
                    print(f"  [✓] room '{room_name}' created")

                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 4:
                print()

                room_name = _prompt("room name")
                models_raw = _prompt("models to assign (comma-separated, blank to skip)", "")
                members_raw = _prompt("members to assign (comma-separated, blank to skip)", "")

                model_list  = [m.strip() for m in models_raw.split(",")  if m.strip()] or None
                member_list = [m.strip() for m in members_raw.split(",") if m.strip()] or None

                try:
                    client.update_room(room_name, model_list, member_list)
                    print(f"  [✓] room '{room_name}' updated")

                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 5:
                print()

                model_name = _prompt("model name")
                model_creator = _prompt("model creator", client.username or "")
                message = _prompt("message to hide")

                try:
                    print("  [→] encoding...")
                    stego_buffer = client.stego_encode(model_name, model_creator, message)
                    print(f"  [✓] done — stego image in memory ({len(stego_buffer)} chars)")

                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 6:
                print()

                model_name = _prompt("model name")
                model_creator = _prompt("model creator", client.username or "")

                if stego_buffer is not None:
                    use_buf = _prompt("use last encoded image? (y/n)", "y").lower()
                    stego = stego_buffer if use_buf == "y" else _prompt("paste stego image data")

                else:
                    stego = _prompt("paste stego image data")

                try:
                    recovered = client.stego_decode(stego, model_name, model_creator)
                    print(f"\n  [✓] decoded message: {recovered}")

                except RuntimeError as e:
                    print(f"  [✗] {e}")

            elif choice == 7:
                client.token = None
                client.username = None

                state = "login"
                print("  [✓] logged out")

            elif choice == 8:
                client.token = None
                client.username = None
                state = None


if __name__ == "__main__":
    main()