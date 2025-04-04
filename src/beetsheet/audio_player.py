"""
Module for audio playback functionality.
"""

import os
import threading
import time
import logging
from typing import Optional, Callable

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check for available audio libraries
try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False
    logger.warning("pygame not found. Installing it will enable audio playback.")

try:
    import simpleaudio as sa
    HAS_SIMPLEAUDIO = True
except ImportError:
    HAS_SIMPLEAUDIO = False
    logger.warning("simpleaudio not found. It's an alternative for audio playback.")


class AudioPlayer:
    """Handles playback of audio files."""

    def __init__(self):
        """Initialize audio player."""
        self.current_file = None
        self.is_playing = False
        self.is_paused = False
        self.playback_thread = None
        self.stop_event = threading.Event()
        self.on_playback_status_change = None
        self.on_playback_finished = None

        # Initialize pygame mixer if available
        if HAS_PYGAME:
            pygame.mixer.init()

    def set_callbacks(self, status_change: Callable = None, finished: Callable = None) -> None:
        """Set callbacks for playback events.

        Args:
            status_change: Called when playback status changes
            finished: Called when playback finishes
        """
        self.on_playback_status_change = status_change
        self.on_playback_finished = finished

    def play(self, file_path: str) -> bool:
        """Play an audio file.

        Args:
            file_path: Path to the audio file to play

        Returns:
            bool: True if playback started successfully
        """
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False

        # Stop any current playback
        self.stop()

        # Set as current file
        self.current_file = file_path

        # Check file extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ['.mp3', '.wav', '.flac', '.ogg']:
            logger.error(f"Unsupported file format: {ext}")
            return False

        # Handle playback based on available libraries
        if HAS_PYGAME:
            try:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.play()
                self.is_playing = True
                self.is_paused = False

                # Start a thread to monitor playback
                self.stop_event.clear()
                self.playback_thread = threading.Thread(target=self._monitor_playback_pygame)
                self.playback_thread.daemon = True
                self.playback_thread.start()

                if self.on_playback_status_change:
                    self.on_playback_status_change(True)

                return True
            except Exception as e:
                logger.error(f"Error playing file with pygame: {str(e)}")
                return False
        elif HAS_SIMPLEAUDIO and ext == '.wav':  # simpleaudio only supports WAV
            try:
                self.wave_obj = sa.WaveObject.from_wave_file(file_path)
                self.play_obj = self.wave_obj.play()
                self.is_playing = True
                self.is_paused = False

                # Start a thread to monitor playback
                self.stop_event.clear()
                self.playback_thread = threading.Thread(target=self._monitor_playback_simpleaudio)
                self.playback_thread.daemon = True
                self.playback_thread.start()

                if self.on_playback_status_change:
                    self.on_playback_status_change(True)

                return True
            except Exception as e:
                logger.error(f"Error playing file with simpleaudio: {str(e)}")
                return False
        else:
            logger.error("No suitable audio playback library available")
            return False

    def pause(self) -> None:
        """Pause playback."""
        if not self.is_playing or self.is_paused:
            return

        if HAS_PYGAME and pygame.mixer.get_init():
            try:
                pygame.mixer.music.pause()
                self.is_paused = True

                if self.on_playback_status_change:
                    self.on_playback_status_change(False, paused=True)
            except Exception as e:
                logger.error(f"Error pausing: {str(e)}")

    def resume(self) -> None:
        """Resume playback."""
        if not self.is_playing or not self.is_paused:
            return

        if HAS_PYGAME and pygame.mixer.get_init():
            try:
                pygame.mixer.music.unpause()
                self.is_paused = False

                if self.on_playback_status_change:
                    self.on_playback_status_change(True)
            except Exception as e:
                logger.error(f"Error resuming: {str(e)}")

    def stop(self) -> None:
        """Stop playback."""
        self.stop_event.set()

        if HAS_PYGAME and pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

        if hasattr(self, 'play_obj') and self.play_obj and self.play_obj.is_playing():
            try:
                self.play_obj.stop()
            except Exception:
                pass

        self.is_playing = False
        self.is_paused = False

        # Only notify if callback is set
        if self.on_playback_status_change:
            try:
                self.on_playback_status_change(False)
            except Exception as e:
                logger.warning(f"Error in playback status callback: {e}")

    def toggle_pause(self) -> None:
        """Toggle between pause and play states."""
        if self.is_paused:
            self.resume()
        elif self.is_playing:
            self.pause()

    def _monitor_playback_pygame(self) -> None:
        """Monitor pygame playback in a separate thread."""
        while self.is_playing and not self.stop_event.is_set():
            if not pygame.mixer.music.get_busy() and not self.is_paused:
                # Playback has finished
                self.is_playing = False
                if self.on_playback_finished:
                    self.on_playback_finished()
                break
            time.sleep(0.1)

    def _monitor_playback_simpleaudio(self) -> None:
        """Monitor simpleaudio playback in a separate thread."""
        while self.is_playing and not self.stop_event.is_set():
            if hasattr(self, 'play_obj') and not self.play_obj.is_playing():
                # Playback has finished
                self.is_playing = False
                if self.on_playback_finished:
                    self.on_playback_finished()
                break
            time.sleep(0.1)

    def cleanup(self) -> None:
        """Clean up resources when done."""
        # Set flags first to avoid triggering callbacks
        self.is_playing = False
        self.is_paused = False

        # Stop playback thread
        self.stop_event.set()

        # Clean up pygame if initialized
        if HAS_PYGAME and pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            except Exception as e:
                logger.warning(f"Error cleaning up pygame: {e}")
