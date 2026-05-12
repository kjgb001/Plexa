from __future__ import annotations

from datetime import UTC, datetime

from plexa_server.models.course import Course, CourseLessonWindow
from plexa_server.models.lesson import Lesson
from plexa_server.models.session import Session
from plexa_server.models.workspace_state import UserCourseState, UserLessonState


def resolve_pinned_lesson_window(
    course: Course,
    now: datetime | None = None,
) -> CourseLessonWindow | None:
    """Return the currently active pinned lesson window for a course."""
    effective_now = now or datetime.now(UTC)
    matches = [
        window
        for window in course.lesson_timeline
        if window.starts_at <= effective_now
        and (window.ends_at is None or effective_now < window.ends_at)
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError("Course lesson timeline has overlapping active windows.")
    return matches[0]


def order_courses_for_user(
    courses: list[Course],
    states: list[UserCourseState],
) -> list[Course]:
    """Order courses by user recency with a deterministic fallback."""
    state_by_course_id = {state.course_id: state for state in states}
    return sorted(
        courses,
        key=lambda course: (
            0 if state_by_course_id.get(course.course_id) is not None else 1,
            -state_by_course_id.get(course.course_id).last_accessed_at.timestamp()
            if state_by_course_id.get(course.course_id) is not None
            else float("inf"),
            course.title.lower(),
            course.course_id,
        ),
    )


def order_lessons_for_user(
    course: Course,
    lessons: list[Lesson],
    states: list[UserLessonState],
    now: datetime | None = None,
) -> list[Lesson]:
    """Order lessons by last accessed first, pinned second, then recency."""
    state_by_key = {
        (state.lesson_id, state.lesson_version): state
        for state in states
    }
    lesson_by_key = {
        (lesson.identity.lesson_id, lesson.identity.version): lesson
        for lesson in lessons
    }

    last_accessed_state = max(
        states,
        key=lambda state: state.last_accessed_at,
        default=None,
    )
    last_accessed_key = None
    if last_accessed_state is not None:
        candidate_key = (last_accessed_state.lesson_id, last_accessed_state.lesson_version)
        if candidate_key in lesson_by_key:
            last_accessed_key = candidate_key

    pinned_window = resolve_pinned_lesson_window(course, now=now)
    pinned_key = None
    if pinned_window is not None:
        candidate_key = (pinned_window.lesson_id, pinned_window.lesson_version)
        if candidate_key in lesson_by_key:
            pinned_key = candidate_key

    sequence_index_by_key = {
        (lesson_id, lesson_version): index
        for index, (lesson_id, lesson_version) in enumerate(course.lessons.items())
    }

    def sort_key(lesson: Lesson) -> tuple[int, float, int, str]:
        lesson_key = (lesson.identity.lesson_id, lesson.identity.version)
        if lesson_key == last_accessed_key:
            priority = 0
        elif lesson_key == pinned_key and lesson_key != last_accessed_key:
            priority = 1
        else:
            priority = 2

        state = state_by_key.get(lesson_key)
        recency_score = (
            -state.last_accessed_at.timestamp()
            if state is not None
            else float("inf")
        )
        sequence_index = sequence_index_by_key.get(lesson_key, len(sequence_index_by_key))
        return (priority, recency_score, sequence_index, lesson.identity.title.lower())

    return sorted(lessons, key=sort_key)


def order_sessions_by_updated_at(sessions: list[Session]) -> list[Session]:
    """Order sessions by most recently updated first."""
    return sorted(
        sessions,
        key=lambda session: (session.updated_at, session.created_at, session.session_id),
        reverse=True,
    )
