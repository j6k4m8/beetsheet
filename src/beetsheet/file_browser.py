"""
File browser screen for selecting files using Textual.
"""

import os
from pathlib import Path
from typing import List, Callable, Optional, Set
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Button, Label, DirectoryTree, Footer, Static
from textual.containers import Horizontal, VerticalScroll, Vertical
from textual.binding import Binding


class FileBrowserScreen(Screen):
    """Screen for browsing and selecting files."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cancel"),
        Binding("f5", "refresh_directory", "Refresh"),
    ]

    def __init__(
        self,
        title: str = "Select a File",
        extensions: List[str] = None,
        on_select: Callable[[str], None] = None,
        start_dir: str = None
    ):
        """Initialize file browser screen.

        Args:
            title: Title to display at the top of the screen
            extensions: List of file extensions to filter (e.g. ['.mp3', '.jpg'])
            on_select: Callback function when a file is selected
            start_dir: Starting directory (defaults to user's home dir)
        """
        super().__init__()
        self.title_text = title
        self.extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions] if extensions else None
        self.on_select_callback = on_select
        self.start_dir = start_dir or os.path.expanduser("~")
        self.file_selected = False
        self.current_path = None

    def compose(self) -> ComposeResult:
        """Compose file browser UI."""
        with Vertical(id="file-browser-container"):
            yield Label(self.title_text, id="file-browser-title")

            with Horizontal(id="file-browser-main"):
                # Directory navigation tree
                yield DirectoryTree(self.start_dir, id="directory-tree")

                # Right panel with file info and buttons
                with Vertical(id="file-info-panel"):
                    yield Label("Selected File:", id="selected-file-label")
                    yield Static("No file selected", id="selected-file-path")

                    # Button container at the bottom
                    with Horizontal(id="file-browser-buttons"):
                        yield Button("Cancel", variant="error", id="cancel-button")
                        yield Button("Select", variant="success", id="select-button", disabled=True)

            # Filter information
            if self.extensions:
                extensions_text = ", ".join(self.extensions)
                yield Label(f"File filter: {extensions_text}", id="file-filter-info")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in the directory tree."""
        path = event.path

        # Check if file extension matches filter
        if self.extensions and not any(str(path).lower().endswith(ext) for ext in self.extensions):
            # File doesn't match filter
            self.query_one("#selected-file-path").update(f"Not a valid file type: {os.path.basename(path)}")
            self.query_one("#select-button").disabled = True
            self.file_selected = False
            self.current_path = None
            return

        # Valid file selected
        # Convert path to string before updating the Static widget
        self.query_one("#selected-file-path").update(str(path))
        self.query_one("#select-button").disabled = False
        self.file_selected = True
        self.current_path = path

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "select-button" and self.file_selected:
            if self.on_select_callback and self.current_path:
                self.on_select_callback(self.current_path)
            self.app.pop_screen()
        elif event.button.id == "cancel-button":
            self.app.pop_screen()

    def action_refresh_directory(self) -> None:
        """Refresh the directory tree."""
        directory_tree = self.query_one(DirectoryTree)
        directory_tree.reload()
