from unittest.mock import MagicMock

import pytest

from plexa_server.api.app import build_app
from plexa_server.db.config import DatabaseConfig
from plexa_server.inference.stub import StubInference
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseStorage,
    SessionStorage,
    WorkspaceStateStorage,
)
from plexa_server.utils.cryptography import generate_encryption_key


def _injected_storages() -> dict:
    return {
        "artifact_storage": MagicMock(spec=ArtifactStorage),
        "session_storage": MagicMock(spec=SessionStorage),
        "course_storage": MagicMock(spec=CourseStorage),
        "workspace_state_storage": MagicMock(spec=WorkspaceStateStorage),
    }


def test_build_app_accepts_complete_storage_injection(monkeypatch):
    monkeypatch.setenv("PLEXA_LOG_ENCRYPTION_KEY", generate_encryption_key())

    app = build_app(inference_backend=StubInference(), **_injected_storages())

    assert app.title == "Plexa Server"


def test_build_app_rejects_partial_storage_injection():
    storages = _injected_storages()
    storages.pop("workspace_state_storage")

    with pytest.raises(ValueError, match="requires artifact, session, course, and workspace"):
        build_app(inference_backend=StubInference(), **storages)


def test_build_app_requires_postgres_when_storages_are_not_injected(monkeypatch):
    monkeypatch.setattr(
        "plexa_server.db.config.get_database_config",
        lambda: DatabaseConfig(),
    )

    with pytest.raises(RuntimeError, match="requires PostgreSQL storage"):
        build_app(inference_backend=StubInference())
