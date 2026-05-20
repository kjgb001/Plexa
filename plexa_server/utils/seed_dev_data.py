import argparse
import asyncio
from pathlib import Path

from plexa_server.db.config import get_named_database_config, load_server_env_file
from plexa_server.db.session import create_session_factory
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.storage.filesystem import FileSystemArtifactStorage, FileSystemCourseStorage
from plexa_server.storage.postgres import PostgresArtifactStorage, PostgresCourseStorage
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage
from plexa_server.tests.fixtures import (
    SEEDED_COURSE_SPECS,
    SEEDED_LESSON_SPECS,
    make_seeded_lesson_payload,
    seeded_course_base_payload,
    valid_course,
)
from plexa_server.utils.filesystem_data_dir import get_data_dir_path


DATA_PATH = get_data_dir_path()


def parse_args() -> argparse.Namespace:
    """Parse the seed CLI arguments."""
    parser = argparse.ArgumentParser(description="Seed Plexa development lesson and course data.")
    parser.add_argument(
        "--target",
        choices=["filesystem", "dev", "test"],
        default="dev",
        help="Persistence target to seed. Defaults to the development database.",
    )
    return parser.parse_args()


def _build_storage(target: str) -> tuple[ArtifactStorage, CourseStorage]:
    """Build the artifact/course storages for the requested target."""
    if target == "filesystem":
        return FileSystemArtifactStorage(DATA_PATH), FileSystemCourseStorage(DATA_PATH)

    load_server_env_file()
    database_config = get_named_database_config(target)
    session_factory = create_session_factory(
        database_config.resolved_async_url(),
        echo=database_config.echo,
    )
    return PostgresArtifactStorage(session_factory), PostgresCourseStorage(session_factory)


async def seed_course(
    lessons: list[Lesson],
    course_title: str,
    course_desc: str,
    lesson_timeline: list[dict],
    owner_id: str | None,
    instructor_name: str | None,
    course_storage: CourseStorage,
) -> None:
    """Create a fixture-backed course and bind the supplied lesson versions."""
    payload = seeded_course_base_payload()
    if course_title != "default":
        payload["course_id"] = course_title
        payload["title"] = course_title
    if course_desc != "default":
        payload["description"] = course_desc
    if owner_id:
        payload["owner_id"] = owner_id
    if instructor_name:
        payload["instructor"] = instructor_name

    for lesson in lessons:
        payload["lessons"][lesson.identity.lesson_id] = lesson.identity.version
    payload["lesson_timeline"] = lesson_timeline

    course = Course.model_validate(payload)
    await course_storage.save_course(course)


async def seed_lesson(
    lesson_id: str,
    lesson_version: str,
    artifact_storage: ArtifactStorage,
) -> Lesson:
    """Create and persist a seeded lesson with an explicit inference profile."""
    expected_version = SEEDED_LESSON_SPECS.get(lesson_id, {}).get("version", lesson_version)
    if lesson_version != expected_version:
        raise ValueError(
            f"Seed lesson version mismatch for '{lesson_id}': "
            f"got {lesson_version!r}, expected {expected_version!r}."
        )

    lesson = Lesson.model_validate(make_seeded_lesson_payload(lesson_id, lesson_version))
    await artifact_storage.save_lesson(lesson)
    return lesson


async def seed_target(target: str) -> None:
    """Seed the requested storage target with example lessons and courses."""
    artifact_storage, course_storage = _build_storage(target)

    for course_spec in SEEDED_COURSE_SPECS:
        lessons: list[Lesson] = []
        for lesson_id in course_spec["lesson_ids"]:
            lesson_version = SEEDED_LESSON_SPECS[lesson_id]["version"]
            lessons.append(await seed_lesson(lesson_id, lesson_version, artifact_storage))
        await seed_course(
            lessons=lessons,
            course_title=course_spec["course_title"],
            course_desc=course_spec["course_description"],
            lesson_timeline=course_spec.get("lesson_timeline", []),
            owner_id=course_spec.get("owner_id"),
            instructor_name=course_spec.get("instructor"),
            course_storage=course_storage,
        )


async def main() -> None:
    """Seed the requested target with development lesson and course data."""
    args = parse_args()
    await seed_target(args.target)
    print(f"Seed data created for target: {args.target}")


if __name__ == "__main__":
    asyncio.run(main())
