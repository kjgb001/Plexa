from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from plexa_server.inference.base import InferenceError


def get_health_router(
    session_storage,
    artifact_storage,
    inference_backend,
) -> APIRouter:

    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health():
        return {"status": "alive"}

    @router.get("/ready")
    def ready():
        dependencies = {
            "artifact_storage": "ok",
            "session_storage": "ok",
            "inference": "ok",
        }

        try:
            # basic filesystem checks
            if not artifact_storage.base_path.exists():
                dependencies["artifact_storage"] = "missing"

            if not session_storage.base_path.exists():
                dependencies["session_storage"] = "missing"

            inference_backend.health_check()

        except InferenceError:
            dependencies["inference"] = "unavailable"

        if any(v != "ok" for v in dependencies.values()):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "dependencies": dependencies,
                },
            )

        return {
            "status": "ready",
            "dependencies": dependencies,
        }

    return router
