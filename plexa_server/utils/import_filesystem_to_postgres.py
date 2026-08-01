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

    courses = await source_courses.list_courses()
    for course in courses:
        shell = course.model_copy(update={"lessons": {}, "lesson_timeline": []})
        await target_courses.save_course(shell)

    for source_course in courses:
        for lesson_id, version in source_course.lessons.items():
            lesson = await source_artifacts.load_lesson(
                lesson_id,
                version,
                course_id=source_course.course_id,
            )
            if lesson is None:
                lesson = await source_artifacts.load_lesson(
                    lesson_id,
                    version,
                    course_id=None,
                )
            if lesson is not None:
                await target_artifacts.save_lesson(lesson, course_id=source_course.course_id)
        target_course = await target_courses.get_course(source_course.course_id)
        if target_course is None:
            raise RuntimeError(f"Failed to import course {source_course.course_id}.")
        target_course.lessons = dict(source_course.lessons)
        target_course.lesson_timeline = list(source_course.lesson_timeline)
        await target_courses.save_course(target_course)

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
