"""
Bulk edit screen for updating multiple tracks at once.
"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import VerticalScroll, Horizontal
from textual.widgets import Button, Label, Input, Static, OptionList
from textual.binding import Binding
from typing import List, Callable, Any


class BulkEditScreen(Screen):
    """A screen for bulk editing artist or album information."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "submit", "Submit"),
    ]

    CSS = """
    BulkEditScreen {
        align: center middle;
    }

    #bulk-edit-container {
        width: 80%;
        height: auto;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        padding: 1;
        text-style: bold;
        color: $text;
    }

    #current-values {
        height: auto;
        max-height: 10;
        overflow-y: scroll;
        margin: 1 0;
    }

    .value-item {
        padding: 0 1;
    }

    #new-value-label {
        margin-top: 1;
    }

    #new-value {
        margin-top: 1;
        border: tall $accent;
    }

    #button-container {
        layout: horizontal;
        width: 100%;
        margin-top: 2;
        align: right middle;
    }

    Button {
        margin: 0 1 0 0;
    }
    """

    def __init__(
        self,
        title: str,
        field_name: str,
        current_values: List[str],
        default_value: str = "",
        on_submit: Callable[[str], None] = None
    ) -> None:
        """Initialize the bulk edit screen.

        Args:
            title: The title to display on the screen
            field_name: The name of the field being edited (artist, album, etc.)
            current_values: A list of the current unique values
            default_value: The default value to pre-fill in the input
            on_submit: A callback function to call with the new value when submitted
        """
        super().__init__()
        self.screen_title = title
        self.field_name = field_name
        self.current_values = current_values
        self.default_value = default_value
        self.on_submit_callback = on_submit

    def compose(self) -> ComposeResult:
        """Compose the screen's widgets."""
        with VerticalScroll(id="bulk-edit-container"):
            yield Label(self.screen_title, id="title")

            yield Label(f"Current {self.field_name.title()} Values:")
            with VerticalScroll(id="current-values"):
                for value in self.current_values:
                    yield Label(value, classes="value-item")

            yield Label(f"Enter New {self.field_name.title()} Value:", id="new-value-label")
            yield Input(value=self.default_value, id="new-value")

            with Horizontal(id="button-container"):
                yield Button("Cancel", variant="error")
                yield Button("Submit", variant="primary")

    def on_mount(self):
        """Set focus to the input when the screen is mounted."""
        self.query_one("#new-value").focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.label == "Cancel":
            self.dismiss()
        elif event.button.label == "Submit":
            self.submit_changes()

    def action_cancel(self) -> None:
        """Cancel the edit and close the screen."""
        self.dismiss()

    def action_submit(self) -> None:
        """Submit the changes and close the screen."""
        self.submit_changes()

    def submit_changes(self) -> None:
        """Get the new value and submit it to the callback."""
        new_value = self.query_one("#new-value").value

        if self.on_submit_callback:
            self.on_submit_callback(new_value)

        self.dismiss()
