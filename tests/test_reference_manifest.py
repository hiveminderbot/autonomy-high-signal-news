#!/usr/bin/env python3
"""Tests for reference package manifest generation and preflight validation."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.reference_manifest import (
    build_manifest,
    preflight_manifest,
    validate_manifest,
    write_manifest,
)


def _make_lab(root: Path, name: str, marker_name: str, marker_content: str) -> Path:
    lab = root / "labs" / name
    lab.mkdir(parents=True)
    (lab / marker_name).write_text(marker_content, encoding="utf-8")
    return lab


def test_build_manifest_captures_local_package_evidence(tmp_path):
    _make_lab(
        tmp_path,
        "example-python",
        "pyproject.toml",
        '[project]\nname = "example-python"\n',
    )
    _make_lab(
        tmp_path,
        "example-node",
        "package.json",
        '{"name": "example-node"}\n',
    )

    manifest = build_manifest(tmp_path)

    assert manifest["schema_version"] == 1
    assert manifest["summary"]["package_count"] == 2
    assert manifest["summary"]["local_marker_count"] == 2
    names = {package["name"] for package in manifest["packages"]}
    assert names == {"example-python", "example-node"}
    assert all(package["evidence"] for package in manifest["packages"])


def test_preflight_accepts_written_manifest(tmp_path):
    _make_lab(tmp_path, "example", "flake.nix", "{}\n")
    manifest = build_manifest(tmp_path)
    output = tmp_path / "state" / "reference_packages.json"
    write_manifest(manifest, output)

    ok, message = preflight_manifest(output)

    assert ok is True
    assert "REFERENCE_MANIFEST_OK" in message
    assert "packages=1" in message


def test_preflight_rejects_missing_manifest(tmp_path):
    ok, message = preflight_manifest(tmp_path / "state" / "reference_packages.json")

    assert ok is False
    assert message.startswith("REFERENCE_MANIFEST_MISSING")


def test_validate_rejects_empty_package_list():
    errors = validate_manifest(
        {
            "schema_version": 1,
            "generated_at": "2026-04-27T00:00:00+00:00",
            "packages": [],
        }
    )

    assert "packages must be a non-empty list" in errors


def test_manifest_json_round_trip_contains_concrete_evidence(tmp_path):
    _make_lab(tmp_path, "example", "requirements.txt", "requests\n")
    output = tmp_path / "state" / "reference_packages.json"
    write_manifest(build_manifest(tmp_path), output)

    data = json.loads(output.read_text(encoding="utf-8"))

    evidence = data["packages"][0]["evidence"][0]
    assert evidence["kind"] == "local_marker"
    assert evidence["path"] == "labs/example/requirements.txt"
    assert evidence["detail"] == "requirements.txt exists"
