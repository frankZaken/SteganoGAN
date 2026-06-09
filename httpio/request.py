# httpio/request.py

from dataclasses import dataclass, field


@dataclass
class HTTPRequest:
    method:     str   = "GET"
    uri:        str   = "/"
    version:    str   = "HTTP/1.1"
    headers:    dict  = field(default_factory=dict)
    body:       bytes = b""
    line_break: bytes = b"\r\n"

    def dump(self) -> bytes:
        body = self.body or b""
        request_line = b" ".join([
            self.method.encode(), self.uri.encode(), self.version.encode()
        ])
        all_headers = {**self.headers, "Content-Length": str(len(body))}
        headers = self.line_break.join(
            f"{k}: {v}".encode() for k, v in all_headers.items()
        )
        return request_line + self.line_break + headers + self.line_break * 2 + body

    def __repr__(self) -> str:
        return f"{self.method} {self.uri} {self.version} | body={len(self.body)}B"


def load_request(data: bytes, line_break: bytes = b"\r\n") -> HTTPRequest:
    sep = line_break * 2
    if sep in data:
        header_part, body = data.split(sep, 1)
    else:
        header_part, body = data, b""
    lines = header_part.split(line_break)
    method, uri, version = lines[0].decode().split(" ")
    headers = {}
    for item in lines[1:]:
        if not item:
            continue
        key, value = item.split(b": ", 1)
        headers[key.decode()] = value.decode()
    return HTTPRequest(method, uri, version, headers, body, line_break)
