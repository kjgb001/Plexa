import threading

from plexa_server.utils.lock_manager import LockManager


def test_same_session_returns_same_lock():
    manager = LockManager()

    lock1 = manager.get_lock("s1")
    lock2 = manager.get_lock("s1")

    assert lock1 is lock2


def test_different_sessions_return_different_locks():
    manager = LockManager()

    lock1 = manager.get_lock("s1")
    lock2 = manager.get_lock("s2")

    assert lock1 is not lock2


def test_release_removes_lock():
    manager = LockManager()

    lock1 = manager.get_lock("s1")
    manager.release_lock("s1")
    lock2 = manager.get_lock("s1")

    assert lock1 is not lock2


def test_thread_safe_lock_creation():
    manager = LockManager()
    locks = []

    def get_lock():
        locks.append(manager.get_lock("s1"))

    threads = [threading.Thread(target=get_lock) for _ in range(20)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    first = locks[0]
    assert all(lock is first for lock in locks)
