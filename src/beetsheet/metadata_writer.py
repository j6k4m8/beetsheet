"""
Module for writing metadata back to music files.
"""

import os
import mutagen
from mutagen.id3 import ID3, TIT2, TPE1, TALB
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from typing import Dict, Any, Optional


def save_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """
    Save metadata changes back to a music file.

    Args:
        file_path: Path to the music file
        metadata: Dictionary containing metadata to update

    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        # Determine file type and use appropriate method
        extension = os.path.splitext(file_path)[1].lower()

        if extension == '.mp3':
            return _save_mp3_metadata(file_path, metadata)
        elif extension == '.flac':
            return _save_flac_metadata(file_path, metadata)
        elif extension in ('.ogg', '.oga'):
            return _save_ogg_metadata(file_path, metadata)
        else:
            # Try generic method as fallback
            return _save_generic_metadata(file_path, metadata)

    except Exception as e:
        print(f"Error saving metadata to {file_path}: {str(e)}")
        return False


def _save_mp3_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """Save metadata to MP3 file."""
    try:
        # Try using EasyID3 interface first
        try:
            audio = EasyID3(file_path)
        except mutagen.id3.ID3NoHeaderError:
            # If the file doesn't have an ID3 tag yet, add one
            audio = mutagen.File(file_path, easy=True)
            if audio is None:
                # Create an ID3 tag if none exists
                audio = EasyID3()
                audio.save(file_path)
                audio = EasyID3(file_path)

        # Update metadata fields
        if 'title' in metadata:
            audio['title'] = metadata['title']
        if 'artist' in metadata:
            audio['artist'] = metadata['artist']
        if 'album' in metadata:
            audio['album'] = metadata['album']

        audio.save()
        return True

    except Exception as e:
        print(f"Error saving MP3 metadata: {str(e)}")

        # Fallback to basic ID3 if EasyID3 fails
        try:
            audio = ID3(file_path)
            if 'title' in metadata:
                audio.add(TIT2(encoding=3, text=metadata['title']))
            if 'artist' in metadata:
                audio.add(TPE1(encoding=3, text=metadata['artist']))
            if 'album' in metadata:
                audio.add(TALB(encoding=3, text=metadata['album']))
            audio.save()
            return True
        except Exception as e2:
            print(f"Fallback ID3 saving also failed: {str(e2)}")
            return False


def _save_flac_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """Save metadata to FLAC file."""
    try:
        audio = FLAC(file_path)

        if 'title' in metadata:
            audio['TITLE'] = metadata['title']
        if 'artist' in metadata:
            audio['ARTIST'] = metadata['artist']
        if 'album' in metadata:
            audio['ALBUM'] = metadata['album']

        audio.save()
        return True
    except Exception as e:
        print(f"Error saving FLAC metadata: {str(e)}")
        return False


def _save_ogg_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """Save metadata to OGG file."""
    try:
        audio = OggVorbis(file_path)

        if 'title' in metadata:
            audio['TITLE'] = metadata['title']
        if 'artist' in metadata:
            audio['ARTIST'] = metadata['artist']
        if 'album' in metadata:
            audio['ALBUM'] = metadata['album']

        audio.save()
        return True
    except Exception as e:
        print(f"Error saving OGG metadata: {str(e)}")
        return False


def _save_generic_metadata(file_path: str, metadata: Dict[str, Any]) -> bool:
    """
    Generic fallback method for saving metadata to other file formats.
    """
    try:
        audio = mutagen.File(file_path)
        if audio is None:
            return False

        # Different formats may use different tag keys, try common variations
        if 'title' in metadata:
            for key in ['title', 'TITLE', 'TIT2']:
                try:
                    audio[key] = metadata['title']
                    break
                except (KeyError, TypeError):
                    pass

        if 'artist' in metadata:
            for key in ['artist', 'ARTIST', 'TPE1']:
                try:
                    audio[key] = metadata['artist']
                    break
                except (KeyError, TypeError):
                    pass

        if 'album' in metadata:
            for key in ['album', 'ALBUM', 'TALB']:
                try:
                    audio[key] = metadata['album']
                    break
                except (KeyError, TypeError):
                    pass

        audio.save()
        return True
    except Exception as e:
        print(f"Error saving generic metadata: {str(e)}")
        return False
