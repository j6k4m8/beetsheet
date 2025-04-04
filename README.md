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

## Features

-   Display music files in a spreadsheet format showing Artist, Album, and Title
-   Navigate through your music files in a simple interface

## Development

### Running tests

Install the development dependencies:

Run the tests:

```bash
uv run pytest
```
