#!/usr/bin/env python3
"""Build and validate local reference package evidence for briefing preflights.

The generated manifest is intentionally runtime state (``state/reference_packages.json``)
so daily briefings can score ecosystem/security items against the local autonomy
workspace without falling back to ad-hoc evidence scraped from prior reports.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

SCHEMA_VERSION = 1
DEFAULT_MARKERS = (
    "pyproject.toml",
    "package.json",
    "flake.nix",
    "requirements.txt",
    "Cargo.toml",
)


@dataclass(frozen=True)
class Evidence:
    kind: str
    path: str
    detail: str


def _run_git(repo: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip()


def _safe_remote(remote_url: str) -> str:
    """Return a credential-free remote identifier suitable for committing to JSON."""
    if remote_url.startswith("git@"):
        host_and_path = remote_url.split(":", 1)
        if len(host_and_path) == 2:
            return f"git@{host_and_path[0].split('@')[-1]}:{host_and_path[1]}"
        return "git@unknown"

    parsed = urlparse(remote_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.hostname or parsed.netloc}{parsed.path}"
    return remote_url.replace(str(Path.home()), "~")


def _read_pyproject_name(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("name") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip('"\'') or None
    return None


def _read_package_json_name(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    name = data.get("name")
    return name if isinstance(name, str) and name else None


def _infer_name(lab: Path, markers: dict[str, Path]) -> str:
    if "pyproject.toml" in markers:
        name = _read_pyproject_name(markers["pyproject.toml"])
        if name:
            return name
    if "package.json" in markers:
        name = _read_package_json_name(markers["package.json"])
        if name:
            return name
    return lab.name


def _marker_evidence(lab: Path, workspace_root: Path) -> tuple[dict[str, Path], list[Evidence]]:
    markers: dict[str, Path] = {}
    evidence: list[Evidence] = []
    for marker in DEFAULT_MARKERS:
        path = lab / marker
        if path.exists():
            markers[marker] = path
            evidence.append(
                Evidence(
                    kind="local_marker",
                    path=str(path.relative_to(workspace_root)),
                    detail=f"{marker} exists",
                )
            )
    return markers, evidence


def _git_evidence(lab: Path, workspace_root: Path) -> list[Evidence]:
    if not (lab / ".git").exists():
        return []

    evidence: list[Evidence] = []
    commit = _run_git(lab, "rev-parse", "--short=12", "HEAD")
    if commit:
        evidence.append(
            Evidence(
                kind="git_commit",
                path=str(lab.relative_to(workspace_root)),
                detail=commit,
            )
        )

    remotes = _run_git(lab, "remote", "-v") or ""
    github_remotes = sorted(
        {
            _safe_remote(line.split()[1])
            for line in remotes.splitlines()
            if len(line.split()) >= 2 and "github.com/hiveminderbot/" in line.split()[1]
        }
    )
    for remote in github_remotes:
        evidence.append(
            Evidence(
                kind="github_remote",
                path=str(lab.relative_to(workspace_root)),
                detail=remote,
            )
        )
    return evidence


def discover_reference_packages(workspace_root: Path) -> list[dict[str, Any]]:
    labs_root = workspace_root / "labs"
    if not labs_root.exists():
        raise FileNotFoundError(f"labs directory not found under {workspace_root}")

    packages: list[dict[str, Any]] = []
    for lab in sorted(p for p in labs_root.iterdir() if p.is_dir()):
        markers, evidence = _marker_evidence(lab, workspace_root)
        evidence.extend(_git_evidence(lab, workspace_root))
        if not evidence:
            continue

        package_managers = sorted(
            marker
            for marker in ("pyproject.toml", "package.json", "Cargo.toml", "flake.nix", "requirements.txt")
            if marker in markers
        )
        packages.append(
            {
                "name": _infer_name(lab, markers),
                "lab": lab.name,
                "relative_path": str(lab.relative_to(workspace_root)),
                "package_managers": package_managers,
                "evidence": [item.__dict__ for item in evidence],
            }
        )
    return packages


def build_manifest(workspace_root: Path) -> dict[str, Any]:
    packages = discover_reference_packages(workspace_root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "workspace_root": str(workspace_root),
        "purpose": "Reference local autonomy packages/repos for high-signal briefing relevance scoring and preflight checks.",
        "packages": packages,
        "summary": {
            "package_count": len(packages),
            "github_remote_count": sum(
                1
                for package in packages
                for evidence in package["evidence"]
                if evidence["kind"] == "github_remote"
            ),
            "local_marker_count": sum(
                1
                for package in packages
                for evidence in package["evidence"]
                if evidence["kind"] == "local_marker"
            ),
        },
    }


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if not manifest.get("generated_at"):
        errors.append("generated_at is required")
    packages = manifest.get("packages")
    if not isinstance(packages, list) or not packages:
        errors.append("packages must be a non-empty list")
        return errors

    for index, package in enumerate(packages):
        prefix = f"packages[{index}]"
        for key in ("name", "lab", "relative_path"):
            if not isinstance(package.get(key), str) or not package[key]:
                errors.append(f"{prefix}.{key} must be a non-empty string")
        evidence = package.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}.evidence must be a non-empty list")
            continue
        if not any(item.get("kind") in {"local_marker", "github_remote", "git_commit"} for item in evidence if isinstance(item, dict)):
            errors.append(f"{prefix}.evidence must contain concrete local/git evidence")
        for ev_index, item in enumerate(evidence):
            ev_prefix = f"{prefix}.evidence[{ev_index}]"
            if not isinstance(item, dict):
                errors.append(f"{ev_prefix} must be an object")
                continue
            for key in ("kind", "path", "detail"):
                if not isinstance(item.get(key), str) or not item[key]:
                    errors.append(f"{ev_prefix}.{key} must be a non-empty string")
    return errors


def preflight_manifest(path: Path) -> tuple[bool, str]:
    try:
        manifest = load_manifest(path)
    except FileNotFoundError:
        return False, f"REFERENCE_MANIFEST_MISSING path={path}"
    except json.JSONDecodeError as exc:
        return False, f"REFERENCE_MANIFEST_INVALID_JSON path={path} error={exc}"

    errors = validate_manifest(manifest)
    if errors:
        return False, "REFERENCE_MANIFEST_INVALID " + "; ".join(errors[:5])

    summary = manifest.get("summary", {})
    packages = manifest.get("packages", [])
    return (
        True,
        "REFERENCE_MANIFEST_OK "
        f"path={path} packages={len(packages)} "
        f"github_remotes={summary.get('github_remote_count', 0)} "
        f"local_markers={summary.get('local_marker_count', 0)}",
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Autonomy workspace root containing labs/ (default: inferred from this script)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("state/reference_packages.json"),
        help="Manifest output path for generate mode",
    )
    parser.add_argument(
        "--check",
        type=Path,
        help="Validate/preflight an existing manifest instead of generating one",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing output in generate mode",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.check:
        ok, message = preflight_manifest(args.check)
        print(message)
        return 0 if ok else 1

    manifest = build_manifest(args.workspace_root.resolve())
    errors = validate_manifest(manifest)
    if errors:
        print("REFERENCE_MANIFEST_GENERATION_INVALID " + "; ".join(errors[:5]))
        return 1

    if not args.dry_run:
        write_manifest(manifest, args.output)
    print(
        "REFERENCE_MANIFEST_GENERATED "
        f"packages={len(manifest['packages'])} "
        f"github_remotes={manifest['summary']['github_remote_count']} "
        f"local_markers={manifest['summary']['local_marker_count']} "
        f"output={args.output if not args.dry_run else '<dry-run>'}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
