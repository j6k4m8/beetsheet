"""
Custom command palette for Beetsheet.
"""

from typing import List, Optional, Dict, Any
from textual.screen import Screen
from textual.widgets import Input, ListView, ListItem
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.message import Message

class CustomCommandPalette(Screen):
    """A command palette for quickly accessing app commands."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close", show=False),
        Binding("enter", "select_command", "Select", show=False),
    ]

    DEFAULT_CSS = """
    CustomCommandPalette {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr;
        background: $surface;
        border: tall $accent;
        height: auto;
        max-height: 60%;
        width: 80%;
        margin: 2 4;
    }

    #search {
        margin: 1 2;
        border: tall $accent-darken-2;
        background: $surface;
        color: $text;
    }

    #results {
        height: auto;
        max-height: 20;
        margin: 0 1 1 1;
        background: $surface;
        border: tall $accent-darken-1;
        color: $text;
    }

    .command-item {
        padding: 0 1;
    }

    .command-item.--highlight {
        background: $accent;
        color: $text;
    }
    """

    class SelectCommand(Message):
        """Message sent when a command is selected."""
        def __init__(self, command_id: str) -> None:
            self.command_id = command_id
            super().__init__()

    def __init__(self):
        super().__init__()
        self.commands = []
        self.filtered_commands = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Input(placeholder="Type to search commands...", id="search")
        yield ListView(id="results")

    def on_mount(self) -> None:
        """Set up the palette when mounted."""
        # Get commands from the app
        self.commands = list(self.app.commands())
        self.filtered_commands = self.commands.copy()

        # Populate the list view
        self.update_command_list()

        # Focus the search input
        search_input = self.query_one("#search", Input)
        search_input.focus()

    def update_command_list(self) -> None:
        """Update the command list with filtered commands."""
        results = self.query_one("#results", ListView)
        results.clear()

        for cmd in self.filtered_commands:
            item = ListItem(Label=f"{cmd.title} - {cmd.description}",
                           classes="command-item",
                           id=f"cmd-{cmd.command_id}")
            item.data = cmd.command_id
            results.append(item)

        if results.index is None and len(self.filtered_commands) > 0:
            results.index = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the commands as the user types."""
        query = event.value.lower()
        if query:
            self.filtered_commands = [
                cmd for cmd in self.commands
                if query in cmd.title.lower() or query in cmd.description.lower()
            ]
        else:
            self.filtered_commands = self.commands.copy()

        self.update_command_list()

    def action_select_command(self) -> None:
        """Select the currently highlighted command."""
        results = self.query_one("#results", ListView)
        if results.index is not None and 0 <= results.index < len(self.filtered_commands):
            selected_item = results.get_item_at(results.index)
            if selected_item and hasattr(selected_item, "data"):
                command_id = selected_item.data
                # Close the palette and run the command
                self.app.pop_screen()
                for cmd in self.commands:
                    if cmd.command_id == command_id:
                        cmd.handler()
                        break
