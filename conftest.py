import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_env_file() -> None:
    """Load default pytest environment values from `plexa_server/.env`.

    Existing process environment variables take precedence and are not
    overwritten.
    """
    env_path = Path(__file__).resolve().parent / "plexa_server" / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def pytest_addoption(parser) -> None:
    """Register the storage backend selector during pytest's initial CLI parse.

    Args:
        parser: Pytest parser used to register custom command-line options.
    """
    parser.addoption(
        "--storage-backend",
        action="store",
        default=os.getenv("PLEXA_TEST_STORAGE_BACKEND", "filesystem"),
        choices=["filesystem", "postgres", "both"],
        help="Select the storage backend for backend-agnostic tests.",
    )
