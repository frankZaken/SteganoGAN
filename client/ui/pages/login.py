# client/ui/pages/login.py

import flet as ft
from ui import theme


class LoginPage:
    def __init__(self, page: ft.Page, router):
        self.page   = page
        self.router = router

        self.username_field = theme.text_field("Username", width=320)
        self.password_field = theme.text_field("Password", width=320, password=True)
        self.error_text     = ft.Text("", color=theme.ERROR, size=13)

    def _on_login(self, e):
        ok, session = log_in(
            self.username_field.value,
            self.password_field.value,
        )
        if not ok:
            self.error_text.value = "Wrong username or password"
            self.page.update()
            return
        self.router.session = session
        self.router.go("/user")

    def build(self) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                    ]),
                    ft.Container(height=20),
                    ft.Icon(ft.Icons.LOCK_OPEN, size=52, color=theme.ACCENT),
                    theme.title("Log In", size=26),
                    ft.Container(height=20),
                    self.username_field,
                    ft.Container(height=8),
                    self.password_field,
                    ft.Container(height=4),
                    self.error_text,
                    ft.Container(height=12),
                    theme.accent_button("Log In", self._on_login, icon=ft.Icons.LOGIN, width=320),
                    ft.Container(height=12),
                    ft.Row(
                        [
                            theme.label("No account?"),
                            ft.TextButton(
                                "Sign up",
                                on_click=lambda e: self.router.go("/signup"),
                                style=ft.ButtonStyle(color=theme.ACCENT),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=40,
        )
