# client/client.py

import base64
import json
import os
import socket as _socket
import subprocess
import sys
import time
import zlib
import threading

from pathlib import Path

from httpio import HTTPClient, HTTPRequest


def _compress(data: bytes) -> str:
    compressed = zlib.compress(data, level=9)
    payload = (b"Z" + compressed) if len(compressed) < len(data) else (b"R" + data)
    return base64.b64encode(payload).decode()


class SteganoClient:

    def __init__(self, server_address: tuple[str, int]):
        self.server_address = server_address
        self.http_client: HTTPClient = HTTPClient(server_address)
        self.token: str | None = None

    def _check_token(self):
        if self.token is None:
            raise RuntimeError("must login first.")

    def signup(self, username: str, email: str, password: str):

        body = {
            "username": username,
            "email": email,
            "password": password
        }

        request = HTTPRequest(method="POST", uri="/signup", body=json.dumps(body).encode())
        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"signup failed: {response.message}")

    def login(self, username: str, password: str):

        body = {
            "username": username,
            "password": password
        }

        request = HTTPRequest(method="POST", uri="/login", body=json.dumps(body).encode())
        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"login failed: {response.message}")

        self.token = response.headers["token"]

    def get_model_names(self) -> list[str]:
        self._check_token()

        request = HTTPRequest(method="POST", uri="/models", headers={"token": self.token})
        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"get model names failed: {response.message}")

        return json.loads(response.body)["model_names"]

    def create_room(self, name: str, members: list[str]):
        self._check_token()

        body = {
            "name": name,
            "members": members
        }

        request = HTTPRequest(
            method="POST",
            uri="/room/create",
            headers={"token": self.token},
            body=json.dumps(body).encode()
        )

        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"room creation failed: {response.message}")

    def update_room(self, name: str, model_names: list[str] | None, members: list[str] | None):
        self._check_token()

        body = {
            "name": name,
            "model_names": model_names,
            "members": members
        }

        request = HTTPRequest(
            method="POST",
            uri="/room/update",
            headers={"token": self.token},
            body=json.dumps(body).encode()
        )

        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"room update failed: {response.message}")

    def train_model(self, model_name: str, model_description: str, image_data: bytes):
        self._check_token()

        body = {
            "model_name": model_name,
            "model_description": model_description,
            "image_data": _compress(image_data)
        }

        request = HTTPRequest(
            method="POST",
            uri="/model/train",
            headers={"token": self.token},
            body=json.dumps(body).encode()
        )

        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"model training failed: {response.message}")

    def stego_encode(self, model_name: str, model_creator: str, message: str) -> str:
        self._check_token()

        body = {
            "model_name": model_name,
            "model_creator": model_creator,
            "message": message
        }

        request = HTTPRequest(
            method="POST",
            uri="/model/encode",
            headers={"token": self.token},
            body=json.dumps(body).encode()
        )

        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"encode failed: {response.message}")

        return json.loads(response.body)["stego_image"]

    def stego_decode(self, stego_image: str, model_name: str, model_creator: str) -> str:
        self._check_token()

        body = {
            "stego_image": stego_image,
            "model_name": model_name,
            "model_creator": model_creator
        }

        request = HTTPRequest(
            method="POST",
            uri="/model/decode",
            headers={"token": self.token},
            body=json.dumps(body).encode()
        )

        response = self.http_client.open(request)

        if response.status != 200:
            raise RuntimeError(f"decode failed: {response.message}")

        return json.loads(response.body)["message"]



def _prompt(label: str, default: str = "") -> str:

    answer = input(f"  {label}: ").strip()
    return answer if answer else default


def _stream_server(proc: subprocess.Popen):

    if proc.stdout is None:
        return

    out = proc.stdout

    def _read():
        for line in iter(out.readline, b""):
            print(f"[server] {line.decode(errors='replace')}", end="", flush=True)

    threading.Thread(target=_read, daemon=True).start()


def main():
    project_root = Path(__file__).resolve().parent.parent
    server_dir = project_root / "server"

    env = os.environ.copy()
    env["PYTHONPATH"] = (
        str(project_root) + os.pathsep +
        str(server_dir) + os.pathsep +
        env.get("PYTHONPATH", "")
    )

    print("[*] starting server...")
    proc = subprocess.Popen(
        [sys.executable, "-u", "__main__.py"],
        cwd=str(server_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    _stream_server(proc)

    for _ in range(60):
        try:
            s = _socket.socket()
            s.settimeout(1)
            s.connect(("127.0.0.1", 8080))
            s.close()
            print("[✓] server ready\n")
            break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    else:
        print("[✗] server did not start — check output above")
        proc.kill()
        return

    try:
        print("=== StegoGAN test ===\n")

        # --- credentials (used for signup if new, then login) ---
        print("Enter your account details (used for signup + login):")
        username = _prompt("username", "peleg")
        password = _prompt("password", "123")
        email    = _prompt("email (only needed for signup)", f"{username}@gmail.com")

        client = SteganoClient(("127.0.0.1", 8080))

        # 1. signup
        print("\n1. signup")
        try:
            client.signup(username, email, password)
            print("   [✓] signed up")
        except RuntimeError as e:
            print(f"   [~] {e}")

        # 2. login
        print("\n2. login")
        client.login(username, password)
        print("   [✓] logged in")

        # 3. list models
        print("\n3. your models")
        names = client.get_model_names()
        print(f"   [✓] {names if names else '(none yet)'}")

        # 4. create room (optional)
        print("\n4. create room")
        if _prompt("create a room? (y/n)", "n").lower() == "y":
            room_name = _prompt("room name", "lab")
            try:
                client.create_room(room_name, [])
                print(f"   [✓] room '{room_name}' created")
            except RuntimeError as e:
                print(f"   [~] {e}")
        else:
            print("   (skipped)")

        # 5. train model (optional)
        print("\n5. train model")
        model_name = _prompt("model name to use", "test_model")
        if model_name not in names:
            if _prompt(f"'{model_name}' not found — train it now? (y/n)", "y").lower() == "y":
                image_path = project_root / "original.png"
                print(f"   [→] training on {image_path.name} — this takes several minutes...")
                with open(image_path, "rb") as f:
                    image_data = f.read()
                desc = _prompt("model description", f"model for {image_path.name}")
                client.train_model(model_name, desc, image_data)
                print("   [✓] training complete")
            else:
                print("   (skipped — encode/decode will fail if model doesn't exist)")
        else:
            print(f"   [~] '{model_name}' already trained, skipping")

        # 6. encode
        print("\n6. encode")
        message = _prompt("message to hide", "Hello from StegoGAN! אופק גבר!")
        print(f"   [→] encoding...")
        stego = client.stego_encode(model_name, username, message)
        print(f"   [✓] stego image received ({len(stego)} chars)")

        # 7. decode
        print("\n7. decode")
        recovered = client.stego_decode(stego, model_name, username)
        print(f"   [✓] recovered: '{recovered}'")

        print()
        if recovered == message:
            print("[✓✓] SUCCESS — 100% decode accuracy confirmed!")
        else:
            print("[✗] MISMATCH!")
            print(f"    expected : {message!r}")
            print(f"    got      : {recovered!r}")

    except Exception as e:
        import traceback
        print(f"\n[✗] ERROR: {e}")
        traceback.print_exc()

    finally:
        proc.terminate()
        print("\n[*] server terminated")


if __name__ == '__main__':
    main()