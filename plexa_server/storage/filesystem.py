import json
from pathlib import Path
from typing import Optional
from typing import List
from uuid import uuid4

from plexa_server.models.lesson import Lesson
from plexa_server.models.session import Session
from plexa_server.models.course import Course
from plexa_server.inference.base import InferenceConfig
from plexa_server.storage.session_protocol import SessionStorage


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


class FileSystemArtifactStorage:
    """
    Persistent storage for lesson artifacts and encrypted logs.

    This class does not decrypt logs and does not modify lesson/session contents.
    """

    def __init__(self, base_path: Path):
        """Initialize lesson and log directories beneath the given base path.

        Args:
            base_path: Root directory under which artifact files are stored.
        """
        self.base_path = base_path
        self.lessons_path = base_path / "lessons"
        self.logs_path = base_path / "logs"

        self.lessons_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

    def save_lesson(self, lesson: Lesson) -> None:
        """Persist a lesson document under its lesson id and version.

        Args:
            lesson: Lesson document to serialize and store.

        Raises:
            ValueError: If the lesson is missing an id or version.
        """
        if not lesson.identity.lesson_id:
            raise ValueError("Lesson must have a lesson_id before saving.")

        if not lesson.identity.version.strip():
            raise ValueError("Lesson version must be specified before saving.")

        lesson_file = self.lessons_path / (
            f"{lesson.identity.lesson_id}_{lesson.identity.version}.json"
        )

        temp_file = lesson_file.with_suffix(".tmp")

        serialized = lesson.model_dump_json(indent=2)

        with temp_file.open("w", encoding="utf-8") as f:
            f.write(serialized)

        temp_file.replace(lesson_file)

    def load_lesson(self, lesson_id: str, version: str) -> Optional[Lesson]:
        """Load a lesson version from disk.

        Args:
            lesson_id: Lesson identifier to load.
            version: Version string to load for the lesson.

        Returns:
            Optional[Lesson]: Parsed lesson document, or `None` if no matching
            file exists.
        """
        lesson_file = self.lessons_path / f"{lesson_id}_{version}.json"
        if not lesson_file.exists():
            return None

        with lesson_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Lesson.model_validate(data)

    def save_encrypted_log(self, instance_id: str, encrypted_blob: bytes) -> None:
        """Persist an opaque encrypted log blob for a lesson instance.

        Args:
            instance_id: Identifier used as the log filename stem.
            encrypted_blob: Encrypted bytes to store without inspection.
        """
        log_file = self.logs_path / f"{instance_id}.log"
        with log_file.open("wb") as f:
            f.write(encrypted_blob)

    def load_encrypted_log(self, instance_id: str) -> Optional[bytes]:
        """Load an encrypted log blob.

        Args:
            instance_id: Identifier used as the log filename stem.

        Returns:
            Optional[bytes]: Stored encrypted bytes, or `None` if no matching
            log exists.
        """
        log_file = self.logs_path / f"{instance_id}.log"
        if not log_file.exists():
            return None

        with log_file.open("rb") as f:
            return f.read()


class FileSystemSessionStorage(SessionStorage):
    """
    Persistent filesystem-backed session storage.

    Stores sessions and inference configs as JSON.
    """

    def __init__(self, base_path: Path):
        """Create filesystem directories for session and config documents.

        Args:
            base_path: Root directory under which session data is stored.
        """
        self.base_path = Path(base_path)

        self.sessions_path = self.base_path / "sessions"
        self.configs_path = self.base_path / "configs"

        self.sessions_path.mkdir(parents=True, exist_ok=True)
        self.configs_path.mkdir(parents=True, exist_ok=True)

    def save_session(self, session: Session) -> None:
        """Serialize and store a session document by session id.

        Args:
            session: Session object to persist.
        """
        path = self.sessions_path / f"{session.session_id}.json"
        serialized = session.model_dump_json(indent=2)
        _atomic_write(path, serialized)

    def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session document from disk.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Parsed session document, or `None` if it does
            not exist.
        """
        path = self.sessions_path / f"{session_id}.json"
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    def delete_session(self, session_id: str) -> None:
        """Delete a session document and its persisted inference config.

        Args:
            session_id: Identifier of the session to delete.
        """
        path = self.sessions_path / f"{session_id}.json"
        path.unlink(missing_ok=True)

        config_path = self.configs_path / f"{session_id}.json"
        config_path.unlink(missing_ok=True)

    def save_inference_config(
        self,
        session_id: str,
        config: InferenceConfig,
    ) -> None:
        """Persist the frozen inference config associated with a session.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to persist.
        """
        path = self.configs_path / f"{session_id}.json"
        serialized = config.model_dump_json(indent=2)
        _atomic_write(path, serialized)

    def get_inference_config(
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
        path = self.configs_path / f"{session_id}.json"
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return InferenceConfig.model_validate(data)


class FileSystemCourseStorage:
    """
    Persistent filesystem-backed storage for Course metadata.

    Responsible only for atomic IO of Course documents.
    No business logic.
    """

    def __init__(self, base_path: Path):
        """Create the course metadata directory beneath the base path.

        Args:
            base_path: Root directory under which course data is stored.
        """
        self.base_path = Path(base_path)
        self.courses_path = self.base_path / "configs" / "courses"

        self.courses_path.mkdir(parents=True, exist_ok=True)

    def _course_path(self, course_id: str) -> Path:
        """Return the JSON document path for a course id.

        Args:
            course_id: Identifier of the course document.

        Returns:
            Path: Filesystem path where the course document is stored.
        """
        return self.courses_path / f"{course_id}.json"

    def save_course(self, course: Course) -> None:
        """Persist a course document using its course id as the filename.

        Args:
            course: Course document to serialize and store.
        """
        path = self._course_path(course.course_id)
        serialized = course.model_dump_json(indent=2)
        _atomic_write(path, serialized)

    def get_course(self, course_id: str) -> Optional[Course]:
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

    def delete_course(self, course_id: str) -> None:
        """Delete a persisted course document if it exists.

        Args:
            course_id: Identifier of the course to delete.
        """
        path = self._course_path(course_id)
        path.unlink(missing_ok=True)

    def list_courses(self) -> List[Course]:
        """Load and return every persisted course document.

        Returns:
            List[Course]: Parsed course documents found in the storage
            directory.
        """
        results: List[Course] = []

        for file in self.courses_path.glob("*.json"):
            if not file:
                return None
            with file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                results.append(Course.model_validate(data))

        return results

    def bind_lesson_to_course(self, course_id, lesson_id, version) -> None:
        """Bind or replace a lesson version in a course document.

        Args:
            course_id: Identifier of the course to update.
            lesson_id: Lesson identifier to bind.
            version: Lesson version to store for the bound lesson.
        """

        # Course storage path
        courses_dir = self.base_path / "configs" / "courses"
        courses_dir.mkdir(parents=True, exist_ok=True)

        course_path = courses_dir / f"{course_id}.json"

        if course_path.exists():
            with open(course_path, "r") as f:
                course_data = json.load(f)
        else:
            course_data = {
                "course_id": course_id,
                "lessons": {},
            }

        # Replace or insert
        course_data["lessons"][lesson_id] = version

        with open(course_path, "w") as f:
            json.dump(course_data, f, indent=2)
