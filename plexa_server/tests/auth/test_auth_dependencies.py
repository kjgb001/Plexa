import asyncio
import base64
import hashlib
import hmac
import json
import time

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
from plexa_server.auth.factory import clear_request_authenticator_cache
from plexa_server.auth.identity import UserIdentity
from plexa_server.auth.middleware import auth_identity_middleware
from plexa_server.core.sessions import SessionNotFoundError
from plexa_server.models.course import Course
from plexa_server.models.session import Session


def run(coro):
    return asyncio.run(coro)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def make_hs256_jwt(secret: str, payload: dict[str, object], header: dict[str, object] | None = None) -> str:
    header_dict = {"alg": "HS256", "typ": "JWT"}
    if header:
        header_dict.update(header)
    encoded_header = _b64url(json.dumps(header_dict, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_b64url(signature)}"


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


@pytest.fixture(autouse=True)
def clear_auth_cache():
    clear_request_authenticator_cache()
    yield
    clear_request_authenticator_cache()


@pytest.fixture
def dev_auth_app(monkeypatch) -> FastAPI:
    monkeypatch.setenv("PLEXA_AUTH_MODE", "dev-header")
    monkeypatch.setenv("PLEXA_ADMIN_USER_IDS", "admin-user")

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
def dev_auth_client(dev_auth_app: FastAPI) -> TestClient:
    return TestClient(dev_auth_app)


@pytest.fixture
def bearer_auth_app(monkeypatch) -> FastAPI:
    monkeypatch.setenv("PLEXA_AUTH_MODE", "bearer-jwt")
    monkeypatch.setenv("PLEXA_AUTH_SHARED_SECRET", "super-secret")
    monkeypatch.setenv("PLEXA_AUTH_ALLOWED_ALGORITHMS", "HS256")
    monkeypatch.setenv("PLEXA_AUTH_ISSUER", "https://issuer.example")
    monkeypatch.setenv("PLEXA_AUTH_AUDIENCE", "plexa-api")
    monkeypatch.setenv("PLEXA_AUTH_ROLES_CLAIM", "roles")
    monkeypatch.setenv("PLEXA_ADMIN_USER_IDS", '["admin-sub"]')

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
def bearer_auth_client(bearer_auth_app: FastAPI) -> TestClient:
    return TestClient(bearer_auth_app)


def test_identity_dependency_rejects_anonymous(dev_auth_client: TestClient):
    response = dev_auth_client.get("/identity")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing user identity"


def test_identity_dependency_accepts_dev_user(dev_auth_client: TestClient):
    response = dev_auth_client.get("/identity", headers={"X-User-Id": "tester"})

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


def test_admin_dependency_accepts_allowlisted_dev_admin(dev_auth_client: TestClient):
    response = dev_auth_client.get("/admin", headers={"X-User-Id": "admin-user"})

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "admin-user",
        "roles": ["admin", "user"],
        "claims": {},
        "auth_type": "dev_header",
        "is_authenticated": True,
        "is_admin": True,
        "is_anonymous": False,
    }


def test_admin_dependency_rejects_non_admin_dev_identity(dev_auth_client: TestClient):
    response = dev_auth_client.get("/admin", headers={"X-User-Id": "tester"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access denied"


def test_bearer_identity_dependency_accepts_valid_jwt(bearer_auth_client: TestClient):
    token = make_hs256_jwt(
        "super-secret",
        {
            "sub": "student-1",
            "iss": "https://issuer.example",
            "aud": "plexa-api",
            "exp": int(time.time()) + 3600,
            "roles": ["learner"],
        },
    )

    response = bearer_auth_client.get("/identity", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "student-1"
    assert payload["roles"] == ["learner", "user"]
    assert payload["auth_type"] == "bearer_jwt"
    assert payload["is_authenticated"] is True


def test_bearer_admin_dependency_accepts_allowlisted_admin_user(bearer_auth_client: TestClient):
    token = make_hs256_jwt(
        "super-secret",
        {
            "sub": "admin-sub",
            "iss": "https://issuer.example",
            "aud": "plexa-api",
            "exp": int(time.time()) + 3600,
        },
    )

    response = bearer_auth_client.get("/admin", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "admin-sub"
    assert payload["roles"] == ["admin", "user"]
    assert payload["auth_type"] == "bearer_jwt"


def test_bearer_dependency_rejects_invalid_token(bearer_auth_client: TestClient):
    response = bearer_auth_client.get("/identity", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"


def test_bearer_dependency_rejects_wrong_audience(bearer_auth_client: TestClient):
    token = make_hs256_jwt(
        "super-secret",
        {
            "sub": "student-1",
            "iss": "https://issuer.example",
            "aud": "wrong-audience",
            "exp": int(time.time()) + 3600,
        },
    )

    response = bearer_auth_client.get("/identity", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid bearer token"


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

    async def get_session(self, session_id: str):
        if self._session is None:
            raise SessionNotFoundError(session_id)
        return self._session


def test_get_owned_session_returns_matching_session():
    session = Session(
        session_id="session-1",
        user_id="owner-1",
        lesson_id="lesson-1",
        lesson_version="1.0.0",
        course_id="CS101",
        messages=[],
    )
    manager = _FakeSessionManager(session)
    identity = UserIdentity(user_id="owner-1", roles={"user"}, auth_type="dev_header")

    loaded = run(get_owned_session(manager, "session-1", identity))
    assert loaded.session_id == "session-1"


def test_get_owned_session_rejects_other_user():
    session = Session(
        session_id="session-1",
        user_id="owner-1",
        lesson_id="lesson-1",
        lesson_version="1.0.0",
        course_id="CS101",
        messages=[],
    )
    manager = _FakeSessionManager(session)
    identity = UserIdentity(user_id="other-user", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        run(get_owned_session(manager, "session-1", identity))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"


def test_get_owned_session_rejects_missing_session():
    manager = _FakeSessionManager(None)
    identity = UserIdentity(user_id="owner-1", roles={"user"}, auth_type="dev_header")

    with pytest.raises(HTTPException) as exc_info:
        run(get_owned_session(manager, "missing", identity))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Session not found"
