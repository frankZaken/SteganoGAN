# client/ui/pages/send.py
# Send Model â€” share one of your models directly with another user by username.

import flet as ft
from ui import theme


class SendPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session

    def build(self) -> ft.Control:
        models = get_user_models(self.session.user_id)

        selected  = {"id": None}
        recipient = theme.text_field("Recipient username", width=340)
        status    = ft.Text("", size=13)

        if models:
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
                    scroll=ft.ScrollMode.AUTO,
                ),
                on_change=lambda e: selected.update({"id": int(e.control.value)}),
            )
            models_section = ft.Column([
                theme.label("Select a model to share:"),
                ft.Container(height=4),
                radio_group,
            ], spacing=4)
        else:
            models_section = ft.Column([
                theme.label("You have no models yet."),
                ft.Container(height=4),
                theme.secondary_button(
                    "Create a Model",
                    lambda e: self.router.go("/create-model"),
                    icon=ft.Icons.ADD,
                ),
            ], spacing=8)

        def do_send(e):
            if selected["id"] is None:
                status.value = "Please select a model first."
                status.color = theme.ERROR
                self.page.update()
                return
            name = recipient.value.strip()
            if not name:
                status.value = "Please enter a recipient username."
                status.color = theme.ERROR
                self.page.update()
                return

            ok, err = send_model_to_user(self.session.user_id, name, selected["id"])
            if ok:
                status.value = f"Model sent to {name}!"
                status.color = theme.SUCCESS
                recipient.value  = ""
                selected["id"]   = None
            else:
                status.value = err
                status.color = theme.ERROR
            self.page.update()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.ARROW_BACK,
                            icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                        theme.title("Send Model", size=24),
                    ]),
                    theme.label("Share one of your models directly with another user."),
                    theme.divider(),
                    ft.Container(height=4),
                    models_section,
                    ft.Container(height=16),
                    theme.label("Recipient:"),
                    ft.Container(height=4),
                    recipient,
                    ft.Container(height=12),
                    theme.accent_button("Send", do_send, icon=ft.Icons.SEND),
                    ft.Container(height=8),
                    status,
                ],
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=32,
        )
