from pydantic import BaseModel, Field
from typing import Literal, Optional, Dict, Any
from datetime import datetime


class Message(BaseModel):
    message_id: str
    role: Literal["system", "assistant", "user", "instructor"] # Can map instructor to system if not in use
    content: str

    created_at: datetime = Field(default_factory=datetime.utcnow)

    metadata: Optional[Dict[str, Any]] = None
