
from httpio import HTTPServer, HTTPEndpoint

from endpoints import update_room, create_room, train_model, get_model_names, login, signup

HOST = "0.0.0.0"
PORT = 8080


def start_server():
    server = HTTPServer(
        endpoints=[
            HTTPEndpoint(
                uri="/signup",
                method="POST",
                endpoint=signup
            ),

            HTTPEndpoint(
                uri="/login",
                method="POST",
                endpoint=login
            ),

            HTTPEndpoint(
                uri="/models",
                method="POST",
                endpoint=get_model_names
            ),

            HTTPEndpoint(
                uri="/room/create",
                method="POST",
                endpoint=create_room
            ),

            HTTPEndpoint(
                uri="/room/update",
                method="POST",
                endpoint=update_room
            ),

            HTTPEndpoint(
                uri="/model/train",
                method="POST",
                endpoint=train_model
            )
        ]
    )

    server.serve_forever((HOST, PORT))


if __name__ == "__main__":
    start_server()