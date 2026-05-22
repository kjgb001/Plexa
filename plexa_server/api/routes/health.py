from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from plexa_server.inference.base import InferenceConfig
from plexa_server.inference.routing import InferenceRouter
from plexa_server.runtime import get_app_environment
from plexa_server.storage.storage_interface import ArtifactStorage, SessionStorage


def get_health_router(
    session_storage: SessionStorage,
    artifact_storage: ArtifactStorage,
    inference_router: InferenceRouter,
    required_backend_ids: set[str] | None = None,
) -> APIRouter:
    """Create liveness and readiness endpoints for the server process.

    Args:
        session_storage: Session storage dependency checked by readiness.
        artifact_storage: Artifact storage dependency checked by readiness.
        inference_router: Inference router queried by readiness checks.
        required_backend_ids: Optional subset of backend ids that must be
            healthy for readiness.

    Returns:
        APIRouter: Router exposing `/api/health` and `/api/ready`.
    """

    router = APIRouter(prefix="/api", tags=["health"])

    @router.get("/health")
    async def health():
        """Report that the API process is running.

        Returns:
            dict: Liveness payload indicating that the API is alive.
        """
        return {"status": "alive"}

    @router.get("/ready")
    async def ready():
        """Report dependency readiness for storage and inference services.

        Returns:
            dict | JSONResponse: Readiness payload describing dependency
            status, or a 503 response when any dependency is not ready.
        """
        dependencies = {
            "artifact_storage": "ok",
            "session_storage": "ok",
            "inference": "ok",
        }

        if not await artifact_storage.health_check():
            dependencies["artifact_storage"] = "missing"

        if not await session_storage.health_check():
            dependencies["session_storage"] = "missing"

        inference_statuses = await inference_router.health_check(required_backend_ids)
        if any(status is False for status in inference_statuses.values()):
            dependencies["inference"] = "unavailable"

        if any(v != "ok" for v in dependencies.values()):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "dependencies": dependencies,
                    "inference_backends": inference_statuses,
                },
            )

        return {
            "status": "ready",
            "dependencies": dependencies,
            "inference_backends": inference_statuses,
        }

    @router.get("/debug/inference")
    async def debug_inference():
        """Report active inference routing in non-production environments."""
        if get_app_environment() == "production":
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Not found"},
            )

        profiles = {
            name: {
                "backend_id": profile.backend_id,
                "model": profile.model,
            }
            for name, profile in inference_router.registry.list_profiles().items()
        }
        backends = {
            backend_id: backend.name
            for backend_id, backend in inference_router.registry.list_backends().items()
        }
        resolved_examples = {}
        for profile_name in sorted(set(profiles) | {"default", "fast", "reasoning"}):
            try:
                resolved = inference_router.resolve(InferenceConfig(profile=profile_name))
                resolved_examples[profile_name] = {
                    "backend_id": resolved.backend_id,
                    "backend_name": resolved.backend_name,
                    "model": resolved.model,
                }
            except Exception as exc:
                resolved_examples[profile_name] = {
                    "error": str(exc),
                }

        return {
            "environment": get_app_environment(),
            "default_backend_id": inference_router.default_backend_id,
            "backends": backends,
            "profiles": profiles,
            "resolved_examples": resolved_examples,
        }

    return router
