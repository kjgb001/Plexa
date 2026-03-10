from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    content: str
    message_id: str | None = None
