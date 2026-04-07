import os
import re
import sys
import webbrowser
from pathlib import Path
from PIL import Image

from rich.text import Text

from textual import work, on
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import (
    Header,
    Footer,
    Button,
    Input,
    Label,
    RichLog,
    LoadingIndicator,
    Switch,
    DirectoryTree,
    Static,
)

# ── ASCII char sets ────────────────────────────────────────────────────────────

ASCII_CHARS_DENSE = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
ASCII_CHARS_STD   = "@%#*+=-:. "

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp", ".ico"}

# ── Core generation logic (untouched) ─────────────────────────────────────────

def resize_image(image, new_width=100):
    width, height = image.size
    aspect_ratio = height / width
    new_height = int(aspect_ratio * new_width * 0.55)
    return image.resize((new_width, new_height))


def grayscale(image):
    return image.convert("L")


def pixels_to_ascii(image, chars=ASCII_CHARS_DENSE):
    pixels = image.getdata()
    ascii_str = ""
    for pixel in pixels:
        ascii_str += chars[pixel * (len(chars) - 1) // 255]
    return ascii_str


def image_to_ascii_colored(image_path, width=120, chars=None, detailed=False):
    ascii_chars = chars if chars else (ASCII_CHARS_DENSE if detailed else ASCII_CHARS_STD)
    try:
        image = Image.open(image_path)
    except Exception as e:
        return None, f"Error opening image: {e}"

    image = resize_image(image, width)
    pixels = list(image.getdata())
    w, h = image.size

    ascii_lines = []
    for y in range(h):
        line = ""
        for x in range(w):
            idx = y * w + x
            pixel = pixels[idx]
            r, g, b = pixel[:3]
            gray = int(0.299 * r + 0.587 * g + 0.114 * b)
            char = ascii_chars[gray * (len(ascii_chars) - 1) // 255]
            line += f"\033[38;2;{r};{g};{b}m{char}\033[0m"
        ascii_lines.append(line)

    return "\n".join(ascii_lines), None


def image_to_ascii_bw(image_path, width=120, chars=None, detailed=False):
    ascii_chars = chars if chars else (ASCII_CHARS_DENSE if detailed else ASCII_CHARS_STD)
    try:
        image = Image.open(image_path)
    except Exception as e:
        return None, f"Error opening image: {e}"

    image = resize_image(image, width)
    image = grayscale(image)
    ascii_str = pixels_to_ascii(image, ascii_chars)
    pixel_count = len(ascii_str)
    ascii_image = "\n".join(
        ascii_str[i:(i + width)] for i in range(0, pixel_count, width)
    )
    return ascii_image, None


# ── File browser modal ─────────────────────────────────────────────────────────

class ImageDirectoryTree(DirectoryTree):
    """DirectoryTree that only shows directories and supported image files."""

    def filter_paths(self, paths):
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() in IMAGE_EXTS
        ]


class FileBrowserScreen(ModalScreen):
    """Modal file picker — navigate directories and select an image file."""

    CSS = """
    FileBrowserScreen {
        align: center middle;
    }

    #browser-dialog {
        width: 70;
        height: 30;
        border: solid $primary;
        background: $surface;
    }

    #browser-title {
        background: $primary;
        color: $text;
        text-align: center;
        height: 1;
        padding: 0 1;
    }

    #browser-cwd {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        background: $panel;
    }

    #browser-tree {
        height: 1fr;
        border-top: solid $primary-darken-2;
        border-bottom: solid $primary-darken-2;
    }

    #browser-hint {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-align: center;
    }
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, start_dir: str = ".") -> None:
        super().__init__()
        self._start_dir = os.path.abspath(start_dir)

    def compose(self) -> ComposeResult:
        with Vertical(id="browser-dialog"):
            yield Static("  Browse for image", id="browser-title")
            yield Static(self._start_dir, id="browser-cwd")
            yield ImageDirectoryTree(self._start_dir, id="browser-tree")
            yield Static("↑↓ navigate   Enter select   Esc cancel", id="browser-hint")

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        event.stop()
        path = event.path
        if path.suffix.lower() in IMAGE_EXTS:
            self.dismiss(str(path))
        else:
            self.notify("Not a supported image file.", severity="warning")

    @on(DirectoryTree.DirectorySelected)
    def on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        event.stop()
        self.query_one("#browser-cwd", Static).update(str(event.path))

    def action_cancel(self) -> None:
        self.dismiss(None)


# ── Main TUI CSS ───────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #0f172a;
    color: #f8fafc;
}

#layout {
    height: 1fr;
}

#sidebar {
    width: 35;
    height: 100%;
    background: #1e293b;
    border-right: solid #334155;
    padding: 1 2;
}

#sidebar Label {
    color: #94a3b8;
    margin-top: 1;
    text-style: bold;
}

#sidebar Input {
    margin-top: 0;
    border: solid #334155;
    background: #0f172a;
}

#sidebar Input:focus {
    border: solid #3b82f6;
}

.switch-row {
    height: 3;
    align: left middle;
}

.switch-label {
    width: 1fr;
    content-align: left middle;
    color: #f1f5f9;
    margin: 0;
}

#path-row {
    height: 3;
    margin-top: 0;
}

#path {
    width: 1fr;
}

#browse {
    width: 10;
    min-width: 10;
    margin-left: 1;
    background: #334155;
}

#generate {
    margin-top: 2;
    width: 100%;
    background: #3b82f6;
    color: #ffffff;
    text-style: bold;
}

#generate:hover {
    background: #2563eb;
}

#save {
    margin-top: 1;
    width: 100%;
    background: #1e293b;
}

#output-area {
    width: 1fr;
    height: 100%;
}

#output {
    width: 1fr;
    height: 1fr;
    padding: 1 2;
    background: #020617;
}

#loader {
    height: 3;
    display: none;
    color: #3b82f6;
}

#loader.active {
    display: block;
}

#status {
    height: 1;
    padding: 0 2;
    color: #64748b;
    background: #0f172a;
}

#branding {
    text-align: center;
    color: #64748b;
    margin-top: 3;
    padding: 1;
    border-top: solid #334155;
    text-style: italic;
}

#branding:hover {
    color: #3b82f6;
    text-style: underline italic;
}
"""


# ── Main app ───────────────────────────────────────────────────────────────────

class AsciiArtApp(App):
    """ASCII Art TUI — convert images to ASCII art with live preview."""

    CSS = CSS
    TITLE = "PiCLI by Kairva Corp."
    BINDINGS = [
        ("ctrl+g", "generate", "Generate"),
        ("ctrl+s", "save",     "Save"),
        ("ctrl+b", "browse",   "Browse"),
        ("ctrl+q", "quit",     "Quit"),
    ]

    _last_output: str | None = None
    _last_was_colored: bool = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="layout"):
            with VerticalScroll(id="sidebar"):
                yield Label("Image path")
                with Horizontal(id="path-row"):
                    yield Input(placeholder="/path/to/image.png", id="path")
                    yield Button("Browse", id="browse", variant="default")

                yield Label("Width")
                yield Input(value="120", placeholder="120", id="width")

                yield Label("Options")

                with Horizontal(classes="switch-row"):
                    yield Switch(id="detailed", value=False)
                    yield Label("  Dense charset", classes="switch-label")

                with Horizontal(classes="switch-row"):
                    yield Switch(id="auto_scale", value=False)
                    yield Label("  Auto-resize window", classes="switch-label")

                yield Label("Custom chars (optional)")
                yield Input(placeholder="dark → light", id="chars")

                yield Button("Generate", id="generate", variant="primary")
                yield Button("Save to file", id="save", variant="default")

                yield Static("[@click=open_link]Built by Kairva Corp[/]", id="branding")

            with Vertical(id="output-area"):
                yield LoadingIndicator(id="loader")
                yield Label("", id="status")
                yield RichLog(id="output", wrap=False, highlight=False, markup=False, max_lines=100_000)

        yield Footer()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_generate(self) -> None:
        self.query_one("#generate", Button).press()

    def action_save(self) -> None:
        self.query_one("#save", Button).press()

    def action_browse(self) -> None:
        self.query_one("#browse", Button).press()

    def action_open_link(self) -> None:
        webbrowser.open("https://github.com/Kairva-Corp")

    # ── Button handler ────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate":
            self._do_generate()
        elif event.button.id == "save":
            self._do_save()
        elif event.button.id == "browse":
            self._open_browser()

    # ── File browser ──────────────────────────────────────────────────────────

    def _open_browser(self) -> None:
        current = self.query_one("#path", Input).value.strip()
        if current and os.path.isfile(current):
            start = os.path.dirname(current)
        elif current and os.path.isdir(current):
            start = current
        else:
            start = os.path.expanduser("/")

        def handle_result(selected: str | None) -> None:
            if selected:
                self.query_one("#path", Input).value = selected

        self.push_screen(FileBrowserScreen(start_dir=start), handle_result)

    # ── Generate ──────────────────────────────────────────────────────────────

    def _do_generate(self) -> None:
        path   = self.query_one("#path", Input).value.strip()
        width  = self.query_one("#width", Input).value.strip()
        color  = True # Output is now permanently colored
        detail = self.query_one("#detailed", Switch).value
        auto_resize = self.query_one("#auto_scale", Switch).value
        chars  = self.query_one("#chars", Input).value.strip() or None

        if not path:
            self.notify("Enter an image path.", severity="error")
            return
        if not os.path.exists(path):
            self.notify(f"File not found: {path}", severity="error")
            return
        try:
            width_int = int(width)
            if width_int < 10 or width_int > 1000:
                raise ValueError
        except ValueError:
            self.notify("Width must be an integer between 10 and 1000.", severity="error")
            return

        if auto_resize:
            try:
                target_cols = 35 + width_int + 4
                with Image.open(path) as img:
                    ratio = img.height / img.width
                target_rows = int(ratio * width_int * 0.55) + 12
                # Clamp to avoid extreme terminal sizes
                target_cols = min(max(target_cols, 80), 350)
                target_rows = min(max(target_rows, 24), 100)
                sys.stdout.write(f"\x1b[8;{target_rows};{target_cols}t")
                sys.stdout.flush()
            except Exception:
                pass 

        log = self.query_one("#output", RichLog)
        log.clear()
        self._set_loading(True)
        self._set_status("Generating…")
        self._last_output = None

        self._run_generation(path, width_int, color, detail, chars)

    @work(thread=True)
    def _run_generation(self, path: str, width: int, color: bool, detail: bool, chars: str | None) -> None:
        if color:
            result, err = image_to_ascii_colored(path, width, chars, detail)
        else:
            result, err = image_to_ascii_bw(path, width, chars, detail)

        self.call_from_thread(self._display_result, result, err, color)

    def _display_result(self, result: str | None, err: str | None, was_colored: bool) -> None:
        self._set_loading(False)
        if err or result is None:
            self.notify(err or "Generation failed.", severity="error")
            self._set_status("Error.")
            return

        log = self.query_one("#output", RichLog)
        for line in result.split("\n"):
            log.write(Text.from_ansi(line))

        self._last_output = result
        self._last_was_colored = was_colored
        lines = result.count("\n") + 1
        self._set_status(f"{lines} lines  |  width {len(result.split(chr(10))[0]) if lines else 0}  |  {'color' if was_colored else 'b&w'}")

    # ── Save ──────────────────────────────────────────────────────────────────

    def _do_save(self) -> None:
        if self._last_output is None:
            self.notify("Nothing to save — generate first.", severity="warning")
            return

        path = self.query_one("#path", Input).value.strip()
        out_path = os.path.splitext(path)[0] + "_ascii.txt"

        clean = re.sub(r"\033\[[0-9;]*m", "", self._last_output)
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(clean)
            self.notify(f"Saved → {out_path}")
        except OSError as e:
            self.notify(f"Save failed: {e}", severity="error")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_loading(self, active: bool) -> None:
        loader = self.query_one("#loader", LoadingIndicator)
        if active:
            loader.add_class("active")
        else:
            loader.remove_class("active")

    def _set_status(self, msg: str) -> None:
        self.query_one("#status", Label).update(msg)


if __name__ == "__main__":
    AsciiArtApp().run()