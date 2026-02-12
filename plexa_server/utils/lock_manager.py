import threading
from typing import Dict


class LockManager:
    """
    Centralized session-level lock manager.

    Provides single-writer serialization per session.
    """

    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def get_lock(self, session_id: str) -> threading.Lock:
        with self._registry_lock:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[session_id] = lock
            return lock

    def release_lock(self, session_id: str) -> None:
        '''Cleanup hook to prevent unbounded growth.'''
        with self._registry_lock:
            self._locks.pop(session_id, None)
