from pathlib import Path
import os

def get_data_dir_path() -> Path:
    return Path(os.path.join(os.path.dirname(__file__), "../data"))