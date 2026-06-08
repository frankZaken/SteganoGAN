# client/ui/pages/create_model.py

import flet as ft
from ui import theme


class CreateModelPage:
    def __init__(self, page: ft.Page, router):
        self.page    = page
        self.router  = router
        self.session = router.session

        self.name_field  = theme.text_field("Model name", hint="e.g. My Portrait")
        self.desc_field  = theme.text_field("Description (optional)")
        self.image_path  = None
        self.image_label = ft.Text("No image selected", color=theme.SUBTLE, size=13)
        self.progress    = theme.progress_bar(value=0)
        self.status_text = ft.Text("", color=theme.SUBTLE, size=13)
        self.error_text  = ft.Text("", color=theme.ERROR, size=13)
        self.train_btn   = None
        self.progress.visible = False
        self._picker     = ft.FilePicker()

    async def _pick_image(self, e):
        files = await self._picker.pick_files(allowed_extensions=["jpg", "jpeg", "png"])
        if files:
            self.image_path        = files[0].path
            self.image_label.value = f"âœ“ {files[0].name}"
            self.image_label.color = theme.SUCCESS
            self.page.update()

    def _on_create(self, e):
        name = self.name_field.value.strip()
        if not name:
            self.error_text.value = "Please enter a model name"
            self.page.update()
            return
        if not self.image_path:
            self.error_text.value = "Please select an image"
            self.page.update()
            return

        self.error_text.value  = ""
        self.progress.visible  = True
        self.progress.value    = 0
        self.status_text.value = "Startingâ€¦"
        if self.train_btn:
            self.train_btn.disabled = True
        self.page.update()

        from api.api_model_manager import train_model_async
        from client.api import jobs as job_store

        job_id = job_store.start(name)

        def on_progress(step: str, percent: int):
            job_store.update(job_id, step, percent)
            self.router.update_banner()
            self.progress.value    = percent / 100
            self.status_text.value = step
            try:
                self.page.update()
            except Exception:
                pass

        def on_done(model_id: int):
            job_store.finish(job_id)
            self.router.update_banner()
            self.router.show_snack(
                f"âœ“ Model '{name}' is ready!",
                color=theme.SUCCESS,
                action_text="My Models",
                on_action=lambda e: self.router.go("/models"),
            )

        def on_error(msg: str):
            job_store.fail(job_id, msg)
            self.router.update_banner()
            self.router.show_snack(
                f"Training failed: {msg}",
                color=theme.ERROR,
            )
            self.progress.visible  = False
            self.error_text.value  = f"Error: {msg}"
            self.status_text.value = ""
            if self.train_btn:
                self.train_btn.disabled = False
            try:
                self.page.update()
            except Exception:
                pass

        train_model_async(
            user_id=     self.session.user_id,
            name=        name,
            description= self.desc_field.value.strip(),
            image_path=  self.image_path,
            on_progress= on_progress,
            on_done=     on_done,
            on_error=    on_error,
        )

    def build(self) -> ft.Control:
        self.page.services.append(self._picker)

        self.train_btn = theme.accent_button(
            "Train Model",
            self._on_create,
            icon=ft.Icons.PSYCHOLOGY,
            width=180,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.ARROW_BACK,
                            icon_color=theme.SUBTLE,
                            on_click=lambda e: self.router.back(),
                        ),
                        theme.title("Create Model", size=24),
                    ]),
                    theme.divider(),
                    ft.Container(height=12),

                    theme.label("Train an AI model for your specific image."),
                    theme.label(
                        "Training takes several minutes â€” you can navigate freely while it runs."
                    ),
                    ft.Container(height=12),

                    self.name_field,
                    self.desc_field,
                    ft.Container(height=8),

                    ft.Row([
                        theme.secondary_button(
                            "Select Image", self._pick_image, icon=ft.Icons.IMAGE,
                        ),
                        self.image_label,
                    ], spacing=12),

                    ft.Container(height=16),
                    self.error_text,
                    self.progress,
                    self.status_text,
                    ft.Container(height=8),
                    self.train_btn,
                ],
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
            bgcolor=theme.PRIMARY,
            padding=32,
        )
