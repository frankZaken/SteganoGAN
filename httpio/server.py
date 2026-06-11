# httpio/server.py

import socket
import threading
import warnings
from typing import Any

from .endpoint import HTTPEndpoint
from .request  import HTTPRequest, load_request
from .response import HTTPResponse


# TODO: Creates RSA key pair for the server. The public key should be hardcoded in the client, as the privet key should be hardcoded in the server.


class HTTPServer:
    def __init__(self, endpoints: list[HTTPEndpoint], headers: dict[str,  Any] | None = None):
        self.endpoints = endpoints
        self.headers   = headers or {}
        self.server:   socket.socket | None = None
        self.buffer    = 4096

    def open(self, address: tuple[str, int]):
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(address)
        self.server.listen()

    def _recv_full(self, sock: socket.socket) -> bytes:
        """Read a complete HTTP request, using Content-Length for the body."""
        sep  = b"\r\n\r\n"
        data = b""
        while sep not in data:
            chunk = sock.recv(self.buffer)
            if not chunk:
                break
            data += chunk
        if sep not in data:
            return data
        header_end   = data.index(sep)
        headers_raw  = data[:header_end]
        body_so_far  = data[header_end + 4:]
        content_length = 0
        for line in headers_raw.split(b"\r\n")[1:]:
            if line.lower().startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
                break
        while len(body_so_far) < content_length:
            needed = content_length - len(body_so_far)
            chunk  = sock.recv(min(self.buffer, needed))
            if not chunk:
                break
            body_so_far += chunk
        return headers_raw + sep + body_so_far

    def handle(self, client: socket.socket | None = None, close: bool = True):
        if client is None:
            client, _ = self.server.accept()

        # TODO: Use Diffie-Hellman key exchange, where the client encrypts his public number, using the server's public key.
        # TODO: Having a secret key, it will be a seed for a cryptographic generator, to generate AES and HMAC keys, as well as IV for the AES model.
        # TODO: Make sure there are 2 sets of keys generated (aes-key, hmac-key, iv) for each direction (server -> client, client -> server)
        # TODO first keys set: server -> client, second keys set: client -> server

        data = self._recv_full(client)

        if not data:
            return

        # TODO: Decrypt data using (client -> server)

        try:
            request = load_request(data)

        except ValueError as e:
            warnings.warn(f"bad request: {e}")
            client.send(HTTPResponse(status=400, message="Bad_Request").dump())
            if close:
                client.close()

            return

        print(request)

        response = respond(request, self.endpoints)
        response.headers.update(
            {k: v for k, v in self.headers.items() if k not in response.headers}
        )

        print(response)
        print()

        # TODO: Encrypt response.dump AES(AES-KEY).Mode(IV) + HMAC(HMAC-KEY) using (client -> server)
        client.send(response.dump())
        if close:
            client.close()

    def serve_forever(self, address: tuple[str, int]):
        """Accept connections in a loop, dispatching each to a daemon thread."""
        self.open(address)
        print(f"[server] listening on {address[0]}:{address[1]}")
        while True:
            client, addr = self.server.accept()
            print(addr)
            t = threading.Thread(target=self.handle, args=(client,))
            t.start()


def respond(request: HTTPRequest, endpoints: list[HTTPEndpoint]) -> HTTPResponse:
    uri, method = request.uri, request.method
    uri_found = method_found = False
    endpoint = None

    for ep in endpoints:
        if uri == ep.uri:
            uri_found = True
            if method == ep.method:
                method_found = True
                endpoint = ep

    if not uri_found:
        return HTTPResponse(status=404, message="Not_Found")
    if not method_found:
        return HTTPResponse(status=405, message="Method_Not_Allowed")

    try:
        return endpoint.endpoint(request)
    except Exception:
        import traceback
        print(f"[server] ERROR in {uri}:", flush=True)
        traceback.print_exc()
        return HTTPResponse(status=500, message="Internal_Server_Error")
