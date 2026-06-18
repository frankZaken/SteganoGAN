import socket

from security.asymmetric.dhe import DHE
from security.protocols.dhe import UDPKeyEstablishing, DHESKE
from security.symmetric.kdf import KDF
from security.symmetric.aes.aes128 import AES128
from security.symmetric.aes.modes import CBC

from colorama import Fore, Style

from utils import bytes_to_int, int_to_bytes

IP = "127.0.0.1"
PORT = 3434
ADDRESS = (IP, PORT)

BUFFER = 2048
N = 23


def main():
    server = socket.socket(type=socket.SOCK_DGRAM)
    server.bind(ADDRESS)
    print("Server is running...")

    dhe = DHE(n=N)
    public_key = dhe.send()
    print(f"[Server] Public key: {public_key}")

    # Step 1: Receive client's public key
    client_key_data, addr = server.recvfrom(BUFFER)
    client_public = int(client_key_data.decode())


    # Step 2: Send server's public key to client
    server.sendto(str(public_key).encode(), addr)


    # Step 3: Calculate shared secret
    shared_secret = dhe.receive(client_public)
    print(f"[Server] Shared secret with {addr}: {shared_secret}")


    # Step 4: Derive the AES encryption key using KDF
    kdf_key = KDF(algorithm="sha256", key=shared_secret.to_bytes(16, byteorder="big"), size=16)
    derived_key = kdf_key.digest()

    print(f"\tAfter KDF: {derived_key}\n")


    # Step 5: Initialize CBC mode with a random IV
    kdf_iv = KDF(algorithm="sha256", key=derived_key, size=16)
    iv = kdf_iv.digest()

    aes = AES128(key=derived_key)
    cbc = CBC(aes, iv)


    # Step 6: Start communication with encryption using CBC
    while True:
        data, addr = server.recvfrom(BUFFER)
        decrypted_data = b"".join(cbc.decrypt(data))

        print(f"[Client]: {Fore.RED}{data}{Style.RESET_ALL}"
              f" --> {Fore.GREEN}{decrypted_data.decode()}{Style.RESET_ALL}")
        response = input("Server: ")
        print()

        encrypted_response = b"".join(cbc.encrypt(response.encode()))
        server.sendto(encrypted_response, addr)


def main2():
    server = socket.socket(type=socket.SOCK_DGRAM)
    server.bind(ADDRESS)
    print("Server is running...")

    communication = UDPKeyEstablishing(server, BUFFER, ADDRESS)
    key_maker = DHESKE(send=communication.send, receive=communication.receive, auto=True)

    # bace = 3
    # server.sendto(int_to_bytes(bace), ADDRESS)
    # key_maker.dhe.g = bace

    shared_secret = key_maker.shared_key()
    print(f"[Client] Shared secret: {shared_secret}")


if __name__ == '__main__':
    main2()
