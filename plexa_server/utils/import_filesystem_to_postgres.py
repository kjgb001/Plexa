import asyncio
import argparse
from pathlib import Path

from plexa_server.db.config import get_named_database_config
from plexa_server.db.session import create_session_factory
from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemSessionStorage,
)
from plexa_server.storage.postgres import (
    PostgresArtifactStorage,
    PostgresCourseStorage,
    PostgresSessionStorage,
)
from plexa_server.utils.filesystem_data_dir import get_data_dir_path


async def import_filesystem_to_postgres(data_dir: Path, target: str = "dev") -> None:
    """Import filesystem-backed Plexa data into Postgres.

    Args:
        data_dir: Filesystem data root to import from.
        target: Database target name, either `dev` or `test`.

    Raises:
        ValueError: If no database URL has been configured.
    """
    database_config = get_named_database_config(target)
    if not database_config.is_configured:
        raise ValueError(f"Database configuration for target '{target}' is missing.")

    session_factory = create_session_factory(database_config.resolved_async_url(), echo=database_config.echo)

    source_artifacts = FileSystemArtifactStorage(data_dir)
    source_courses = FileSystemCourseStorage(data_dir)
    source_sessions = FileSystemSessionStorage(data_dir)

    target_artifacts = PostgresArtifactStorage(session_factory)
    target_courses = PostgresCourseStorage(session_factory)
    target_sessions = PostgresSessionStorage(session_factory)

    for lesson_path in sorted(source_artifacts.lessons_path.glob("*.json")):
        stem = lesson_path.stem
        lesson_id, version = stem.rsplit("_", 1)
        lesson = await source_artifacts.load_lesson(lesson_id, version)
        if lesson is not None:
            await target_artifacts.save_lesson(lesson)

    for course in await source_courses.list_courses():
        await target_courses.save_course(course)

    for session in await source_sessions.list_sessions():
        await target_sessions.save_session(session)
        config = await source_sessions.get_inference_config(session.session_id)
        if config is not None:
            await target_sessions.save_inference_config(session.session_id, config)


def parse_args() -> argparse.Namespace:
    """Parse importer CLI arguments.

    Returns:
        argparse.Namespace: Parsed importer arguments.
    """
    parser = argparse.ArgumentParser(description="Import filesystem data into a Postgres Plexa database.")
    parser.add_argument(
        "--target",
        choices=["dev", "test"],
        default="dev",
        help="Database target to import into.",
    )
    return parser.parse_args()


async def main() -> None:
    """Import the default filesystem data directory into Postgres."""
    args = parse_args()
    await import_filesystem_to_postgres(get_data_dir_path(), target=args.target)


if __name__ == "__main__":
    asyncio.run(main())
