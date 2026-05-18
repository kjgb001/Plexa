from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request as UrlRequest, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Request

from plexa_server.auth.base import (
    AuthConfigurationError,
    AuthVerificationError,
    RequestAuthenticator,
)
from plexa_server.auth.config import AuthConfig
from plexa_server.auth.identity import UserIdentity


def _b64url_decode(data: str) -> bytes:
    """Decode a base64url string."""
    padding_len = (-len(data)) % 4
    return base64.urlsafe_b64decode(data + ("=" * padding_len))


def _load_json_file(path: str) -> dict:
    """Load a JSON document from disk."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_roles(value: object) -> set[str]:
    """Normalize token role claims to a set of strings."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return {item for item in value if isinstance(item, str) and item.strip()}
    return set()


@dataclass
class _JwtParts:
    """Decoded JWT envelope."""

    raw_header: dict[str, object]
    raw_payload: dict[str, object]
    signing_input: bytes
    signature: bytes


class _JwksResolver:
    """Resolve RSA public keys from configured JWKS sources."""

    def __init__(self, config: AuthConfig):
        self._config = config
        self._cached_jwks: dict[str, object] | None = None
        self._cached_at = 0.0

    def _load_jwks(self) -> dict[str, object]:
        now = time.time()
        if self._cached_jwks is not None and (now - self._cached_at) < self._config.jwks_refresh_s:
            return self._cached_jwks

        if self._config.jwks_json:
            jwks = json.loads(self._config.jwks_json)
        elif self._config.jwks_file:
            jwks = _load_json_file(self._config.jwks_file)
        elif self._config.jwks_url:
            request = UrlRequest(self._config.jwks_url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=5) as response:
                jwks = json.loads(response.read().decode("utf-8"))
        else:
            raise AuthConfigurationError(
                "Bearer JWT auth requires JWKS, public key PEM, or shared secret configuration."
            )

        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise AuthConfigurationError("Configured JWKS must be a JSON object containing a 'keys' list.")

        self._cached_jwks = jwks
        self._cached_at = now
        return jwks

    def resolve_rsa_key(self, kid: str | None) -> rsa.RSAPublicKey:
        """Resolve an RSA public key by token kid."""
        jwks = self._load_jwks()
        keys = jwks["keys"]
        if kid is None and len(keys) != 1:
            raise AuthVerificationError("JWT missing 'kid' and multiple JWKS keys are configured.")

        candidate = None
        for key in keys:
            if not isinstance(key, dict):
                continue
            if kid is None or key.get("kid") == kid:
                candidate = key
                break

        if candidate is None:
            raise AuthVerificationError("No matching JWKS key found for JWT.")
        if candidate.get("kty") != "RSA":
            raise AuthVerificationError("Only RSA JWKS keys are currently supported.")

        n = candidate.get("n")
        e = candidate.get("e")
        if not isinstance(n, str) or not isinstance(e, str):
            raise AuthVerificationError("RSA JWKS key must contain 'n' and 'e'.")

        modulus = int.from_bytes(_b64url_decode(n), "big")
        exponent = int.from_bytes(_b64url_decode(e), "big")
        return rsa.RSAPublicNumbers(exponent, modulus).public_key()


class BearerJwtAuthenticator(RequestAuthenticator):
    """Authenticate requests using a verified Bearer JWT."""

    def __init__(self, config: AuthConfig):
        self._config = config
        if not any(
            [
                config.shared_secret,
                config.public_key_pem,
                config.public_key_file,
                config.jwks_json,
                config.jwks_file,
                config.jwks_url,
            ]
        ):
            raise AuthConfigurationError(
                "PLEXA_AUTH_MODE=bearer-jwt requires a shared secret, public key, or JWKS source."
            )
        self._jwks_resolver = _JwksResolver(config)
        self._pem_public_key = self._load_pem_public_key()

    def _load_pem_public_key(self):
        pem_value = self._config.public_key_pem
        if pem_value is None and self._config.public_key_file:
            pem_value = Path(self._config.public_key_file).read_text(encoding="utf-8")
        if pem_value is None:
            return None
        key = serialization.load_pem_public_key(pem_value.encode("utf-8"))
        if not isinstance(key, rsa.RSAPublicKey):
            raise AuthConfigurationError("Only RSA PEM public keys are currently supported.")
        return key

    def _get_bearer_token(self, request: Request) -> str | None:
        header = request.headers.get(self._config.authorization_header_name)
        if header is None:
            return None

        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise AuthVerificationError("Authorization header must use Bearer token format.")
        return token.strip()

    def _parse_token(self, token: str) -> _JwtParts:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthVerificationError("JWT must contain exactly three segments.")

        header_segment, payload_segment, signature_segment = parts
        try:
            header = json.loads(_b64url_decode(header_segment))
            payload = json.loads(_b64url_decode(payload_segment))
        except (ValueError, json.JSONDecodeError) as exc:
            raise AuthVerificationError("JWT header or payload is not valid JSON.") from exc

        if not isinstance(header, dict) or not isinstance(payload, dict):
            raise AuthVerificationError("JWT header and payload must be JSON objects.")

        return _JwtParts(
            raw_header=header,
            raw_payload=payload,
            signing_input=f"{header_segment}.{payload_segment}".encode("utf-8"),
            signature=_b64url_decode(signature_segment),
        )

    def _verify_hs256(self, parts: _JwtParts) -> None:
        secret = self._config.shared_secret
        if secret is None:
            raise AuthConfigurationError("HS256 bearer JWT auth requires PLEXA_AUTH_SHARED_SECRET.")

        expected = hmac.new(secret.encode("utf-8"), parts.signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, parts.signature):
            raise AuthVerificationError("JWT signature verification failed.")

    def _verify_rs256(self, parts: _JwtParts) -> None:
        kid = parts.raw_header.get("kid")
        if kid is not None and not isinstance(kid, str):
            raise AuthVerificationError("JWT 'kid' must be a string when present.")

        public_key = self._pem_public_key
        if public_key is None:
            public_key = self._jwks_resolver.resolve_rsa_key(kid)

        try:
            public_key.verify(
                parts.signature,
                parts.signing_input,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except Exception as exc:  # cryptography raises backend-specific errors
            raise AuthVerificationError("JWT signature verification failed.") from exc

    def _verify_signature(self, parts: _JwtParts) -> None:
        alg = parts.raw_header.get("alg")
        if not isinstance(alg, str) or not alg:
            raise AuthVerificationError("JWT header missing 'alg'.")
        if alg not in self._config.allowed_algorithms:
            raise AuthVerificationError(f"JWT algorithm '{alg}' is not allowed.")

        if alg == "HS256":
            self._verify_hs256(parts)
            return
        if alg == "RS256":
            self._verify_rs256(parts)
            return
        raise AuthVerificationError(f"JWT algorithm '{alg}' is not supported by Plexa.")

    def _verify_registered_claims(self, payload: dict[str, object]) -> None:
        now = int(time.time())

        exp = payload.get("exp")
        if exp is not None:
            if not isinstance(exp, (int, float)) or int(exp) <= now:
                raise AuthVerificationError("JWT is expired.")

        nbf = payload.get("nbf")
        if nbf is not None:
            if not isinstance(nbf, (int, float)) or int(nbf) > now:
                raise AuthVerificationError("JWT is not yet valid.")

        issuer = self._config.issuer
        if issuer is not None and payload.get("iss") != issuer:
            raise AuthVerificationError("JWT issuer did not match expected issuer.")

        audience = self._config.audience
        if audience is not None:
            aud = payload.get("aud")
            if isinstance(aud, str):
                audiences = {aud}
            elif isinstance(aud, list):
                audiences = {item for item in aud if isinstance(item, str)}
            else:
                audiences = set()
            if audience not in audiences:
                raise AuthVerificationError("JWT audience did not match expected audience.")

    def _build_identity(self, payload: dict[str, object]) -> UserIdentity:
        user_value = payload.get(self._config.user_id_claim)
        user_id = user_value if isinstance(user_value, str) and user_value.strip() else None
        if user_id is None:
            raise AuthVerificationError(
                f"JWT payload missing required user id claim '{self._config.user_id_claim}'."
            )

        roles = {"user"}
        if self._config.roles_claim is not None:
            roles |= _normalize_roles(payload.get(self._config.roles_claim))
        if self._config.admin_role_name and self._config.admin_role_name in roles:
            roles.add("admin")
        if user_id in self._config.admin_user_ids:
            roles.add("admin")

        claims = dict(payload)
        return UserIdentity(
            user_id=user_id,
            roles=roles,
            claims=claims,
            auth_type="bearer_jwt",
        )

    def authenticate_request(self, request: Request) -> UserIdentity:
        """Authenticate the request bearer token when present."""
        try:
            token = self._get_bearer_token(request)
        except AuthVerificationError:
            return UserIdentity(
                claims={"bearer_token_present": True, "bearer_token_valid": False},
            )

        if token is None:
            return UserIdentity()

        try:
            parts = self._parse_token(token)
            self._verify_signature(parts)
            self._verify_registered_claims(parts.raw_payload)
            return self._build_identity(parts.raw_payload)
        except AuthVerificationError as exc:
            return UserIdentity(
                claims={
                    "bearer_token_present": True,
                    "bearer_token_valid": False,
                    "auth_error": str(exc),
                },
                auth_type="bearer_jwt",
            )
