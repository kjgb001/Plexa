from pathlib import Path

from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
)
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage

from plexa_server.models.lesson import Lesson
from plexa_server.models.course import Course
from plexa_server.utils.filesystem_data_dir import get_data_dir_path

from plexa_server.tests.fixtures import (
    valid_course,
    valid_lesson
)


DATA_PATH = get_data_dir_path()

def seed_course(lessons, course_title, course_desc, course_storage: CourseStorage):
    """Create a fixture-backed course and bind the supplied lesson version.

    Args:
        lesson_id: Lesson identifier to bind into the seeded course.
        lesson_version: Lesson version to bind into the seeded course.
        course_storage: Storage backend used to persist the seeded course.
    """
    payload = valid_course()
    if course_title != "default":
        payload["course_id"] = course_title
        payload["title"] = course_title
    if course_desc != "default":
        payload["description"] = course_desc

    for lesson in lessons:
        payload["lessons"][lesson.identity.lesson_id] = lesson.identity.version
    course = Course.model_validate(payload)
    course_storage.save_course(course)


def seed_lesson(lesson_id, lesson_version, artifact_storage: ArtifactStorage):
    """Create and persist the fixture lesson, returning its id and version.

    Args:
        artifact_storage: Storage backend used to persist the seeded lesson.

    Returns:
        tuple[str, str]: Seeded lesson id and version.
    """
    payload = valid_lesson()
    if lesson_id != "default":
        payload["identity"]["lesson_id"] = lesson_id
        payload["identity"]["title"] = lesson_id
    if lesson_version != "default":
        payload["identity"]["version"] = lesson_version
    lesson = Lesson.model_validate(payload)

    artifact_storage.save_lesson(lesson)

    return lesson


def main():
    """Seed the repository data directory with one lesson and one course."""
    
    artifact_storage = FileSystemArtifactStorage(DATA_PATH)
    course_storage = FileSystemCourseStorage(DATA_PATH)

    courses = {"default": "default", "Data Visualization": "Using AI for accelerated visualization"}
    course_titles = list(courses.keys())
    course_descs = list(courses.values())

    lessons = []
    lesson_data = {"default": "default", "The Danger of Hallucinations": "0.1.0",
        "The Power of Prompt Engineering": "0.3.0", "Managing Context Decay": "0.2.0"}
    for l in lesson_data.items():
        lessons.append(seed_lesson(l[0], l[1], artifact_storage))
    seed_course(lessons, course_titles[0], course_descs[0], course_storage)

    lessons = []
    lesson_data = {"Prompt Engineering for Data Viz": "0.2.0", "LLM Assisted Data Evaluation": "0.4.0"}
    for l in lesson_data.items():
        lessons.append(seed_lesson(l[0], l[1], artifact_storage))
    seed_course(lessons, course_titles[1], course_descs[1], course_storage)

    print("Seed data created.")


if __name__ == "__main__":
    main()
