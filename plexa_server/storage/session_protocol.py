from abc import ABC
from typing import Optional

from plexa_server.models.session import Session
from plexa_server.inference.base import InferenceConfig

class SessionStorage(ABC):
    """Minimal storage contract for sessions and frozen inference configs."""

    def save_session(self, session: Session) -> None:
        """Persist the current session state.

        Args:
            session: Session object to store.
        """
        ...

    def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Persisted session, or `None` if it does not
            exist.
        """
        ...

    def delete_session(self, session_id: str) -> None:
        """Delete any persisted state associated with a session id.

        Args:
            session_id: Identifier of the session to delete.
        """
        ...

    def save_inference_config(self, session_id: str, config: InferenceConfig) -> None:
        """Persist the frozen inference config for a session.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to store.
        """
        ...

    def get_inference_config(self, session_id: str) -> Optional[InferenceConfig]:
        """Load a session's inference config.

        Args:
            session_id: Identifier of the session whose config should be loaded.

        Returns:
            Optional[InferenceConfig]: Persisted config, or `None` if absent.
        """
        ...
