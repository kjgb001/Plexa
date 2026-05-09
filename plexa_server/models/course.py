from pydantic import BaseModel, Field, model_validator
from typing import Dict, Optional, List
from datetime import datetime, UTC
from uuid import uuid4


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

    def has_instructor_access(self, user_id: str | None) -> bool:
        """Return whether the user is an authorized instructor for the course."""
        return user_id is not None and user_id in self.instructor_ids
