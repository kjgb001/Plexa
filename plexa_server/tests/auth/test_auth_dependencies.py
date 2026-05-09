import asyncio

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from plexa_server.auth.dependencies import (
    ensure_course_instructor,
    ensure_course_owner,
    ensure_enrolled_or_owner,
    get_owned_session,
    require_admin,
    require_identity,
)
from plexa_server.auth.identity import UserIdentity
from plexa_server.auth.middleware import auth_identity_middleware
from plexa_server.models.course import Course
from plexa_server.core.sessions import SessionNotFoundError
from plexa_server.models.session import Session
from plexa_server.tests.fixtures import make_valid_lesson_payload


def run(coro):
    return asyncio.run(coro)


def _identity_payload(identity: UserIdentity) -> dict:
    return {
        "user_id": identity.user_id,
        "roles": sorted(identity.roles),
        "claims": identity.claims,
        "auth_type": identity.auth_type,
        "is_authenticated": identity.is_authenticated,
        "is_admin": identity.is_admin,
        "is_anonymous": identity.is_anonymous,
    }


@pytest.fixture
def auth_app(monkeypatch) -> FastAPI:
    """Return a minimal app exposing auth middleware and dependencies.

    Args:
        monkeypatch: Pytest monkeypatch fixture used to control env config.

    Returns:
        FastAPI: Test app with auth middleware installed.
    """
    monkeypatch.setenv("PLEXA_ADMIN_TOKEN", "test-token")

    app = FastAPI()
    app.middleware("http")(auth_identity_middleware)

    @app.get("/identity")
    async def identity_route(identity: UserIdentity = Depends(require_identity)):
        return _identity_payload(identity)

    @app.get("/admin")
    async def admin_route(identity: UserIdentity = Depends(require_admin)):
        return _identity_payload(identity)

    return app


@pytest.fixture
def auth_client(auth_app: FastAPI) -> TestClient:
    """Return a test client for the auth test app.

    Args:
        auth_app: App exposing auth middleware and dependencies.

    Returns:
        TestClient: Synchronous test client.
    """
    return TestClient(auth_app)


def test_identity_dependency_rejects_anonymous(auth_client: TestClient):
    response = auth_client.get("/identity")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing user identity"


def test_identity_dependency_accepts_dev_user(auth_client: TestClient):
    response = auth_client.get("/identity", headers={"X-User-Id": "tester"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "tester",
        "roles": ["user"],
        "claims": {},
        "auth_type": "dev_header",
        "is_authenticated": True,
        "is_admin": False,
        "is_anonymous": False,
    }


def test_admin_dependency_accepts_valid_admin_token(auth_client: TestClient):
    response = auth_client.get("/admin", headers={"X-Admin-Token": "test-token"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": None,
        "roles": ["admin"],
        "claims": {"admin_token_present": True},
        "auth_type": "admin_token",
        "is_authenticated": False,
        "is_admin": True,
        "is_anonymous": False,
    }


def test_admin_dependency_accepts_admin_plus_user_identity(auth_client: TestClient):
    response = auth_client.get(
        "/admin",
        headers={
            "X-Admin-Token": "test-token",
            "X-User-Id": "instructor-1",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "instructor-1",
        "roles": ["admin", "user"],
        "claims": {"admin_token_present": True},
        "auth_type": "admin_token",
        "is_authenticated": True,
        "is_admin": True,
        "is_anonymous": False,
    }


def test_admin_dependency_rejects_invalid_admin_token(auth_client: TestClient):
    response = auth_client.get("/admin", headers={"X-Admin-Token": "wrong-token"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin token"


def test_admin_dependency_rejects_user_only_identity(auth_client: TestClient):
    response = auth_client.get("/admin", headers={"X-User-Id": "tester"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid admin token"


def test_admin_dependency_returns_500_when_token_unconfigured(monkeypatch):
    monkeypatch.delenv("PLEXA_ADMIN_TOKEN", raising=False)

    app = FastAPI()
    app.middleware("http")(auth_identity_middleware)

    @app.get("/admin")
    async def admin_route(identity: UserIdentity = Depends(require_admin)):
        return _identity_payload(identity)

    client = TestClient(app)
    response = client.get("/admin", headers={"X-Admin-Token": "anything"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Admin token not configured"


def test_ensure_course_owner_allows_owner():
    identity = UserIdentity(user_id="owner-1", roles={"user"}, auth_type="dev_header")

    ensure_course_owner("owner-1", identity)


def test_ensure_course_owner_rejects_non_owner():
    identity = UserIdentity(user_id="student-1", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        ensure_course_owner("owner-1", identity)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Course not found"


def test_ensure_course_instructor_allows_authorized_instructor():
    course = Course.model_validate(
        {
            "course_id": "CS101",
            "title": "Intro",
            "owner_id": "owner-1",
            "instructor_ids": ["owner-1", "assistant-1"],
        }
    )
    identity = UserIdentity(user_id="assistant-1", roles={"user"}, auth_type="dev_header")

    ensure_course_instructor(course, identity)


def test_ensure_course_instructor_rejects_non_instructor():
    course = Course.model_validate(
        {
            "course_id": "CS101",
            "title": "Intro",
            "owner_id": "owner-1",
            "instructor_ids": ["owner-1", "assistant-1"],
        }
    )
    identity = UserIdentity(user_id="student-1", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        ensure_course_instructor(course, identity)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Course not found"


def test_ensure_enrolled_or_owner_allows_enrolled_user():
    identity = UserIdentity(user_id="student-1", roles={"user"}, auth_type="dev_header")

    ensure_enrolled_or_owner("owner-1", ["student-1", "student-2"], identity)


def test_ensure_enrolled_or_owner_allows_owner():
    identity = UserIdentity(user_id="owner-1", roles={"user"}, auth_type="dev_header")

    ensure_enrolled_or_owner("owner-1", ["student-1", "student-2"], identity)


def test_ensure_enrolled_or_owner_rejects_non_member():
    identity = UserIdentity(user_id="outsider", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        ensure_enrolled_or_owner("owner-1", ["student-1", "student-2"], identity)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Course not found"


class _FakeSessionManager:
    def __init__(self, session: Session | None):
        self._session = session

    async def get_session(self, session_id: str) -> Session:
        if self._session is None or self._session.session_id != session_id:
            raise SessionNotFoundError(session_id)
        return self._session


def _make_session(session_id: str = "s1", user_id: str = "tester") -> Session:
    lesson_payload = make_valid_lesson_payload()
    return Session(
        session_id=session_id,
        user_id=user_id,
        lesson_id=lesson_payload["identity"]["lesson_id"],
        lesson_version=lesson_payload["identity"]["version"],
        course_id="CS101",
        messages=[],
        turn_count=0,
        max_turns=lesson_payload["constraints"]["turn_limit"],
        is_active=True,
    )


def test_get_owned_session_returns_session_for_owner():
    session = _make_session()
    identity = UserIdentity(user_id="tester", roles={"user"}, auth_type="dev_header")

    loaded = run(get_owned_session(_FakeSessionManager(session), "s1", identity))

    assert loaded.session_id == "s1"


def test_get_owned_session_hides_missing_session():
    identity = UserIdentity(user_id="tester", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        run(get_owned_session(_FakeSessionManager(None), "missing", identity))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"


def test_get_owned_session_hides_non_owned_session():
    session = _make_session(user_id="alice")
    identity = UserIdentity(user_id="bob", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        run(get_owned_session(_FakeSessionManager(session), "s1", identity))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"
