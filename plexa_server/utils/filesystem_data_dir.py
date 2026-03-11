from pathlib import Path
import os

def get_data_dir_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data"