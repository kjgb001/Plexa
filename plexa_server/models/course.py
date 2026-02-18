from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from datetime import datetime, UTC
from uuid import uuid4


class Course(BaseModel):
    course_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    instructor: Optional[str] = None
    term: Optional[str] = None

    owner_id: str
    discoverable: bool = True

    enrolled_users: List[str] = Field(default_factory=list)
    pending_requests: List[str] = Field(default_factory=list)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    lessons: Dict[str, str] = Field(default_factory=dict)
