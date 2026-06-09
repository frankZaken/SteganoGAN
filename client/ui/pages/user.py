# client/ui/pages/user.py
# User dashboard â€” entry point after login.

import flet as ft
from ui import theme


class UserPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session

    def _logout(self, e):
        log_out(self.router.session)
        self.router.session = None
        self.router.go("/")

    def _feature_card(self, icon: str, title: str, desc: str, route: str) -> ft.Control:
        return theme.card(
            ft.Column(
                controls=[
                    ft.Icon(icon, size=40, color=theme.ACCENT),
                    theme.subtitle(title),
                    theme.label(desc),
                    ft.Container(height=8),
                    theme.accent_button("Open", lambda e, r=route: self.router.go(r), width=120),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
            ),
        )

    def build(self) -> ft.Control:
        username = self.session.username if self.session else "?"

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.LOCK, color=theme.ACCENT, size=22),
                        theme.title(f"Hello, {username}", size=24),
                        ft.Container(expand=True),
                        ft.TextButton(
                            "Log Out",
                            on_click=self._logout,
                            style=ft.ButtonStyle(color=theme.SUBTLE),
                        ),
                    ]),
                    theme.divider(),
                    ft.Container(height=8),
                    theme.label("What would you like to do?"),
                    ft.Container(height=16),
                    ft.Row(
                        controls=[
                            self._feature_card(
                                ft.Icons.PSYCHOLOGY,
                                "Create Model",
                                "Train AI for your specific image",
                                "/create-model",
                            ),
                            self._feature_card(
                                ft.Icons.IMAGE_SEARCH,
                                "My Models",
                                "Encode & decode hidden messages",
                                "/models",
                            ),
                            self._feature_card(
                                ft.Icons.PHOTO_LIBRARY,
                                "Creations",
                                "Browse your encoded stego images",
                                "/creations",
                            ),
                            self._feature_card(
                                ft.Icons.GROUPS,
                                "Rooms",
                                "Share models securely with others",
                                "/rooms",
                            ),
                            self._feature_card(
                                ft.Icons.SEND,
                                "Send Model",
                                "Share a model directly with a user",
                                "/send",
                            ),
                            self._feature_card(
                                ft.Icons.MOVE_TO_INBOX,
                                "Shared With Me",
                                "Models other users sent you",
                                "/shared",
                            ),
                        ],
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=40,
        )
