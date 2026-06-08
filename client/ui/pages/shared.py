# client/ui/pages/shared.py
# Shared With Me â€” models that other users sent directly to this user.

import flet as ft
from ui import theme
from ui.components.image_card import _thumb, ImageCard


class SharedPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session

        self._encode_picker = ft.FilePicker()

    def build(self) -> ft.Control:
        self.page.services.append(self._encode_picker)

        from api.api_share_manager import get_shared_with_me, remove_share

        shares = get_shared_with_me(self.session.user_id)

        def share_card(share: dict) -> ft.Control:
            m     = share["model"]
            thumb = _thumb(m.get("image_path", ""), max_px=200) if m.get("image_path") else None
            if thumb:
                img = ft.Image(src=thumb, width=100, height=100, fit=ft.BoxFit.COVER)
            else:
                img = ft.Container(
                    content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED, color=theme.SUBTLE, size=28),
                    width=100, height=100,
                    bgcolor=theme.BORDER,
                    alignment=ft.Alignment(0, 0),
                )

            desc = (m.get("description") or "").strip()
            if len(desc) > 120:
                desc = desc[:119] + "â€¦"

            date_str = share.get("created", "")[:16].replace("T", " ")

            return ft.Container(
                content=ft.Column([
                    ft.Text(
                        m["name"],
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=theme.TEXT,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Container(
                            content=img,
                            border_radius=4,
                            clip_behavior=ft.ClipBehavior.HARD_EDGE,
                        ),
                        ft.Container(width=10),
                        ft.Column([
                            ft.Text(
                                desc or "No description.",
                                size=11,
                                color=theme.SUBTLE,
                                max_lines=4,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True,
                            ),
                        ], expand=True, spacing=0),
                    ], spacing=0),
                    ft.Container(height=6),
                    ft.Row([
                        ft.Icon(ft.Icons.PERSON, color=theme.SUBTLE, size=12),
                        ft.Container(width=4),
                        ft.Text(
                            f"From {share['sender_username']}  Â·  {date_str}",
                            size=11,
                            color=theme.SUBTLE,
                        ),
                    ], spacing=0),
                    ft.Container(height=8),
                    ft.Row([
                        theme.secondary_button(
                            "Use Model",
                            lambda e, s=share: self._open_encode_dialog(s),
                            icon=ft.Icons.LOCK_OPEN,
                        ),
                        theme.danger_button(
                            "Remove",
                            lambda e, sid=share["id"]: self._remove(sid),
                        ),
                    ], spacing=8),
                ], spacing=0),
                bgcolor=theme.SURFACE,
                border=ft.Border.all(1, theme.BORDER),
                border_radius=8,
                padding=12,
                width=268,
            )

        if shares:
            grid = ft.Row(
                [share_card(s) for s in shares],
                wrap=True,
                spacing=12,
                run_spacing=12,
            )
        else:
            grid = ft.Column([
                ft.Icon(ft.Icons.INBOX, color=theme.SUBTLE, size=48),
                ft.Container(height=8),
                theme.label("No models have been shared with you yet."),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                        theme.title("Shared With Me", size=24),
                    ]),
                    theme.label("Models that other users sent directly to you."),
                    theme.divider(),
                    ft.Container(height=8),
                    grid,
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=32,
        )

    # â”€â”€ Encode with a shared model â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _open_encode_dialog(self, share: dict):
        model = share["model"]
        self._active_model_id = model["id"]
        self._msg_field       = theme.text_field("Hidden message", hint="Type your secretâ€¦", width=340)
        self._preview_row     = ft.Row([], spacing=12)
        self._picked_path     = None

        async def pick_image(e):
            files = await self._encode_picker.pick_files(
                dialog_title="Choose cover image",
                allowed_extensions=["png", "jpg", "jpeg", "bmp"],
                allow_multiple=False,
            )
            if not files:
                return
            self._picked_path = files[0].path
            thumb = _thumb(self._picked_path, max_px=200)
            if thumb:
                self._preview_row.controls = [
                    ImageCard(self.page, self._picked_path,
                              label="Original", card_width=150, show_download=False)
                ]
                self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text(f"Encode with '{model['name']}'"),
            content=ft.Column([
                theme.label("Pick an image to hide your message in:"),
                theme.secondary_button("Choose Image", pick_image, icon=ft.Icons.IMAGE),
                ft.Container(height=6),
                self._preview_row,
                ft.Container(height=6),
                self._msg_field,
            ], spacing=8, tight=True),
            actions=[
                theme.accent_button("Encode", lambda e: self._do_encode()),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        ))

    def _do_encode(self):
        if not getattr(self, "_picked_path", None):
            self.router.show_snack("Please choose an image first.", color=theme.ERROR)
            return
        msg = getattr(self, "_msg_field", None)
        msg = msg.value.strip() if msg else ""
        if not msg:
            self.router.show_snack("Message cannot be empty.", color=theme.ERROR)
            return

        import time
        from api.api_model_manager import encode_with_model, CREATIONS_DIR

        out_dir = CREATIONS_DIR / f"user_{self.session.user_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / f"stego_{int(time.time())}.png")

        try:
            encode_with_model(self._active_model_id, self._picked_path, msg, out_path)
            from api.api_model_manager import _client as _get_client
            _get_client().creation_add(self.session.user_id, self._active_model_id,
                                       self._picked_path, out_path)
            self.page.pop_dialog()
            self._show_result(out_path)
        except Exception as ex:
            self.router.show_snack(f"Encode failed: {ex}", color=theme.ERROR)

    def _show_result(self, stego_path: str):
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Encoded!", color=theme.SUCCESS),
            content=ft.Column([
                theme.label("Stego image saved to your Creations."),
                ft.Container(height=8),
                ImageCard(self.page, stego_path, label="Stego image",
                          card_width=260, show_download=True),
            ], tight=True, spacing=4),
            actions=[
                theme.accent_button(
                    "My Creations",
                    lambda e: (self.page.pop_dialog(), self.router.go("/creations")),
                    icon=ft.Icons.PHOTO_LIBRARY,
                ),
                ft.TextButton("Done", on_click=lambda e: self.page.pop_dialog()),
            ],
        ))

    def _remove(self, share_id: int):
        from api.api_share_manager import remove_share
        remove_share(share_id)
        self.router.go("/shared")
