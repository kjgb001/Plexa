from typing import Dict, Optional
from typing import List

from plexa_server.models.session import Session
from plexa_server.inference.base import InferenceConfig
from plexa_server.storage.storage_interface import SessionStorage


class InMemoryStorage(SessionStorage):
    """
    Ephemeral storage for development and testing.

    Stores sessions and associated inference configurations in memory.
    Not safe for multi-process or production use.
    """

    def __init__(self):
        """Initialize empty in-memory stores for sessions and configs.
        """
        self._sessions: Dict[str, Session] = {}
        self._inference_configs: Dict[str, InferenceConfig] = {}

    async def save_session(self, session: Session) -> None:
        """Store or replace a session in memory.

        Args:
            session: Session object to persist in memory.
        """
        self._sessions[session.session_id] = session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Return a stored session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Stored session object, or `None` if absent.
        """
        return self._sessions.get(session_id)

    async def delete_session(self, session_id: str) -> None:
        """Remove a stored session if present.

        Args:
            session_id: Identifier of the session to remove.
        """
        self._sessions.pop(session_id, None)
        self._inference_configs.pop(session_id, None)

    async def save_inference_config(
        self,
        session_id: str,
        config: InferenceConfig,
    ) -> None:
        """Associate a frozen inference config with a session id.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to store.
        """
        self._inference_configs[session_id] = config

    async def get_inference_config(
        self,
        session_id: str,
    ) -> Optional[InferenceConfig]:
        """Return a stored inference config.

        Args:
            session_id: Identifier of the session whose config should be loaded.

        Returns:
            Optional[InferenceConfig]: Stored config, or `None` if absent.
        """
        return self._inference_configs.get(session_id)

    async def list_sessions(self) -> List[Session]:
        """Return all stored sessions.

        Returns:
            List[Session]: Sessions currently held in memory.
        """
        return list(self._sessions.values())

    async def health_check(self) -> bool:
        """Report whether the in-memory storage backend is available.

        Returns:
            bool: Always `True` for in-memory storage.
        """
        return True
