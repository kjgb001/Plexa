from pathlib import Path
import os

def get_data_dir_path() -> Path:
    """Return the default source directory for legacy filesystem migration.

    Returns:
        Path: Absolute path to the repository's `data` directory.
    """
    return Path(__file__).resolve().parent.parent / "data"
