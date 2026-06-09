# client/ui/shell.py
# Persistent collapsible sidebar + main-content shell for authenticated routes.

import flet as ft
from ui import theme

_WIDE      = 220
_COLLAPSED =  60


class Shell:
    def __init__(self, page: ft.Page, router):
        self.page   = page
        self.router = router

        self._collapsed      = False
        self._rooms_expanded = True

        # â”€â”€ Banner (training progress strip) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._banner_text = ft.Text("", size=12, color=theme.TEXT)
        self._banner_bar  = ft.ProgressBar(
            value=0, color=theme.ACCENT, bgcolor=theme.BORDER, height=3,
        )
        self._banner_row = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=theme.ACCENT),
                    self._banner_text,
                ], spacing=8),
                self._banner_bar,
            ], spacing=4),
            bgcolor="#0D1F2D",
            border=ft.Border(bottom=ft.BorderSide(1, theme.BORDER)),
            padding=ft.Padding(left=16, top=6, right=16, bottom=6),
            visible=False,
        )

        # â”€â”€ Sidebar & main area â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self._sidebar = ft.Container(
            width=_WIDE,
            bgcolor="#0A1628",
            border=ft.Border(right=ft.BorderSide(1, theme.BORDER)),
        )
        self._main = ft.Container(expand=True, bgcolor=theme.PRIMARY)

        self._sidebar.content = self._build_sidebar_content()

        self.layout = ft.Column(
            [
                theme.app_header(),
                self._banner_row,
                ft.Row(
                    [self._sidebar, self._main],
                    spacing=0,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                ),
            ],
            spacing=0,
            expand=True,
        )

    # â”€â”€ Public API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def set_content(self, content: ft.Control):
        self._main.content = content
        self._sidebar.content = self._build_sidebar_content()
        self.update_banner()
        try:
            self.page.update()
        except Exception:
            pass

    def update_banner(self):
        from api.jobs import active, cleanup
        cleanup()
        running = active()
        if running:
            parts = [f"'{j['name']}' {j['percent']}% â€” {j['step']}" for j in running]
            self._banner_text.value  = "Training: " + " | ".join(parts)
            self._banner_bar.value   = running[0]["percent"] / 100
            self._banner_row.visible = True
        else:
            self._banner_row.visible = False

    # â”€â”€ Sidebar content builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build_sidebar_content(self) -> ft.Control:
        col     = self._collapsed
        exp     = self._rooms_expanded
        session = self.router.session
        current = self.router._current
        username = getattr(session, "username", "") if session else ""

        rooms_own  = []
        rooms_join = []
        if session:
            try:
                data       = get_my_rooms(session.user_id)
                rooms_own  = data.get("owned",  [])
                rooms_join = data.get("joined", [])
            except Exception:
                pass

        def nav_item(icon, label, route):
            active = (current == route)
            if col:
                return ft.Container(
                    content=ft.Icon(icon,
                                    color=theme.ACCENT if active else theme.SUBTLE,
                                    size=20),
                    width=_COLLAPSED,
                    height=40,
                    alignment=ft.Alignment(0, 0),
                    bgcolor=theme.SURFACE if active else "transparent",
                    border_radius=4,
                    on_click=lambda e, r=route: self.router.go(r),
                    tooltip=label,
                )
            accent_bar = ft.Container(
                width=3, height=32,
                bgcolor=theme.ACCENT if active else "transparent",
            )
            return ft.Container(
                content=ft.Row([
                    accent_bar,
                    ft.Container(width=10),
                    ft.Icon(icon,
                            color=theme.ACCENT if active else theme.SUBTLE,
                            size=18),
                    ft.Container(width=8),
                    ft.Text(
                        label,
                        color=theme.TEXT if active else theme.SUBTLE,
                        size=13,
                        weight=ft.FontWeight.W_500 if active else ft.FontWeight.NORMAL,
                    ),
                ], spacing=0),
                height=40,
                bgcolor=theme.SURFACE if active else "transparent",
                border_radius=4,
                on_click=lambda e, r=route: self.router.go(r),
            )

        def room_item(room: dict, owned: bool):
            is_active = (current == "/room" and self.router.room_id == room["id"])
            if col:
                return ft.Container(
                    content=ft.Icon(
                        ft.Icons.STAR if owned else ft.Icons.FORUM,
                        color="#F0C040" if owned else theme.SUBTLE,
                        size=16,
                    ),
                    width=_COLLAPSED,
                    height=34,
                    alignment=ft.Alignment(0, 0),
                    bgcolor=theme.SURFACE if is_active else "transparent",
                    border_radius=4,
                    tooltip=room["name"],
                    on_click=lambda e, rid=room["id"]: self._open_room(rid),
                )
            name = room["name"]
            if len(name) > 18:
                name = name[:17] + "â€¦"
            return ft.Container(
                content=ft.Row([
                    ft.Container(width=16),
                    ft.Icon(
                        ft.Icons.STAR if owned else ft.Icons.FORUM,
                        color="#F0C040" if owned else theme.SUBTLE,
                        size=13,
                    ),
                    ft.Container(width=6),
                    ft.Text(name,
                            color=theme.TEXT if is_active else theme.SUBTLE,
                            size=12),
                ], spacing=0),
                height=32,
                bgcolor=theme.SURFACE if is_active else "transparent",
                border_radius=4,
                on_click=lambda e, rid=room["id"]: self._open_room(rid),
            )

        toggle_icon = ft.Icons.CHEVRON_LEFT if not col else ft.Icons.CHEVRON_RIGHT
        toggle_btn  = ft.IconButton(
            toggle_icon,
            icon_color=theme.SUBTLE,
            icon_size=18,
            on_click=self._toggle_collapse,
            tooltip="Collapse sidebar" if not col else "Expand sidebar",
        )

        if col:
            top_row = ft.Column([
                ft.Container(
                    content=toggle_btn,
                    width=_COLLAPSED,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Container(
                    content=ft.IconButton(
                        ft.Icons.ACCOUNT_CIRCLE,
                        icon_color=theme.ACCENT,
                        icon_size=22,
                        on_click=self._account_menu,
                        tooltip=username,
                    ),
                    width=_COLLAPSED,
                    alignment=ft.Alignment(0, 0),
                ),
            ], spacing=0)
        else:
            user_btn = ft.Container(
                content=ft.Row([
                    ft.Container(width=12),
                    ft.Icon(ft.Icons.ACCOUNT_CIRCLE, color=theme.ACCENT, size=18),
                    ft.Container(width=6),
                    ft.Text(username, color=theme.TEXT, size=13,
                            weight=ft.FontWeight.W_500, expand=True),
                    ft.Icon(ft.Icons.EXPAND_MORE, color=theme.SUBTLE, size=14),
                    ft.Container(width=4),
                ], spacing=0),
                height=38,
                border_radius=6,
                bgcolor="#0D1F2D",
                on_click=self._account_menu,
                tooltip="Account options",
                expand=True,
            )
            top_row = ft.Row(
                [user_btn, toggle_btn],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        if col:
            rooms_hdr  = ft.Container(
                content=ft.Icon(ft.Icons.PEOPLE, color=theme.SUBTLE, size=20),
                width=_COLLAPSED,
                height=40,
                alignment=ft.Alignment(0, 0),
                on_click=lambda e: self.router.go("/rooms"),
                tooltip="Rooms",
            )
            room_items = []
        else:
            rooms_hdr = ft.Container(
                content=ft.Row([
                    ft.Container(width=13),
                    ft.Icon(ft.Icons.PEOPLE, color=theme.SUBTLE, size=18),
                    ft.Container(width=8),
                    ft.Text("Rooms", color=theme.SUBTLE, size=13, expand=True),
                    ft.IconButton(
                        ft.Icons.EXPAND_LESS if exp else ft.Icons.EXPAND_MORE,
                        icon_color=theme.SUBTLE,
                        icon_size=16,
                        on_click=self._toggle_rooms,
                    ),
                ], spacing=0),
                height=40,
                on_click=lambda e: self.router.go("/rooms"),
            )
            if exp:
                all_rooms  = [(r, True) for r in rooms_own] + [(r, False) for r in rooms_join]
                room_items = [room_item(r, o) for r, o in all_rooms]
                if not all_rooms:
                    room_items = [ft.Container(
                        content=ft.Text("No rooms yet", color=theme.SUBTLE,
                                        size=11, italic=True),
                        padding=ft.Padding(left=36, top=2, right=0, bottom=2),
                        height=28,
                    )]
            else:
                room_items = []

        shared_active = (current == "/shared")
        if col:
            bottom_ctrl = ft.Container(
                content=ft.Icon(
                    ft.Icons.MOVE_TO_INBOX,
                    color=theme.ACCENT if shared_active else theme.SUBTLE,
                    size=18,
                ),
                width=_COLLAPSED,
                height=36,
                alignment=ft.Alignment(0, 0),
                bgcolor=theme.SURFACE if shared_active else "transparent",
                border_radius=4,
                on_click=lambda e: self.router.go("/shared"),
                tooltip="Shared With Me",
            )
        else:
            bottom_ctrl = ft.Container(
                content=ft.Row([
                    ft.Container(width=14),
                    ft.Icon(
                        ft.Icons.MOVE_TO_INBOX,
                        color=theme.ACCENT if shared_active else theme.SUBTLE,
                        size=16,
                    ),
                    ft.Container(width=8),
                    ft.Text(
                        "Shared With Me",
                        color=theme.TEXT if shared_active else theme.SUBTLE,
                        size=12,
                    ),
                ], spacing=0),
                height=36,
                bgcolor=theme.SURFACE if shared_active else "transparent",
                border_radius=4,
                on_click=lambda e: self.router.go("/shared"),
            )

        return ft.Column(
            [
                ft.Container(
                    content=top_row,
                    padding=ft.Padding(left=4, top=4, right=4, bottom=4),
                ),
                ft.Divider(height=1, color=theme.BORDER, thickness=1),
                ft.Container(height=4),
                nav_item(ft.Icons.ADD_CIRCLE_OUTLINE, "Create Model",   "/create-model"),
                nav_item(ft.Icons.VIEW_LIST,           "My Models",     "/models"),
                nav_item(ft.Icons.COLLECTIONS,         "Creations",     "/creations"),
                nav_item(ft.Icons.SEND,                "Send Model",    "/send"),
                ft.Container(height=4),
                ft.Divider(height=1, color=theme.BORDER, thickness=1),
                ft.Container(height=4),
                rooms_hdr,
                *room_items,
                ft.Container(expand=True),
                ft.Divider(height=1, color=theme.BORDER, thickness=1),
                bottom_ctrl,
                ft.Container(height=4),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            expand=True,
        )

    # â”€â”€ Toggle handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _toggle_collapse(self, e):
        self._collapsed       = not self._collapsed
        self._sidebar.width   = _COLLAPSED if self._collapsed else _WIDE
        self._sidebar.content = self._build_sidebar_content()
        try:
            self.page.update()
        except Exception:
            pass

    def _toggle_rooms(self, e):
        self._rooms_expanded  = not self._rooms_expanded
        self._sidebar.content = self._build_sidebar_content()
        try:
            self.page.update()
        except Exception:
            pass

    def _open_room(self, room_id: int):
        self.router.room_id = room_id
        self.router.go("/room")

    # â”€â”€ Account menu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _account_menu(self, e):
        session  = self.router.session
        username = getattr(session, "username", "") if session else ""

        def _row(icon, label, on_click, color=theme.TEXT):
            return ft.Container(
                content=ft.Row([
                    ft.Icon(icon, color=color, size=18),
                    ft.Container(width=10),
                    ft.Text(label, color=color, size=13),
                ], spacing=0),
                height=40,
                border_radius=6,
                padding=ft.Padding(left=8, top=0, right=8, bottom=0),
                on_click=on_click,
                ink=True,
            )

        def do_edit(e):
            self.page.pop_dialog()
            self._edit_account_dialog()

        def do_change_user(e):
            self.page.pop_dialog()
            self._logout_and_go("/login")

        def do_logout(e):
            self.page.pop_dialog()
            self._logout_and_go("/")

        def do_delete(e):
            self.page.pop_dialog()
            self._confirm_delete_dialog()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text(username, size=15, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                _row(ft.Icons.EDIT,           "Edit Account",   do_edit),
                _row(ft.Icons.SWAP_HORIZ,     "Change User",    do_change_user),
                _row(ft.Icons.LOGOUT,         "Log Out",        do_logout),
                ft.Divider(color=theme.BORDER, height=1),
                _row(ft.Icons.DELETE_FOREVER, "Delete Account", do_delete,
                     color=theme.ERROR),
            ], spacing=4, tight=True, width=260),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        ))

    def _logout_and_go(self, route: str):
        log_out(self.router.session)
        self.router.session = None
        self.router._shell  = None
        self.router._stack  = []
        self.router.go(route)

    def _edit_account_dialog(self):
        pw_field  = theme.text_field("New password", password=True, width=280)
        pw2_field = theme.text_field("Confirm password", password=True, width=280)
        msg_ctrl  = ft.Text("", size=12)

        def do_change(e):
            if pw_field.value != pw2_field.value:
                msg_ctrl.value = "Passwords do not match"
                msg_ctrl.color = theme.ERROR
                self.page.update()
                return

            ok, err = change_password(self.router.session, pw_field.value)
            if ok:
                msg_ctrl.value = "Password updated!"
                msg_ctrl.color = theme.SUCCESS
            else:
                msg_ctrl.value = err
                msg_ctrl.color = theme.ERROR
            self.page.update()

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Edit Account"),
            content=ft.Column([
                theme.label("Change your password:"),
                ft.Container(height=6),
                pw_field,
                pw2_field,
                msg_ctrl,
            ], spacing=8, tight=True),
            actions=[
                theme.accent_button("Save", do_change),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        ))

    def _confirm_delete_dialog(self):
        confirm_field = theme.text_field(
            "Type your username to confirm", width=300,
        )
        session  = self.router.session
        username = getattr(session, "username", "") if session else ""

        def do_delete(e):
            if confirm_field.value.strip() != username:
                self.router.show_snack("Username doesn't match.", color=theme.ERROR)
                self.page.pop_dialog()
                return

            delete_account(self.router.session)
            self.router.session = None
            self.router._shell  = None
            self.page.pop_dialog()
            self.router.go("/")

        self.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Delete Account", color=theme.ERROR),
            content=ft.Column([
                ft.Text(
                    "This permanently deletes your account, models, and creations.",
                    color=theme.SUBTLE, size=13,
                ),
                ft.Container(height=8),
                confirm_field,
            ], spacing=6, tight=True),
            actions=[
                theme.danger_button("Delete Forever", do_delete),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        ))
