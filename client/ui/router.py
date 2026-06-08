# client/ui/router.py
# Page router with history stack, persistent Shell for authenticated routes.

import flet as ft
from ui import theme

_UNAUTH_ROUTES = {"/", "/login", "/signup"}


class Router:
    def __init__(self, page: ft.Page):
        self.page    = page
        self.session = None
        self.room_id = None
        self._stack:   list[str] = []
        self._current: str       = ""
        self._shell = None

    # â”€â”€ Navigation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def go(self, route: str, _from_back: bool = False):
        if route not in _UNAUTH_ROUTES and self.session is None:
            self._stack.clear()
            route = "/"

        if not _from_back and self._current:
            self._stack.append(self._current)
        self._current = route

        is_auth = self.session is not None and route not in _UNAUTH_ROUTES

        if is_auth:
            self.page.services.clear()
            page_ctrl = self._build(route)

            if self._shell is None:
                from ui.shell import Shell
                self._shell = Shell(self.page, self)
                self.page.controls.clear()
                self.page.overlay.clear()
                self.page.controls.append(self._shell.layout)

            self._shell.set_content(page_ctrl)

        else:
            self._shell = None
            self.page.controls.clear()
            self.page.overlay.clear()
            self.page.services.clear()
            self.page.controls.append(theme.app_header())
            self.page.controls.append(self._build(route))
            self.page.update()

    def back(self):
        if self._stack:
            prev = self._stack.pop()
            self.go(prev, _from_back=True)
        else:
            self.go("/", _from_back=True)

    # â”€â”€ Banner update â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def update_banner(self):
        if self._shell:
            self._shell.update_banner()
            try:
                self.page.update()
            except Exception:
                pass

    # â”€â”€ SnackBar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def show_snack(
        self,
        message:     str,
        color:       str = None,
        action_text: str = None,
        on_action        = None,
    ):
        sb = ft.SnackBar(
            content=ft.Text(message, color=color or theme.TEXT),
            action=action_text,
            on_action=on_action,
            open=True,
            bgcolor=theme.SURFACE,
        )
        self.page.overlay.append(sb)
        try:
            self.page.update()
        except Exception:
            pass

    # â”€â”€ Route â†’ page builder â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _build(self, route: str) -> ft.Control:
        from ui.pages.welcome      import WelcomePage
        from ui.pages.login        import LoginPage
        from ui.pages.signup       import SignupPage
        from ui.pages.user         import UserPage
        from ui.pages.create_model import CreateModelPage
        from ui.pages.models       import ModelsPage
        from ui.pages.creations    import CreationsPage
        from ui.pages.rooms        import RoomsPage
        from ui.pages.room         import RoomPage
        from ui.pages.send         import SendPage
        from ui.pages.shared       import SharedPage

        ROUTES = {
            "/":             WelcomePage,
            "/login":        LoginPage,
            "/signup":       SignupPage,
            "/user":         UserPage,
            "/create-model": CreateModelPage,
            "/models":       ModelsPage,
            "/creations":    CreationsPage,
            "/rooms":        RoomsPage,
            "/room":         RoomPage,
            "/send":         SendPage,
            "/shared":       SharedPage,
        }
        return ROUTES.get(route, WelcomePage)(self.page, self).build()
