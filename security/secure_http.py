# security/secure_http.py

from httpio.server import HTTPServer
from httpio.client import HTTPClient
from security.channel import handshake, seal, open_
from security.protocols.dhe import recv_msg, send_msg


class SecureHTTPServer(HTTPServer):

    def __init__(self, *a, server_private, **kw):
        super().__init__(*a, **kw)
        self._priv = server_private

    def _handshake(self, sock):
        return handshake(sock, "server", server_private=self._priv)

    def _recv(self, sock, ctx):
        return open_(recv_msg(sock), ctx[1])   # c2s

    def _send(self, sock, data, ctx):
        send_msg(sock, seal(data, ctx[0]))     # s2c


class SecureHTTPClient(HTTPClient):

    def __init__(self, *a, server_public, **kw):
        super().__init__(*a, **kw)
        self._pub = server_public

    def _handshake(self, sock):
        return handshake(sock, "client", server_public=self._pub)

    def _send(self, sock, data, ctx):
        sent = seal(data, ctx[1])
        send_msg(sock, sent)     # c2s

    def _recv(self, sock, ctx):
        received = recv_msg(sock)
        data = open_(received, ctx[0])
        return data# s2c