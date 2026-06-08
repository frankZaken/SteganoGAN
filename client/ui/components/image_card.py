# client/ui/components/image_card.py
# Reusable image card: PIL-thumbnailed display + fullscreen viewer + download.

import io
import shutil
from pathlib import Path

import flet as ft
from ui import theme


def _thumb(path: str, max_px: int = 320) -> bytes | None:
    try:
        from PIL import Image as PilImage
        with PilImage.open(path) as img:
            img = img.convert("RGB")
            img.thumbnail((max_px, max_px), PilImage.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
    except Exception:
        return None


class ImageCard(ft.Container):
    def __init__(
        self,
        page:          ft.Page,
        image_path:    str,
        label:         str  = "",
        card_width:    int  = 180,
        thumb_height:  int  = 140,
        show_download: bool = True,
        extra_actions: list = None,
    ):
        self._page = page
        self._path = image_path

        thumb_bytes = _thumb(image_path, max_px=max(card_width, thumb_height) * 2)

        if thumb_bytes:
            img_ctrl = ft.Image(
                src=thumb_bytes,
                width=card_width,
                height=thumb_height,
                fit=ft.BoxFit.COVER,
                error_content=ft.Icon(ft.Icons.BROKEN_IMAGE, color=theme.SUBTLE),
            )
        else:
            img_ctrl = ft.Container(
                content=ft.Icon(ft.Icons.BROKEN_IMAGE, color=theme.SUBTLE, size=40),
                width=card_width,
                height=thumb_height,
                alignment=ft.Alignment(0, 0),
            )

        thumb_box = ft.Container(
            content=img_ctrl,
            on_click=self._view,
            tooltip="Click to view full size",
        )

        below: list[ft.Control] = []

        if label:
            below.append(
                ft.Text(
                    label,
                    size=11,
                    color=theme.SUBTLE,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    width=card_width - 4,
                )
            )

        btn_row: list[ft.Control] = [
            ft.IconButton(
                ft.Icons.ZOOM_IN,
                icon_color=theme.SUBTLE,
                icon_size=18,
                tooltip="View full size",
                on_click=self._view,
            )
        ]
        if show_download:
            btn_row.append(
                ft.IconButton(
                    ft.Icons.DOWNLOAD,
                    icon_color=theme.ACCENT,
                    icon_size=18,
                    tooltip="Download to ~/Downloads",
                    on_click=self._download,
                )
            )
        if extra_actions:
            btn_row.extend(extra_actions)

        below.append(ft.Row(btn_row, spacing=0))

        super().__init__(
            content=ft.Column(
                [thumb_box] + below,
                spacing=4,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=theme.SURFACE,
            border=ft.Border.all(1, theme.BORDER),
            border_radius=8,
            padding=6,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            width=card_width + 12,
        )

    def _view(self, e):
        data = _thumb(self._path, max_px=900)
        if not data:
            return
        dlg = ft.AlertDialog(
            content=ft.Image(
                src=data,
                fit=ft.BoxFit.CONTAIN,
                width=700,
                height=540,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda _: self._page.pop_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(dlg)

    def _download(self, e):
        try:
            dest = Path.home() / "Downloads" / Path(self._path).name
            shutil.copy2(self._path, dest)
            msg, color = f"Saved to:\n{dest}", theme.SUCCESS
        except Exception as ex:
            msg, color = f"Error: {ex}", theme.ERROR

        dlg = ft.AlertDialog(
            content=ft.Text(msg, color=color, selectable=True),
            actions=[ft.TextButton("OK", on_click=lambda _: self._page.pop_dialog())],
        )
        self._page.show_dialog(dlg)
