from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import os

from plexa_server.db.config import get_database_config, load_server_env_file
from plexa_server.db.session import create_session_factory
from plexa_server.storage.postgres import PostgresArtifactStorage, PostgresSessionStorage
from plexa_server.storage.storage_interface import SessionRevisionConflictError


def _retention_days() -> int:
    raw = os.getenv("PLEXA_CONTENT_RETENTION_DAYS", "")
    if not raw.isdigit() or int(raw) <= 0:
        raise ValueError("PLEXA_CONTENT_RETENTION_DAYS must be a positive integer.")
    return int(raw)


async def cleanup_once(dry_run: bool = False) -> int:
    """Expire student-authored content while retaining submission metadata."""
    load_server_env_file()
    config = get_database_config()
    session_factory = create_session_factory(config.resolved_async_url(), echo=config.echo)
    sessions = PostgresSessionStorage(session_factory)
    artifacts = PostgresArtifactStorage(session_factory)
    cutoff = datetime.now(UTC) - timedelta(days=_retention_days())
    expired = 0

    for session in await sessions.list_sessions():
        content_date = session.turned_in_at or session.closed_at
        if session.is_active or content_date is None or content_date >= cutoff:
            continue
        content_already_expired = (
            not session.transcript_available
            and session.transcript_unavailable_reason == "content_expired"
        )
        if not content_already_expired:
            expired += 1
        if dry_run:
            continue
        if not content_already_expired:
            session.messages = []
            session.transcript_available = False
            session.transcript_unavailable_reason = "content_expired"
            for hook in session.reflection_hooks:
                hook.response_text = None
                hook.last_updated_at = None
            try:
                await sessions.save_session(session)
            except SessionRevisionConflictError:
                continue
        await artifacts.expire_encrypted_log_content(session.session_id)

    return expired


async def run(loop: bool, dry_run: bool) -> None:
    while True:
        expired = await cleanup_once(dry_run=dry_run)
        print(f"Retention cleanup matched {expired} session(s).")
        if not loop:
            return
        await asyncio.sleep(24 * 60 * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Expire Plexa session content by policy.")
    parser.add_argument("--loop", action="store_true", help="Run cleanup once per day.")
    parser.add_argument("--dry-run", action="store_true", help="Report without deleting content.")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(run(loop=arguments.loop, dry_run=arguments.dry_run))
