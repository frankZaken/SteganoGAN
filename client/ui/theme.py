# client/ui/theme.py
# Color palette and reusable Flet component helpers.

import flet as ft

# ── Colors ─────────────────────────────────────────────────────────────────────
PRIMARY  = "#0D1117"
SURFACE  = "#161B22"
BORDER   = "#30363D"
TEXT     = "#E6EDF3"
SUBTLE   = "#8B949E"
ACCENT   = "#58A6FF"
ACCENT2  = "#BC8CFF"
SUCCESS  = "#3FB950"
ERROR    = "#F85149"


# ── Typography ─────────────────────────────────────────────────────────────────

def title(text: str, size: int = 28) -> ft.Text:
    return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=TEXT)

def subtitle(text: str) -> ft.Text:
    return ft.Text(text, size=16, weight=ft.FontWeight.W_600, color=TEXT)

def body(text: str) -> ft.Text:
    return ft.Text(text, size=14, color=TEXT)

def label(text: str) -> ft.Text:
    return ft.Text(text, size=12, color=SUBTLE)


# ── Inputs ─────────────────────────────────────────────────────────────────────

def text_field(
    label_text: str,
    hint:       str  = None,
    width:      int  = None,
    password:   bool = False,
) -> ft.TextField:
    return ft.TextField(
        label=               label_text,
        hint_text=           hint,
        width=               width,
        password=            password,
        can_reveal_password= password,
        border_color=        BORDER,
        focused_border_color=ACCENT,
        label_style=         ft.TextStyle(color=SUBTLE),
        text_style=          ft.TextStyle(color=TEXT),
        bgcolor=             SURFACE,
        cursor_color=        ACCENT,
    )

def progress_bar(value: float = 0) -> ft.ProgressBar:
    return ft.ProgressBar(value=value, color=ACCENT, bgcolor=BORDER)


# ── Buttons ────────────────────────────────────────────────────────────────────

def _btn_content(text: str, icon=None, color: str = TEXT) -> ft.Control:
    if icon is not None:
        return ft.Row(
            [ft.Icon(icon, color=color, size=18), ft.Text(text, color=color)],
            tight=True, spacing=8,
        )
    return ft.Text(text, color=color)


def accent_button(
    text:     str,
    on_click,
    icon      = None,
    width:    int = None,
) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        content=  _btn_content(text, icon, color="#0D1117"),
        width=    width,
        on_click= on_click,
        style=    ft.ButtonStyle(
            bgcolor= {ft.ControlState.DEFAULT: ACCENT,
                      ft.ControlState.HOVERED: "#79B8FF"},
            shape=   ft.RoundedRectangleBorder(radius=6),
        ),
    )

def secondary_button(
    text:     str,
    on_click,
    icon      = None,
    width:    int = None,
) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=  _btn_content(text, icon, color=TEXT),
        width=    width,
        on_click= on_click,
        style=    ft.ButtonStyle(
            side=  {ft.ControlState.DEFAULT: ft.BorderSide(1, BORDER),
                    ft.ControlState.HOVERED: ft.BorderSide(1, ACCENT)},
            shape= ft.RoundedRectangleBorder(radius=6),
        ),
    )

def danger_button(text: str, on_click, width: int = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        content=  _btn_content(text, color=ERROR),
        width=    width,
        on_click= on_click,
        style=    ft.ButtonStyle(
            bgcolor= {ft.ControlState.DEFAULT: "#2D1B1B",
                      ft.ControlState.HOVERED: "#3D2020"},
            side=    {ft.ControlState.DEFAULT: ft.BorderSide(1, ERROR)},
            shape=   ft.RoundedRectangleBorder(radius=6),
        ),
    )


# ── Layout helpers ─────────────────────────────────────────────────────────────

def divider() -> ft.Divider:
    return ft.Divider(color=BORDER, height=1)

def app_header() -> ft.Container:
    return ft.Container(
        content=ft.Row([
            ft.Container(width=14),
            ft.Icon(ft.Icons.SECURITY, color=ACCENT, size=20),
            ft.Container(width=8),
            ft.Text("SteganoGAN", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
        ], spacing=0),
        bgcolor="#07111D",
        border=ft.Border(bottom=ft.BorderSide(1, BORDER)),
        height=44,
    )


def card(content: ft.Control) -> ft.Container:
    return ft.Container(
        content=      content,
        bgcolor=      SURFACE,
        border=       ft.Border.all(1, BORDER),
        border_radius=8,
        padding=      16,
    )
