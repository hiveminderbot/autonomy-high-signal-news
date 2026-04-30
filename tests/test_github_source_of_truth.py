#!/usr/bin/env python3
"""Regression tests for GitHub-only source-of-truth metadata."""

import json
import subprocess
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parent.parent
RETIRED_PATTERNS = ("forgejo", "gitea", "localhost:3000", "tin-sun", "172.17.0.1:3000")
GITHUB_REPO = "github.com/hiveminderbot/autonomy-high-signal-news"


def test_status_json_declares_private_github_source_of_truth():
    status = json.loads((LAB_ROOT / "STATUS.json").read_text(encoding="utf-8"))

    assert status["repository"] == "github:hiveminderbot/autonomy-high-signal-news"
    assert status["source_of_truth"]["remote"] == "github"
    assert status["source_of_truth"]["url"] == f"https://{GITHUB_REPO}.git"
    assert status["ci_cd"]["github_remote"] == "github:hiveminderbot/autonomy-high-signal-news"
    assert status["ci_cd"]["validation_config"] == "validation.json"
    assert "forgejo_workflows" not in status["ci_cd"]

    active_metadata = json.dumps(
        {
            "repository": status["repository"],
            "source_of_truth_remote": status["source_of_truth"]["remote"],
            "source_of_truth_url": status["source_of_truth"]["url"],
            "ci_cd": status["ci_cd"],
        },
        sort_keys=True,
    ).lower()
    assert not any(pattern in active_metadata for pattern in RETIRED_PATTERNS)


def test_readme_header_points_at_private_github_not_retired_forgejo():
    readme_lines = (LAB_ROOT / "README.md").read_text(encoding="utf-8").splitlines()[:8]
    header = "\n".join(readme_lines).lower()

    assert GITHUB_REPO in header
    assert not any(pattern in header for pattern in RETIRED_PATTERNS)


def test_validation_json_requires_github_remote_hygiene_gate():
    validation = json.loads((LAB_ROOT / "validation.json").read_text(encoding="utf-8"))
    checks = {check["name"]: check for check in validation["checks"]}

    gate = checks["GitHub source-of-truth remote hygiene"]
    assert gate["check_id"] == "command"
    assert gate["severity"] == "required"
    assert gate["strong_correctness"] is True
    command = gate["config"]["command"]
    assert GITHUB_REPO in command
    assert "grep -Eqi 'forgejo|gitea|localhost:3000|tin-sun|172\\.17\\.0\\.1:3000'" in command
    assert gate["config"]["expected_output"] == "PASS: GitHub-only source of truth"


def test_configured_git_remotes_are_github_only():
    result = subprocess.run(
        ["git", "remote", "-v"],
        cwd=LAB_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    remotes = result.stdout.lower()

    assert GITHUB_REPO in remotes
    assert not any(pattern in remotes for pattern in RETIRED_PATTERNS)
