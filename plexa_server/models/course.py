from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime, UTC
from uuid import uuid4


class Course(BaseModel):
    course_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: Optional[str] = None
    instructor: Optional[str] = None
    term: Optional[str] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    lessons: Dict[str, str] = Field(default_factory=dict)
