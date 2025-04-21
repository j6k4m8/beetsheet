from pathlib import Path
import os
import re
from typing import Dict, List, Tuple, Optional

class TitleGuesser:
    """Utility class for guessing titles from filenames."""

    @staticmethod
    def guess_title_from_filename(filepath: str) -> str:
        """Extract a probable title from a filename."""
        # Get just the filename without path and extension
        filename = Path(filepath).stem

        # Remove YouTube IDs (usually 11 characters in square brackets)
        # Example: "Song Title [dQw4w9WgXcQ].mp3" -> "Song Title"
        filename = re.sub(r'\s*\[[a-zA-Z0-9_-]{11}\]\s*', '', filename)

        # Remove other common patterns in brackets or parentheses
        # filename = re.sub(r'\s*\([^)]*\)\s*', ' ', filename)  # Remove (text)
        # filename = re.sub(r'\s*\[[^\]]*\]\s*', ' ', filename)  # Remove [text]

        # Remove common prefixes like track numbers
        clean_name = re.sub(r'^\d+[\s\-_\.]+', '', filename)

        # Replace underscores and dots with spaces
        clean_name = re.sub(r'[_\.]', ' ', clean_name)

        # Replace multiple spaces with single space
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()

        # Title case the result
        title = ' '.join(word for word in clean_name.split())

        return title

    @staticmethod
    def guess_track_number_from_filename(filepath: str) -> Optional[int]:
        """Extract a track number from a filename."""
        # Get just the filename without path and extension
        filename = Path(filepath).stem

        # Look for common track number patterns at the start of the filename
        # Pattern 1: "01 - Track Name.mp3"
        # Pattern 2: "1. Track Name.mp3"
        # Pattern 3: "1_Track Name.mp3"
        track_num_match = re.match(r'^(\d+)[\s\.\-_]+', filename)

        if track_num_match:
            try:
                track_number = int(track_num_match.group(1))
                return track_number
            except ValueError:
                pass

        # Try to find track numbers in brackets or parentheses
        # Pattern: "Track Name (1).mp3" or "Track Name [01].mp3"
        bracket_match = re.search(r'[\(\[]\s*(\d+)\s*[\)\]]', filename)
        if bracket_match:
            try:
                track_number = int(bracket_match.group(1))
                return track_number
            except ValueError:
                pass

        return None

    @staticmethod
    def clean_youtube_id(title: str) -> str:
        """
        Remove YouTube IDs from a string.

        Args:
            title: The string that might contain YouTube IDs

        Returns:
            The cleaned string without YouTube IDs
        """
        return re.sub(r'\s*\[[a-zA-Z0-9_-]{11}\]\s*', '', title)

    @staticmethod
    def find_common_prefix(filenames: List[str]) -> Optional[str]:
        """Find common prefix across multiple filenames that might indicate artist/album."""
        if not filenames:
            return None

        # Extract stems from paths
        stems = [Path(f).stem for f in filenames]

        # Look for common prefixes that might be artist names
        # This is a simplified approach - real implementation would be more sophisticated
        parts = [s.split(' - ', 1) for s in stems]
        if all(len(p) > 1 for p in parts):
            prefixes = [p[0] for p in parts]
            if len(set(prefixes)) == 1:
                return prefixes[0]

        return None

    @staticmethod
    def guess_titles_for_files(filepaths: List[str]) -> Dict[str, str]:
        """Generate title guesses for multiple files."""
        result = {}
        for filepath in filepaths:
            result[filepath] = TitleGuesser.guess_title_from_filename(filepath)

        # Check for common prefix that might be artist/album
        common_prefix = TitleGuesser.find_common_prefix(filepaths)

        return result, common_prefix
