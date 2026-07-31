import asyncio

from plexa_server.utils.lock_manager import LockManager


def run(coro):
    return asyncio.run(coro)


def test_same_session_mutations_are_serialized():
    async def scenario():
        manager = LockManager()
        first_entered = asyncio.Event()
        release_first = asyncio.Event()
        order: list[str] = []

        async def first():
            async with manager.lock("s1"):
                order.append("first-entered")
                first_entered.set()
                await release_first.wait()
                order.append("first-leaving")

        async def second():
            await first_entered.wait()
            async with manager.lock("s1"):
                order.append("second-entered")

        first_task = asyncio.create_task(first())
        second_task = asyncio.create_task(second())
        await first_entered.wait()
        await asyncio.sleep(0)
        assert order == ["first-entered"]
        release_first.set()
        await asyncio.gather(first_task, second_task)

        assert order == ["first-entered", "first-leaving", "second-entered"]
        assert manager._locks == {}

    run(scenario())


def test_different_sessions_can_mutate_concurrently():
    async def scenario():
        manager = LockManager()
        both_entered = asyncio.Event()
        entered: set[str] = set()

        async def worker(session_id: str):
            async with manager.lock(session_id):
                entered.add(session_id)
                if len(entered) == 2:
                    both_entered.set()
                await asyncio.wait_for(both_entered.wait(), timeout=1)

        await asyncio.gather(worker("s1"), worker("s2"))
        assert entered == {"s1", "s2"}
        assert manager._locks == {}

    run(scenario())


def test_cancelled_waiter_does_not_leak_lock_entry():
    async def scenario():
        manager = LockManager()
        holder_entered = asyncio.Event()
        release_holder = asyncio.Event()

        async def holder():
            async with manager.lock("s1"):
                holder_entered.set()
                await release_holder.wait()

        async def waiter():
            async with manager.lock("s1"):
                raise AssertionError("cancelled waiter entered the lock")

        holder_task = asyncio.create_task(holder())
        await holder_entered.wait()
        waiter_task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        waiter_task.cancel()
        try:
            await waiter_task
        except asyncio.CancelledError:
            pass
        release_holder.set()
        await holder_task

        assert manager._locks == {}

    run(scenario())
