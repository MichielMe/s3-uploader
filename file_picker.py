from textual import work
from textual.app import App, ComposeResult
from textual_fspicker import FileOpen


class BasicFileOpenApp(App[None]):
    def compose(self) -> ComposeResult:
        # No widgets needed - file picker shows immediately
        return []

    @work
    async def on_mount(self) -> None:
        """Show the file picker immediately when the app starts."""
        if opened := await self.push_screen_wait(FileOpen()):
            self.exit(opened)
        else:
            # User cancelled, exit with None
            self.exit(None)


if __name__ == "__main__":
    result = BasicFileOpenApp().run()
    if result is not None:
        print(str(result))
