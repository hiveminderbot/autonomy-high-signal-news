#!/usr/bin/env python3
"""
CI Test Runner for High-Signal News

Runs all validation and end-to-end tests:
1. RSS source validator (HTTP 200, valid XML, entries > 0)
2. End-to-end fetch test (live RSS → briefing with ≥3 stories)
3. Existing unit tests (briefing generator, feed formats, etc.)

Target: completes in < 60 seconds total.
"""

import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "test-output"
REPORT_PATH = OUTPUT_DIR / "ci_test_report.json"


def run_command(cmd: list, description: str, timeout: int = 45) -> dict:
    """Run a command and return structured result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}")

    start = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent
        )
        duration = (datetime.now() - start).total_seconds()

        success = result.returncode == 0
        print(result.stdout)
        if result.stderr:
            print(result.stderr)

        return {
            "description": description,
            "command": " ".join(cmd),
            "success": success,
            "returncode": result.returncode,
            "duration_seconds": round(duration, 2),
            "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
            "stderr": result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
        }

    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start).total_seconds()
        print(f"TIMEOUT after {duration:.1f}s")
        return {
            "description": description,
            "command": " ".join(cmd),
            "success": False,
            "returncode": -1,
            "duration_seconds": round(duration, 2),
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
        }
    except Exception as e:
        duration = (datetime.now() - start).total_seconds()
        return {
            "description": description,
            "command": " ".join(cmd),
            "success": False,
            "returncode": -1,
            "duration_seconds": round(duration, 2),
            "stdout": "",
            "stderr": str(e),
        }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    overall_start = datetime.now()
    results = []

    # 1. RSS Source Validator
    results.append(run_command(
        [sys.executable, "scripts/validate_rss_sources.py", "--ci", "--min-ok-rate", "0.6"],
        "RSS Source Validator",
        timeout=45
    ))

    # 2. End-to-End Fetch Test
    results.append(run_command(
        [sys.executable, "tests/test_e2e_rss_briefing.py"],
        "End-to-End RSS Briefing Test",
        timeout=45
    ))

    # 3. Unit tests
    results.append(run_command(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-q"],
        "Unit Tests (pytest)",
        timeout=30
    ))

    overall_duration = (datetime.now() - overall_start).total_seconds()

    all_passed = all(r["success"] for r in results)

    report = {
        "timestamp": datetime.now().isoformat(),
        "overall_success": all_passed,
        "overall_duration_seconds": round(overall_duration, 2),
        "tests": results,
    }

    with open(REPORT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*60}")
    print(f"CI Test Summary")
    print(f"{'='*60}")
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        print(f"  [{status}] {r['description']} ({r['duration_seconds']:.1f}s)")
    print(f"\n  Overall: {'PASS' if all_passed else 'FAIL'} ({overall_duration:.1f}s)")
    print(f"  Report: {REPORT_PATH}")
    print(f"{'='*60}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
