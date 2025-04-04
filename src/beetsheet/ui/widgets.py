"""
Custom widgets for the Beetsheet app.
"""

from textual.widgets import Input
from textual.message import Message
from typing import Optional
from rich.style import Style


class EditField(Input):
    """A custom edit field widget for inline editing in tables."""

    class Submitted(Message):
        """Message sent when the edit field is submitted."""
        def __init__(self, input: "EditField", value: str) -> None:
            self.input = input
            self.value = value
            super().__init__()

    class Cancelled(Message):
        """Message sent when the edit field is cancelled."""
        def __init__(self, input: "EditField") -> None:
            self.input = input
            super().__init__()

    def __init__(
        self,
        value: str = "",
        placeholder: str = "",
        password: bool = False,
    ) -> None:
        """Initialize the edit field.

        Args:
            value: The initial value of the input field
            placeholder: Text to display when input is empty
            password: Whether to hide the input text
        """
        super().__init__(value=value, placeholder=placeholder, password=password)
        # Set styles to make it blend with the table
        self.border_title = None

    def _on_key(self, event) -> None:
        """Handle key events."""
        # Handle specific keys for the editor
        if event.key == "escape":
            # Cancel editing
            event.prevent_default()
            event.stop()
            self.post_message(self.Cancelled(self))
        elif event.key == "enter":
            # Submit the edit
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted(self, self.value))
        else:
            # Let the base class handle other keys
            super()._on_key(event)
