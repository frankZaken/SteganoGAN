# httpio/client.py

import socket
from dataclasses import dataclass

from .request  import HTTPRequest
from .response import HTTPResponse, load_response


@dataclass
class HTTPClient:
    server_address: tuple
    client_address: tuple = None
    buffer: int   = 4096

    def open(self,request: HTTPRequest, client: socket.socket = None, close: bool = True) -> HTTPResponse:

        if client is None:
            client = socket.socket()

            if self.client_address is not None:
                client.bind(self.client_address)

            client.connect(self.server_address)
        client.send(request.dump())

        sep  = b"\r\n\r\n"
        data = b""

        while sep not in data:
            chunk = client.recv(self.buffer)

            if not chunk:
                break

            data += chunk

        if sep in data:
            header_end = data.index(sep)
            headers_raw = data[:header_end]
            body_so_far = data[header_end + 4:]
            content_length = 0

            for line in headers_raw.split(b"\r\n")[1:]:
                if line.lower().startswith(b"content-length:"):
                    content_length = int(line.split(b":", 1)[1].strip())
                    break

            while len(body_so_far) < content_length:
                needed = content_length - len(body_so_far)
                chunk  = client.recv(min(self.buffer, needed))

                if not chunk:
                    break

                body_so_far += chunk
            data = headers_raw + sep + body_so_far

        if close:
            client.close()

        return load_response(data)
