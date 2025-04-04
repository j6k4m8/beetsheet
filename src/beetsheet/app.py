"""
Beetsheet app module.
"""

from typing import List, Dict, Any, Optional, Tuple, Set
import os
from pathlib import Path
from textual.app import App, ComposeResult
from textual.command import Command
from textual.widgets import DataTable, Footer, Input, Button, Static
from textual.containers import Container, VerticalScroll, Horizontal
from textual import events
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.coordinate import Coordinate
from textual.screen import Screen

from .metadata import extract_metadata
from .title_guesser import TitleGuesser
from .ui.custom_palette import CustomCommandPalette
from .metadata_writer import save_metadata, save_album_art
from .ui.widgets import EditField
from .ui.bulk_edit_screen import BulkEditScreen
from .album_art import AlbumArtScreen, preview_album_art
from .file_browser import FileBrowserScreen
from .audio_player import AudioPlayer
from .ui.audio_controls import AudioPlayerControls

class CommandInput(Input):
    """A command input that appears at the bottom of the screen."""

    def __init__(self) -> None:
        super().__init__(placeholder=":")
        self.visible = False

    def toggle_visibility(self) -> None:
        """Toggle the visibility of the command input."""
        self.visible = not self.visible
        if self.visible:
            self.focus()

# Create a custom Footer class that doesn't show the command binding
class BeetsheetFooter(Footer):
    """Custom footer that doesn't show the command mode binding."""

    def __init__(self):
        super().__init__()
        # We'll use a custom key binding filter in compose

class BeetsheetApp(App):
    """A spreadsheet-like app for displaying music file metadata."""

    # Add CSS files from the ui/css directory
    CSS_PATH = [
        Path(__file__).parent / "ui" / "css" / "app.css",
        Path(__file__).parent / "ui" / "css" / "command_palette.css",
        Path(__file__).parent / "ui" / "css" / "album_art.css",
        Path(__file__).parent / "ui" / "css" / "file_browser.css",
        Path(__file__).parent / "ui" / "css" / "audio_player.css",
    ]

    CSS = """
    DataTable {
        height: 1fr;
        width: 1fr;
    }

    CommandInput {
        dock: bottom;
        margin: 0 1 0 1;
        background: $surface;
        color: $text;
        height: 1;
    }

    EditField {
        background: $boost;
        color: $text;
        border: none;
        padding: 0;
    }
    """

    # Only include the bindings we want to show
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit"),
        Binding(key="ctrl+p", action="show_command_palette", description="Command Palette"),
        Binding(key="g", action="guess_title", description="Guess Title"),
        Binding(key="G", action="guess_all_titles", description="Guess All Titles"),  # Capital G for shift+g
        Binding(key="s", action="save_changes", description="Save Changes"),
        Binding(key="e", action="edit_cell", description="Edit Cell"),
        Binding(key="escape", action="cancel_edit", description="Cancel Edit"),
        Binding(key="ctrl+a", action="edit_all_artists", description="Edit All Artists"),
        Binding(key="ctrl+l", action="edit_all_albums", description="Edit All Albums"),
        Binding(key="a", action="add_track_album_art", description="Add Album Art"),
        Binding(key="A", action="add_bulk_album_art", description="Add Album Art to Selected"),
        Binding(key="space", action="toggle_select_track", description="Select/Deselect Track"),
        Binding(key="p", action="play_current_audio", description="Play/Pause Track"),
        Binding(key="P", action="stop_audio", description="Stop Playback"),  # Capital P for shift+p
    ]

    def __init__(self, file_paths: List[str]) -> None:
        # Initialize with standard parameters
        super().__init__()
        self.file_paths = file_paths
        self.metadata_list = []
        self.library = None
        self.selected_cell = None
        self.modified_tracks = set()  # Track which files have been modified
        self.editing = False  # Track if we're in edit mode
        self.edit_widget = None
        self.selected_tracks: Set[int] = set()  # Track indices of selected rows
        self.current_action = None  # To track callback context for file browser

        # Initialize audio player
        self.audio_player = AudioPlayer()

        # Set up audio player callbacks
        def on_status_change(is_playing, paused=False):
            # Check if the app is still mounted and has AudioPlayerControls
            try:
                audio_controls = self.query_one(AudioPlayerControls)
                if audio_controls:
                    current_track = self.get_current_track_path()
                    audio_controls.update_status(
                        is_playing=is_playing,
                        is_paused=paused,
                        track_path=current_track if is_playing else None
                    )
            except NoMatches:
                # App is likely shutting down, AudioPlayerControls no longer available
                pass

        def on_finished():
            try:
                audio_controls = self.query_one(AudioPlayerControls)
                if audio_controls:
                    audio_controls.update_status(is_playing=False)
            except NoMatches:
                # App is likely shutting down, AudioPlayerControls no longer available
                pass

        self.audio_player.set_callbacks(
            status_change=on_status_change,
            finished=on_finished
        )

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield DataTable(id="music-table")
        yield AudioPlayerControls()
        yield CommandInput()
        yield BeetsheetFooter()  # Use our custom footer instead

    def on_mount(self) -> None:
        """Load data after the app is mounted."""
        # Make sure CSS directories exist
        css_dir = Path(__file__).parent / "ui" / "css"
        css_dir.mkdir(exist_ok=True, parents=True)

        table = self.query_one(DataTable)
        table.cursor_type = "row"

        # Add columns - add a Status column at the beginning
        table.add_columns("Status", "File", "Artist", "Album", "Title", "Art")

        # Extract metadata and add rows
        for path in self.file_paths:
            try:
                metadata = extract_metadata(path)
                self.metadata_list.append(metadata)
                # Add art indicator if album art exists
                has_art = "✓" if metadata.get("has_album_art", False) else ""
                table.add_row(
                    "",  # Empty status to start
                    os.path.basename(path),
                    metadata.get("artist", "Unknown"),
                    metadata.get("album", "Unknown"),
                    metadata.get("title", "Unknown"),
                    has_art  # Album art indicator
                )
            except Exception as e:
                self.notify(f"Error loading {os.path.basename(path)}: {str(e)}")

        # Create a simple library representation for the title guesser commands
        self.create_library()

        # Set initial selection to the first row if available
        if table.row_count > 0:
            table.cursor_coordinate = (0, 1)  # Default to first row, file column
            self.selected_cell = (0, 4)  # Move selected_cell to title column

        # Initialize the audio player controls
        audio_controls = self.query_one(AudioPlayerControls)
        audio_controls.update_status(False)

    def on_unmount(self) -> None:
        """Clean up resources when the app is closing."""
        if hasattr(self, 'audio_player'):
            # Temporarily remove callbacks to avoid UI updates during shutdown
            self.audio_player.set_callbacks(None, None)
            self.audio_player.cleanup()

    def create_library(self):
        """Create a simple library representation for the UI commands."""
        class Track:
            def __init__(self, path, title):
                self.path = path
                self.title = title

        class Library:
            def __init__(self):
                self.tracks = []

        self.library = Library()
        for i, path in enumerate(self.file_paths):
            title = self.metadata_list[i].get("title", "Unknown")
            track = Track(path, title)
            self.library.tracks.append(track)

    def get_current_track_path(self) -> Optional[str]:
        """Get the file path for the currently selected track."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return None

        row, _ = table.cursor_coordinate
        if row < 0 or row >= len(self.library.tracks):
            return None

        return self.library.tracks[row].path

    def action_play_current_audio(self) -> None:
        """Play or pause the currently selected audio track."""
        track_path = self.get_current_track_path()

        if not track_path:
            self.notify("No track selected")
            return

        # Check if we're already playing this track
        if self.audio_player.is_playing and self.audio_player.current_file == track_path:
            # Toggle pause/resume
            self.action_toggle_pause_audio()
            return

        # Start playing the selected track
        if self.audio_player.play(track_path):
            self.notify(f"Playing: {os.path.basename(track_path)}")
        else:
            self.notify("Failed to play audio. Check if pygame is installed.", severity="error")

    def action_stop_audio(self) -> None:
        """Stop audio playback."""
        if self.audio_player.is_playing:
            self.audio_player.stop()
            self.notify("Playback stopped")

    def action_pause_audio(self) -> None:
        """Pause audio playback."""
        if self.audio_player.is_playing and not self.audio_player.is_paused:
            self.audio_player.pause()
            self.notify("Playback paused")

    def action_resume_audio(self) -> None:
        """Resume audio playback."""
        if self.audio_player.is_playing and self.audio_player.is_paused:
            self.audio_player.resume()
            self.notify("Playback resumed")

    def action_toggle_pause_audio(self) -> None:
        """Toggle between pause and play states."""
        if self.audio_player.is_playing:
            self.audio_player.toggle_pause()
            if self.audio_player.is_paused:
                self.notify("Playback paused")
            else:
                self.notify("Playback resumed")

    # Command palette commands
    def commands(self) -> list[Command]:
        yield Command(
            command_id="guess_title",
            title="Guess Title from Filename",
            description="Guess the title for the currently selected track based on its filename",
            handler=self.action_guess_title,
        )

        yield Command(
            command_id="guess_all_titles",
            title="Guess All Titles",
            description="Guess titles for all tracks based on their filenames",
            handler=self.action_guess_all_titles,
        )

        yield Command(
            command_id="save_changes",
            title="Save Changes",
            description="Save all changes to the music library",
            handler=self.action_save_changes,
        )

        yield Command(
            command_id="edit_all_artists",
            title="Edit All Artists",
            description="Edit artist name for all tracks at once",
            handler=self.action_edit_all_artists,
        )

        yield Command(
            command_id="edit_all_albums",
            title="Edit All Albums",
            description="Edit album name for all tracks at once",
            handler=self.action_edit_all_albums,
        )

        yield Command(
            command_id="add_album_art",
            title="Add Album Art",
            description="Add album art to the current track",
            handler=self.action_add_track_album_art,
        )

        yield Command(
            command_id="add_bulk_album_art",
            title="Add Album Art to Selected",
            description="Add album art to all selected tracks",
            handler=self.action_add_bulk_album_art,
        )

        yield Command(
            command_id="preview_album_art",
            title="Preview Album Art",
            description="Preview the album art for the current track",
            handler=self.action_preview_album_art,
        )

        yield Command(
            command_id="play_current_audio",
            title="Play Current Track",
            description="Play the currently selected audio track",
            handler=self.action_play_current_audio,
        )

        yield Command(
            command_id="stop_audio",
            title="Stop Playback",
            description="Stop audio playback",
            handler=self.action_stop_audio,
        )