from abc import ABC, abstractmethod
from typing import List, Optional

from plexa_server.inference.base import InferenceConfig
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.models.session import Session


class ArtifactStorage(ABC):
    """Abstract storage contract for lesson artifacts and encrypted logs."""

    @abstractmethod
    def save_lesson(self, lesson: Lesson) -> None:
        """Persist a lesson artifact.

        Args:
            lesson: Lesson document to store.
        """

    @abstractmethod
    def load_lesson(self, lesson_id: str, version: str) -> Optional[Lesson]:
        """Load a lesson artifact by identifier and version.

        Args:
            lesson_id: Lesson identifier to load.
            version: Lesson version to load.

        Returns:
            Optional[Lesson]: Stored lesson document, or `None` if absent.
        """

    @abstractmethod
    def save_encrypted_log(self, instance_id: str, encrypted_blob: bytes) -> None:
        """Persist an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.
            encrypted_blob: Opaque encrypted bytes to store.
        """

    @abstractmethod
    def load_encrypted_log(self, instance_id: str) -> Optional[bytes]:
        """Load an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.

        Returns:
            Optional[bytes]: Stored encrypted bytes, or `None` if absent.
        """


class SessionStorage(ABC):
    """Abstract storage contract for sessions and frozen inference configs."""

    @abstractmethod
    def save_session(self, session: Session) -> None:
        """Persist the current session state.

        Args:
            session: Session object to store.
        """

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Persisted session, or `None` if absent.
        """

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Delete any persisted state associated with a session id.

        Args:
            session_id: Identifier of the session to delete.
        """

    @abstractmethod
    def save_inference_config(self, session_id: str, config: InferenceConfig) -> None:
        """Persist the frozen inference config for a session.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to store.
        """

    @abstractmethod
    def get_inference_config(self, session_id: str) -> Optional[InferenceConfig]:
        """Load a session's inference config.

        Args:
            session_id: Identifier of the session whose config should be loaded.

        Returns:
            Optional[InferenceConfig]: Persisted config, or `None` if absent.
        """

    @abstractmethod
    def list_sessions(self) -> List[Session]:
        """Load every persisted session document.

        Returns:
            List[Session]: All persisted sessions.
        """


class CourseStorage(ABC):
    """Abstract storage contract for course metadata and lesson bindings."""

    @abstractmethod
    def save_course(self, course: Course) -> None:
        """Persist a course document.

        Args:
            course: Course document to store.
        """

    @abstractmethod
    def get_course(self, course_id: str) -> Optional[Course]:
        """Load a course by id.

        Args:
            course_id: Identifier of the course to load.

        Returns:
            Optional[Course]: Persisted course, or `None` if absent.
        """

    @abstractmethod
    def delete_course(self, course_id: str) -> None:
        """Delete a persisted course document.

        Args:
            course_id: Identifier of the course to delete.
        """

    @abstractmethod
    def list_courses(self) -> List[Course]:
        """Load every persisted course document.

        Returns:
            List[Course]: All persisted courses.
        """

    @abstractmethod
    def bind_lesson_to_course(self, course_id: str, lesson_id: str, version: str) -> None:
        """Bind a lesson version into a course document.

        Args:
            course_id: Identifier of the course to update.
            lesson_id: Lesson identifier to bind.
            version: Lesson version to store.
        """
