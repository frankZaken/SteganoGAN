# server/__main__


from httpio import HTTPServer, HTTPEndpoint

from endpoints import update_room, create_room, train_model, get_model_names, login, signup, stego_encode, stego_decode
from server.endpoints import get_model_status, model_training_done

IP = "192.168.0.85"
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
            ),

            HTTPEndpoint(
                uri="/model/encode",
                method="POST",
                endpoint=stego_encode
            ),

            HTTPEndpoint(
                uri="/model/decode",
                method="POST",
                endpoint=stego_decode
            ),

            HTTPEndpoint(
                uri="/model/get_status",
                method="POST",
                endpoint=get_model_status
            ),
            #
            # HTTPEndpoint(
            #     uri="/model/status",
            #     method="GET",
            #     endpoint=model_training_done
            # )
        ]
    )

    server.serve_forever((IP, PORT))


if __name__ == "__main__":
    start_server()