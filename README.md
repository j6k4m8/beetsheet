# Beetsheet

A terminal spreadsheet-like app for music file metadata.

![Image](https://github.com/user-attachments/assets/e4c0e731-ad85-4664-997f-76a77b8724e4)


![image](https://github.com/user-attachments/assets/39bcd3cb-1a88-4461-a0b4-0aa7fd48c5a2)


## Installation

```bash
uv sync
```

## Usage

```bash
uv run beetsheet ~/Downloads/New-Music/**/*.mp3
```

Or specify individual files:

```bash
uv run beetsheet /path/to/music/file1.mp3 /path/to/music/file2.flac
```

## Controls

-   `q`: Quit the application
-   `a`: Add/change album art for current track
-   `A`: Add/change album art for all selected tracks
-   `Space`: Select/deselect current track
-   `s`: Save changes to files
-   `p`: Play/pause the currently selected audio track
-   `P`: Stop audio playback

## Features

-   Display music files in a spreadsheet format showing Artist, Album, and Title
-   Navigate through your music files in a simple interface
-   Album art management:
    -   Browse for and add cover art to individual tracks
    -   Batch add the same cover art to multiple selected tracks
    -   Preview album art in the terminal interface
    -   Supports common image formats (JPG, PNG)
-   Audio playback:
    -   Play and preview audio tracks directly in the terminal
    -   Pause/resume and stop controls
    -   Shows currently playing track information

## Development

### Running tests

Install the development dependencies:

Run the tests:

```bash
uv run pytest
```

## Album Art Management

### Adding album art to a single track

1. Navigate to the desired track
2. Press `a` to open a file browser
3. Select an image file to use as album art
4. The selected image will be embedded as the track's cover art

### Adding album art to multiple tracks

1. Select tracks by navigating to each one and pressing `Space`
2. Press `A` to open a file browser
3. Select an image file to use as album art
4. The selected image will be embedded as cover art for all selected tracks

## Audio Playback

To enable audio playback, you'll need to have pygame installed:

```bash
pip install pygame
```

Once installed:

1. Select a track with the cursor
2. Press `p` to play/pause the selected track
3. Press `P` (shift+p) to stop playback
4. Use the playback controls in the bottom panel to control audio
