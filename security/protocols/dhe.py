import socket
import struct
import time
from dataclasses import dataclass
from typing import Callable

from security.asymmetric.dhe import DHE
from security.utils import int_to_bytes, bytes_to_int, random_prime


@dataclass
class DHESKE: # (Diffie-Hellman Ephemeral Symmetric Key Establishing)
    send: Callable[[bytes], ...] = None
    receive: Callable[..., bytes] = None
    dhe: DHE = None
    size: int = 2048
    auto: bool = False

    def _shared_modulus(self) -> int:
        public_modulus = random_prime(self.size)
        self.send(int_to_bytes(public_modulus))

        received_modulus = bytes_to_int(self.receive())
        return max(public_modulus, received_modulus)

    def initialize(self):
        self.dhe = DHE(n=self._shared_modulus())

    def shared_key(self) -> int:
        if self.dhe is None:
            if not self.auto:
                raise RuntimeError("bro. (when auto set to true, initialize must be called before shared key. but noOOo! You HAD TO INSIST on doing it YOURSElF even though I SPECIFICALLY ASKED YOU if you want me to do it. And you were like: 'no no bro it's totally fine, I'll do it.' and I was like: 'ha, what a nice guy, usually others take the offer...' and it's not like it is a complicated thing to remember to do, IT'S literally - 'initialize()'. THAT'S IT!! OH MY GOD, I am so pissed right now, WOW.)")

            self.initialize()

        self.send(str(self.dhe.send()).encode())
        return self.dhe.receive(int(bytes_to_int(self.receive())))


@dataclass
class UDPKeyEstablishing:
    connection: socket.socket
    buffer: int
    addr: tuple[str, int]

    def send(self, data: bytes):
        self.connection.sendto(data, self.addr)

    def receive(self) -> bytes:
        return self.connection.recvfrom(self.buffer)[0]

@dataclass
class TCPKeyEstablishing:
    connection: socket.socket
    buffer: int  # unused now but keep for compatibility

    def send(self, data: bytes):
        send_msg(self.connection, data)

    def receive(self) -> bytes:
        return recv_msg(self.connection)

def send_msg(sock: socket.socket, data: bytes):
    # Prefix each message with a 4-byte length (network byte order)
    length = struct.pack('!I', len(data))
    sock.sendall(length + data)

def recv_msg(sock: socket.socket) -> bytes:
    # Read the 4-byte length prefix
    raw_len = recvall(sock, 4)
    if not raw_len:
        return b''  # Connection closed or error
    msg_len = struct.unpack('!I', raw_len)[0]
    # Read the message data based on the length
    return recvall(sock, msg_len)

def recvall(sock: socket.socket, n: int) -> bytes:
    # Helper to recv exactly n bytes or return b'' if connection closes early
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return b''
        data += packet
    return data

