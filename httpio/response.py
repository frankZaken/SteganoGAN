# httpio/response.py

from dataclasses import dataclass, field


@dataclass
class HTTPResponse:
    version:    str   = "HTTP/1.1"
    status:     int   = 200
    message:    str   = "OK"
    headers:    dict  = field(default_factory=dict)
    body:       bytes = b""
    line_break: bytes = b"\r\n"

    def dump(self) -> bytes:
        body = self.body or b""
        response_line = " ".join([self.version, str(self.status), self.message]).encode()
        all_headers = {**self.headers, "Content-Length": str(len(body))}
        headers = self.line_break.join(
            f"{k}: {v}".encode() for k, v in all_headers.items()
        )
        return self.line_break.join((response_line, headers + self.line_break, body))

    def __repr__(self) -> str:
        return f"{self.version} {self.status} {self.message} | body={len(self.body)}B"


def load_response(data: bytes, line_break: bytes = b"\r\n") -> HTTPResponse:
    sep = line_break * 2
    if sep in data:
        header_part, body = data.split(sep, 1)
    else:
        header_part, body = data, b""
    lines = header_part.split(line_break)
    version, status, message = lines[0].decode().split(" ", 2)
    headers = {}
    for item in lines[1:]:
        if not item:
            continue
        key, val = item.split(b": ", 1)
        headers[key.decode()] = val.decode()
    return HTTPResponse(version, int(status), message, headers, body, line_break)
