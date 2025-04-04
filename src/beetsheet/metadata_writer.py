"""
Module for writing metadata back to music files.
"""

import os
from typing import Dict, Any, Optional
import logging
import shutil

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import mutagen
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
    from mutagen.mp3 import MP3
    from mutagen.easyid3 import EasyID3
    from mutagen.flac import FLAC, Picture
    from mutagen.oggvorbis import OggVorbis
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    logger.warning("Mutagen library not found. Installing it will enable better metadata writing.")


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
        logger.error(f"Error saving metadata to {file_path}: {str(e)}")
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
        logger.error(f"Error saving MP3 metadata: {str(e)}")

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
            logger.error(f"Fallback ID3 saving also failed: {str(e2)}")
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
        logger.error(f"Error saving FLAC metadata: {str(e)}")
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
        logger.error(f"Error saving OGG metadata: {str(e)}")
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
        logger.error(f"Error saving generic metadata: {str(e)}")
        return False


def save_album_art(file_path: str, image_path: str) -> bool:
    """
    Save album art to a music file.

    Args:
        file_path: Path to the music file
        image_path: Path to the album art image file

    Returns:
        bool: True if save was successful, False otherwise
    """
    if not HAS_MUTAGEN:
        logger.error("Mutagen library is required for album art functionality")
        return False

    if not os.path.exists(file_path):
        logger.error(f"Music file does not exist: {file_path}")
        return False

    if not os.path.exists(image_path):
        logger.error(f"Image file does not exist: {image_path}")
        return False

    try:
        # Determine file type and use appropriate method
        extension = os.path.splitext(file_path)[1].lower()

        if extension == '.mp3':
            return _save_mp3_album_art(file_path, image_path)
        elif extension == '.flac':
            return _save_flac_album_art(file_path, image_path)
        elif extension in ('.ogg', '.oga'):
            return _save_ogg_album_art(file_path, image_path)
        else:
            # Try generic method as fallback
            return _save_generic_album_art(file_path, image_path)

    except Exception as e:
        logger.error(f"Error saving album art to {file_path}: {str(e)}")
        return False


def _save_mp3_album_art(file_path: str, image_path: str) -> bool:
    """Save album art to MP3 file."""
    try:
        # Read the image data
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()

        # Get the MIME type based on file extension
        mime_type = _get_mime_type(image_path)

        # Try to load ID3 tags or create if not present
        try:
            audio = ID3(file_path)
        except mutagen.id3.ID3NoHeaderError:
            # Create a new ID3 tag if none exists
            audio = ID3()

        # Remove existing album art
        for key in list(audio.keys()):
            if key.startswith('APIC:'):
                del audio[key]

        # Add the new album art
        audio.add(
            APIC(
                encoding=3,  # 3 is for UTF-8
                mime=mime_type,
                type=3,  # 3 is for cover image
                desc='Cover',
                data=image_data
            )
        )

        # Save the changes
        audio.save(file_path)
        return True

    except Exception as e:
        logger.error(f"Error saving MP3 album art: {str(e)}")
        return False


def _save_flac_album_art(file_path: str, image_path: str) -> bool:
    """Save album art to FLAC file."""
    try:
        # Read the image data
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()

        # Get the MIME type based on file extension
        mime_type = _get_mime_type(image_path)

        # Load the FLAC file
        audio = FLAC(file_path)

        # Remove any existing pictures
        audio.clear_pictures()

        # Create a Picture object
        picture = Picture()
        picture.data = image_data
        picture.type = 3  # 3 is for cover image
        picture.mime = mime_type
        picture.desc = "Cover"

        # Add the picture
        audio.add_picture(picture)

        # Save the changes
        audio.save()
        return True

    except Exception as e:
        logger.error(f"Error saving FLAC album art: {str(e)}")
        return False


def _save_ogg_album_art(file_path: str, image_path: str) -> bool:
    """Save album art to OGG file."""
    try:
        # For OGG Vorbis, we need to convert the image to a base64 string
        import base64

        # Read the image data
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()

        # Get the MIME type based on file extension
        mime_type = _get_mime_type(image_path)

        # Load the OGG file
        audio = OggVorbis(file_path)

        # Remove any existing pictures
        if 'METADATA_BLOCK_PICTURE' in audio:
            del audio['METADATA_BLOCK_PICTURE']

        # Create a Picture object (needed for the proper formatting)
        picture = Picture()
        picture.data = image_data
        picture.type = 3  # 3 is for cover image
        picture.mime = mime_type
        picture.desc = "Cover"

        # Convert to base64 format that OGG Vorbis expects
        data = picture.write()
        encoded_data = base64.b64encode(data).decode('ascii')

        # Add the picture
        audio['METADATA_BLOCK_PICTURE'] = [encoded_data]

        # Save the changes
        audio.save()
        return True

    except Exception as e:
        logger.error(f"Error saving OGG album art: {str(e)}")
        return False


def _save_generic_album_art(file_path: str, image_path: str) -> bool:
    """Generic fallback method for saving album art."""
    # This is a very basic fallback that just copies the image file alongside the music file
    try:
        # Generate a filename for the cover image next to the music file
        dir_name = os.path.dirname(file_path)
        music_name = os.path.splitext(os.path.basename(file_path))[0]
        image_ext = os.path.splitext(image_path)[1]
        cover_name = f"{music_name}_cover{image_ext}"
        cover_path = os.path.join(dir_name, cover_name)

        # Copy the image file
        shutil.copyfile(image_path, cover_path)

        return True

    except Exception as e:
        logger.error(f"Error saving generic album art: {str(e)}")
        return False


def _get_mime_type(file_path: str) -> str:
    """Determine MIME type based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext in ('.jpg', '.jpeg'):
        return 'image/jpeg'
    elif ext == '.png':
        return 'image/png'
    elif ext == '.gif':
        return 'image/gif'
    elif ext == '.bmp':
        return 'image/bmp'
    else:
        # Default to JPEG if unknown
        return 'image/jpeg'
