from pathlib import Path

from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
)

from plexa_server.models.lesson import Lesson
from plexa_server.models.course import Course
from plexa_server.utils.filesystem_data_dir import get_data_dir_path

from plexa_server.tests.fixtures import (
    valid_course,
    valid_lesson
)


DATA_PATH = get_data_dir_path()

def seed_course(lesson_id, lesson_version, course_storage: FileSystemCourseStorage):
    """Create a fixture-backed course and bind the supplied lesson version.

    Args:
        lesson_id: Lesson identifier to bind into the seeded course.
        lesson_version: Lesson version to bind into the seeded course.
        course_storage: Storage backend used to persist the seeded course.
    """
    payload = valid_course()
    payload["lessons"][lesson_id] = lesson_version
    course = Course.model_validate(payload)
    course_storage.save_course(course)


def seed_lesson(artifact_storage: FileSystemArtifactStorage):
    """Create and persist the fixture lesson, returning its id and version.

    Args:
        artifact_storage: Storage backend used to persist the seeded lesson.

    Returns:
        tuple[str, str]: Seeded lesson id and version.
    """
    payload = valid_lesson()
    lesson = Lesson.model_validate(payload)

    artifact_storage.save_lesson(lesson)

    lesson_id = payload["identity"]["lesson_id"]
    lesson_version = payload["identity"]["version"]
    return lesson_id, lesson_version


def main():
    """Seed the repository data directory with one lesson and one course."""
    
    artifact_storage = FileSystemArtifactStorage(DATA_PATH)
    course_storage = FileSystemCourseStorage(DATA_PATH)

    lesson_id, lesson_version = seed_lesson(artifact_storage)
    seed_course(lesson_id, lesson_version, course_storage)

    print("Seed data created.")


if __name__ == "__main__":
    main()
