# client/ui/pages/rooms.py
# Rooms page â€” create, join, view rooms.

import flet as ft
from ui import theme


class RoomsPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session
        self.rooms   = {"owned": [], "joined": []}

    def _load_rooms(self):
        from api.api_room_manager import get_my_rooms
        self.rooms = get_my_rooms(self.session.user_id)

    def _create_room_dialog(self):
        name_field = theme.text_field("Room name", width=320)
        key_label  = ft.Text("", color=theme.SUCCESS, size=13, selectable=True)

        def do_create(e):
            name = name_field.value.strip()
            if not name:
                return
            from api.api_room_manager import create_room
            room_id, auth_key, _ = create_room(self.session.user_id, name)
            key_label.value      = f"Room ID: {room_id}   Auth Key: {auth_key}"
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Create Room"),
            content=ft.Column([
                theme.label("Give your room a name:"),
                name_field,
                ft.Container(height=4),
                key_label,
                theme.label("Share the Auth Key with people you want to invite."),
            ], spacing=8, tight=True),
            actions=[
                theme.accent_button("Create", do_create),
                ft.TextButton("Close", on_click=lambda e: (self.page.pop_dialog(), self.router.go("/rooms"))),
            ],
        )
        self.page.show_dialog(dlg)

    def _join_room_dialog(self):
        id_field  = theme.text_field("Room ID", hint="123", width=140)
        key_field = theme.text_field("Auth Key", hint="a3f1b2c4...", width=200)
        msg_label = ft.Text("", size=13)

        def do_join(e):
            from api.api_room_manager import join_room
            try:
                room_id = int(id_field.value.strip())
                ok = join_room(self.session.user_id, room_id, key_field.value.strip())
                if ok:
                    msg_label.value = "âœ“ Joined!"
                    msg_label.color = theme.SUCCESS
                else:
                    msg_label.value = "Wrong room ID or key"
                    msg_label.color = theme.ERROR
                self.page.update()
            except ValueError:
                msg_label.value = "Room ID must be a number"
                msg_label.color = theme.ERROR
                self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Join Room"),
            content=ft.Column([
                ft.Row([id_field, key_field], spacing=8),
                msg_label,
            ], spacing=8, tight=True),
            actions=[
                theme.accent_button("Join", do_join),
                ft.TextButton("Cancel", on_click=lambda e: self.page.pop_dialog()),
            ],
        )
        self.page.show_dialog(dlg)

    def _room_card(self, room: dict, owned: bool) -> ft.Control:
        subtitle = f"Auth key: {room['auth_key']}" if owned else f"Room #{room['id']}"
        return theme.card(
            ft.Row([
                ft.Column([
                    theme.body(room["name"]),
                    theme.label(subtitle),
                ], expand=True, spacing=2),
                theme.secondary_button(
                    "Open",
                    lambda e, rid=room["id"]: self._open_room(rid),
                    width=80,
                    icon=ft.Icons.OPEN_IN_NEW,
                ),
            ]),
        )

    def _open_room(self, room_id: int):
        self.router.room_id = room_id
        self.router.go("/room")

    def build(self) -> ft.Control:
        self._load_rooms()

        owned_cards  = [self._room_card(r, owned=True)  for r in self.rooms["owned"]]
        joined_cards = [self._room_card(r, owned=False) for r in self.rooms["joined"]]

        def section(title: str, cards: list, empty_msg: str):
            if not cards:
                cards = [theme.label(empty_msg)]
            return ft.Column([theme.subtitle(title)] + cards, spacing=8)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_BACK, icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                        theme.title("Rooms", size=24),
                    ]),
                    theme.divider(),
                    ft.Row([
                        theme.accent_button("Create Room", self._create_room_dialog, icon=ft.Icons.ADD, width=150),
                        theme.secondary_button("Join Room", self._join_room_dialog, icon=ft.Icons.LOGIN, width=150),
                    ], spacing=12),
                    ft.Container(height=8),
                    section("Your Rooms",    owned_cards,  "No rooms yet"),
                    ft.Container(height=8),
                    section("Rooms You're In", joined_cards, "Not in any rooms yet"),
                ],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=32,
        )
