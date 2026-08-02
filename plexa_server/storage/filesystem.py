"""Deprecated filesystem storage retained only for 0.1.x data migration."""

import json
import base64
import warnings
from pathlib import Path
from typing import Optional
from typing import List
from uuid import uuid4

from plexa_server.models.lesson import Lesson
from plexa_server.models.session import Session
from plexa_server.models.course import Course
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditAction, EncryptedLogAccessAuditEntry
from plexa_server.models.workspace_state import UserCourseState, UserLessonState
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseRevisionConflictError,
    CourseStorage,
    LessonRevisionConflictError,
    SessionRevisionConflictError,
    SessionStorage,
    WorkspaceStateStorage,
)


_DEPRECATION_MESSAGE = (
    "Filesystem storage is deprecated and retained only for migration in Plexa 0.1.x; "
    "it will be removed in 0.2.0."
)
_deprecation_emitted = False


def _prepare_directories(paths: tuple[Path, ...], read_only: bool) -> None:
    """Create writable storage paths or validate a migration source."""
    global _deprecation_emitted
    if not _deprecation_emitted:
        warnings.warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)
        _deprecation_emitted = True
    if read_only:
        return
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, data: str) -> None:
    """Write text to a temp file and atomically replace the destination.

    Args:
        path: Final file path to replace.
        data: Serialized text content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")

    with temp_path.open("w", encoding="utf-8") as f:
        f.write(data)
    temp_path.replace(path)


def _safe_component(value: str) -> str:
    """Encode an external identifier as one traversal-safe path component."""
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


class FileSystemArtifactStorage(ArtifactStorage):
    """
    Persistent storage for lesson artifacts and encrypted logs.

    This class does not decrypt logs and does not modify lesson/session contents.
    """

    def __init__(self, base_path: Path, *, read_only: bool = False):
        """Initialize lesson and log directories beneath the given base path.

        Args:
            base_path: Root directory under which artifact files are stored.
        """
        self.base_path = Path(base_path)
        self.lessons_path = self.base_path / "lessons"
        self.logs_path = self.base_path / "logs"
        self.log_access_audits_path = self.base_path / "log_access_audits"

        _prepare_directories(
            (self.lessons_path, self.logs_path, self.log_access_audits_path),
            read_only,
        )

    def _lesson_path(self, lesson_id: str, version: str, course_id: str | None) -> Path:
        scope = "_legacy" if course_id is None else _safe_component(course_id)
        return self.lessons_path / scope / f"{_safe_component(lesson_id)}.{_safe_component(version)}.json"

    async def save_lesson(
        self,
        lesson: Lesson,
        course_id: str,
        expected_revision: int | None = None,
    ) -> int:
        """Persist a lesson document under its lesson id and version.

        Args:
            lesson: Lesson document to serialize and store.
            course_id: Course that owns the mutable artifact.

        Raises:
            ValueError: If the lesson is missing an id or version.
        """
        if not lesson.identity.lesson_id:
            raise ValueError("Lesson must have a lesson_id before saving.")

        if not lesson.identity.version.strip():
            raise ValueError("Lesson version must be specified before saving.")

        lesson_file = self._lesson_path(
            lesson.identity.lesson_id,
            lesson.identity.version,
            course_id,
        )
        revision = 1
        if lesson_file.exists():
            with lesson_file.open("r", encoding="utf-8") as f:
                existing = json.load(f)
            current_revision = int(existing.get("artifact_revision", 1))
            if expected_revision is not None and expected_revision != current_revision:
                raise LessonRevisionConflictError(
                    f"Lesson changed since revision {expected_revision}; reload and retry."
                )
            revision = current_revision + 1
        elif expected_revision is not None:
            raise LessonRevisionConflictError("Lesson no longer exists; reload before saving.")
        serialized = json.dumps(
            {"artifact_revision": revision, "lesson": lesson.model_dump(mode="json")},
            indent=2,
        )
        _atomic_write(lesson_file, serialized)
        return revision

    async def load_lesson(
        self,
        lesson_id: str,
        version: str,
        course_id: str | None,
    ) -> Optional[Lesson]:
        """Load a lesson version from disk.

        Args:
            lesson_id: Lesson identifier to load.
            version: Version string to load for the lesson.

        Returns:
            Optional[Lesson]: Parsed lesson document, or `None` if no matching
            file exists.
        """
        lesson_file = self._lesson_path(lesson_id, version, course_id)
        if (
            not lesson_file.exists()
            and course_id is None
            and "/" not in lesson_id
            and "/" not in version
            and ".." not in lesson_id
            and ".." not in version
        ):
            legacy_file = self.lessons_path / f"{lesson_id}_{version}.json"
            lesson_file = legacy_file
        if not lesson_file.exists():
            return None

        with lesson_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Lesson.model_validate(data.get("lesson", data))

    async def get_lesson_revision(
        self,
        lesson_id: str,
        version: str,
        course_id: str | None,
    ) -> int | None:
        lesson_file = self._lesson_path(lesson_id, version, course_id)
        if not lesson_file.exists():
            return None
        with lesson_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("artifact_revision", 1))

    async def save_encrypted_log(
        self,
        instance_id: str,
        encrypted_blob: bytes,
        metadata: EncryptedLogMetadata | None = None,
    ) -> None:
        """Persist an opaque encrypted log blob and optional plaintext metadata.

        Args:
            instance_id: Identifier used as the log filename stem.
            encrypted_blob: Encrypted bytes to store without inspection.
            metadata: Optional plaintext metadata describing the artifact.
        """
        stem = _safe_component(instance_id)
        existing_metadata = await self.load_encrypted_log_metadata(instance_id)
        if existing_metadata is not None and not existing_metadata.content_available:
            return
        log_file = self.logs_path / f"{stem}.log"
        with log_file.open("wb") as f:
            f.write(encrypted_blob)
        if metadata is not None:
            metadata_file = self.logs_path / f"{stem}.meta.json"
            _atomic_write(metadata_file, metadata.model_dump_json(indent=2))

    async def load_encrypted_log(self, instance_id: str) -> Optional[bytes]:
        """Load an encrypted log blob.

        Args:
            instance_id: Identifier used as the log filename stem.

        Returns:
            Optional[bytes]: Stored encrypted bytes, or `None` if no matching
            log exists.
        """
        log_file = self.logs_path / f"{_safe_component(instance_id)}.log"
        if not log_file.exists():
            return None

        with log_file.open("rb") as f:
            return f.read()

    async def load_encrypted_log_metadata(self, instance_id: str) -> Optional[EncryptedLogMetadata]:
        """Load plaintext metadata describing an encrypted log blob.

        Args:
            instance_id: Identifier used as the log filename stem.

        Returns:
            Optional[EncryptedLogMetadata]: Stored metadata, or `None` if absent.
        """
        metadata_file = self.logs_path / f"{_safe_component(instance_id)}.meta.json"
        if not metadata_file.exists():
            return None

        with metadata_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return EncryptedLogMetadata.model_validate(data)

    async def list_encrypted_log_metadata(
        self,
        course_id: str | None = None,
        lesson_id: str | None = None,
        lesson_version: str | None = None,
        owner_id: str | None = None,
        instructor_id: str | None = None,
        user_id: str | None = None,
    ) -> list[EncryptedLogMetadata]:
        """List plaintext metadata for encrypted session logs.

        Args:
            course_id: Optional course filter.
            lesson_id: Optional lesson filter.
            lesson_version: Optional lesson version filter.
            owner_id: Optional course owner filter.
            instructor_id: Optional authorized instructor filter.
            user_id: Optional student/user filter.

        Returns:
            list[EncryptedLogMetadata]: Matching metadata records.
        """
        results: list[EncryptedLogMetadata] = []
        for metadata_file in self.logs_path.glob("*.meta.json"):
            with metadata_file.open("r", encoding="utf-8") as f:
                metadata = EncryptedLogMetadata.model_validate(json.load(f))
            if course_id is not None and metadata.course_id != course_id:
                continue
            if lesson_id is not None and metadata.lesson_id != lesson_id:
                continue
            if lesson_version is not None and metadata.lesson_version != lesson_version:
                continue
            if owner_id is not None and metadata.course_owner_id != owner_id:
                continue
            if instructor_id is not None and instructor_id not in metadata.authorized_instructor_ids:
                continue
            if user_id is not None and metadata.user_id != user_id:
                continue
            results.append(metadata)
        return results

    async def delete_encrypted_log(self, instance_id: str) -> None:
        """Delete a stored encrypted log blob.

        Args:
            instance_id: Identifier used as the log filename stem.
        """
        stem = _safe_component(instance_id)
        log_file = self.logs_path / f"{stem}.log"
        log_file.unlink(missing_ok=True)
        metadata_file = self.logs_path / f"{stem}.meta.json"
        metadata_file.unlink(missing_ok=True)

    async def expire_encrypted_log_content(self, instance_id: str) -> None:
        """Delete encrypted content while retaining its lookup metadata."""
        stem = _safe_component(instance_id)
        (self.logs_path / f"{stem}.log").unlink(missing_ok=True)
        metadata = await self.load_encrypted_log_metadata(instance_id)
        if metadata is not None and metadata.content_available:
            metadata.content_available = False
            _atomic_write(
                self.logs_path / f"{stem}.meta.json",
                metadata.model_dump_json(indent=2),
            )

    async def save_encrypted_log_access_audit(
        self,
        entry: EncryptedLogAccessAuditEntry,
    ) -> None:
        """Persist an audit record for encrypted log access."""
        path = self.log_access_audits_path / f"{entry.created_at.strftime('%Y%m%dT%H%M%S%fZ')}_{entry.audit_id}.json"
        _atomic_write(path, entry.model_dump_json(indent=2))

    async def list_encrypted_log_access_audits(
        self,
        course_id: str | None = None,
        session_id: str | None = None,
        requester_user_id: str | None = None,
        action: EncryptedLogAccessAuditAction | None = None,
    ) -> list[EncryptedLogAccessAuditEntry]:
        """List persisted audit records for encrypted log access."""
        entries: list[EncryptedLogAccessAuditEntry] = []
        for path in sorted(self.log_access_audits_path.glob("*.json")):
            with path.open("r", encoding="utf-8") as f:
                entry = EncryptedLogAccessAuditEntry.model_validate(json.load(f))
            if course_id is not None and entry.course_id != course_id:
                continue
            if session_id is not None and entry.session_id != session_id:
                continue
            if requester_user_id is not None and entry.requester_user_id != requester_user_id:
                continue
            if action is not None and entry.action != action:
                continue
            entries.append(entry)
        return entries

    async def health_check(self) -> bool:
        """Report whether the artifact filesystem paths are available.

        Returns:
            bool: `True` when the expected filesystem paths exist.
        """
        return (
            self.base_path.exists()
            and self.lessons_path.exists()
            and self.logs_path.exists()
            and self.log_access_audits_path.exists()
        )


class FileSystemSessionStorage(SessionStorage):
    """
    Persistent filesystem-backed session storage.

    Stores sessions and inference configs as JSON.
    """

    def __init__(self, base_path: Path, *, read_only: bool = False):
        """Create filesystem directories for session and config documents.

        Args:
            base_path: Root directory under which session data is stored.
        """
        self.base_path = Path(base_path)

        self.sessions_path = self.base_path / "sessions"
        self.configs_path = self.base_path / "configs"

        _prepare_directories((self.sessions_path, self.configs_path), read_only)

    async def save_session(self, session: Session) -> None:
        """Serialize and store a session document by session id.

        Args:
            session: Session object to persist.
        """
        path = self.sessions_path / f"{_safe_component(session.session_id)}.json"
        if path.exists():
            with path.open("r", encoding="utf-8") as existing_file:
                existing = Session.model_validate(json.load(existing_file))
            if existing.persistence_revision != session.persistence_revision:
                raise SessionRevisionConflictError(
                    "Session changed concurrently; reload and retry."
                )
            session.persistence_revision += 1
        persisted = session
        if session.logging_policy == "disabled":
            persisted = session.model_copy(
                update={
                    "messages": [],
                    "transcript_available": session.transcript_available,
                }
            )
        serialized = persisted.model_dump_json(indent=2)
        _atomic_write(path, serialized)

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session document from disk.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Parsed session document, or `None` if it does
            not exist.
        """
        path = self.sessions_path / f"{_safe_component(session_id)}.json"
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    async def delete_session(self, session_id: str) -> None:
        """Delete a session document and its persisted inference config.

        Args:
            session_id: Identifier of the session to delete.
        """
        path = self.sessions_path / f"{_safe_component(session_id)}.json"
        path.unlink(missing_ok=True)

        config_path = self.configs_path / f"{_safe_component(session_id)}.json"
        config_path.unlink(missing_ok=True)

    async def save_inference_config(
        self,
        session_id: str,
        config: InferenceConfig,
    ) -> None:
        """Persist the frozen inference config associated with a session.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to persist.
        """
        path = self.configs_path / f"{_safe_component(session_id)}.json"
        serialized = config.model_dump_json(indent=2)
        _atomic_write(path, serialized)

    async def get_inference_config(
        self,
        session_id: str,
    ) -> Optional[InferenceConfig]:
        """Load a session's inference config.

        Args:
            session_id: Identifier of the session whose config should be loaded.

        Returns:
            Optional[InferenceConfig]: Parsed inference config, or `None` if no
            stored config exists.
        """
        path = self.configs_path / f"{_safe_component(session_id)}.json"
        if not path.exists():
            session = await self.get_session(session_id)
            return None if session is None else session.frozen_inference_config

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return InferenceConfig.model_validate(data)

    async def list_sessions(self) -> List[Session]:
        """Load and return every persisted session document.

        Returns:
            List[Session]: Parsed session documents found in storage.
        """
        results: List[Session] = []

        for file in self.sessions_path.glob("*.json"):
            with file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                results.append(Session.model_validate(data))

        return results

    async def health_check(self) -> bool:
        """Report whether the session filesystem paths are available.

        Returns:
            bool: `True` when the expected filesystem paths exist.
        """
        return self.base_path.exists() and self.sessions_path.exists() and self.configs_path.exists()


class FileSystemCourseStorage(CourseStorage):
    """
    Persistent filesystem-backed storage for Course metadata.

    Responsible only for atomic IO of Course documents.
    No business logic.
    """

    def __init__(self, base_path: Path, *, read_only: bool = False):
        """Create the course metadata directory beneath the base path.

        Args:
            base_path: Root directory under which course data is stored.
        """
        self.base_path = Path(base_path)
        self.courses_path = self.base_path / "configs" / "courses"

        _prepare_directories((self.courses_path,), read_only)

    def _course_path(self, course_id: str) -> Path:
        """Return the JSON document path for a course id.

        Args:
            course_id: Identifier of the course document.

        Returns:
            Path: Filesystem path where the course document is stored.
        """
        return self.courses_path / f"{_safe_component(course_id)}.json"

    async def save_course(self, course: Course) -> None:
        """Persist a course document using its course id as the filename.

        Args:
            course: Course document to serialize and store.
        """
        path = self._course_path(course.course_id)
        next_revision = course.revision
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                current = Course.model_validate(json.load(f))
            if current.revision != course.revision:
                raise CourseRevisionConflictError(
                    f"Course changed since revision {course.revision}; reload and retry."
                )
            next_revision += 1
        for lesson_id, version in course.lessons.items():
            target = (
                self.base_path
                / "lessons"
                / _safe_component(course.course_id)
                / f"{_safe_component(lesson_id)}.{_safe_component(version)}.json"
            )
            if target.exists():
                continue
            legacy = (
                self.base_path
                / "lessons"
                / "_legacy"
                / f"{_safe_component(lesson_id)}.{_safe_component(version)}.json"
            )
            if legacy.exists():
                _atomic_write(target, legacy.read_text(encoding="utf-8"))
            if not target.exists():
                raise ValueError(
                    f"Lesson {lesson_id}@{version} does not exist for course {course.course_id}."
                )
        persisted = course.model_copy(update={"revision": next_revision})
        serialized = persisted.model_dump_json(indent=2)
        _atomic_write(path, serialized)
        course.revision = next_revision

    async def get_course(self, course_id: str) -> Optional[Course]:
        """Load a course document from disk.

        Args:
            course_id: Identifier of the course to load.

        Returns:
            Optional[Course]: Parsed course document, or `None` if it does not
            exist.
        """
        path = self._course_path(course_id)
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Course.model_validate(data)

    async def delete_course(self, course_id: str) -> None:
        """Delete a persisted course document if it exists.

        Args:
            course_id: Identifier of the course to delete.
        """
        path = self._course_path(course_id)
        path.unlink(missing_ok=True)

    async def list_courses(self) -> List[Course]:
        """Load and return every persisted course document.

        Returns:
            List[Course]: Parsed course documents found in the storage
            directory.
        """
        results: List[Course] = []

        for file in self.courses_path.glob("*.json"):
            with file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                results.append(Course.model_validate(data))

        return results

    async def health_check(self) -> bool:
        """Report whether the course filesystem path is available.

        Returns:
            bool: `True` when the expected filesystem path exists.
        """
        return self.base_path.exists() and self.courses_path.exists()


class FileSystemWorkspaceStateStorage(WorkspaceStateStorage):
    """Filesystem-backed storage for user course and lesson recency state."""

    def __init__(self, base_path: Path, *, read_only: bool = False):
        """Create workspace state directories beneath the base path."""
        self.base_path = Path(base_path)
        self.course_states_path = self.base_path / "configs" / "workspace" / "course_states"
        self.lesson_states_path = self.base_path / "configs" / "workspace" / "lesson_states"
        _prepare_directories((self.course_states_path, self.lesson_states_path), read_only)

    def _course_state_path(self, user_id: str, course_id: str) -> Path:
        return self.course_states_path / _safe_component(user_id) / f"{_safe_component(course_id)}.json"

    def _lesson_state_path(
        self,
        user_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
    ) -> Path:
        filename = ".".join(
            (_safe_component(course_id), _safe_component(lesson_id), _safe_component(lesson_version))
        ) + ".json"
        return self.lesson_states_path / _safe_component(user_id) / filename

    async def touch_course(
        self,
        user_id: str,
        course_id: str,
    ) -> UserCourseState:
        state = UserCourseState(user_id=user_id, course_id=course_id)
        _atomic_write(self._course_state_path(user_id, course_id), state.model_dump_json(indent=2))
        return state

    async def touch_lesson(
        self,
        user_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
    ) -> UserLessonState:
        state = UserLessonState(
            user_id=user_id,
            course_id=course_id,
            lesson_id=lesson_id,
            lesson_version=lesson_version,
        )
        _atomic_write(
            self._lesson_state_path(user_id, course_id, lesson_id, lesson_version),
            state.model_dump_json(indent=2),
        )
        return state

    async def list_course_states(self, user_id: str) -> list[UserCourseState]:
        directory = self.course_states_path / _safe_component(user_id)
        if not directory.exists():
            return []

        states: list[UserCourseState] = []
        for file in directory.glob("*.json"):
            with file.open("r", encoding="utf-8") as f:
                states.append(UserCourseState.model_validate(json.load(f)))
        return states

    async def list_lesson_states(
        self,
        user_id: str,
        course_id: str | None = None,
    ) -> list[UserLessonState]:
        directory = self.lesson_states_path / _safe_component(user_id)
        if not directory.exists():
            return []

        states: list[UserLessonState] = []
        for file in directory.glob("*.json"):
            with file.open("r", encoding="utf-8") as f:
                state = UserLessonState.model_validate(json.load(f))
            if course_id is not None and state.course_id != course_id:
                continue
            states.append(state)
        return states

    async def list_all_course_states(self) -> list[UserCourseState]:
        """Return every legacy course state for the migration importer."""
        states: list[UserCourseState] = []
        for file in self.course_states_path.glob("*/*.json"):
            with file.open("r", encoding="utf-8") as f:
                states.append(UserCourseState.model_validate(json.load(f)))
        return states

    async def list_all_lesson_states(self) -> list[UserLessonState]:
        """Return every legacy lesson state for the migration importer."""
        states: list[UserLessonState] = []
        for file in self.lesson_states_path.glob("*/*.json"):
            with file.open("r", encoding="utf-8") as f:
                states.append(UserLessonState.model_validate(json.load(f)))
        return states

    async def health_check(self) -> bool:
        return (
            self.base_path.exists()
            and self.course_states_path.exists()
            and self.lesson_states_path.exists()
        )
