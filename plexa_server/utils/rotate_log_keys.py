from __future__ import annotations

import asyncio

from plexa_server.core.encrypted_logs import EncryptedLogService
from plexa_server.db.config import get_database_config, load_server_env_file
from plexa_server.db.session import create_session_factory
from plexa_server.storage.postgres import PostgresArtifactStorage, PostgresCourseStorage


async def main() -> None:
    load_server_env_file()
    config = get_database_config()
    session_factory = create_session_factory(config.resolved_async_url(), echo=config.echo)
    artifacts = PostgresArtifactStorage(session_factory)
    courses = PostgresCourseStorage(session_factory)
    service = EncryptedLogService.from_env(artifacts, courses)
    if service is None:
        raise RuntimeError("Encrypted-log keyring is not configured.")
    count = await service.reencrypt_all_with_active_key()
    print(f"Re-encrypted {count} log(s) with the active key.")


if __name__ == "__main__":
    asyncio.run(main())
