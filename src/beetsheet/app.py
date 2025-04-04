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

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield DataTable(id="music-table")
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

    def notify(self, message: str, title: str = None, severity: str = "information", **kwargs) -> None:
        """Override the default notify method to handle potential rich markup conflicts.

        Args:
            message: The message to show in the notification
            title: Optional title for the notification
            severity: Severity of the notification (information, warning, error)
            **kwargs: Additional keyword arguments to pass to the parent notify method
        """
        # Escape any characters in the message that might be interpreted as markup
        # Particularly important for filenames containing YouTube IDs which look like CSS colors
        safe_message = str(message).replace("[", "\\[").replace("]", "\\]")

        # If there's a title, escape it too
        safe_title = None
        if title:
            safe_title = str(title).replace("[", "\\[").replace("]", "\\]")

        # Call the parent notify method with corrected arguments
        super().notify(message=safe_message, title=safe_title, severity=severity, **kwargs)

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Handle cell selection in the data table."""
        self.selected_cell = (event.coordinate.row, event.coordinate.column)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        # When a row is selected, store both row key and index
        table = self.query_one(DataTable)
        row_index = None

        # Try to find the index of the selected row
        for i, row_key in enumerate(table.rows):
            if row_key == event.row_key:
                row_index = i
                break

        # Store both the row key and the numeric index if we found it
        self.selected_cell = {
            'row_key': event.row_key,
            'row_index': row_index,
            'column': 3  # Title column
        }

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

    def action_toggle_command(self) -> None:
        """Toggle the command input visibility."""
        command_input = self.query_one(CommandInput)
        command_input.toggle_visibility()

    def action_show_command_palette(self) -> None:
        """Show the command palette."""
        self.push_screen(CustomCommandPalette())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input submission."""
        command_input = self.query_one(CommandInput)
        command = event.value

        # Clear and hide the command input
        command_input.value = ""
        command_input.toggle_visibility()

    def action_toggle_select_track(self) -> None:
        """Toggle selection of the current track."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, _ = table.cursor_coordinate

        if row in self.selected_tracks:
            self.selected_tracks.remove(row)
            table.update_cell_at(Coordinate(row, 0), "*" if self.library.tracks[row].path in self.modified_tracks else "")
            self.notify(f"Deselected track: {os.path.basename(self.library.tracks[row].path)}")
        else:
            self.selected_tracks.add(row)
            table.update_cell_at(Coordinate(row, 0), "➤")
            self.notify(f"Selected track: {os.path.basename(self.library.tracks[row].path)}")

    async def action_add_track_album_art(self) -> None:
        """Browse for and add album art to the current track."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            self.notify("No track selected")
            return

        row, _ = table.cursor_coordinate

        if row < 0 or row >= len(self.library.tracks):
            self.notify("Invalid track selection")
            return

        # Set current action context for the file browser callback
        self.current_action = {
            "action": "add_single_album_art",
            "track_row": row
        }

        # Open file browser for image selection
        await self.push_screen(FileBrowserScreen(
            "Select Album Art Image",
            [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            self._on_image_selected
        ))

    async def action_add_bulk_album_art(self) -> None:
        """Browse for and add album art to all selected tracks."""
        if not self.selected_tracks:
            self.notify("No tracks selected. Use Space to select tracks.")
            return

        # Set current action context for the file browser callback
        self.current_action = {
            "action": "add_bulk_album_art",
            "track_rows": list(self.selected_tracks)
        }

        # Open file browser for image selection
        await self.push_screen(FileBrowserScreen(
            "Select Album Art for Multiple Tracks",
            [".jpg", ".jpeg", ".png", ".gif", ".bmp"],
            self._on_image_selected
        ))

    def _on_image_selected(self, image_path: str) -> None:
        """Handle when an image is selected from the file browser.

        Args:
            image_path: Path to the selected image file
        """
        if not self.current_action or not image_path or not os.path.exists(image_path):
            return

        action = self.current_action.get("action")

        if action == "add_single_album_art":
            row = self.current_action.get("track_row")
            if row is not None and 0 <= row < len(self.library.tracks):
                track_path = self.library.tracks[row].path
                self._apply_album_art(track_path, image_path, row)

        elif action == "add_bulk_album_art":
            rows = self.current_action.get("track_rows", [])
            success_count = 0

            for row in rows:
                if row < 0 or row >= len(self.library.tracks):
                    continue

                track_path = self.library.tracks[row].path
                if self._apply_album_art(track_path, image_path, row, notify=False):
                    success_count += 1

            if success_count > 0:
                self.notify(f"Added album art to {success_count} tracks")
            else:
                self.notify("Failed to add album art to any tracks", severity="error")

        # Clear the current action
        self.current_action = None

    def _apply_album_art(self, track_path: str, image_path: str, row: int, notify: bool = True) -> bool:
        """Apply album art to a track and update UI.

        Args:
            track_path: Path to the music file
            image_path: Path to the image file
            row: Row index in the table
            notify: Whether to show notifications

        Returns:
            bool: True if successful
        """
        table = self.query_one(DataTable)

        try:
            # Save album art to the file
            if save_album_art(track_path, image_path):
                if notify:
                    self.notify(f"Album art added to {os.path.basename(track_path)}")
                self.modified_tracks.add(track_path)
                table.update_cell_at(Coordinate(row, 0), "*")
                table.update_cell_at(Coordinate(row, 5), "✓")
                return True
            else:
                if notify:
                    self.notify(f"Failed to add album art", severity="error")
                return False
        except Exception as e:
            if notify:
                self.notify(f"Error: {str(e)}", severity="error")
            return False

    async def action_preview_album_art(self) -> None:
        """Preview album art for the current track."""
        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, _ = table.cursor_coordinate
        if row < 0 or row >= len(self.library.tracks):
            return

        track_path = self.library.tracks[row].path

        # Show the album art preview screen
        await self.push_screen(AlbumArtScreen(track_path))

    def get_track_for_row(self, row_index_or_key):
        """Get track for a specific row."""
        # Check if we got a dictionary from our tracking system
        if isinstance(row_index_or_key, dict) and 'row_index' in row_index_or_key:
            row_index = row_index_or_key['row_index']
            if row_index is not None and 0 <= row_index < len(self.library.tracks):
                return self.library.tracks[row_index]

        # Handle legacy format or direct row index
        numeric_index = None

        # Handle various row index types
        if hasattr(row_index_or_key, 'value'):
            # It's a RowKey object
            if row_index_or_key.value is not None:
                numeric_index = row_index_or_key.value
            else:
                # If value is None, find the index in the table
                table = self.query_one(DataTable)
                for i, row_key in enumerate(table.rows):
                    if row_key == row_index_or_key:
                        numeric_index = i
                        break
        else:
            # Try to use the value directly
            try:
                numeric_index = int(row_index_or_key)
            except (TypeError, ValueError):
                pass

        # Use the numeric index if we found one
        if numeric_index is not None and 0 <= numeric_index < len(self.library.tracks):
            return self.library.tracks[numeric_index]

        return None

    def refresh_data_table(self):
        """Refresh the data table with updated metadata."""
        table = self.query_one(DataTable)

        # Store current selection before clearing the table
        stored_selection = None
        if hasattr(self, 'selected_cell') and self.selected_cell:
            # Store a copy of the selection info
            if isinstance(self.selected_cell, dict):
                stored_selection = dict(self.selected_cell)
                # Avoid logging complex objects that might cause rendering issues
                self.notify(f"Refreshing table, keeping selection at row {stored_selection.get('row_index')}")
            else:
                # Handle older format (tuple)
                row, column = self.selected_cell
                stored_selection = {'row_key': row, 'column': column}

        # Clear and rebuild the table
        table.clear()

        # Repopulate with current data
        for i, track in enumerate(self.library.tracks):
            metadata = self.metadata_list[i]
            # Add status indicator for modified tracks
            status = "*" if track.path in self.modified_tracks else ""
            # Add art indicator if album art exists
            has_art = "✓" if metadata.get("has_album_art", False) else ""
            table.add_row(
                status,
                os.path.basename(track.path),
                metadata.get("artist", "Unknown"),
                metadata.get("album", "Unknown"),
                track.title,
                has_art
            )

        # Set stored_selection to the app for use after refresh
        self._stored_selection = stored_selection

        # Use a simple delayed restoration (more reliable than complex callbacks)
        def restore():
            # Only try to restore if we have a selection to restore
            if hasattr(self, '_stored_selection') and self._stored_selection:
                row_index = self._stored_selection.get('row_index')
                if row_index is not None:
                    try:
                        # Make sure row_index is an integer in valid range
                        row_index = int(row_index)
                        if 0 <= row_index < table.row_count:
                            table.focus()
                            table.move_cursor(row=row_index)
                            # Don't notify as it might cause more issues
                    except (TypeError, ValueError, IndexError):
                        # Don't log error notifications that might cause rendering issues
                        pass

        # Schedule the restoration for next refresh cycle
        self.call_later(restore)

    def apply_title_changes(self, changes):
        """Apply the title changes to the tracks."""
        # Get the current selection before making changes
        stored_selection = None
        if hasattr(self, 'selected_cell') and self.selected_cell:
            if isinstance(self.selected_cell, dict):
                stored_selection = dict(self.selected_cell)
            else:
                # Handle legacy tuple format
                row, column = self.selected_cell
                stored_selection = {'row_key': row, 'column': column}
                if isinstance(row, int):
                    stored_selection['row_index'] = row

        # Track changed back to the original format
        row_before_changes = None
        if stored_selection and 'row_index' in stored_selection:
            row_before_changes = stored_selection['row_index']

        # Apply the changes to the track data
        table = self.query_one(DataTable)
        for file_path, (_, new_title) in changes.items():
            # Find the track with this path and update its title
            for i, track in enumerate(self.library.tracks):
                if track.path == file_path:
                    track.title = new_title
                    if i < len(self.metadata_list):
                        self.metadata_list[i]["title"] = new_title
                        # Mark this track as modified
                        self.modified_tracks.add(file_path)
                        # Update the status column
                        table.update_cell_at(Coordinate(i, 0), "*")
                    break

        # Store the selected row for access after refresh
        self._stored_row = row_before_changes

        # Update the UI to reflect changes
        self.refresh_data_table()

        # After refresh_data_table, check if we need to directly set cursor
        # This is a fallback in case our callback-based approach doesn't work
        def direct_restore():
            table = self.query_one(DataTable)
            if hasattr(self, '_stored_row') and self._stored_row is not None:
                try:
                    row_idx = int(self._stored_row)
                    if 0 <= row_idx < table.row_count:
                        table.focus()
                        table.move_cursor(row=row_idx)
                        self.selected_cell = row_idx
                        # Use minimal notification to avoid issues
                        self.notify(f"Selection restored")
                except (ValueError, TypeError):
                    pass

        # Schedule this as a fallback
        self.call_later(direct_restore)

    async def guess_title_from_filename(self):
        """Guess title for the currently selected cell."""
        if not hasattr(self, 'selected_cell'):
            self.notify("No cell selected")
            return

        # Handle both dictionary and tuple formats for selected_cell
        row = None
        if isinstance(self.selected_cell, dict):
            row = self.selected_cell.get('row_index')
            if row is None:
                row = self.selected_cell.get('row_key')
        else:
            try:
                # Handle tuple format
                row, _ = self.selected_cell
            except (TypeError, ValueError):
                # If it's neither a dict nor a tuple/list, try using it directly
                row = self.selected_cell

        # Store the row index for restoration
        if isinstance(row, int):
            self._stored_row = row

        track = self.get_track_for_row(row)
        if not track or not track.path:
            self.notify(f"No filepath available for this track")
            return

        # Try to get the numeric row index
        numeric_row = None
        if isinstance(row, int):
            numeric_row = row
        elif hasattr(row, 'value') and row.value is not None:
            numeric_row = row.value

        guessed_title = TitleGuesser.guess_title_from_filename(track.path)
        # Don't include potentially problematic strings in notifications
        self.notify(f"Title guessed for row {numeric_row}")

        # Create preview with just this one change
        changes = {track.path: (track.title, guessed_title)}

        # Apply directly for now (simplified)
        self.apply_title_changes(changes)

        # Directly try to set selection after a short delay
        def set_selection():
            if numeric_row is not None:
                table = self.query_one(DataTable)
                if 0 <= numeric_row < table.row_count:
                    table.move_cursor(row=numeric_row)

        self.call_later(set_selection)
        self.notify("Title updated")

    async def guess_all_titles(self):
        """Guess titles for all tracks in the library."""
        if not hasattr(self, 'library') or not self.library.tracks:
            self.notify("No tracks in library")
            return

        # Get tracks with file paths
        tracks_with_paths = [t for t in self.library.tracks if hasattr(t, 'path') and t.path]
        if not tracks_with_paths:
            self.notify("No tracks with file paths found")
            return

        # Generate guesses
        changes = {}
        for track in tracks_with_paths:
            guessed_title = TitleGuesser.guess_title_from_filename(track.path)
            changes[track.path] = (track.title, guessed_title)

        # Apply the changes directly (simplified)
        self.apply_title_changes(changes)
        self.notify(f"{len(changes)} titles updated!")

    async def save_changes(self):
        """Save changes to the library."""
        if not self.modified_tracks:
            self.notify("No changes to save")
            return

        success_count = 0
        fail_count = 0
        table = self.query_one(DataTable)

        for file_path in list(self.modified_tracks):  # Use list to allow safe modification during iteration
            # Find the corresponding metadata
            metadata = None
            row_index = None
            for i, track in enumerate(self.library.tracks):
                if track.path == file_path:
                    metadata = self.metadata_list[i]
                    row_index = i
                    break

            if metadata:
                # Save the metadata back to the file
                if save_metadata(file_path, metadata):
                    success_count += 1
                    self.modified_tracks.remove(file_path)
                    # Clear the status indicator
                    if row_index is not None:
                        table.update_cell_at(Coordinate(row_index, 0), "")
                else:
                    fail_count += 1

        # Notify the user of the results
        if fail_count == 0:
            self.notify(f"Successfully saved changes to {success_count} file(s)")
        else:
            self.notify(f"Saved changes to {success_count} file(s), {fail_count} failed", severity="warning")

    def action_edit_cell(self) -> None:
        """Enter edit mode for the currently selected cell."""
        if self.editing:
            return

        table = self.query_one(DataTable)
        if not table.cursor_coordinate:
            return

        row, column = table.cursor_coordinate

        # Only allow editing artist, album, and title columns (2, 3, 4)
        if column < 2 or column > 4:
            self.notify("This column cannot be edited directly")
            return

        # Get current cell value
        current_value = table.get_cell_at(Coordinate(row, column))
        if current_value is None:
            current_value = ""

        # Alternative approach to determine cell position using relative positioning
        try:
            # Determine cell position by calculating positions
            cell_position = self._calculate_cell_position(table, row, column)
            if not cell_position:
                self.notify("Could not calculate cell position")
                return

            position_x, position_y, width, height = cell_position

            # Create an edit widget for the cell
            edit = EditField(value=str(current_value))
            edit.styles.width = width
            edit.styles.height = height
            self.edit_widget = edit

            # Add edit widget to the app and position it
            self.mount(edit)
            edit.styles.offset = (position_x, position_y)
            edit.focus()
            self.editing = True

        except Exception as e:
            self.notify(f"Error positioning editor: {str(e)}")

    def _calculate_cell_position(self, table, row, column):
        """Calculate the position of a cell in the table.

        Returns:
            Tuple[int, int, int, int]: (x, y, width, height) or None if calculation fails
        """
        try:
            # Calculate approximate positions based on table dimensions
            table_region = table.region
            if not table_region:
                return None

            # Get the table's content offset (accounting for headers and borders)
            content_offset_x = 1  # Assuming 1-cell border
            content_offset_y = 2  # Assuming 1-cell border + 1 header row

            # Basic calculation for column widths - adjust as needed for your style
            # These are approximations - you may need to tune these values
            column_widths = [5, 25, 25, 25, 25, 10]  # Status column is 5 wide, others 25% each, Art column is 10 wide

            # Calculate total width to use for percentage calculations
            total_width = table_region.width - 2  # Subtract borders

            # Calculate position
            x = table_region.x + content_offset_x
            y = table_region.y + content_offset_y + row

            # Add widths of preceding columns to get to our column
            for i in range(column):
                if i == 0:  # Status column (fixed width)
                    x += column_widths[0]
                elif i == 5:  # Art column (fixed width)
                    x += column_widths[5]
                else:
                    # Other columns use percentage width
                    x += int((total_width - column_widths[0] - column_widths[5]) * 0.25)

            # Get width of current column
            if column == 0:
                width = column_widths[0]  # Status column
            elif column == 5:
                width = column_widths[5]  # Art column
            else:
                # Other columns
                width = int((total_width - column_widths[0] - column_widths[5]) * 0.25) - 1  # Subtract 1 for padding

            height = 1  # Cells are typically 1 unit high

            return (x, y, width, height)

        except Exception as e:
            self.notify(f"Position calculation error: {str(e)}")
            return None

    def action_cancel_edit(self) -> None:
        """Cancel editing and remove the edit widget."""
        if not self.editing or not self.edit_widget:
            return

        self.editing = False
        self.edit_widget.remove()
        self.edit_widget = None
        table = self.query_one(DataTable)
        table.focus()

    def on_edit_field_submitted(self, event: EditField.Submitted) -> None:
        """Handle when an edit is submitted."""
        if not self.editing or not self.edit_widget:
            return

        new_value = event.value.strip()
        table = self.query_one(DataTable)
        row, column = table.cursor_coordinate

        # Update the cell
        self._update_cell_value(row, column, new_value)

        # Clean up
        self.action_cancel_edit()

    def on_edit_field_cancelled(self, event: EditField.Cancelled) -> None:
        """Handle when the edit is cancelled."""
        self.action_cancel_edit()

    def _update_cell_value(self, row: int, column: int, new_value: str) -> None:
        """Update a cell value and the corresponding metadata."""
        table = self.query_one(DataTable)
        track_path = self.library.tracks[row].path

        # Determine what field we're editing
        field_map = {
            2: "artist",
            3: "album",
            4: "title"
        }

        field = field_map.get(column)
        if not field:
            return

        # Update the metadata and UI
        if field == "title":
            # Update the track title
            old_value = self.library.tracks[row].title
            self.library.tracks[row].title = new_value

        # Update metadata list
        if row < len(self.metadata_list):
            self.metadata_list[row][field] = new_value

        # Mark as modified
        self.modified_tracks.add(track_path)

        # Update the table cell
        table.update_cell_at(Coordinate(row, column), new_value)

        # Update the status column to show modification
        table.update_cell_at(Coordinate(row, 0), "*")

        self.notify(f"Updated {field} to '{new_value}'")

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

    async def action_edit_all_artists(self) -> None:
        """Open bulk edit screen for artists."""
        if not hasattr(self, 'library') or not self.library.tracks:
            self.notify("No tracks to edit")
            return

        # Get current unique artists and a sample value
        artists = set()
        default_value = None
        for i, _ in enumerate(self.library.tracks):
            artist = self.metadata_list[i].get("artist", "")
            if artist:
                artists.add(artist)
                if default_value is None:
                    default_value = artist

        # Open the bulk edit screen
        await self.push_screen(
            BulkEditScreen(
                title="Edit All Artists",
                field_name="artist",
                current_values=list(artists),
                default_value=default_value or "",
                on_submit=self.apply_bulk_artist_change
            )
        )

    async def action_edit_all_albums(self) -> None:
        """Open bulk edit screen for albums."""
        if not hasattr(self, 'library') or not self.library.tracks:
            self.notify("No tracks to edit")
            return

        # Get current unique albums and a sample value
        albums = set()
        default_value = None
        for i, _ in enumerate(self.library.tracks):
            album = self.metadata_list[i].get("album", "")
            if album:
                albums.add(album)
                if default_value is None:
                    default_value = album

        # Open the bulk edit screen
        await self.push_screen(
            BulkEditScreen(
                title="Edit All Albums",
                field_name="album",
                current_values=list(albums),
                default_value=default_value or "",
                on_submit=self.apply_bulk_album_change
            )
        )

    def apply_bulk_artist_change(self, new_value: str) -> None:
        """Apply a new artist value to all tracks."""
        table = self.query_one(DataTable)
        count = 0

        for i, track in enumerate(self.library.tracks):
            # Update the metadata
            self.metadata_list[i]["artist"] = new_value

            # Mark as modified
            self.modified_tracks.add(track.path)

            # Update the table cell
            table.update_cell_at(Coordinate(i, 2), new_value)  # Artist column
            table.update_cell_at(Coordinate(i, 0), "*")  # Status column

            count += 1

        self.notify(f"Updated artist to '{new_value}' for {count} tracks")

    def apply_bulk_album_change(self, new_value: str) -> None:
        """Apply a new album value to all tracks."""
        table = self.query_one(DataTable)
        count = 0

        for i, track in enumerate(self.library.tracks):
            # Update the metadata
            self.metadata_list[i]["album"] = new_value

            # Mark as modified
            self.modified_tracks.add(track.path)

            # Update the table cell
            table.update_cell_at(Coordinate(i, 3), new_value)  # Album column
            table.update_cell_at(Coordinate(i, 0), "*")  # Status column

            count += 1

        self.notify(f"Updated album to '{new_value}' for {count} tracks")

    # Command action handlers
    async def action_guess_title(self) -> None:
        """Handle the guess title command."""
        await self.guess_title_from_filename()

    async def action_guess_all_titles(self) -> None:
        """Handle the guess all titles command."""
        await self.guess_all_titles()

    async def action_save_changes(self) -> None:
        """Handle the save changes command."""
        await self.save_changes()