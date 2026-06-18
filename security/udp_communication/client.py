import socket

from security.asymmetric.dhe import DHE
from security.symmetric.kdf import KDF
from security.symmetric.aes.aes128 import AES128
from security.symmetric.aes.modes import CBC
from protocols.dhe import DHESKE, UDPKeyEstablishing

from colorama import Fore, Style

from utils import bytes_to_int

IP = "127.0.0.1"
PORT = 3434
ADDRESS = (IP, PORT)

BUFFER = 2048
N = 23


def main():
    client = socket.socket(type=socket.SOCK_DGRAM)

    dhe = DHE(n=N)
    public_key = dhe.send()

    print(f"[Client] Public key: {public_key}")

    # Step 1: Send client's public key
    client.sendto(str(public_key).encode(), ADDRESS)


    # Step 2: Receive server's public key
    server_key_data, _ = client.recvfrom(BUFFER)
    server_public = int(server_key_data.decode())
    shared_secret = dhe.receive(server_public)

    print(f"[Client] Shared secret: {shared_secret}")


    # Step 3: Derive the AES encryption key using KDF
    kdf = KDF(algorithm="sha256", key=shared_secret.to_bytes(16, byteorder="big"), size=16)
    derived_key = kdf.digest()

    print(f"\tAfter KDF: {derived_key}\n")


    # Step 4: Initialize CBC mode with a random IV
    kdf_iv = KDF(algorithm="sha256", key=derived_key, size=16)
    iv = kdf_iv.digest()

    aes = AES128(key=derived_key)
    cbc = CBC(aes, iv)


    # Step 5: Start communication with encryption using CBC
    while True:
        message = input("Client: ")
        encrypted_message = b"".join(cbc.encrypt(message.encode()))
        client.sendto(encrypted_message, ADDRESS)

        received, addr = client.recvfrom(BUFFER)
        decrypted_message = b"".join(cbc.decrypt(received))

        print(f"[Server]: {Fore.RED}{received}{Style.RESET_ALL}"
              f" --> {Fore.GREEN}{decrypted_message.decode()}{Style.RESET_ALL}\n")

def main2():
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.bind(ADDRESS)
    print("Client is running...")

    communication = UDPKeyEstablishing(client, BUFFER, ADDRESS)
    key_maker = DHESKE(send=communication.send, receive=communication.receive, auto=True)

    # bace = bytes_to_int(communication.receive())
    # key_maker.dhe.g = bace

    shared_secret = key_maker.shared_key()
    print(f"[Client] Shared secret: {shared_secret}")


if __name__ == '__main__':
    main2()
