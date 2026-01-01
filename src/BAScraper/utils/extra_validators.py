import sys
import re
from pathlib import Path
from typing import Literal

LOG_LEVELS = Literal[
    10, # logging.DEBUG
    20, # logging.INFO
    30, # logging.WARNING
    40, # logging.ERROR
    50, # logging.CRITICAL
]

# for file mode validation
VALID_MODES = Literal[
    # Text modes
    'r', 'w', 'a', 'x',
    'r+', 'w+', 'a+', 'x+',
    'rt', 'wt', 'at', 'xt',
    'r+t', 'w+t', 'a+t', 'x+t',

    # Binary modes (permutations included)
    'rb', 'wb', 'ab', 'xb',
    'r+b', 'w+b', 'a+b', 'x+b',
    'rb+', 'wb+', 'ab+', 'xb+'
]

reddit_id_rule = r'^[0-9a-zA-Z]+$'  # Base36 ID rule
reddit_username_rule = r'^[A-Za-z0-9_-]{3,20}$'  # Reddit username rule
subreddit_name_rule = r'^[A-Za-z0-9][A-Za-z0-9_]{1,20}$'  # Subreddit name rule

def validate_output_path(v: Path) -> Path:
    """
    Validates that a path is suitable for writing a new file.
    Windows/Unix naming constraints.
    """
    # 1. Check if the path is actually a directory
    if v.is_dir():
        raise ValueError(f"The path '{v}' is a directory, not a file.")

    # 2. Check if the parent directory exists (so user can write to it)
    if not v.parent.exists():
        raise ValueError(f"Parent directory '{v.parent}' does not exist.")

    # 3. OS-Specific Filename Validation
    filename = v.name

    if sys.platform == 'win32':
        # Windows: Forbidden characters < > : " / \ | ? * and ASCII 0-31
        # Note: only check the 'filename' part, as colons/slashes are valid in the full path (drive letters)
        forbidden_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(forbidden_chars, filename):
            raise ValueError(f"Filename '{filename}' contains characters forbidden on Windows.")

        # Windows: Reserved filenames (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
        reserved_names = {
            "CON", "PRN", "AUX", "NUL",
            "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
            "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
        }
        if v.stem.upper() in reserved_names:
            raise ValueError(f"Filename '{filename}' is a reserved name on Windows.")

    else:
        # Linux/macOS: Mostly just null bytes are forbidden in filenames
        # Forward slashes are separators and won't appear in v.name via pathlib
        if '\x00' in filename:
            raise ValueError("Filename contains null byte.")

    return v
