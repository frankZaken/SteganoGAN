# client/ui/pages/room.py
# Room detail page: model grid + OTP-encrypted messaging (text & stego images).

import base64
import io

import flet as ft
from ui import theme
from ui.components.image_card import _thumb


class RoomPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session
        self.room_id = router.room_id

        self._encode_picker  = ft.FilePicker()
        self._img_msg_picker = ft.FilePicker()
        self._pending_use: dict | None = None

        self._msg_list    = ft.Column([], spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self._text_input  = theme.text_field("Type a messageâ€¦", width=None)
        self._send_status = ft.Text("", size=11, color=theme.SUBTLE)

    def build(self) -> ft.Control:
        self.page.services.extend([self._encode_picker, self._img_msg_picker])

        get_user_by_id = lambda uid: _get_client().get_user_by_id(uid)

        room = get_room_by_id(self.room_id)
        if room is None:
            return ft.Container(
                content=ft.Text("Room not found.", color=theme.ERROR),
                bgcolor=theme.PRIMARY, padding=32,
            )

        owner      = get_user_by_id(room["owner_id"])
        owner_name = owner["username"] if owner else "Unknown"
        is_owner   = self.session.user_id == room["owner_id"]
        allow_mem  = get_room_setting(self.room_id)
        entries    = get_room_models_detailed(self.room_id)

        # â”€â”€ Initial message load â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._load_messages(get_inbox)

        # â”€â”€ Model card â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        def model_card(entry: dict) -> ft.Control:
            m     = entry["model"]
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

            btn_row_controls = [
                theme.secondary_button(
                    "Use Model",
                    lambda e, mod=m: self._open_use_dialog(mod),
                    icon=ft.Icons.LOCK_OPEN,
                ),
            ]
            if is_owner:
                btn_row_controls.append(
                    theme.danger_button(
                        "Remove",
                        lambda e, eid=entry["id"]: self._remove_and_refresh(eid),
                    )
                )

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
                        ft.Text(
                            desc or "No description.",
                            size=11,
                            color=theme.SUBTLE,
                            max_lines=5,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            expand=True,
                        ),
                    ], spacing=0),
                    ft.Container(height=8),
                    ft.Row(btn_row_controls, spacing=8),
                ], spacing=0),
                bgcolor=theme.SURFACE,
                border=ft.Border.all(1, theme.BORDER),
                border_radius=8,
                padding=12,
                width=268,
            )

        # â”€â”€ Model grid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if entries:
            grid = ft.Row(
                [model_card(e) for e in entries],
                wrap=True,
                spacing=12,
                run_spacing=12,
            )
        else:
            grid = theme.label("No models shared in this room yet.")

        # â”€â”€ Owner-only controls â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        auth_key_row = ft.Row([
            theme.label("Auth Key:"),
            ft.Text(
                room["auth_key"],
                color=theme.ACCENT,
                size=13,
                selectable=True,
                font_family="monospace",
            ),
        ], spacing=6) if is_owner else ft.Container()

        self._allow_setting = allow_mem
        allow_toggle = ft.Checkbox(
            label="Allow members to add models",
            value=allow_mem,
            active_color=theme.ACCENT,
            label_style=ft.TextStyle(color=theme.SUBTLE, size=13),
            on_change=lambda e: self._toggle_allow(e.control.value),
        ) if is_owner else ft.Container()

        can_add = is_owner or allow_mem
        add_btn = (
            theme.accent_button(
                "Add Model to Room",
                lambda e: self._add_model_dialog(get_user_models),
                icon=ft.Icons.ADD,
            ) if can_add else ft.Container()
        )

        # â”€â”€ Messaging section â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        async def pick_stego_image(e):
            files = await self._img_msg_picker.pick_files(
                dialog_title="Choose stego image to share",
                allowed_extensions=["png"],
                allow_multiple=False,
            )
            if not files:
                return
            self._send_status.value = "Sending imageâ€¦"
            try:
                self.page.update()
            except Exception:
                pass
            try:
                send_image_message(self.room_id, self.session.user_id, files[0].path)
                self._send_status.value = "Image sent!"
                self._send_status.color = theme.SUCCESS
                self._load_messages(get_inbox)
            except Exception as ex:
                self._send_status.value = f"Error: {ex}"
                self._send_status.color = theme.ERROR
            try:
                self.page.update()
            except Exception:
                pass

        def send_text(e):
            text = self._text_input.value.strip()
            if not text:
                return
            try:
                send_text_message(self.room_id, self.session.user_id, text)
                self._text_input.value  = ""
                self._send_status.value = ""
                self._load_messages(get_inbox)
            except Exception as ex:
                self._send_status.value = f"Error: {ex}"
                self._send_status.color = theme.ERROR
            try:
                self.page.update()
            except Exception:
                pass

        def refresh_inbox(e):
            self._load_messages(get_inbox)
            try:
                self.page.update()
            except Exception:
                pass

        msg_input_row = ft.Row([
            ft.Container(content=self._text_input, expand=True),
            theme.accent_button("Send", send_text, icon=ft.Icons.SEND),
            theme.secondary_button("Send Image", pick_stego_image, icon=ft.Icons.IMAGE),
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        messaging_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    theme.subtitle("Messages"),
                    ft.Container(expand=True),
                    ft.IconButton(
                        ft.Icons.REFRESH,
                        icon_color=theme.SUBTLE,
                        icon_size=18,
                        tooltip="Refresh messages",
                        on_click=refresh_inbox,
                    ),
                ], spacing=0),
                ft.Divider(height=1, color=theme.BORDER),
                ft.Container(
                    content=self._msg_list,
                    height=260,
                    border=ft.Border.all(1, theme.BORDER),
                    border_radius=6,
                    bgcolor=theme.PRIMARY,
                    padding=ft.Padding(left=10, top=8, right=10, bottom=8),
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                ),
                ft.Container(height=6),
                self._send_status,
                msg_input_row,
            ], spacing=8),
            bgcolor=theme.SURFACE,
            border=ft.Border.all(1, theme.BORDER),
            border_radius=8,
            padding=16,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                        theme.title(room["name"], size=24),
                    ]),
                    theme.label(f"Owner: {owner_name}"),
                    auth_key_row,
                    theme.divider(),
                    ft.Container(height=4),
                    allow_toggle,
                    ft.Container(height=4) if is_owner else ft.Container(),
                    add_btn,
                    ft.Container(height=8),
                    theme.subtitle("Shared Models"),
                    ft.Container(height=8),
                    grid,
                    ft.Container(height=16),
                    messaging_section,
                ],
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=32,
        )

    # â”€â”€ Message rendering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _load_messages(self, get_inbox_fn):
        try:
            messages = get_inbox_fn(self.room_id)
        except Exception:
            messages = []

        controls = []
        for msg in messages:
            sender_label = ft.Text(
                f"User #{msg.get('sender_id', '?')}",
                size=10,
                color=theme.SUBTLE,
                weight=ft.FontWeight.W_500,
            )
            ts = (msg.get("created", "") or "")[:16].replace("T", " ")
            time_label = ft.Text(ts, size=10, color=theme.SUBTLE)

            if msg["type"] == "text":
                content_ctrl = ft.Text(
                    msg.get("decoded_text", ""),
                    size=13,
                    color=theme.TEXT,
                    selectable=True,
                )
            elif msg["type"] == "image":
                content_ctrl = self._image_message_ctrl(msg.get("image_bytes", ""))
            else:
                content_ctrl = ft.Text(f"[{msg['type']}]", size=12, color=theme.SUBTLE)

            bubble = ft.Container(
                content=ft.Column([
                    ft.Row([sender_label, ft.Container(expand=True), time_label], spacing=0),
                    content_ctrl,
                ], spacing=4),
                bgcolor=theme.SURFACE,
                border=ft.Border.all(1, theme.BORDER),
                border_radius=6,
                padding=ft.Padding(left=10, top=6, right=10, bottom=6),
            )
            controls.append(bubble)

        self._msg_list.controls = controls if controls else [
            ft.Text("No messages yet.", size=12, color=theme.SUBTLE, italic=True)
        ]

    def _image_message_ctrl(self, image_b64: str) -> ft.Control:
        try:
            raw = base64.b64decode(image_b64)
            # Thumbnail the received image for display
            from PIL import Image as PilImage
            with PilImage.open(io.BytesIO(raw)) as img:
                img = img.convert("RGB")
                img.thumbnail((220, 180), PilImage.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                thumb = buf.getvalue()

            def view_full(e, data=raw):
                with PilImage.open(io.BytesIO(data)) as full:
                    full = full.convert("RGB")
                    full.thumbnail((700, 560), PilImage.LANCZOS)
                    out = io.BytesIO()
                    full.save(out, format="JPEG", quality=90)
                self.page.show_dialog(ft.AlertDialog(
                    content=ft.Image(src=out.getvalue(), fit=ft.BoxFit.CONTAIN, width=700, height=540),
                    actions=[ft.TextButton("Close", on_click=lambda _: self.page.pop_dialog())],
                    actions_alignment=ft.MainAxisAlignment.END,
                ))

            return ft.Container(
                content=ft.Image(src=thumb, width=220, height=180, fit=ft.BoxFit.CONTAIN),
                on_click=view_full,
                tooltip="Click to view full size",
            )
        except Exception:
            return ft.Text("[image]", size=12, color=theme.SUBTLE)

    # â”€â”€ Add model dialog â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _add_model_dialog(self, get_user_models):
        models = get_user_models(self.session.user_id)
        if not models:
            self.router.show_snack("You have no models to share.", color=theme.SUBTLE)
            return

        selected = {"id": None}
        radio_group = ft.RadioGroup(
            content=ft.Column(
                [
                    ft.Radio(
                        value=str(m["id"]),
                        label=f"{m['name']}  â€”  {m.get('description') or 'no description'}",
                        label_style=ft.TextStyle(color=theme.TEXT, size=13),
                    )
                    for m in models
                ],
                spacing=4,
            ),
            on_change=lambda e: selected.update({"id": int(e.control.value)}),
        )

        def do_add(e):
            if selected["id"] is None:
                return
            add_model_to_room(self.room_id, selected["id"], self.session.user_id)
            self.page.pop_dialog()
            self.router.go("/room")

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Add Model to Room"),
            content=ft.Container(
                content=ft.Column(
                    [
                        theme.label("Select one of your models to share:"),
                        ft.Container(height=6),
                        radio_group,
                    ],
                    scroll=ft.ScrollMode.AUTO,
                    spacing=4,
                ),
                width=400,
                height=280,
            ),
            actions=[
                theme.accent_button("Add", do_add),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        ))

    # â”€â”€ Use model (encode) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _open_use_dialog(self, model: dict):
        self._pending_use = model
        self._msg_field   = theme.text_field("Hidden message", hint="Type your secretâ€¦", width=340)
        self._preview_row = ft.Row([], spacing=12)
        self._picked_path = None

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
                from ui.components.image_card import ImageCard
                self._preview_row.controls = [
                    ImageCard(self.page, self._picked_path, label="Original",
                              card_width=150, show_download=False)
                ]
                self.page.update()

        dlg = ft.AlertDialog(
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
                theme.accent_button("Encode", lambda e: self._do_encode(model["id"])),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    def _do_encode(self, model_id: int):
        if not self._picked_path:
            self.router.show_snack("Please choose an image first.", color=theme.ERROR)
            return
        msg = self._msg_field.value.strip() if self._msg_field else ""
        if not msg:
            self.router.show_snack("Message cannot be empty.", color=theme.ERROR)
            return

        out_dir = CREATIONS_DIR / f"user_{self.session.user_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = str(out_dir / f"stego_{int(time.time())}.png")

        try:
            encode_with_model(model_id, self._picked_path, msg, out_path)
            from api.api_model_manager import _client as _get_client
            _get_client().creation_add(self.session.user_id, model_id,
                                       self._picked_path, out_path)
            self.page.pop_dialog()
            self._show_result_dialog(out_path)
        except Exception as ex:
            self.router.show_snack(f"Encode failed: {ex}", color=theme.ERROR)

    def _show_result_dialog(self, stego_path: str):
        from ui.components.image_card import ImageCard
        result_card = ImageCard(self.page, stego_path, label="Stego image", card_width=260)
        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Encoded!"),
            content=ft.Column([
                theme.label("Your message is hidden in this image:"),
                ft.Container(height=8),
                result_card,
            ], tight=True, spacing=4),
            actions=[ft.TextButton("Done", on_click=lambda e: self.page.pop_dialog())],
        ))

    # â”€â”€ Settings helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _toggle_allow(self, value: bool):
        set_room_setting(self.room_id, value)

    def _remove_and_refresh(self, entry_id: int):
        remove_model_from_room(entry_id)
        self.router.go("/room")
