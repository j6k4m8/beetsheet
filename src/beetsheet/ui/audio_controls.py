"""
Audio player control widgets for Beetsheet.
"""

import os
import re
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Static
from textual.reactive import reactive


class AudioPlayerControls(Horizontal):
    """Widget for controlling audio playback."""

    is_playing = reactive(False)
    is_paused = reactive(False)
    current_track = reactive("")

    def __init__(self, id: str = "audio-player-container"):
        """Initialize audio player controls."""
        super().__init__(id=id)
        self._visible = True

    def compose(self) -> ComposeResult:
        """Compose the audio player UI."""
        # Track information
        yield Static("Not playing", id="now-playing")

        # Player controls
        with Horizontal(id="player-controls"):
            yield Button("▶ Play", id="play-button", variant="primary")
            yield Button("■ Stop", id="stop-button", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "play-button":
            # Toggle between play and pause
            if self.is_playing and not self.is_paused:
                self.app.action_pause_audio()
            elif self.is_paused:
                self.app.action_resume_audio()
            else:
                self.app.action_play_current_audio()
        elif event.button.id == "stop-button":
            # Stop playback
            self.app.action_stop_audio()

    def update_status(self, is_playing: bool, is_paused: bool = False, track_path: str = None) -> None:
        """Update the player status display.

        Args:
            is_playing: Whether audio is currently playing
            is_paused: Whether audio is currently paused
            track_path: Path to the current track (if any)
        """
        self.is_playing = is_playing
        self.is_paused = is_paused

        play_button = self.query_one("#play-button")
        now_playing = self.query_one("#now-playing")

        # Update button text based on state
        if is_playing and not is_paused:
            play_button.label = "⏸ Pause"
            now_playing.remove_class("--paused")
            now_playing.add_class("--playing")
        elif is_paused:
            play_button.label = "▶ Resume"
            now_playing.remove_class("--playing")
            now_playing.add_class("--paused")
        else:
            play_button.label = "▶ Play"
            now_playing.remove_class("--playing")
            now_playing.remove_class("--paused")

        # Update track display
        if track_path and is_playing:
            self.current_track = track_path
            filename = os.path.basename(track_path)
            # Escape any text that might be interpreted as Rich markup or color codes
            safe_filename = self._escape_rich_markup(filename)
            status = "Paused: " if is_paused else "Playing: "
            now_playing.update(f"{status}{safe_filename}")
        else:
            self.current_track = ""
            now_playing.update("Not playing")

    def _escape_rich_markup(self, text: str) -> str:
        """Escape text to prevent Rich markup interpretation.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for display
        """
        # Escape brackets which Rich uses for markup
        escaped = text.replace("[", "\\[").replace("]", "\\]")

        # Handle YouTube IDs in square brackets that could be mistaken for color codes
        escaped = re.sub(r'(\[[a-zA-Z0-9\-_]{11}\])', lambda m: f"\\{m.group(1)}", escaped)

        return escaped

    def show(self) -> None:
        """Show the player controls."""
        self.remove_class("hidden")
        self._visible = True

    def hide(self) -> None:
        """Hide the player controls."""
        self.add_class("hidden")
        self._visible = False

    @property
    def visible(self) -> bool:
        """Get visibility state."""
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        """Set visibility state."""
        if value and not self._visible:
            self.show()
        elif not value and self._visible:
            self.hide()
