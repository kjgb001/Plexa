from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class _LockEntry:
    lock: asyncio.Lock
    users: int = 0


class LockManager:
    """Reference-counted asynchronous session lock registry."""

    def __init__(self) -> None:
        self._locks: dict[str, _LockEntry] = {}
        self._registry_lock = threading.Lock()

    @asynccontextmanager
    async def lock(self, session_id: str) -> AsyncIterator[None]:
        """Serialize one asynchronous mutation for a session."""
        with self._registry_lock:
            entry = self._locks.get(session_id)
            if entry is None:
                entry = _LockEntry(lock=asyncio.Lock())
                self._locks[session_id] = entry
            entry.users += 1

        acquired = False
        try:
            await entry.lock.acquire()
            acquired = True
            yield
        finally:
            if acquired:
                entry.lock.release()
            with self._registry_lock:
                entry.users -= 1
                if entry.users == 0 and self._locks.get(session_id) is entry:
                    self._locks.pop(session_id, None)
