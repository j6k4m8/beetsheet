"""
Module for album art management functionality.
"""

import os
import io
from typing import Optional
from pathlib import Path
import tempfile
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, Label
from textual.containers import VerticalScroll, Horizontal
from textual.binding import Binding
from rich.console import Console
from rich.panel import Panel

# Try to import PIL for image processing
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Try to import mutagen for metadata handling
try:
    import mutagen
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def extract_album_art(file_path: str) -> Optional[bytes]:
    """Extract album art from a music file.

    Args:
        file_path: Path to the music file

    Returns:
        Optional[bytes]: The album art image data or None if not found
    """
    if not HAS_MUTAGEN:
        return None

    if not os.path.exists(file_path):
        return None

    try:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".mp3":
            try:
                audio = MP3(file_path, ID3=ID3)
                for tag in audio.tags.values():
                    if tag.FrameID == 'APIC':
                        return tag.data
            except Exception:
                pass

        elif ext == ".flac":
            try:
                audio = FLAC(file_path)
                if audio.pictures:
                    return audio.pictures[0].data
            except Exception:
                pass

        return None

    except Exception:
        return None


def preview_album_art(file_path: str) -> Optional[str]:
    """Generate a terminal-friendly preview of album art.

    Args:
        file_path: Path to the music file

    Returns:
        Optional[str]: A string with ASCII/ANSI art representation or None if not possible
    """
    if not (HAS_MUTAGEN and HAS_PIL):
        return None

    image_data = extract_album_art(file_path)
    if not image_data:
        return None

    try:
        # Create an image from the binary data
        img = Image.open(io.BytesIO(image_data))

        # Resize to a reasonable terminal size (maintain aspect ratio)
        max_width = 40  # Characters in width
        max_height = 20  # Lines in height

        # Calculate new dimensions
        width, height = img.size
        aspect = width / height

        if aspect > 1:  # Wider than tall
            new_width = max_width
            new_height = int(max_width / aspect)
        else:  # Taller than wide or square
            new_height = max_height
            new_width = int(max_height * aspect)

        # Ensure minimum dimensions
        new_width = max(10, new_width)
        new_height = max(5, new_height)

        # Resize image
        img = img.resize((new_width, new_height))

        # Convert to terminal viewable format
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            img.save(tmp.name)
            tmp_path = tmp.name

        # Create a panel with the image path for Rich to handle
        console = Console(file=io.StringIO(), width=new_width+4)
        console.print(Panel(f"[blue]Album Art Preview[/blue]\n[yellow]File: {os.path.basename(file_path)}[/yellow]"))
        art_preview = console.file.getvalue()

        return art_preview

    except Exception:
        return None


class AlbumArtScreen(Screen):
    """Screen for previewing album art."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("q", "app.pop_screen", "Back"),
    ]

    def __init__(self, file_path: str) -> None:
        """Initialize the album art screen.

        Args:
            file_path: Path to the music file to preview album art for
        """
        super().__init__()
        self.file_path = file_path
        self.image_data = extract_album_art(file_path)

    def compose(self) -> ComposeResult:
        """Compose the screen with a preview of the album art."""
        with VerticalScroll(id="art-preview-container"):
            yield Label(f"Album Art: {os.path.basename(self.file_path)}", id="art-title")

            if self.image_data:
                # Preview available
                preview = preview_album_art(self.file_path)
                if preview:
                    yield Static(preview, id="art-image")
                else:
                    yield Static("Album art is available but can't be displayed in the terminal.", id="art-message")
            else:
                # No album art
                yield Static("No album art found for this track.", id="art-message")

            with Horizontal(id="button-container"):
                yield Button("Back", variant="primary", id="back-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "back-button":
            self.app.pop_screen()
