import json
from pathlib import Path
from typing import Optional

from plexa_server.models.lesson import Lesson
from plexa_server.models.session import Session
from plexa_server.inference.base import InferenceConfig
from plexa_server.storage.session_protocol import SessionStorage


class FileSystemArtifactStorage:
    """
    Persistent storage for lesson/session artifacts and encrypted logs.

    This class does not decrypt logs and does not modify lesson/session contents.
    """

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.lessons_path = base_path / "lessons"
        self.logs_path = base_path / "logs"

        self.lessons_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

    def save_lesson(self, lesson: Lesson) -> None:
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
        lesson_file = self.lessons_path / f"{lesson_id}_{version}.json"
        if not lesson_file.exists():
            return None

        with lesson_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Lesson.model_validate(data)

    def save_encrypted_log(self, instance_id: str, encrypted_blob: bytes) -> None:
        log_file = self.logs_path / f"{instance_id}.log"
        with log_file.open("wb") as f:
            f.write(encrypted_blob)

    def load_encrypted_log(self, instance_id: str) -> Optional[bytes]:
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
        self.base_path = Path(base_path)

        self.sessions_path = self.base_path / "sessions"
        self.configs_path = self.base_path / "configs"

        self.sessions_path.mkdir(parents=True, exist_ok=True)
        self.configs_path.mkdir(parents=True, exist_ok=True)

    def _atomic_write(self, path: Path, data: str) -> None:
        temp_path = path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as f:
            f.write(data)
        temp_path.replace(path)

    def save_session(self, session: Session) -> None:
        path = self.sessions_path / f"{session.session_id}.json"
        serialized = session.model_dump_json(indent=2)
        self._atomic_write(path, serialized)

    def get_session(self, session_id: str) -> Optional[Session]:
        path = self.sessions_path / f"{session_id}.json"
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return Session.model_validate(data)

    def delete_session(self, session_id: str) -> None:
        path = self.sessions_path / f"{session_id}.json"
        path.unlink(missing_ok=True)

        config_path = self.configs_path / f"{session_id}.json"
        config_path.unlink(missing_ok=True)

    def save_inference_config(
        self,
        session_id: str,
        config: InferenceConfig,
    ) -> None:
        path = self.configs_path / f"{session_id}.json"
        serialized = config.model_dump_json(indent=2)
        self._atomic_write(path, serialized)

    def get_inference_config(
        self,
        session_id: str,
    ) -> Optional[InferenceConfig]:
        path = self.configs_path / f"{session_id}.json"
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        return InferenceConfig.model_validate(data)