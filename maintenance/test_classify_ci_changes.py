#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from classify_ci_changes import Selection, changed_paths, classify_paths, main


class ClassifyPathsTests(unittest.TestCase):
    def assert_selection(self, paths: list[str], **expected: bool) -> None:
        actual = classify_paths(paths)
        expected_selection = Selection(**expected)
        self.assertEqual(actual, expected_selection)

    def test_root_readme_is_lightweight(self) -> None:
        self.assert_selection(["README.md"])

    def test_nested_readmes_are_lightweight(self) -> None:
        self.assert_selection(["deploy/README.md", "plexa_server/alembic/README"])

    def test_citation_and_license_are_lightweight(self) -> None:
        self.assert_selection(["CITATION.cff", "LICENSE"])

    def test_docs_content_only_builds_docs(self) -> None:
        self.assert_selection(["docs/source/index.md"], docs=True)

    def test_docs_python_is_scanned(self) -> None:
        self.assert_selection(["docs/generate_openapi.py"], docs=True, codeql_python=True)

    def test_portal_source_builds_portal_docs_and_javascript_codeql(self) -> None:
        self.assert_selection(
            ["plexa_portal/src/api/http.ts"],
            portal=True,
            docs=True,
            codeql_javascript=True,
        )

    def test_portal_styles_do_not_run_codeql(self) -> None:
        self.assert_selection(["plexa_portal/src/index.css"], portal=True, docs=True)

    def test_server_source_builds_server_docs_and_python_codeql(self) -> None:
        self.assert_selection(
            ["plexa_server/core/sessions.py"],
            server=True,
            docs=True,
            codeql_python=True,
        )

    def test_server_dockerfile_also_validates_deployment(self) -> None:
        self.assert_selection(
            ["plexa_server/Dockerfile"],
            server=True,
            deployment=True,
            docs=True,
        )

    def test_dependency_lock_runs_server_docs_and_deployment(self) -> None:
        self.assert_selection(["uv.lock"], server=True, deployment=True, docs=True)

    def test_deployment_script_only_validates_deployment(self) -> None:
        self.assert_selection(["deploy/check-production.sh"], deployment=True)

    def test_workflow_or_classifier_changes_force_everything(self) -> None:
        self.assertEqual(classify_paths([".github/workflows/ci.yml"]), Selection.all())
        self.assertEqual(classify_paths(["maintenance/classify_ci_changes.py"]), Selection.all())

    def test_unknown_path_forces_everything(self) -> None:
        self.assertEqual(classify_paths(["unexpected.config"]), Selection.all())

    def test_mixed_changes_merge_categories(self) -> None:
        self.assert_selection(
            ["plexa_server/core/sessions.py", "plexa_portal/src/index.css"],
            portal=True,
            server=True,
            docs=True,
            codeql_python=True,
        )


class GitDiffTests(unittest.TestCase):
    def test_invalid_or_zero_object_ids_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            changed_paths("invalid", "a" * 40)
        with self.assertRaises(ValueError):
            changed_paths("0" * 40, "a" * 40)

    @patch("classify_ci_changes.subprocess.run")
    def test_changed_paths_uses_nul_delimited_diff_without_collapsing_renames(self, run) -> None:
        run.return_value = subprocess.CompletedProcess([], 0, b"README.md\0docs/source/index.md\0", b"")
        self.assertEqual(changed_paths("a" * 40, "b" * 40), ["README.md", "docs/source/index.md"])
        run.assert_called_once_with(
            ["git", "diff", "--name-only", "-z", "--no-renames", f"{'a' * 40}...{'b' * 40}"],
            check=True,
            capture_output=True,
        )

    def test_rename_source_and_destination_select_both_categories(self) -> None:
        selection = classify_paths(
            ["plexa_server/removed.py", "docs/source/replacement.py"]
        )
        self.assertEqual(
            selection,
            Selection(server=True, docs=True, codeql_python=True),
        )

    def test_cli_force_all_writes_every_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            self.assertEqual(main(["--all", "--github-output", str(output)]), 0)
            values = dict(line.split("=", 1) for line in output.read_text().splitlines())
        self.assertEqual(values, {name: "true" for name in Selection.__dataclass_fields__})

    @patch("classify_ci_changes.changed_paths", side_effect=ValueError("missing base"))
    def test_cli_diff_failure_fails_closed(self, _changed_paths) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "github-output"
            self.assertEqual(
                main(
                    [
                        "--base",
                        "a" * 40,
                        "--head",
                        "b" * 40,
                        "--github-output",
                        str(output),
                        "--json",
                    ]
                ),
                0,
            )
            github_values = dict(line.split("=", 1) for line in output.read_text().splitlines())
        self.assertEqual(github_values, {name: "true" for name in Selection.__dataclass_fields__})


if __name__ == "__main__":
    unittest.main()
