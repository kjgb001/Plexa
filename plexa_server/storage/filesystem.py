import json
from pathlib import Path
from typing import Optional

from plexa_server.models.lesson import Lesson


class FileSystemStorage:
    """
    Persistent storage for lesson artifacts and encrypted logs.

    This class does not decrypt logs and does not modify lesson contents.
    """

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.lessons_path = base_path / "lessons"
        self.logs_path = base_path / "logs"

        self.lessons_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

    def save_lesson(self, lesson: Lesson) -> None:
        lesson_file = self.lessons_path / f"{lesson.identity.lesson_id}_{lesson.identity.version}.json"
        with lesson_file.open("w", encoding="utf-8") as f:
            f.write(lesson.model_dump_json(indent=2))

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
