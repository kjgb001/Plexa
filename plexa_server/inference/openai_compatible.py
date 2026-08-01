from __future__ import annotations

import asyncio
import json
import socket
import time
from typing import Any, AsyncIterator, List
from urllib import error, request

import httpx

from plexa_server.db.config import load_server_env_file
from plexa_server.inference.base import (
    InferenceBackend,
    InferenceBackendUnavailable,
    InferenceChunk,
    InferenceError,
    InferenceMalformedResponse,
    InferenceRejected,
    InferenceResult,
    InferenceTimeout,
    ResolvedInferenceConfig,
    Usage,
)


class _NoRedirectHandler(request.HTTPRedirectHandler):
    """Prevent inference credentials from following redirects to another URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenAICompatibleInference(InferenceBackend):
    """Inference adapter for OpenAI-compatible chat completion servers.

    This adapter is intentionally generic. Ollama, vLLM, and similar local
    runtimes can be targeted by configuration as long as they expose a
    sufficiently compatible `/v1` HTTP surface.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        """Initialize the adapter.

        Args:
            base_url: Base OpenAI-compatible API URL, typically ending in `/v1`.
            api_key: Optional bearer token for the backend.
            timeout_s: Default network timeout in seconds.
        """
        if timeout_s <= 0:
            raise ValueError("Inference timeout must be greater than zero.")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_s = timeout_s

    @property
    def name(self) -> str:
        """Return the stable adapter identifier."""
        return "openai-compatible"

    @classmethod
    def from_env(cls) -> "OpenAICompatibleInference":
        """Build an adapter from environment configuration.

        Returns:
            OpenAICompatibleInference: Configured inference adapter.

        Raises:
            ValueError: If required environment configuration is missing or
                invalid.
        """
        import os

        load_server_env_file()

        base_url = os.getenv("PLEXA_OPENAI_BASE_URL")
        if not base_url:
            raise ValueError("PLEXA_OPENAI_BASE_URL must be configured.")

        api_key = os.getenv("PLEXA_OPENAI_API_KEY")
        timeout_s_raw = os.getenv("PLEXA_OPENAI_TIMEOUT_S", "30.0")
        try:
            timeout_s = float(timeout_s_raw)
        except ValueError as exc:
            raise ValueError("PLEXA_OPENAI_TIMEOUT_S must be a float.") from exc

        return cls(
            base_url=base_url,
            api_key=api_key,
            timeout_s=timeout_s,
        )

    def _map_role(self, role: str) -> str:
        """Map Plexa roles into OpenAI-compatible chat roles."""
        if role == "instructor":
            return "system"
        return role

    def _build_payload(
        self,
        messages: List["Message"],
        config: ResolvedInferenceConfig,
    ) -> dict[str, Any]:
        """Build a chat completion request payload."""
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": self._map_role(message.role), "content": message.content}
                for message in messages
            ],
        }

        if config.temperature is not None:
            payload["temperature"] = config.temperature
        if config.top_p is not None:
            payload["top_p"] = config.top_p
        if config.max_tokens is not None:
            payload["max_tokens"] = config.max_tokens
        if config.stop is not None:
            payload["stop"] = config.stop
        if config.seed is not None:
            payload["seed"] = config.seed

        for key, value in config.extra.items():
            if key not in payload:
                payload[key] = value

        return payload

    def _headers(self) -> dict[str, str]:
        """Build HTTP headers for backend requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout_s: float,
    ) -> dict[str, Any]:
        """Execute an HTTP request and parse the response as JSON."""
        url = f"{self._base_url}{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            url,
            data=body,
            headers=self._headers(),
            method=method,
        )

        try:
            opener = request.build_opener(_NoRedirectHandler())
            with opener.open(http_request, timeout=timeout_s) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code == 408:
                raise InferenceTimeout(detail or "Inference request timed out.") from exc
            if exc.code in {400, 401, 403, 422}:
                raise InferenceRejected(detail or f"Inference request rejected ({exc.code}).") from exc
            if exc.code == 404:
                raise InferenceBackendUnavailable(
                    detail or "OpenAI-compatible endpoint not found; verify base URL."
                ) from exc
            raise InferenceBackendUnavailable(
                detail or f"Inference backend returned HTTP {exc.code}."
            ) from exc
        except error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, TimeoutError | socket.timeout):
                raise InferenceTimeout("Inference request timed out.") from exc
            raise InferenceBackendUnavailable("Inference backend is unreachable.") from exc
        except TimeoutError as exc:
            raise InferenceTimeout("Inference request timed out.") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise InferenceMalformedResponse("Inference backend returned invalid JSON.") from exc

        if not isinstance(data, dict):
            raise InferenceMalformedResponse("Inference backend returned a non-object JSON response.")

        return data

    def _extract_content(self, content: Any) -> str:
        """Extract assistant text from a response message content field."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                    text_parts.append(item["text"])
            if text_parts:
                return "".join(text_parts)
        raise InferenceMalformedResponse("Inference response did not contain assistant text content.")

    def _normalize_finish_reason(self, value: Any) -> str | None:
        """Normalize a backend finish reason into Plexa's supported values."""
        if value is None:
            return None
        if value in {"stop", "length", "content_filter", "tool_calls", "error", "unknown"}:
            return value
        return "unknown"

    def _raise_stream_http_error(self, status_code: int, detail: str) -> None:
        """Map an HTTP streaming failure into the normalized inference errors."""
        if status_code == 408:
            raise InferenceTimeout(detail or "Inference request timed out.")
        if status_code in {400, 401, 403, 422}:
            raise InferenceRejected(
                detail or f"Inference request rejected ({status_code})."
            )
        if status_code == 404:
            raise InferenceBackendUnavailable(
                detail or "OpenAI-compatible endpoint not found; verify base URL."
            )
        raise InferenceBackendUnavailable(
            detail or f"Inference backend returned HTTP {status_code}."
        )

    async def _stream_response_lines(
        self,
        payload: dict[str, Any],
        timeout_s: float,
    ) -> AsyncIterator[str]:
        """Yield SSE lines from the OpenAI-compatible completion endpoint."""
        url = f"{self._base_url}/chat/completions"
        headers = {**self._headers(), "Accept": "text/event-stream"}

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status_code >= 400:
                        detail = (await response.aread()).decode("utf-8", errors="replace")
                        self._raise_stream_http_error(response.status_code, detail)
                    async for line in response.aiter_lines():
                        yield line
        except InferenceError:
            raise
        except httpx.TimeoutException as exc:
            raise InferenceTimeout("Inference request timed out.") from exc
        except httpx.HTTPError as exc:
            raise InferenceBackendUnavailable(
                "Inference backend streaming connection failed."
            ) from exc

    async def generate(
        self,
        messages: List["Message"],
        config: ResolvedInferenceConfig,
    ) -> InferenceResult:
        """Generate the next assistant reply from an OpenAI-compatible backend."""
        start = time.perf_counter()
        timeout_s = config.timeout_s if config.timeout_s is not None else self._timeout_s
        payload = self._build_payload(messages, config)
        response_data = await asyncio.to_thread(
            self._request_json,
            "POST",
            "/chat/completions",
            payload,
            timeout_s,
        )

        choices = response_data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise InferenceMalformedResponse("Inference response did not include choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise InferenceMalformedResponse("Inference response choice was malformed.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise InferenceMalformedResponse("Inference response choice did not include a message object.")

        content = self._extract_content(message.get("content"))
        finish_reason = first_choice.get("finish_reason", "unknown")
        if finish_reason not in {"stop", "length", "content_filter", "tool_calls", "error", "unknown"}:
            finish_reason = "unknown"

        usage = None
        if isinstance(response_data.get("usage"), dict):
            usage = Usage.model_validate(response_data["usage"])

        latency_ms = int((time.perf_counter() - start) * 1000)

        return InferenceResult(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            backend=self.name,
            model=payload["model"],
            latency_ms=latency_ms,
        )

    async def stream(
        self,
        messages: List["Message"],
        config: ResolvedInferenceConfig,
    ) -> AsyncIterator[InferenceChunk]:
        """Stream assistant text from an OpenAI-compatible SSE response."""
        start = time.perf_counter()
        timeout_s = config.timeout_s if config.timeout_s is not None else self._timeout_s
        payload = self._build_payload(messages, config)
        payload["stream"] = True
        saw_payload = False
        saw_terminal_event = False

        async for line in self._stream_response_lines(payload, timeout_s):
            stripped = line.strip()
            if not stripped or stripped.startswith(":"):
                continue
            if not stripped.startswith("data:"):
                continue

            raw_data = stripped[5:].strip()
            if raw_data == "[DONE]":
                saw_terminal_event = True
                break

            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError as exc:
                raise InferenceMalformedResponse(
                    "Inference stream returned invalid JSON."
                ) from exc
            if not isinstance(data, dict):
                raise InferenceMalformedResponse(
                    "Inference stream returned a non-object event."
                )
            saw_payload = True

            usage = None
            if isinstance(data.get("usage"), dict):
                usage = Usage.model_validate(data["usage"])

            choices = data.get("choices")
            if choices == [] and usage is not None:
                yield InferenceChunk(
                    usage=usage,
                    backend=self.name,
                    model=payload["model"],
                )
                continue
            if not isinstance(choices, list) or not choices:
                raise InferenceMalformedResponse(
                    "Inference stream event did not include choices."
                )

            first_choice = choices[0]
            if not isinstance(first_choice, dict):
                raise InferenceMalformedResponse(
                    "Inference stream choice was malformed."
                )
            delta = first_choice.get("delta")
            if not isinstance(delta, dict):
                raise InferenceMalformedResponse(
                    "Inference stream choice did not include a delta object."
                )

            raw_content = delta.get("content")
            content_delta = ""
            if raw_content is not None:
                content_delta = self._extract_content(raw_content)
            finish_reason = self._normalize_finish_reason(
                first_choice.get("finish_reason")
            )
            if finish_reason is not None:
                saw_terminal_event = True

            if content_delta or finish_reason is not None or usage is not None:
                yield InferenceChunk(
                    content_delta=content_delta,
                    finish_reason=finish_reason,
                    usage=usage,
                    backend=self.name,
                    model=payload["model"],
                    latency_ms=(
                        int((time.perf_counter() - start) * 1000)
                        if finish_reason is not None
                        else None
                    ),
                )

        if not saw_payload:
            raise InferenceMalformedResponse(
                "Inference stream ended without any response events."
            )
        if not saw_terminal_event:
            raise InferenceBackendUnavailable(
                "Inference stream ended before completion."
            )

    async def health_check(self) -> bool:
        """Check whether the backend appears reachable and responsive."""
        try:
            response_data = await asyncio.to_thread(
                self._request_json,
                "GET",
                "/models",
                None,
                min(self._timeout_s, 5.0),
            )
        except (InferenceBackendUnavailable, InferenceMalformedResponse, InferenceTimeout, InferenceRejected):
            return False

        return isinstance(response_data.get("data"), list)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plexa_server.models.message import Message
