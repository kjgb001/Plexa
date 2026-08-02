from fastapi import FastAPI

from plexa_server.api.app import build_app
from plexa_server.api.openapi_schema import configure_openapi_security
from plexa_server.auth.config import AuthConfig
from plexa_server.inference.stub import StubInference


def _schema_for(config: AuthConfig) -> dict:
    app = FastAPI(title="Test", version="1")

    @app.get("/api/health")
    async def health():
        return {"status": "alive"}

    @app.get("/api/v1/courses")
    async def courses():
        return {"courses": []}

    configure_openapi_security(app, config)
    return app.openapi()


def test_openapi_describes_dev_header_auth_and_public_health():
    schema = _schema_for(AuthConfig(mode="dev-header", user_header_name="X-Test-User"))

    scheme = schema["components"]["securitySchemes"]["DevHeaderAuth"]
    assert scheme["type"] == "apiKey"
    assert scheme["name"] == "X-Test-User"
    assert schema["security"] == [{"DevHeaderAuth": []}]
    assert schema["paths"]["/api/health"]["get"]["security"] == []
    assert "security" not in schema["paths"]["/api/v1/courses"]["get"]


def test_openapi_describes_bearer_jwt_auth():
    schema = _schema_for(AuthConfig(mode="bearer-jwt"))

    scheme = schema["components"]["securitySchemes"]["BearerAuth"]
    assert scheme == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Institution-issued bearer JWT.",
    }
    assert schema["security"] == [{"BearerAuth": []}]


def test_application_openapi_documents_every_operation(monkeypatch, tmp_path):
    monkeypatch.setenv("PLEXA_AUTH_MODE", "dev-header")
    app = build_app(inference_backend=StubInference(), data_dir=tmp_path)

    schema = app.openapi()
    assert schema["security"] == [{"DevHeaderAuth": []}]

    operations = []
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            operations.append(operation)
            if path in {"/api/health", "/api/ready", "/api/debug/inference"}:
                assert operation["security"] == []
            else:
                assert "security" not in operation

    assert operations
    assert all(operation.get("summary") for operation in operations)
    assert all(operation.get("description") for operation in operations)
