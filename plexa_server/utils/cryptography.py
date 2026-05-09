from __future__ import annotations

import base64
import json
import secrets
from collections.abc import Callable
from typing import Any


class EncryptedLogCryptoError(RuntimeError):
    """Base class for encrypted log cryptography failures."""


class CryptographyDependencyMissing(EncryptedLogCryptoError):
    """Raised when the optional `cryptography` dependency is unavailable."""


class InvalidEncryptionKey(EncryptedLogCryptoError):
    """Raised when an encryption key is missing or malformed."""


class UnsupportedEnvelopeVersion(EncryptedLogCryptoError):
    """Raised when an encrypted log blob uses an unsupported envelope version."""


def generate_encryption_key() -> str:
    """Generate a base64-encoded 256-bit encryption key."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")


def _require_aesgcm():
    """Return the AESGCM class or raise a dependency error."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ModuleNotFoundError as exc:
        raise CryptographyDependencyMissing(
            "Encrypted logs require the 'cryptography' package."
        ) from exc
    return AESGCM


def _decode_key(encoded_key: str) -> bytes:
    """Decode and validate a base64-encoded 256-bit encryption key.

    Args:
        encoded_key: Base64-encoded key material.

    Returns:
        bytes: Raw 32-byte key.

    Raises:
        InvalidEncryptionKey: If the key is missing or malformed.
    """
    if not encoded_key.strip():
        raise InvalidEncryptionKey("Encryption key is empty.")

    try:
        raw_key = base64.urlsafe_b64decode(encoded_key.encode("ascii"))
    except Exception as exc:
        raise InvalidEncryptionKey("Encryption key is not valid base64.") from exc

    if len(raw_key) != 32:
        raise InvalidEncryptionKey("Encryption key must decode to exactly 32 bytes.")

    return raw_key


def _b64encode(data: bytes) -> str:
    """Return URL-safe base64 text for raw bytes."""
    return base64.urlsafe_b64encode(data).decode("ascii")


def _b64decode(data: str) -> bytes:
    """Return raw bytes decoded from URL-safe base64 text."""
    return base64.urlsafe_b64decode(data.encode("ascii"))


def encrypt_json(payload: dict[str, Any], encoded_key: str, key_id: str = "default") -> bytes:
    """Encrypt a structured JSON payload into a versioned binary envelope.

    Args:
        payload: JSON-serializable payload to encrypt.
        encoded_key: Base64-encoded 256-bit key.
        key_id: Stable key identifier stored in the envelope.

    Returns:
        bytes: Serialized encrypted envelope.
    """
    aesgcm_cls = _require_aesgcm()
    raw_key = _decode_key(encoded_key)
    plaintext = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    nonce = secrets.token_bytes(12)
    aad_payload = {
        "version": 1,
        "algorithm": "AESGCM",
        "key_id": key_id,
    }
    aad = json.dumps(aad_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ciphertext = aesgcm_cls(raw_key).encrypt(nonce, plaintext, aad)
    envelope = {
        **aad_payload,
        "nonce": _b64encode(nonce),
        "ciphertext": _b64encode(ciphertext),
    }
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decrypt_json(blob: bytes, key_resolver: Callable[[str], str]) -> dict[str, Any]:
    """Decrypt a versioned encrypted envelope into a JSON payload.

    Args:
        blob: Serialized encrypted envelope.
        key_resolver: Callable mapping `key_id` to a base64-encoded key.

    Returns:
        dict[str, Any]: Decrypted JSON payload.
    """
    aesgcm_cls = _require_aesgcm()
    envelope = json.loads(blob.decode("utf-8"))
    version = envelope.get("version")
    algorithm = envelope.get("algorithm")
    key_id = envelope.get("key_id")

    if version != 1 or algorithm != "AESGCM" or not isinstance(key_id, str):
        raise UnsupportedEnvelopeVersion("Unsupported encrypted log envelope.")

    raw_key = _decode_key(key_resolver(key_id))
    aad_payload = {
        "version": version,
        "algorithm": algorithm,
        "key_id": key_id,
    }
    aad = json.dumps(aad_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    nonce = _b64decode(envelope["nonce"])
    ciphertext = _b64decode(envelope["ciphertext"])
    plaintext = aesgcm_cls(raw_key).decrypt(nonce, ciphertext, aad)
    return json.loads(plaintext.decode("utf-8"))
