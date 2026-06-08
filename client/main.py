# client/main.py â€” SteganoGAN client entry point.
# Edit SERVER_HOST and SERVER_PORT to point at the machine running old_server.py.

import sys
from pathlib import Path

_root = str(Path(__file__).parent)   # SteganoGAN2/client/
if _root not in sys.path:
    sys.path.insert(0, _root)

import flet as ft
from ui.router import Router
from ui        import theme

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8765


def _check_server(page: ft.Page):
    from api.api_client import APIClient
    try:
        APIClient((SERVER_HOST, SERVER_PORT))
    except Exception:
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Server not reachable", color=theme.ERROR),
            content=ft.Text(
                f"Cannot connect to {SERVER_HOST}:{SERVER_PORT}.\n\n"
                "Make sure old_server.py is running, then edit SERVER_HOST / SERVER_PORT "
                "at the top of client/main.py.",
                size=13,
            ),
            actions=[ft.TextButton("OK", on_click=lambda e: page.pop_dialog())],
        ))


def main(page: ft.Page):
    from api.server_config import set_server
    set_server(SERVER_HOST, SERVER_PORT)

    page.title             = "SteganoGAN"
    page.theme_mode        = ft.ThemeMode.DARK
    page.bgcolor           = theme.PRIMARY
    page.padding           = 0
    page.window.width      = 960
    page.window.height     = 680
    page.window.min_width  = 800
    page.window.min_height = 560

    router = Router(page)
    router.go("/")
    _check_server(page)


ft.run(main)
