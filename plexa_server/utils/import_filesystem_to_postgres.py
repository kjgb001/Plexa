"""One-way migration from deprecated filesystem storage to PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from plexa_server.db.bootstrap import ALEMBIC_INI_PATH
from plexa_server.db.config import get_named_database_config
from plexa_server.db.models import (
    Base,
    CourseRecord,
    EncryptedLogAccessAuditRecord,
    EncryptedLogRecord,
    LessonRecord,
    SessionRecord,
    UserCourseStateRecord,
    UserLessonStateRecord,
)
from plexa_server.db.session import create_session_factory
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.course import Course
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.lesson import Lesson
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditEntry
from plexa_server.models.session import Session
from plexa_server.models.workspace_state import UserCourseState, UserLessonState
from plexa_server.storage.filesystem import (
    FileSystemArtifactStorage,
    FileSystemCourseStorage,
    FileSystemSessionStorage,
    FileSystemWorkspaceStateStorage,
)
from plexa_server.storage.postgres import (
    PostgresArtifactStorage,
    PostgresCourseStorage,
    PostgresSessionStorage,
    PostgresWorkspaceStateStorage,
)
from plexa_server.utils.filesystem_data_dir import get_data_dir_path


CATEGORIES = (
    "courses",
    "lessons",
    "sessions",
    "inference_configs",
    "encrypted_logs",
    "log_access_audits",
    "course_workspace_states",
    "lesson_workspace_states",
)


class MigrationPreflightError(RuntimeError):
    """Raised when source or target validation makes migration unsafe."""


@dataclass(frozen=True)
class SourceLesson:
    """A parsed lesson document and its optional filesystem course scope."""

    path: Path
    course_id: str | None
    lesson: Lesson


@dataclass
class SourceData:
    """Validated source records staged entirely before target writes begin."""

    courses: list[Course]
    lessons: list[tuple[str, Lesson]]
    sessions: list[Session]
    inference_configs: dict[str, InferenceConfig]
    encrypted_logs: list[tuple[EncryptedLogMetadata, bytes | None]]
    log_access_audits: list[EncryptedLogAccessAuditEntry]
    course_workspace_states: list[UserCourseState]
    lesson_workspace_states: list[UserLessonState]

    def counts(self) -> dict[str, int]:
        """Return record counts using stable report category names."""
        return {
            "courses": len(self.courses),
            "lessons": len(self.lessons),
            "sessions": len(self.sessions),
            "inference_configs": len(self.inference_configs),
            "encrypted_logs": len(self.encrypted_logs),
            "log_access_audits": len(self.log_access_audits),
            "course_workspace_states": len(self.course_workspace_states),
            "lesson_workspace_states": len(self.lesson_workspace_states),
        }


@dataclass
class ImportReport:
    """Machine- and human-readable migration result."""

    source: str
    target: str
    dry_run: bool
    source_counts: dict[str, int]
    imported_counts: dict[str, int] = field(default_factory=dict)
    verified_counts: dict[str, int] = field(default_factory=dict)
    status: str = "validated"

    def to_dict(self) -> dict[str, Any]:
        """Serialize the report for JSON output."""
        return asdict(self)


def _decode_component(value: str) -> str:
    """Decode a URL-safe Base64 filesystem path component."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")


def _canonical_model(model: Any, *, exclude: set[str] | None = None) -> dict[str, Any]:
    """Return a stable JSON-mode representation for verification."""
    return model.model_dump(mode="json", exclude=exclude or set())


def _expected_persisted_session(
    session: Session,
    inference_config: InferenceConfig | None,
) -> Session:
    """Apply PostgreSQL's intentional transcript and revision persistence rules."""
    messages = [] if session.logging_policy == "disabled" else [
        message for message in session.messages if message.role != "system"
    ]
    return session.model_copy(
        update={
            "messages": messages,
            "persistence_revision": 0,
            "frozen_inference_config": inference_config,
        }
    )


def _load_legacy_log_blob(data_dir: Path, instance_id: str) -> bytes | None:
    """Load either the encoded current filename or a legacy raw filename."""
    encoded = (
        base64.urlsafe_b64encode(instance_id.encode("utf-8")).decode("ascii").rstrip("=")
    )
    candidates = [(data_dir / "logs" / f"{encoded}.log")]
    if "/" not in instance_id and ".." not in instance_id:
        candidates.append(data_dir / "logs" / f"{instance_id}.log")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_bytes()
    return None


def _encoded_component(value: str) -> str:
    """Encode an identifier using the legacy storage filename convention."""
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _scan_lessons(data_dir: Path) -> list[SourceLesson]:
    """Parse every legacy lesson file without trusting its path for identity."""
    lessons_path = data_dir / "lessons"
    documents: list[SourceLesson] = []
    for path in sorted(lessons_path.glob("**/*.json")):
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        lesson = Lesson.model_validate(_normalize_legacy_lesson(raw.get("lesson", raw), path))
        if path.parent == lessons_path or path.parent.name == "_legacy":
            course_id = None
        else:
            try:
                course_id = _decode_component(path.parent.name)
            except (UnicodeDecodeError, ValueError) as exc:
                raise MigrationPreflightError(
                    f"Cannot decode lesson course scope for {path}."
                ) from exc
        documents.append(SourceLesson(path=path, course_id=course_id, lesson=lesson))
    return documents


def _normalize_legacy_lesson(raw: dict[str, Any], path: Path) -> dict[str, Any]:
    """Translate the pre-hook reflection shape used by early 0.1.x data."""
    reflection = raw.get("reflection")
    if not isinstance(reflection, dict) or "hooks" in reflection:
        return raw
    prompts = reflection.get("reflection_prompts")
    if prompts is None:
        return raw
    timing = reflection.get("reflection_timing")
    if timing not in (None, "post", "post_session", "completion"):
        raise MigrationPreflightError(
            f"Lesson {path} uses unsupported legacy reflection timing {timing!r}."
        )
    attached_metadata = reflection.get("attached_metadata")
    if attached_metadata is not None and attached_metadata != "":
        raise MigrationPreflightError(
            f"Lesson {path} contains legacy attached reflection metadata "
            "that cannot be mapped safely."
        )
    if not isinstance(prompts, list) or not all(isinstance(prompt, str) for prompt in prompts):
        raise MigrationPreflightError(f"Lesson {path} has invalid legacy reflection prompts.")
    normalized = dict(raw)
    normalized["reflection"] = {
        "hooks": [
            {
                "hook_id": f"legacy-post-{index}",
                "prompt": prompt,
                "phase": "post",
                "order_index": index - 1,
            }
            for index, prompt in enumerate(prompts, start=1)
        ],
        "logging_policy": reflection.get("logging_policy"),
    }
    return normalized


def _bind_lessons(
    courses: list[Course],
    documents: list[SourceLesson],
) -> list[tuple[str, Lesson]]:
    """Resolve each course binding to exactly one filesystem lesson document."""
    errors: list[str] = []
    consumed: set[Path] = set()
    resolved: list[tuple[str, Lesson]] = []

    for course in courses:
        for lesson_id, version in course.lessons.items():
            matches = [
                document
                for document in documents
                if document.lesson.identity.lesson_id == lesson_id
                and document.lesson.identity.version == version
                and document.course_id == course.course_id
            ]
            if not matches:
                matches = [
                    document
                    for document in documents
                    if document.lesson.identity.lesson_id == lesson_id
                    and document.lesson.identity.version == version
                    and document.course_id is None
                ]
            if len(matches) != 1:
                errors.append(
                    f"Course {course.course_id} binding {lesson_id}@{version} resolved to "
                    f"{len(matches)} lesson documents."
                )
                continue
            consumed.add(matches[0].path)
            resolved.append((course.course_id, matches[0].lesson))

    orphaned = sorted(str(document.path) for document in documents if document.path not in consumed)
    if orphaned:
        errors.append("Unbound lesson documents: " + ", ".join(orphaned))
    if errors:
        raise MigrationPreflightError("\n".join(errors))
    return resolved


def _load_inference_configs(
    data_dir: Path,
    sessions: list[Session],
) -> dict[str, InferenceConfig]:
    """Load both legacy raw-name and encoded-name inference config files."""
    session_ids = {session.session_id for session in sessions}
    configs: dict[str, InferenceConfig] = {}
    for path in sorted((data_dir / "configs").glob("*.json")):
        candidates = [path.stem]
        try:
            candidates.append(_decode_component(path.stem))
        except (UnicodeDecodeError, ValueError):
            pass
        matches = [candidate for candidate in candidates if candidate in session_ids]
        if len(set(matches)) != 1:
            raise MigrationPreflightError(
                f"Inference config {path} does not identify exactly one source session."
            )
        session_id = matches[0]
        if session_id in configs:
            raise MigrationPreflightError(f"Duplicate inference config for session {session_id}.")
        with path.open("r", encoding="utf-8") as file:
            configs[session_id] = InferenceConfig.model_validate(json.load(file))

    for session in sessions:
        config = configs.get(session.session_id)
        if config is None and session.frozen_inference_config is not None:
            configs[session.session_id] = session.frozen_inference_config
        elif (
            config is not None
            and session.frozen_inference_config is not None
            and config != session.frozen_inference_config
        ):
            raise MigrationPreflightError(
                f"Session {session.session_id} has conflicting frozen inference configs."
            )
    return configs


async def _load_source(data_dir: Path) -> SourceData:
    """Read and validate the complete source tree before target mutation."""
    if not data_dir.is_dir():
        raise MigrationPreflightError(f"Filesystem source does not exist: {data_dir}")

    source_artifacts = FileSystemArtifactStorage(data_dir, read_only=True)
    source_courses = FileSystemCourseStorage(data_dir, read_only=True)
    source_sessions = FileSystemSessionStorage(data_dir, read_only=True)
    source_workspace = FileSystemWorkspaceStateStorage(data_dir, read_only=True)

    try:
        courses = await source_courses.list_courses()
        lessons = _bind_lessons(courses, _scan_lessons(data_dir))
        sessions = await source_sessions.list_sessions()
        inference_configs = _load_inference_configs(data_dir, sessions)
        log_metadata: list[EncryptedLogMetadata] = []
        for path in sorted((data_dir / "logs").glob("*.meta.json")):
            with path.open("r", encoding="utf-8") as file:
                metadata = EncryptedLogMetadata.model_validate(json.load(file))
            valid_stems = {_encoded_component(metadata.instance_id)}
            if "/" not in metadata.instance_id and ".." not in metadata.instance_id:
                valid_stems.add(metadata.instance_id)
            if path.name.removesuffix(".meta.json") not in valid_stems:
                raise MigrationPreflightError(
                    f"Encrypted log metadata filename does not match {metadata.instance_id}: {path}"
                )
            log_metadata.append(metadata)
        audits = await source_artifacts.list_encrypted_log_access_audits()
        course_states = await source_workspace.list_all_course_states()
        lesson_states = await source_workspace.list_all_lesson_states()
    except MigrationPreflightError:
        raise
    except Exception as exc:
        raise MigrationPreflightError(f"Could not parse filesystem source: {exc}") from exc

    course_map = {course.course_id: course for course in courses}
    if len(course_map) != len(courses):
        raise MigrationPreflightError("Duplicate course identifiers exist in the source.")
    session_map = {session.session_id: session for session in sessions}
    if len(session_map) != len(sessions):
        raise MigrationPreflightError("Duplicate session identifiers exist in the source.")
    metadata_ids = [metadata.instance_id for metadata in log_metadata]
    if len(set(metadata_ids)) != len(metadata_ids):
        raise MigrationPreflightError("Duplicate encrypted log identifiers exist in the source.")
    audit_ids = [audit.audit_id for audit in audits]
    if len(set(audit_ids)) != len(audit_ids):
        raise MigrationPreflightError(
            "Duplicate encrypted log audit identifiers exist in the source."
        )
    course_state_keys = [(state.user_id, state.course_id) for state in course_states]
    if len(set(course_state_keys)) != len(course_state_keys):
        raise MigrationPreflightError("Duplicate course workspace states exist in the source.")
    lesson_state_keys = [
        (state.user_id, state.course_id, state.lesson_id)
        for state in lesson_states
    ]
    if len(set(lesson_state_keys)) != len(lesson_state_keys):
        raise MigrationPreflightError("Duplicate lesson workspace states exist in the source.")

    errors: list[str] = []
    for session in sessions:
        course = course_map.get(session.course_id)
        if course is None:
            errors.append(
                f"Session {session.session_id} references missing course {session.course_id}."
            )
        elif course.lessons.get(session.lesson_id) != session.lesson_version:
            errors.append(
                f"Session {session.session_id} references an unbound lesson version "
                f"{session.lesson_id}@{session.lesson_version}."
            )

    encrypted_logs: list[tuple[EncryptedLogMetadata, bytes | None]] = []
    metadata_stems = {
        path.name.removesuffix(".meta.json")
        for path in (data_dir / "logs").glob("*.meta.json")
    }
    for metadata in log_metadata:
        course = course_map.get(metadata.course_id)
        if course is None or course.lessons.get(metadata.lesson_id) != metadata.lesson_version:
            errors.append(
                f"Encrypted log {metadata.instance_id} references an unknown course lesson."
            )
        if metadata.instance_id not in session_map:
            errors.append(f"Encrypted log {metadata.instance_id} has no matching session.")
        blob = _load_legacy_log_blob(data_dir, metadata.instance_id)
        if metadata.content_available:
            if blob is None:
                errors.append(
                    f"Encrypted log {metadata.instance_id} is marked available but missing."
                )
            elif hashlib.sha256(blob).hexdigest() != metadata.artifact_sha256:
                errors.append(f"Encrypted log {metadata.instance_id} failed SHA-256 validation.")
        elif blob is not None:
            errors.append(
                f"Expired encrypted log {metadata.instance_id} still has content on disk."
            )
        encrypted_logs.append((metadata, blob))

    orphan_blob_stems = {
        path.stem for path in (data_dir / "logs").glob("*.log")
    } - metadata_stems
    if orphan_blob_stems:
        errors.append(
            "Encrypted log blobs without metadata: "
            + ", ".join(sorted(orphan_blob_stems))
        )

    for audit in audits:
        if audit.course_id not in course_map:
            errors.append(f"Audit {audit.audit_id} references missing course {audit.course_id}.")
        if audit.session_id is not None and audit.session_id not in session_map:
            errors.append(f"Audit {audit.audit_id} references missing session {audit.session_id}.")

    for state in course_states:
        if state.course_id not in course_map:
            errors.append(
                f"Course workspace state for {state.user_id} references missing "
                f"course {state.course_id}."
            )
    for state in lesson_states:
        course = course_map.get(state.course_id)
        if course is None or course.lessons.get(state.lesson_id) != state.lesson_version:
            errors.append(
                f"Lesson workspace state for {state.user_id} references an unknown course lesson."
            )

    if errors:
        raise MigrationPreflightError("\n".join(errors))
    return SourceData(
        courses=courses,
        lessons=lessons,
        sessions=sessions,
        inference_configs=inference_configs,
        encrypted_logs=encrypted_logs,
        log_access_audits=audits,
        course_workspace_states=course_states,
        lesson_workspace_states=lesson_states,
    )


async def _validate_target(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Require an Alembic-head schema with no existing Plexa domain rows."""
    alembic_config = Config(str(ALEMBIC_INI_PATH))
    expected_heads = set(ScriptDirectory.from_config(alembic_config).get_heads())
    try:
        async with session_factory() as session:
            result = await session.execute(text("SELECT version_num FROM alembic_version"))
            actual_heads = set(result.scalars().all())
            if actual_heads != expected_heads:
                raise MigrationPreflightError(
                    "Target schema is not at Alembic head: "
                    f"expected {sorted(expected_heads)}, found {sorted(actual_heads)}."
                )

            populated: list[str] = []
            for table in Base.metadata.sorted_tables:
                count = await session.scalar(select(func.count()).select_from(table))
                if count:
                    populated.append(f"{table.name}={count}")
            if populated:
                raise MigrationPreflightError(
                    "Target database must be empty; populated tables: " + ", ".join(populated)
                )
    except MigrationPreflightError:
        raise
    except Exception as exc:
        raise MigrationPreflightError(
            "Could not validate the PostgreSQL target. Run Plexa migrations first."
        ) from exc


async def _write_target(
    source: SourceData,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Write staged source data in dependency order."""
    artifacts = PostgresArtifactStorage(session_factory)
    courses = PostgresCourseStorage(session_factory)
    sessions = PostgresSessionStorage(session_factory)
    workspace = PostgresWorkspaceStateStorage(session_factory)

    for source_course in source.courses:
        await courses.save_course(
            source_course.model_copy(update={"lessons": {}, "lesson_timeline": [], "revision": 0})
        )
    for course_id, lesson in source.lessons:
        await artifacts.save_lesson(lesson, course_id=course_id)
    for source_course in source.courses:
        target_course = await courses.get_course(source_course.course_id)
        if target_course is None:
            raise RuntimeError(f"Failed to import course {source_course.course_id}.")
        target_course.lessons = dict(source_course.lessons)
        target_course.lesson_timeline = list(source_course.lesson_timeline)
        await courses.save_course(target_course)

    for source_session in source.sessions:
        staged_session = source_session.model_copy(update={"persistence_revision": 0})
        await sessions.save_session(staged_session)
        config = source.inference_configs.get(source_session.session_id)
        if config is not None:
            await sessions.save_inference_config(source_session.session_id, config)

    for metadata, blob in source.encrypted_logs:
        await artifacts.restore_encrypted_log(metadata, blob)
    for audit in source.log_access_audits:
        await artifacts.save_encrypted_log_access_audit(audit)
    for state in source.course_workspace_states:
        await workspace.restore_course_state(state)
    for state in source.lesson_workspace_states:
        await workspace.restore_lesson_state(state)


async def _verify_target(
    source: SourceData,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, int]:
    """Compare imported identities, content, timestamps, and encrypted bytes."""
    artifacts = PostgresArtifactStorage(session_factory)
    courses = PostgresCourseStorage(session_factory)
    sessions = PostgresSessionStorage(session_factory)
    workspace = PostgresWorkspaceStateStorage(session_factory)
    errors: list[str] = []

    target_courses = {course.course_id: course for course in await courses.list_courses()}
    for expected in source.courses:
        actual = target_courses.get(expected.course_id)
        if actual is None or _canonical_model(actual, exclude={"revision"}) != _canonical_model(
            expected, exclude={"revision"}
        ):
            errors.append(f"Course verification failed: {expected.course_id}")

    for course_id, expected in source.lessons:
        actual = await artifacts.load_lesson(
            expected.identity.lesson_id,
            expected.identity.version,
            course_id,
        )
        if actual != expected:
            errors.append(
                f"Lesson verification failed: {course_id}/{expected.identity.lesson_id}"
            )

    target_sessions = {session.session_id: session for session in await sessions.list_sessions()}
    for expected in source.sessions:
        actual = target_sessions.get(expected.session_id)
        expected_config = source.inference_configs.get(expected.session_id)
        normalized = _expected_persisted_session(expected, expected_config)
        if actual is None or _canonical_model(actual) != _canonical_model(normalized):
            errors.append(f"Session verification failed: {expected.session_id}")
        if await sessions.get_inference_config(expected.session_id) != expected_config:
            errors.append(f"Inference config verification failed: {expected.session_id}")

    for metadata, blob in source.encrypted_logs:
        actual_metadata = await artifacts.load_encrypted_log_metadata(metadata.instance_id)
        actual_blob = await artifacts.load_encrypted_log(metadata.instance_id)
        if actual_metadata != metadata:
            errors.append(f"Encrypted log metadata verification failed: {metadata.instance_id}")
        if actual_blob != blob:
            errors.append(f"Encrypted log content verification failed: {metadata.instance_id}")
        if (
            blob is not None
            and hashlib.sha256(actual_blob or b"").hexdigest() != metadata.artifact_sha256
        ):
            errors.append(f"Encrypted log hash verification failed: {metadata.instance_id}")

    target_audits = await artifacts.list_encrypted_log_access_audits()
    if target_audits != source.log_access_audits:
        errors.append("Encrypted log access audit verification failed.")

    course_users = {state.user_id for state in source.course_workspace_states}
    actual_course_states = [
        state
        for user_id in course_users
        for state in await workspace.list_course_states(user_id)
    ]
    if sorted(map(_canonical_model, actual_course_states), key=str) != sorted(
        map(_canonical_model, source.course_workspace_states), key=str
    ):
        errors.append("Course workspace state verification failed.")

    lesson_users = {state.user_id for state in source.lesson_workspace_states}
    actual_lesson_states = [
        state
        for user_id in lesson_users
        for state in await workspace.list_lesson_states(user_id)
    ]
    if sorted(map(_canonical_model, actual_lesson_states), key=str) != sorted(
        map(_canonical_model, source.lesson_workspace_states), key=str
    ):
        errors.append("Lesson workspace state verification failed.")

    async with session_factory() as database_session:
        target_counts = {
            "courses": await database_session.scalar(
                select(func.count()).select_from(CourseRecord)
            ),
            "lessons": await database_session.scalar(
                select(func.count()).select_from(LessonRecord)
            ),
            "sessions": await database_session.scalar(
                select(func.count()).select_from(SessionRecord)
            ),
            "inference_configs": await database_session.scalar(
                select(func.count())
                .select_from(SessionRecord)
                .where(SessionRecord.frozen_inference_config.is_not(None))
            ),
            "encrypted_logs": await database_session.scalar(
                select(func.count()).select_from(EncryptedLogRecord)
            ),
            "log_access_audits": await database_session.scalar(
                select(func.count()).select_from(EncryptedLogAccessAuditRecord)
            ),
            "course_workspace_states": await database_session.scalar(
                select(func.count()).select_from(UserCourseStateRecord)
            ),
            "lesson_workspace_states": await database_session.scalar(
                select(func.count()).select_from(UserLessonStateRecord)
            ),
        }
    if target_counts != source.counts():
        errors.append(f"Record count mismatch: expected {source.counts()}, found {target_counts}")
    if errors:
        raise RuntimeError("Post-import verification failed:\n" + "\n".join(errors))
    return target_counts


async def import_filesystem_to_postgres(
    data_dir: Path,
    target: str = "dev",
    *,
    dry_run: bool = False,
) -> ImportReport:
    """Validate and import a complete legacy filesystem dataset into PostgreSQL."""
    database_config = get_named_database_config(target)
    if not database_config.is_configured:
        raise ValueError(f"Database configuration for target '{target}' is missing.")
    session_factory = create_session_factory(
        database_config.resolved_async_url(),
        echo=database_config.echo,
    )
    source = await _load_source(Path(data_dir))
    await _validate_target(session_factory)
    report = ImportReport(
        source=str(Path(data_dir).resolve()),
        target=target,
        dry_run=dry_run,
        source_counts=source.counts(),
        imported_counts={category: 0 for category in CATEGORIES},
        verified_counts={category: 0 for category in CATEGORIES},
    )
    if dry_run:
        return report

    await _write_target(source, session_factory)
    report.imported_counts = source.counts()
    report.verified_counts = await _verify_target(source, session_factory)
    report.status = "imported"
    return report


def parse_args() -> argparse.Namespace:
    """Parse importer CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Import deprecated filesystem data into an empty PostgreSQL database."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=get_data_dir_path(),
        help="Legacy filesystem data root. Defaults to plexa_server/data.",
    )
    parser.add_argument(
        "--target",
        choices=["dev", "test"],
        default="dev",
        help="Database target to import into.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the source and target without writing records.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable report.",
    )
    return parser.parse_args()


def _print_report(report: ImportReport, as_json: bool) -> None:
    """Print a concise migration result."""
    if as_json:
        print(json.dumps(report.to_dict(), sort_keys=True))
        return
    action = "validated" if report.dry_run else "imported and verified"
    print(f"Filesystem data {action}: {report.source} -> {report.target}")
    for category in CATEGORIES:
        print(f"  {category}: {report.source_counts[category]}")


async def main() -> None:
    """Run the filesystem migration CLI."""
    args = parse_args()
    try:
        report = await import_filesystem_to_postgres(
            args.data_dir,
            target=args.target,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}))
            raise SystemExit(1) from None
        raise
    _print_report(report, args.json)


if __name__ == "__main__":
    asyncio.run(main())
