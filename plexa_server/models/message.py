from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
from datetime import datetime, UTC


class Message(BaseModel):
    message_id: str
    session_id: str
    role: Literal["system", "assistant", "user", "instructor"] # Can map instructor to system if not in use
    content: str

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    metadata: Optional[Dict[str, Any]] = None
