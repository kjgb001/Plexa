import threading
from typing import Dict


class LockManager:
    """
    Centralized session-level lock manager.

    Provides single-writer serialization per session.
    """

    def __init__(self):
        """Initialize the lock registry and its guard lock."""
        
        self._locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def get_lock(self, session_id: str) -> threading.Lock:
        """Return the shared lock for a session, creating it if needed.

        Args:
            session_id: Identifier of the session whose lock is requested.

        Returns:
            threading.Lock: Lock used to serialize mutations for the session.
        """
        with self._registry_lock:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[session_id] = lock
            return lock

    def release_lock(self, session_id: str) -> None:
        """Remove a lock entry once the session no longer needs coordination.

        Args:
            session_id: Identifier of the session whose lock should be removed.
        """
        with self._registry_lock:
            self._locks.pop(session_id, None)
