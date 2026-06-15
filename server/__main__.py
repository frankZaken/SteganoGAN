# server/__main__


from httpio import HTTPServer, HTTPEndpoint

from endpoints import update_room, create_room, train_model, get_models_info, login, signup, stego_encode, stego_decode, \
    get_rooms, get_room_models
from server.endpoints import get_model_status, model_training_done

IP = "127.0.0.1"
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
                endpoint=get_models_info
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
                uri="/room/get_room_models",
                method="POST",
                endpoint=get_room_models
            ),

            HTTPEndpoint(
                uri="/room/get_rooms",
                method="POST",
                endpoint=get_rooms
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