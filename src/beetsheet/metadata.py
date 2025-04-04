"""
Module for extracting metadata from music files.
"""

import os
from typing import Dict, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import mutagen
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    logger.warning("Mutagen library not found. Installing it will enable better metadata extraction.")

def extract_metadata(file_path: str) -> Dict[str, str]:
    """
    Extract metadata from a music file.

    Args:
        file_path: Path to the music file

    Returns:
        Dictionary containing artist, album, and title
    """
    metadata = {"artist": "Unknown", "album": "Unknown", "title": "Unknown"}

    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return metadata

    # Simple filename-based metadata extraction as fallback
    filename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(filename)[0]

    # Try to extract from filename format: Artist - Album - Title
    parts = name_without_ext.split(" - ")
    if len(parts) >= 3:
        metadata["artist"] = parts[0]
        metadata["album"] = parts[1]
        metadata["title"] = parts[2]
    elif len(parts) == 2:
        metadata["artist"] = parts[0]
        metadata["title"] = parts[1]

    # If mutagen is available, use it for better extraction
    if HAS_MUTAGEN:
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".mp3":
                try:
                    audio = MP3(file_path, ID3=EasyID3)
                    if "artist" in audio:
                        metadata["artist"] = audio["artist"][0]
                    if "album" in audio:
                        metadata["album"] = audio["album"][0]
                    if "title" in audio:
                        metadata["title"] = audio["title"][0]

                    # Check for album art
                    try:
                        id3 = ID3(file_path)
                        for tag in id3.values():
                            if tag.FrameID == 'APIC':
                                metadata["has_album_art"] = True
                                break
                    except:
                        pass
                except Exception as e:
                    logger.warning(f"Error reading MP3 metadata from {filename}: {str(e)}")
            elif ext == ".flac":
                try:
                    audio = FLAC(file_path)
                    if "artist" in audio:
                        metadata["artist"] = audio["artist"][0]
                    if "album" in audio:
                        metadata["album"] = audio["album"][0]
                    if "title" in audio:
                        metadata["title"] = audio["title"][0]

                    # Check for album art in FLAC
                    if audio.pictures:
                        metadata["has_album_art"] = True
                except Exception as e:
                    logger.warning(f"Error reading FLAC metadata from {filename}: {str(e)}")
        except Exception as e:
            logger.warning(f"General error processing metadata for {filename}: {str(e)}")

    # Add the file path to metadata
    metadata["file_path"] = file_path

    return metadata
