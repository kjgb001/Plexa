from pydantic import BaseModel, Field, model_validator
from typing import Dict, Optional, List
from datetime import datetime, UTC
from uuid import uuid4


class CourseLessonWindow(BaseModel):
    """Time window during which a lesson is pinned for a course."""

    lesson_id: str
    lesson_version: str
    starts_at: datetime
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_bounds(self) -> "CourseLessonWindow":
        """Ensure that a bounded window ends after it begins."""
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("Course lesson timeline windows must end after they begin.")
        return self


class Course(BaseModel):
    """Course metadata, enrollment state, and lesson-version bindings."""

    course_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    instructor: Optional[str] = None
    term: Optional[str] = None

    owner_id: str
    instructor_ids: List[str] = Field(default_factory=list)
    discoverable: bool = True

    enrolled_users: List[str] = Field(default_factory=list)
    pending_requests: List[str] = Field(default_factory=list)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    lessons: Dict[str, str] = Field(default_factory=dict)
    lesson_timeline: List[CourseLessonWindow] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_instructors(self) -> "Course":
        """Ensure the owner is always present exactly once in `instructor_ids`."""
        normalized: list[str] = []
        seen: set[str] = set()
        for user_id in [self.owner_id, *self.instructor_ids]:
            if user_id and user_id not in seen:
                normalized.append(user_id)
                seen.add(user_id)
        self.instructor_ids = normalized
        return self

    @model_validator(mode="after")
    def _validate_lesson_timeline(self) -> "Course":
        """Ensure pinned lesson windows do not overlap and are sorted."""
        windows = sorted(self.lesson_timeline, key=lambda window: window.starts_at)
        for index, window in enumerate(windows):
            if window.lesson_id not in self.lessons:
                raise ValueError("Pinned lesson timeline entries must reference bound course lessons.")

            bound_version = self.lessons[window.lesson_id]
            if bound_version != window.lesson_version:
                raise ValueError("Pinned lesson timeline entries must match the bound lesson version.")

            if index == 0:
                continue

            previous = windows[index - 1]
            if previous.ends_at is None:
                raise ValueError("Pinned lesson timeline entries may not overlap.")
            if window.starts_at < previous.ends_at:
                raise ValueError("Pinned lesson timeline entries may not overlap.")

        self.lesson_timeline = windows
        return self

    def has_instructor_access(self, user_id: str | None) -> bool:
        """Return whether the user is an authorized instructor for the course."""
        return user_id is not None and user_id in self.instructor_ids
