import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def _load_env_file() -> None:
    """Load environment variables from the server-local `.env` file.

    Existing environment variables are preserved. Missing `.env` files are
    ignored silently.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")

        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class DatabaseConfig:
    """Database connection settings resolved from the environment."""

    async_url: str | None = None
    sync_url: str | None = None
    echo: bool = False

    @property
    def is_configured(self) -> bool:
        """Return whether a database URL has been configured.

        Returns:
            bool: `True` when either async or sync URLs are present.
        """
        return self.async_url is not None or self.sync_url is not None

    def resolved_async_url(self) -> str:
        """Return the async database URL for runtime use.

        Returns:
            str: SQLAlchemy async database URL.

        Raises:
            ValueError: If no database URL has been configured.
        """
        if self.async_url is not None:
            return self.async_url

        if self.sync_url is None:
            raise ValueError("PLEXA_DATABASE_URL or PLEXA_DATABASE_SYNC_URL is required.")

        if self.sync_url.startswith("postgresql://"):
            return self.sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        return self.sync_url

    def resolved_sync_url(self) -> str:
        """Return the sync database URL for migration use.

        Returns:
            str: SQLAlchemy sync database URL.

        Raises:
            ValueError: If no database URL has been configured.
        """
        if self.sync_url is not None:
            return self.sync_url

        if self.async_url is None:
            raise ValueError("PLEXA_DATABASE_URL or PLEXA_DATABASE_SYNC_URL is required.")

        if self.async_url.startswith("postgresql+asyncpg://"):
            return self.async_url.replace("postgresql+asyncpg://", "postgresql://", 1)

        return self.async_url

    def database_name(self) -> str:
        """Return the database name encoded in the configured URL.

        Returns:
            str: Database name parsed from the resolved async URL.
        """
        parsed = urlsplit(self.resolved_async_url())
        return parsed.path.lstrip("/")

    def with_database(self, database_name: str) -> "DatabaseConfig":
        """Return a config pointing at a different database on the same server.

        Args:
            database_name: Database name to embed in the returned URLs.

        Returns:
            DatabaseConfig: Derived config that targets the supplied database.
        """
        return DatabaseConfig(
            async_url=_replace_database_name(self.resolved_async_url(), database_name),
            sync_url=_replace_database_name(self.resolved_sync_url(), database_name),
            echo=self.echo,
        )


def _replace_database_name(url: str, database_name: str) -> str:
    """Replace the database name in a Postgres connection URL.

    Args:
        url: Source database URL.
        database_name: Replacement database name.

    Returns:
        str: URL with the replaced database path.
    """
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment))


def get_database_config() -> DatabaseConfig:
    """Load database configuration from environment variables.

    Returns:
        DatabaseConfig: Parsed database connection configuration.
    """
    _load_env_file()
    async_url = os.getenv("PLEXA_DATABASE_URL")
    sync_url = os.getenv("PLEXA_DATABASE_SYNC_URL")
    echo = os.getenv("PLEXA_DATABASE_ECHO", "false").lower() == "true"
    return DatabaseConfig(async_url=async_url, sync_url=sync_url, echo=echo)


def get_test_database_config() -> DatabaseConfig:
    """Load test database configuration from environment variables.

    Returns:
        DatabaseConfig: Parsed test database configuration.
    """
    _load_env_file()
    async_url = os.getenv("PLEXA_TEST_DATABASE_URL")
    sync_url = os.getenv("PLEXA_TEST_DATABASE_SYNC_URL")
    echo = os.getenv("PLEXA_DATABASE_ECHO", "false").lower() == "true"
    return DatabaseConfig(async_url=async_url, sync_url=sync_url, echo=echo)


def get_named_database_config(name: str) -> DatabaseConfig:
    """Load a named database configuration.

    Args:
        name: Supported database target name.

    Returns:
        DatabaseConfig: Parsed database configuration for the target.

    Raises:
        ValueError: If the target name is not recognized.
    """
    if name == "dev":
        return get_database_config()
    if name == "test":
        return get_test_database_config()

    raise ValueError(f"Unsupported database target: {name}")


def get_bootstrap_database_config(target: DatabaseConfig) -> DatabaseConfig:
    """Return the admin/bootstrap connection settings for database creation.

    Existing explicit bootstrap URLs win. Otherwise this derives a config that
    connects to the default `postgres` database on the same server.

    Args:
        target: Runtime target database configuration.

    Returns:
        DatabaseConfig: Bootstrap database configuration.
    """
    _load_env_file()
    async_url = os.getenv("PLEXA_BOOTSTRAP_DATABASE_URL")
    sync_url = os.getenv("PLEXA_BOOTSTRAP_DATABASE_SYNC_URL")
    if async_url is not None or sync_url is not None:
        return DatabaseConfig(async_url=async_url, sync_url=sync_url, echo=target.echo)

    return target.with_database("postgres")
