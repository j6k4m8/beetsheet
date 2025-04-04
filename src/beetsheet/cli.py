"""
Command line interface for Beetsheet.
"""

import argparse
import os
import sys
import glob
from typing import List

from .app import BeetsheetApp

def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="A terminal spreadsheet-like app for music file metadata."
    )
    parser.add_argument(
        "files",
        metavar="FILE",
        nargs="+",
        help="Music files to display in the spreadsheet",
    )

    args = parser.parse_args()

    # Expand any glob patterns in the arguments
    expanded_files = []
    for pattern in args.files:
        matched_files = glob.glob(pattern)
        if matched_files:
            expanded_files.extend(matched_files)
        else:
            # Keep the original pattern if no matches found
            expanded_files.append(pattern)

    # Check if files exist
    valid_files = []
    for file_path in expanded_files:
        if os.path.isfile(file_path):
            valid_files.append(os.path.abspath(file_path))
        else:
            print(f"Warning: File not found: {file_path}")

    if not valid_files:
        print("Error: No valid files provided.")
        print("Patterns tried:", args.files)
        print("Expanded to:", expanded_files)
        sys.exit(1)

    # Print found files for debugging
    print(f"Found {len(valid_files)} valid files:")
    for file in valid_files[:5]:  # Show first 5 files
        print(f" - {file}")
    if len(valid_files) > 5:
        print(f" - ... and {len(valid_files) - 5} more")

    # Run the app
    app = BeetsheetApp(valid_files)
    app.run()

if __name__ == "__main__":
    main()
