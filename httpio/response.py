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
        response_line = " ".join([self.version, str(self.status), self.message]).encode()
        headers = self.line_break.join(
            f"{k}: {v}".encode() for k, v in self.headers.items()
        )
        return self.line_break.join((response_line, headers + self.line_break, self.body))

    def __repr__(self) -> str:
        return f"{self.version} {self.status} {self.message} | body={len(self.body)}B"


def load_response(data: bytes, line_break: bytes = b"\r\n") -> HTTPResponse:
    response_line, *headers_, body = data.split(line_break)
    version, status, message = response_line.decode().split(" ", 2)
    headers = {}
    for item in headers_:
        if not item:
            continue
        key, value = item.split(b": ", 1)
        headers[key.decode()] = value.decode()
    return HTTPResponse(version, int(status), message, headers, body, line_break)
