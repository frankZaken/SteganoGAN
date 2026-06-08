# client/ui/pages/welcome.py

import flet as ft
from ui import theme


class WelcomePage:
    def __init__(self, page: ft.Page, router):
        self.page   = page
        self.router = router

    def build(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Icon(ft.Icons.LOCK, size=72, color=theme.ACCENT),
                    ft.Container(height=8),
                    theme.title("StegoFusion"),
                    theme.label("Hide secret messages inside images â€” invisibly"),
                    ft.Container(height=32),
                    theme.accent_button(
                        "Log In",
                        lambda e: self.router.go("/login"),
                        icon=ft.Icons.LOGIN,
                        width=220,
                    ),
                    ft.Container(height=10),
                    theme.secondary_button(
                        "Create Account",
                        lambda e: self.router.go("/signup"),
                        icon=ft.Icons.PERSON_ADD,
                        width=220,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                expand=True,
                spacing=6,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
        )
