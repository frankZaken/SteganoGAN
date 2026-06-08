# httpio/endpoint.py

from typing import Callable


class HTTPEndpoint:
    def __init__(self, uri: str, method: str, endpoint: Callable):
        self.uri      = uri
        self.method   = method
        self.endpoint = endpoint

    def __repr__(self) -> str:
        return f"uri: {self.uri}\tmethod: {self.method}"
