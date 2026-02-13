from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    lesson_id: str
    lesson_version: str
    user_id: str


class SendMessageRequest(BaseModel):
    content: str
    message_id: str | None = None
