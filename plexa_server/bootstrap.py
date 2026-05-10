from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from plexa_server.db.bootstrap import init_database
from plexa_server.db.config import get_database_config, get_test_database_config
from plexa_server.utils.cryptography import generate_encryption_key
from plexa_server.utils.import_filesystem_to_postgres import import_filesystem_to_postgres


SERVER_ENV_PATH = Path(__file__).resolve().parent / ".env"
DEFAULT_INFERENCE_BACKENDS = {
    "ollama-local": {
        "type": "openai-compatible",
        "base_url": "http://localhost:11434/v1",
        "timeout_s": 30.0,
    },
    "vllm-local": {
        "type": "openai-compatible",
        "base_url": "http://localhost:8001/v1",
        "timeout_s": 30.0,
    },
}
DEFAULT_INFERENCE_PROFILES = {
    "default": {
        "backend_id": "ollama-local",
        "model": "llama3.1",
    },
    "fast": {
        "backend_id": "ollama-local",
        "model": "qwen2.5:7b",
    },
    "reasoning": {
        "backend_id": "vllm-local",
        "model": "deepseek-r1-distill-qwen-7b",
    },
}
DEFAULT_ENV_VALUES = {
    "PLEXA_DATABASE_URL": "postgresql+asyncpg://plexa:plexa_dev_password@localhost:5432/plexa",
    "PLEXA_DATABASE_SYNC_URL": "postgresql://plexa:plexa_dev_password@localhost:5432/plexa",
    "PLEXA_TEST_DATABASE_URL": "postgresql+asyncpg://plexa:plexa_dev_password@localhost:5432/plexa_test",
    "PLEXA_TEST_DATABASE_SYNC_URL": "postgresql://plexa:plexa_dev_password@localhost:5432/plexa_test",
    "PLEXA_TEST_STORAGE_BACKEND": "postgres",
    "PLEXA_INFERENCE_BACKENDS": json.dumps(DEFAULT_INFERENCE_BACKENDS, separators=(",", ":")),
    "PLEXA_INFERENCE_PROFILES": json.dumps(DEFAULT_INFERENCE_PROFILES, separators=(",", ":")),
    "PLEXA_INFERENCE_REQUIRED_BACKENDS": json.dumps(
        sorted(DEFAULT_INFERENCE_BACKENDS.keys()),
        separators=(",", ":"),
    ),
}


def _read_env_lines(env_path: Path) -> list[str]:
    """Return raw `.env` lines when the file exists."""
    if not env_path.exists():
        return []
    return env_path.read_text(encoding="utf-8").splitlines()


def _parse_env_value(lines: list[str], key: str) -> str | None:
    """Return the first configured value for a key in `.env`-style lines."""
    prefix = f"{key}="
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        return line[len(prefix):].strip().strip("\"'")
    return None


def ensure_env_defaults(
    env_path: Path | None = None,
    defaults: dict[str, str] | None = None,
) -> dict[str, str]:
    """Ensure the server `.env` file exists and contains baseline defaults.

    Existing values in either the process environment or `.env` file are
    preserved. Missing values are appended to the file and loaded into the
    current process.

    Args:
        env_path: Target `.env` file path.
        defaults: Mapping of default key/value pairs to ensure.

    Returns:
        dict[str, str]: Resolved values for the ensured defaults.
    """
    if env_path is None:
        env_path = SERVER_ENV_PATH
    if defaults is None:
        defaults = DEFAULT_ENV_VALUES

    env_lines = _read_env_lines(env_path)
    resolved: dict[str, str] = {}
    missing_lines: list[str] = []

    for key, default_value in defaults.items():
        existing_env = os.getenv(key)
        if existing_env:
            resolved[key] = existing_env
            continue

        existing_file_value = _parse_env_value(env_lines, key)
        if existing_file_value is not None:
            os.environ[key] = existing_file_value
            resolved[key] = existing_file_value
            continue

        os.environ[key] = default_value
        resolved[key] = default_value
        missing_lines.append(f"{key}={default_value}")

    if missing_lines:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_text = "\n".join(env_lines)
        if env_text and not env_text.endswith("\n"):
            env_text += "\n"
        env_text += "\n".join(missing_lines) + "\n"
        env_path.write_text(env_text, encoding="utf-8")

    return resolved


def ensure_log_encryption_key(env_path: Path | None = None) -> str:
    """Ensure a stable encrypted-log key exists for the application."""
    if env_path is None:
        env_path = SERVER_ENV_PATH

    existing_env = os.getenv("PLEXA_LOG_ENCRYPTION_KEY")
    if existing_env:
        return existing_env

    env_lines = _read_env_lines(env_path)
    existing_file_key = _parse_env_value(env_lines, "PLEXA_LOG_ENCRYPTION_KEY")
    if existing_file_key:
        os.environ["PLEXA_LOG_ENCRYPTION_KEY"] = existing_file_key
        return existing_file_key

    generated_key = generate_encryption_key()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_text = "\n".join(env_lines)
    if env_text and not env_text.endswith("\n"):
        env_text += "\n"
    env_text += f"PLEXA_LOG_ENCRYPTION_KEY={generated_key}\n"
    env_path.write_text(env_text, encoding="utf-8")
    os.environ["PLEXA_LOG_ENCRYPTION_KEY"] = generated_key
    return generated_key


def ensure_bootstrap_environment(env_path: Path | None = None) -> None:
    """Ensure local bootstrap environment prerequisites are present."""
    ensure_env_defaults(env_path=env_path)
    ensure_log_encryption_key(env_path=env_path)


async def init_dev_database(import_filesystem: bool = False, env_path: Path | None = None) -> None:
    """Initialize the development database and optionally import filesystem data."""
    ensure_bootstrap_environment(env_path=env_path)
    config = get_database_config()
    await init_database(config)
    if import_filesystem:
        await import_filesystem_to_postgres(Path(__file__).resolve().parent / "data", target="dev")


async def init_test_database(import_filesystem: bool = False, env_path: Path | None = None) -> None:
    """Initialize the dedicated test database and optionally import fixture data."""
    ensure_bootstrap_environment(env_path=env_path)
    config = get_test_database_config()
    await init_database(config)
    if import_filesystem:
        await import_filesystem_to_postgres(Path(__file__).resolve().parent / "data", target="test")


def parse_args() -> argparse.Namespace:
    """Parse bootstrap CLI arguments."""
    parser = argparse.ArgumentParser(description="Bootstrap Plexa local environment.")
    parser.add_argument(
        "--init-dev",
        action="store_true",
        help="Create and migrate the development database.",
    )
    parser.add_argument(
        "--import-filesystem",
        action="store_true",
        help="Import filesystem data after initializing requested databases.",
    )
    parser.add_argument(
        "--init-test",
        action="store_true",
        help="Create and migrate the dedicated test database.",
    )
    return parser.parse_args()


async def main() -> None:
    """Run the requested application bootstrap workflow."""
    args = parse_args()

    if not args.init_dev and not args.init_test:
        raise SystemExit("Specify at least one of --init-dev or --init-test.")

    if args.init_dev:
        await init_dev_database(import_filesystem=args.import_filesystem)

    if args.init_test:
        await init_test_database(import_filesystem=args.import_filesystem)


if __name__ == "__main__":
    asyncio.run(main())
