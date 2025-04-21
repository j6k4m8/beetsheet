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
        Binding(key="t", action="guess_track", description="Guess Track Number"),
        Binding(key="T", action="guess_all_tracks", description="Guess All Track Numbers"),  # Capital T for shift+t
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

        # Add columns - add a Status column at the beginning and Track# column
        table.add_columns("Status", "Track#", "File", "Artist", "Album", "Title", "Art")

        # Extract metadata and add rows
        for path in self.file_paths:
            try:
                metadata = extract_metadata(path)
                self.metadata_list.append(metadata)
                # Add art indicator if album art exists
                has_art = "✓" if metadata.get("has_album_art", False) else ""
                table.add_row(
                    "",  # Empty status to start
                    metadata.get("track_number", ""),  # Track number
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
            table.cursor_coordinate = Coordinate(0, 2)  # Default to first row, file column
            self.selected_cell = (0, 5)  # Move selected_cell to title column

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

    def action_show_command_palette(self) -> None:
        """Show the command palette."""
        self.push_screen(CustomCommandPalette())

    def action_guess_title(self) -> None:
        """Guess the title for the current track based on its filename."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, _ = table.cursor_coordinate
        if row < 0 or row >= len(self.file_paths):
            return

        # Get the file path and guess the title
        file_path = self.file_paths[row]
        guessed_title = TitleGuesser.guess_title_from_filename(file_path)

        # Update the table and mark as modified
        table.update_cell_at(Coordinate(row, 4), guessed_title)
        self.metadata_list[row]["title"] = guessed_title
        self.modified_tracks.add(row)

        # Update status column to indicate modification
        table.update_cell_at(Coordinate(row, 0), "*")

        self.notify(f"Title guessed: {guessed_title}")

    def action_guess_all_titles(self) -> None:
        """Guess titles for all tracks based on their filenames."""
        table = self.query_one(DataTable)
        count = 0

        for row in range(len(self.file_paths)):
            file_path = self.file_paths[row]
            guessed_title = TitleGuesser.guess_title_from_filename(file_path)

            # Update the table and mark as modified
            table.update_cell_at(Coordinate(row, 4), guessed_title)
            self.metadata_list[row]["title"] = guessed_title
            self.modified_tracks.add(row)

            # Update status column to indicate modification
            table.update_cell_at(Coordinate(row, 0), "*")
            count += 1

        self.notify(f"Guessed titles for {count} tracks")

    def action_save_changes(self) -> None:
        """Save all changes to the music files."""
        table = self.query_one(DataTable)
        saved_count = 0
        error_count = 0

        for row in self.modified_tracks:
            file_path = self.file_paths[row]
            metadata = {
                "title": self.metadata_list[row].get("title", "Unknown"),
                "artist": self.metadata_list[row].get("artist", "Unknown"),
                "album": self.metadata_list[row].get("album", "Unknown"),
                "track_number": self.metadata_list[row].get("track_number", "")
            }

            if save_metadata(file_path, metadata):
                # Clear the status indicator and update count
                table.update_cell_at(Coordinate(row, 0), "")
                saved_count += 1
            else:
                error_count += 1

        # Notify the user about the results
        if saved_count > 0:
            self.notify(f"Saved changes to {saved_count} tracks")
            self.modified_tracks.clear()

        if error_count > 0:
            self.notify(f"Failed to save {error_count} tracks", severity="error")

    def action_edit_cell(self) -> None:
        """Edit the currently selected cell."""
        if self.editing:
            return

        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, column = table.cursor_coordinate

        # Only allow editing track number, artist, album, and title columns (1, 3, 4, 5)
        if column not in (1, 3, 4, 5):
            return

        # Get the current value
        current_value = table.get_cell_at(Coordinate(row, column))

        # Create an edit field and replace the cell content
        self.edit_widget = EditField(value=current_value)
        table.update_cell_at(Coordinate(row, column), self.edit_widget)
        self.edit_widget.focus()
        self.editing = True

        # Store the current cell being edited
        self.selected_cell = (row, column)

    def on_edit_field_submitted(self, event: EditField.Submitted) -> None:
        """Handle edit field submission."""
        if not self.selected_cell:
            return

        row, column = self.selected_cell
        table = self.query_one(DataTable)
        value = event.value

        # Update the metadata based on the column
        if column == 1:  # Track Number
            self.metadata_list[row]["track_number"] = value
        elif column == 3:  # Artist
            self.metadata_list[row]["artist"] = value
        elif column == 4:  # Album
            self.metadata_list[row]["album"] = value
        elif column == 5:  # Title
            self.metadata_list[row]["title"] = value

        # Update the table cell and mark as modified
        table.update_cell_at(Coordinate(row, column), value)
        table.update_cell_at(Coordinate(row, 0), "*")  # Show modification indicator
        self.modified_tracks.add(row)

        # Reset edit state
        self.editing = False
        self.edit_widget = None

    def on_edit_field_cancelled(self, event: EditField.Cancelled) -> None:
        """Handle edit field cancellation."""
        self._restore_cell_value()

    def action_cancel_edit(self) -> None:
        """Cancel the current edit operation."""
        if self.editing and self.edit_widget and self.selected_cell:
            self._restore_cell_value()

    def _restore_cell_value(self) -> None:
        """Restore the original cell value after canceling an edit."""
        if not self.selected_cell:
            return

        row, column = self.selected_cell
        table = self.query_one(DataTable)

        # Get the field name based on column
        field_map = {
            2: "artist",
            3: "album",
            4: "title"
        }

        field_name = field_map.get(column)
        if field_name:
            # Restore the original value
            original_value = self.metadata_list[row].get(field_name, "Unknown")
            table.update_cell_at(Coordinate(row, column), original_value)

        # Reset edit state
        self.editing = False
        self.edit_widget = None

    def action_edit_all_artists(self) -> None:
        """Edit the artist name for all tracks at once."""
        # Get unique artist values
        unique_artists = set()
        for metadata in self.metadata_list:
            unique_artists.add(metadata.get("artist", "Unknown"))

        # Determine default value (most common artist)
        if unique_artists:
            default_artist = max(
                unique_artists,
                key=lambda a: sum(1 for m in self.metadata_list if m.get("artist") == a)
            )
        else:
            default_artist = ""

        # Show bulk edit screen
        self.push_screen(
            BulkEditScreen(
                title="Edit All Artists",
                field_name="artist",
                current_values=list(unique_artists),
                default_value=default_artist,
                on_submit=self.on_bulk_artist_edit
            )
        )

    def on_bulk_artist_edit(self, new_artist: str) -> None:
        """Handle bulk artist name edit submission."""
        if not new_artist:
            return

        table = self.query_one(DataTable)
        count = 0

        for row, metadata in enumerate(self.metadata_list):
            # Update artist
            metadata["artist"] = new_artist
            table.update_cell_at(Coordinate(row, 2), new_artist)

            # Mark as modified
            table.update_cell_at(Coordinate(row, 0), "*")
            self.modified_tracks.add(row)
            count += 1

        self.notify(f"Updated artist for {count} tracks")

    def action_edit_all_albums(self) -> None:
        """Edit the album name for all tracks at once."""
        # Get unique album values
        unique_albums = set()
        for metadata in self.metadata_list:
            unique_albums.add(metadata.get("album", "Unknown"))

        # Determine default value (most common album)
        if unique_albums:
            default_album = max(
                unique_albums,
                key=lambda a: sum(1 for m in self.metadata_list if m.get("album") == a)
            )
        else:
            default_album = ""

        # Show bulk edit screen
        self.push_screen(
            BulkEditScreen(
                title="Edit All Albums",
                field_name="album",
                current_values=list(unique_albums),
                default_value=default_album,
                on_submit=self.on_bulk_album_edit
            )
        )

    def on_bulk_album_edit(self, new_album: str) -> None:
        """Handle bulk album name edit submission."""
        if not new_album:
            return

        table = self.query_one(DataTable)
        count = 0

        for row, metadata in enumerate(self.metadata_list):
            # Update album
            metadata["album"] = new_album
            table.update_cell_at(Coordinate(row, 3), new_album)

            # Mark as modified
            table.update_cell_at(Coordinate(row, 0), "*")
            self.modified_tracks.add(row)
            count += 1

        self.notify(f"Updated album for {count} tracks")

    def action_add_track_album_art(self) -> None:
        """Add album art to the current track."""
        track_path = self.get_current_track_path()
        if not track_path:
            self.notify("No track selected")
            return

        # Store current action for callback context
        self.current_action = "add_art_single"

        # Open file browser to select image
        self.push_screen(
            FileBrowserScreen(
                title="Select Album Art Image",
                extensions=["jpg", "jpeg", "png", "gif", "bmp"],
                on_select=self.on_art_file_selected,
                start_dir=os.path.dirname(track_path)
            )
        )

    def action_add_bulk_album_art(self) -> None:
        """Add album art to all selected tracks."""
        if not self.selected_tracks:
            self.notify("No tracks selected. Select tracks with Space first.")
            return

        # Use the first selected track for directory navigation
        first_selected_idx = min(self.selected_tracks)
        if first_selected_idx >= len(self.file_paths):
            return

        track_path = self.file_paths[first_selected_idx]

        # Store current action for callback context
        self.current_action = "add_art_bulk"

        # Open file browser to select image
        self.push_screen(
            FileBrowserScreen(
                title="Select Album Art Image for Multiple Tracks",
                extensions=["jpg", "jpeg", "png", "gif", "bmp"],
                on_select=self.on_art_file_selected,
                start_dir=os.path.dirname(track_path)
            )
        )

    def on_art_file_selected(self, image_path: str) -> None:
        """Handle album art image selection."""
        if self.current_action == "add_art_single":
            track_path = self.get_current_track_path()
            if track_path and image_path:
                if save_album_art(track_path, image_path):
                    # Update the table to show art indicator
                    table = self.query_one(DataTable)
                    row, _ = table.cursor_coordinate
                    table.update_cell_at(Coordinate(row, 5), "✓")
                    self.notify("Album art added successfully")
                else:
                    self.notify("Failed to add album art", severity="error")

        elif self.current_action == "add_art_bulk":
            table = self.query_one(DataTable)
            success_count = 0
            error_count = 0

            for row in self.selected_tracks:
                if row < len(self.file_paths):
                    track_path = self.file_paths[row]
                    if save_album_art(track_path, image_path):
                        # Update the table to show art indicator
                        table.update_cell_at(Coordinate(row, 5), "✓")
                        success_count += 1
                    else:
                        error_count += 1

            if success_count > 0:
                self.notify(f"Added album art to {success_count} tracks")
            if error_count > 0:
                self.notify(f"Failed to add art to {error_count} tracks", severity="error")

        # Reset action context
        self.current_action = None

    def action_preview_album_art(self) -> None:
        """Preview the album art for the current track."""
        track_path = self.get_current_track_path()
        if not track_path:
            self.notify("No track selected")
            return

        # Show album art preview screen
        self.push_screen(AlbumArtScreen(track_path))

    def action_toggle_select_track(self) -> None:
        """Toggle selection of the current track."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, _ = table.cursor_coordinate

        # Toggle selection
        if row in self.selected_tracks:
            self.selected_tracks.remove(row)
            # Remove selection indicator (could be empty or modified "*")
            is_modified = row in self.modified_tracks
            table.update_cell_at(Coordinate(row, 0), "*" if is_modified else "")
        else:
            self.selected_tracks.add(row)
            # Add selection indicator
            table.update_cell_at(Coordinate(row, 0), "•" if row not in self.modified_tracks else "•*")

        # Update selection count in status bar
        selection_count = len(self.selected_tracks)
        if selection_count > 0:
            self.notify(f"{selection_count} tracks selected")

    def action_guess_track(self) -> None:
        """Guess the track number for the current track from its filename."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, _ = table.cursor_coordinate
        if row < 0 or row >= len(self.file_paths):
            return

        # Get the file path and guess the track number
        file_path = self.file_paths[row]
        guessed_track = TitleGuesser.guess_track_number_from_filename(file_path)

        if guessed_track is not None:
            track_str = str(guessed_track)

            # Update the table and mark as modified
            table.update_cell_at(Coordinate(row, 1), track_str)
            self.metadata_list[row]["track_number"] = track_str
            self.modified_tracks.add(row)

            # Update status column to indicate modification
            table.update_cell_at(Coordinate(row, 0), "*")

            self.notify(f"Track number guessed: {track_str}")
        else:
            self.notify("Could not guess track number from filename", severity="warning")

    def action_guess_all_tracks(self) -> None:
        """Guess track numbers for all tracks based on their filenames."""
        table = self.query_one(DataTable)
        count = 0

        for row in range(len(self.file_paths)):
            file_path = self.file_paths[row]
            guessed_track = TitleGuesser.guess_track_number_from_filename(file_path)

            if guessed_track is not None:
                track_str = str(guessed_track)

                # Update the table and mark as modified
                table.update_cell_at(Coordinate(row, 1), track_str)
                self.metadata_list[row]["track_number"] = track_str
                self.modified_tracks.add(row)

                # Update status column to indicate modification
                table.update_cell_at(Coordinate(row, 0), "*")
                count += 1

        if count > 0:
            self.notify(f"Guessed track numbers for {count} tracks")
        else:
            self.notify("Could not guess track numbers from filenames", severity="warning")