from pydantic import BaseModel


class SendMessageRequest(BaseModel):
    """Request body for appending a user message to a session."""

    content: str
    message_id: str | None = None


class ReflectionResponseRequest(BaseModel):
    """Request body for saving a reflection response."""

    response_text: str
