# client/ui/pages/models.py
# Your models list â€” encode/decode messages, delete models.

import time

import flet as ft
from ui import theme
from ui.components.image_card import ImageCard


class ModelsPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session
        self.models  = []
        self.result_text    = ft.Text("", color=theme.SUCCESS, size=13, selectable=True)
        self._encode_picker = ft.FilePicker()
        self._decode_picker = ft.FilePicker()

    def _load_models(self):
        self.models = get_user_models(self.session.user_id)

    # â”€â”€ Encode dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _encode_dialog(self, model: dict):
        message_field = theme.text_field("Secret message", width=380)
        image_path    = [None]
        preview_area  = ft.Row([], spacing=0)

        async def pick_image(e):
            files = await self._encode_picker.pick_files(
                allowed_extensions=["jpg", "jpeg", "png"]
            )
            if files:
                image_path[0] = files[0].path
                preview_area.controls = [
                    ImageCard(
                        self.page, files[0].path,
                        label=files[0].name,
                        card_width=160, thumb_height=120,
                        show_download=False,
                    )
                ]
                self.page.update()

        def do_encode(e):
            if not image_path[0] or not message_field.value.strip():
                self.result_text.value = "Select an image and enter a message first"
                self.page.update()
                return

            from api.api_model_manager import encode_with_model, CREATIONS_DIR, _client as _get_client

            user_dir = CREATIONS_DIR / f"user_{self.session.user_id}"
            user_dir.mkdir(parents=True, exist_ok=True)
            out_path = str(user_dir / f"stego_{int(time.time())}.png")

            try:
                encode_with_model(model["id"], image_path[0], message_field.value.strip(), out_path)
                _get_client().creation_add(self.session.user_id, model["id"], image_path[0], out_path)
                self.page.pop_dialog()
                self._show_encode_result(image_path[0], out_path)
            except Exception as ex:
                self.result_text.value = f"Encode error: {ex}"
                self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"Encode â€” {model['name']}"),
            content=ft.Column([
                theme.label("1. Pick cover image:"),
                theme.secondary_button("Choose image", pick_image, icon=ft.Icons.IMAGE),
                preview_area,
                ft.Container(height=8),
                theme.label("2. Enter secret message:"),
                message_field,
            ], spacing=8, tight=True, width=420),
            actions=[
                theme.accent_button("Hide Message", do_encode, icon=ft.Icons.LOCK),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    def _show_encode_result(self, original_path: str, stego_path: str):
        dlg = ft.AlertDialog(
            title=ft.Text("Message hidden!", color=theme.SUCCESS),
            content=ft.Column([
                theme.label("Stego image saved to your Creations."),
                ft.Container(height=8),
                ft.Row(
                    [
                        ft.Column([
                            theme.label("Original"),
                            ImageCard(
                                self.page, original_path,
                                card_width=200, thumb_height=160,
                                show_download=False,
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        ft.Icon(ft.Icons.ARROW_FORWARD, color=theme.ACCENT, size=28),
                        ft.Column([
                            theme.label("Stego image"),
                            ImageCard(
                                self.page, stego_path,
                                label="stego.png",
                                card_width=200, thumb_height=160,
                                show_download=True,
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                    ],
                    spacing=16,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ], spacing=8, tight=True),
            actions=[
                theme.accent_button(
                    "My Creations", lambda e: (self.page.pop_dialog(), self.router.go("/creations")),
                    icon=ft.Icons.PHOTO_LIBRARY,
                ),
                ft.TextButton("Done", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    # â”€â”€ Decode dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _decode_dialog(self, model: dict):
        stego_path   = [None]
        result_label = ft.Text("", color=theme.SUBTLE, size=13, selectable=True)
        preview_area = ft.Row([], spacing=0)

        async def pick_stego(e):
            files = await self._decode_picker.pick_files(allowed_extensions=["png"])
            if files:
                stego_path[0] = files[0].path
                preview_area.controls = [
                    ImageCard(
                        self.page, files[0].path,
                        label=files[0].name,
                        card_width=160, thumb_height=120,
                        show_download=False,
                    )
                ]
                self.page.update()

        def do_decode(e):
            if not stego_path[0]:
                return
            from api.api_model_manager import decode_with_model
            try:
                msg = decode_with_model(model["id"], stego_path[0])
                result_label.value = f"Hidden message: {repr(msg)}"
                result_label.color = theme.SUCCESS
                self.page.update()
            except Exception as ex:
                result_label.value = f"Error: {ex}"
                result_label.color = theme.ERROR
                self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"Decode â€” {model['name']}"),
            content=ft.Column([
                theme.label("Select stego image (PNG):"),
                theme.secondary_button("Choose stego", pick_stego, icon=ft.Icons.IMAGE_SEARCH),
                preview_area,
                result_label,
            ], spacing=8, tight=True, width=400),
            actions=[
                theme.accent_button("Reveal Message", do_decode, icon=ft.Icons.LOCK_OPEN),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    # â”€â”€ Delete â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _delete_model(self, model: dict):
        from api.api_model_manager import delete_model
        delete_model(model["id"], self.session.user_id)
        self.router.go("/models")

    # â”€â”€ Model card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _model_card(self, model: dict) -> ft.Control:
        preview = ImageCard(
            self.page, model.get("image_path", ""),
            card_width=100, thumb_height=80,
            show_download=False,
        ) if model.get("image_path") else ft.Container(width=100, height=80)

        return theme.card(
            ft.Row([
                preview,
                ft.Column([
                    theme.body(model["name"]),
                    theme.label(model.get("description") or ""),
                    theme.label(f"Created: {model['created'][:10]}"),
                    ft.Container(height=4),
                    ft.Row([
                        theme.accent_button(
                            "Encode", lambda e, m=model: self._encode_dialog(m), width=90
                        ),
                        theme.secondary_button(
                            "Decode", lambda e, m=model: self._decode_dialog(m), width=90
                        ),
                        theme.danger_button(
                            "Delete", lambda e, m=model: self._delete_model(m), width=80
                        ),
                    ], spacing=8),
                ], expand=True, spacing=4),
            ], spacing=12),
        )

    # â”€â”€ Build â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def build(self) -> ft.Control:
        self.page.services.extend([self._encode_picker, self._decode_picker])
        self._load_models()

        if self.models:
            cards = [self._model_card(m) for m in self.models]
        else:
            cards = [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.PSYCHOLOGY_ALT, size=48, color=theme.SUBTLE),
                        theme.label("No models yet â€” create one first"),
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
                        theme.title("Your Models", size=24),
                        ft.Container(expand=True),
                        theme.secondary_button(
                            "Creations", lambda e: self.router.go("/creations"),
                            icon=ft.Icons.PHOTO_LIBRARY, width=140,
                        ),
                        theme.accent_button(
                            "New Model", lambda e: self.router.go("/create-model"),
                            icon=ft.Icons.ADD, width=140,
                        ),
                    ]),
                    theme.divider(),
                    self.result_text,
                    ft.Column(
                        controls=cards,
                        spacing=12,
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
