from typing import Dict, Optional

from plexa_server.models.session import Session
from plexa_server.inference.base import InferenceConfig
from plexa_server.storage.session_protocol import SessionStorage


class InMemoryStorage(SessionStorage):
    """
    Ephemeral storage for development and testing.

    Stores sessions and associated inference configurations in memory.
    Not safe for multi-process or production use.
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._inference_configs: Dict[str, InferenceConfig] = {}

    def save_session(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def save_inference_config(
        self,
        session_id: str,
        config: InferenceConfig,
    ) -> None:
        self._inference_configs[session_id] = config

    def get_inference_config(
        self,
        session_id: str,
    ) -> Optional[InferenceConfig]:
        return self._inference_configs.get(session_id)
