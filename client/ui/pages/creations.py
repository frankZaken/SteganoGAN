# client/ui/pages/creations.py
# Gallery of all stego images the user has encoded.

import flet as ft
from ui import theme
from ui.components.image_card import ImageCard


class CreationsPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session

    def _load(self) -> list[dict]:
        from api.api_model_manager import _client
        return _client().creation_list(self.session.user_id)

    def _delete(self, creation: dict):
        from api.api_model_manager import _client
        _client().creation_delete(creation["id"])
        self.router.go("/creations")

    def _creation_card(self, c: dict) -> ft.Control:
        delete_btn = ft.IconButton(
            ft.Icons.DELETE_OUTLINE,
            icon_color=theme.ERROR,
            icon_size=16,
            tooltip="Delete",
            on_click=lambda e, cr=c: self._delete(cr),
        )

        return ft.Column(
            [
                ft.Text(
                    "Original  â†’  Stego",
                    size=11, color=theme.SUBTLE,
                ),
                ft.Row(
                    [
                        ImageCard(
                            self.page,
                            c["original_path"],
                            label="Original",
                            card_width=160, thumb_height=130,
                            show_download=False,
                        ),
                        ft.Icon(ft.Icons.ARROW_FORWARD, color=theme.ACCENT, size=22),
                        ImageCard(
                            self.page,
                            c["stego_path"],
                            label="Stego",
                            card_width=160, thumb_height=130,
                            show_download=True,
                        ),
                        ft.Column([
                            delete_btn,
                            ft.Text(c["created"][:10], size=10, color=theme.SUBTLE),
                        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=4,
        )

    def build(self) -> ft.Control:
        creations = self._load()

        if creations:
            items = [
                ft.Container(
                    content=self._creation_card(c),
                    bgcolor=theme.SURFACE,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=8,
                    padding=12,
                )
                for c in reversed(creations)
            ]
        else:
            items = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.PHOTO_LIBRARY, size=52, color=theme.SUBTLE),
                        theme.label("No creations yet â€” encode a message first"),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment(0, 0),
                    height=200,
                )
            ]

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_BACK, icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                        theme.title("My Creations", size=24),
                    ]),
                    theme.divider(),
                    ft.Column(
                        controls=items,
                        spacing=16,
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                    ),
                ],
                spacing=12,
                expand=True,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=32,
        )
