# client/ui/pages/signup.py

import flet as ft
from ui import theme


class SignupPage:
    def __init__(self, page: ft.Page, router):
        self.page   = page
        self.router = router

        self.username_field = theme.text_field("Username", width=320)
        self.password_field = theme.text_field("Password", width=320, password=True)
        self.confirm_field  = theme.text_field("Confirm Password", width=320, password=True)
        self.error_text     = ft.Text("", color=theme.ERROR, size=13)
        self.status_text    = ft.Text("", color=theme.SUBTLE, size=12)

    def _on_signup(self, e):
        if self.password_field.value != self.confirm_field.value:
            self.error_text.value = "Passwords do not match"
            self.page.update()
            return

        self.error_text.value  = ""
        self.status_text.value = "Creating account..."
        self.page.update()

        from api.auth import sign_up
        ok, msg = sign_up(self.username_field.value, self.password_field.value)
        if not ok:
            self.error_text.value  = msg
            self.status_text.value = ""
            self.page.update()
            return

        self.status_text.value = "âœ“ Account created! Please log in."
        self.status_text.color = theme.SUCCESS
        self.page.update()

        import time; time.sleep(1)
        self.router.go("/login")

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
                    ft.Icon(ft.Icons.PERSON_ADD, size=52, color=theme.ACCENT),
                    theme.title("Create Account", size=26),
                    ft.Container(height=20),
                    self.username_field,
                    ft.Container(height=8),
                    self.password_field,
                    ft.Container(height=8),
                    self.confirm_field,
                    ft.Container(height=4),
                    self.error_text,
                    self.status_text,
                    ft.Container(height=12),
                    theme.accent_button(
                        "Create Account",
                        self._on_signup,
                        icon=ft.Icons.PERSON_ADD,
                        width=320,
                    ),
                    ft.Container(height=12),
                    ft.Row(
                        [
                            theme.label("Already have an account?"),
                            ft.TextButton(
                                "Log in",
                                on_click=lambda e: self.router.go("/login"),
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
