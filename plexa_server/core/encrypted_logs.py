from __future__ import annotations

import hashlib
import os
from pathlib import Path
import json
from uuid import uuid4

from plexa_server.core.logging import build_session_log_payload
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.encrypted_log import EncryptedLogEventType, EncryptedLogMetadata
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditEntry
from plexa_server.models.session import Session
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage
from plexa_server.utils.cryptography import decrypt_json, encrypt_json


class EncryptedLogService:
    """Coordinate encrypted session log persistence and retrieval."""

    SERVER_MANAGED_KEY_ID = "server-managed:v1"

    def __init__(
        self,
        artifact_storage: ArtifactStorage,
        course_storage: CourseStorage,
        encoded_key: str,
        keyring: dict[str, str] | None = None,
        active_key_id: str | None = None,
    ):
        """Initialize the encrypted log service.

        Args:
            artifact_storage: Artifact storage used to persist encrypted blobs.
            course_storage: Course storage used to resolve course ownership.
            encoded_key: Base64-encoded server-managed encryption key.
        """
        self._artifact_storage = artifact_storage
        self._course_storage = course_storage
        self._active_key_id = active_key_id or self.SERVER_MANAGED_KEY_ID
        self._keys = keyring or {self._active_key_id: encoded_key}
        if self._active_key_id not in self._keys:
            raise ValueError("Active encrypted-log key id is missing from the keyring.")

    @classmethod
    def from_env(
        cls,
        artifact_storage: ArtifactStorage,
        course_storage: CourseStorage,
    ) -> EncryptedLogService | None:
        """Build an encrypted log service from environment configuration.

        Args:
            artifact_storage: Artifact storage used to persist encrypted blobs.

        Returns:
            EncryptedLogService | None: Configured service, or `None` when no
            encryption key is configured.
        """
        encoded_key = os.getenv("PLEXA_LOG_ENCRYPTION_KEY")
        key_file = os.getenv("PLEXA_LOG_ENCRYPTION_KEY_FILE")
        if encoded_key is None and key_file:
            encoded_key = Path(key_file).read_text(encoding="utf-8").strip()
        keyring_file = os.getenv("PLEXA_LOG_ENCRYPTION_KEYS_FILE")
        active_key_id = os.getenv("PLEXA_LOG_ENCRYPTION_ACTIVE_KEY_ID")
        keyring = None
        if keyring_file:
            raw_keyring = json.loads(Path(keyring_file).read_text(encoding="utf-8"))
            if not isinstance(raw_keyring, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in raw_keyring.items()
            ):
                raise ValueError("Encrypted-log keyring must be a JSON object of string keys.")
            keyring = raw_keyring
            if not active_key_id:
                raise ValueError("PLEXA_LOG_ENCRYPTION_ACTIVE_KEY_ID is required with a keyring.")
            encoded_key = keyring.get(active_key_id)
        if encoded_key is None:
            return None
        return cls(
            artifact_storage=artifact_storage,
            course_storage=course_storage,
            encoded_key=encoded_key,
            keyring=keyring,
            active_key_id=active_key_id,
        )

    async def persist_session_log(
        self,
        session: Session,
        inference_config: InferenceConfig | None = None,
        event_type: EncryptedLogEventType = "message_commit",
    ) -> None:
        """Persist the encrypted canonical log snapshot for a session.

        Args:
            session: Session to serialize and encrypt.
            inference_config: Frozen inference config associated with the session.
            event_type: Lifecycle event that produced the current snapshot.
        """
        if session.logging_policy == "disabled":
            await self._artifact_storage.delete_encrypted_log(session.session_id)
            return

        existing_metadata = await self._artifact_storage.load_encrypted_log_metadata(
            session.session_id
        )
        if existing_metadata is not None and not existing_metadata.content_available:
            return

        course = await self._course_storage.get_course(session.course_id)
        if course is None:
            raise ValueError(f"Course {session.course_id} does not exist.")

        payload = build_session_log_payload(session, inference_config)
        encrypted_blob = encrypt_json(
            payload,
            self._keys[self._active_key_id],
            key_id=self._active_key_id,
        )
        digest = hashlib.sha256(encrypted_blob).hexdigest()
        metadata = EncryptedLogMetadata(
            instance_id=session.session_id,
            user_id=session.user_id,
            course_id=session.course_id,
            lesson_id=session.lesson_id,
            lesson_version=session.lesson_version,
            course_owner_id=course.owner_id,
            authorized_instructor_ids=course.instructor_ids,
            created_at=session.created_at if existing_metadata is None else existing_metadata.created_at,
            updated_at=session.created_at if event_type == "created" and existing_metadata is None else payload["logged_at"],
            closed_at=session.closed_at,
            turned_in_at=session.turned_in_at,
            turn_count=session.turn_count,
            is_active=session.is_active,
            log_version=1,
            artifact_sha256=digest,
            last_event_type=event_type,
            last_event_at=payload["logged_at"],
            key_id=self._active_key_id,
        )
        await self._artifact_storage.save_encrypted_log(
            session.session_id,
            encrypted_blob,
            metadata=metadata,
        )

    async def load_session_log_for_requester(
        self,
        session_id: str,
        requester_user_id: str,
        requester_is_admin: bool = False,
    ) -> dict | None:
        """Load and decrypt a canonical session log payload for an authorized requester.

        Args:
            session_id: Identifier of the session log to load.
            requester_user_id: User requesting decryption.

        Returns:
            dict | None: Decrypted structured payload, or `None` if absent.
        """
        metadata = await self._artifact_storage.load_encrypted_log_metadata(session_id)
        if metadata is None:
            return None
        if not await self._requester_can_access_metadata(
            metadata,
            requester_user_id,
            requester_is_admin=requester_is_admin,
        ):
            return None

        encrypted_blob = await self._artifact_storage.load_encrypted_log(session_id)
        if encrypted_blob is None:
            return None
        payload = decrypt_json(
            encrypted_blob,
            key_resolver=self._resolve_key,
        )
        await self._artifact_storage.save_encrypted_log_access_audit(
            EncryptedLogAccessAuditEntry(
                audit_id=uuid4().hex,
                requester_user_id=requester_user_id,
                course_id=metadata.course_id,
                session_id=metadata.instance_id,
                lesson_id=metadata.lesson_id,
                lesson_version=metadata.lesson_version,
                target_user_id=metadata.user_id,
                action="payload_read",
            )
        )
        return payload

    async def list_session_log_metadata_for_requester(
        self,
        requester_user_id: str,
        course_id: str | None = None,
        lesson_id: str | None = None,
        lesson_version: str | None = None,
        user_id: str | None = None,
        requester_is_admin: bool = False,
    ) -> list[EncryptedLogMetadata]:
        """List encrypted log metadata visible to an authorized requester.

        Args:
            requester_user_id: User requesting metadata.
            course_id: Optional course filter.
            lesson_id: Optional lesson filter.
            lesson_version: Optional lesson version filter.
            user_id: Optional student/user filter.

        Returns:
            list[EncryptedLogMetadata]: Matching metadata records visible to the caller.
        """
        metadata = await self._artifact_storage.list_encrypted_log_metadata(
            course_id=course_id,
            lesson_id=lesson_id,
            lesson_version=lesson_version,
            user_id=user_id,
        )
        visible: list[EncryptedLogMetadata] = []
        for record in metadata:
            if await self._requester_can_access_metadata(
                record,
                requester_user_id,
                requester_is_admin=requester_is_admin,
            ):
                visible.append(record)
        if course_id is not None:
            await self._artifact_storage.save_encrypted_log_access_audit(
                EncryptedLogAccessAuditEntry(
                    audit_id=uuid4().hex,
                    requester_user_id=requester_user_id,
                    course_id=course_id,
                    lesson_id=lesson_id,
                    lesson_version=lesson_version,
                    target_user_id=user_id,
                    action="metadata_list",
                    details={
                        "course_id": course_id,
                        "lesson_id": lesson_id,
                        "lesson_version": lesson_version,
                        "user_id": user_id,
                        "result_count": len(visible),
                    },
                )
            )
        return visible

    async def delete_session_log(self, session_id: str) -> None:
        """Delete an encrypted session log blob.

        Args:
            session_id: Identifier of the session log to delete.
        """
        await self._artifact_storage.delete_encrypted_log(session_id)

    async def _requester_can_access_metadata(
        self,
        metadata: EncryptedLogMetadata,
        requester_user_id: str,
        requester_is_admin: bool = False,
    ) -> bool:
        """Return whether the requester is currently authorized for the log's course.

        Args:
            metadata: Plaintext encrypted log metadata.
            requester_user_id: User requesting access.

        Returns:
            bool: `True` when the requester is currently an authorized instructor.
        """
        if requester_is_admin:
            return True
        course = await self._course_storage.get_course(metadata.course_id)
        if course is None:
            return False
        return course.has_instructor_access(requester_user_id)

    def _resolve_key(self, key_id: str) -> str:
        """Resolve the server-managed encryption key for a given key id.

        Args:
            key_id: Requested key identifier from the encrypted envelope.

        Returns:
            str: Base64-encoded key material.
        """
        if key_id not in self._keys:
            raise ValueError(f"Unsupported encrypted log key id: {key_id}")
        return self._keys[key_id]

    async def reencrypt_all_with_active_key(self) -> int:
        """Re-encrypt all readable logs using the configured active key."""
        count = 0
        for metadata in await self._artifact_storage.list_encrypted_log_metadata():
            blob = await self._artifact_storage.load_encrypted_log(metadata.instance_id)
            if blob is None:
                continue
            payload = decrypt_json(blob, key_resolver=self._resolve_key)
            encrypted = encrypt_json(
                payload,
                self._keys[self._active_key_id],
                key_id=self._active_key_id,
            )
            metadata.key_id = self._active_key_id
            metadata.artifact_sha256 = hashlib.sha256(encrypted).hexdigest()
            await self._artifact_storage.save_encrypted_log(
                metadata.instance_id,
                encrypted,
                metadata=metadata,
            )
            count += 1
        return count
