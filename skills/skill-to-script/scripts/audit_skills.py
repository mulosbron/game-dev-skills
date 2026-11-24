#!/usr/bin/env python3
"""Run unit tests and skill_lint.py across one or more skill directories.

Usage:
  python audit_skills.py SKILL_DIR [SKILL_DIR ...]
  python audit_skills.py SKILL_DIR --output audit_report.md --json audit_report.json
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LINTER = Path(__file__).resolve().parent / "skill_lint.py"


def run_cmd(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def audit_skills(folders):
    """Run unittest (where tests/ exists) and skill_lint.py across all folders."""
    summary_lines = []
    total_tests = 0
    all_ok = True
    test_results = []

    for folder in folders:
        root = Path(folder).resolve()
        tests_dir = root / "tests"
        if tests_dir.is_dir():
            proc = run_cmd([sys.executable, "-m", "unittest", "discover", "-s", "tests"], root)
            m = re.search(r"Ran (\d+) tests?", proc.stderr)
            count = int(m.group(1)) if m else 0
            total_tests += count
            ok = proc.returncode == 0
            status = "OK" if ok else "FAILED"
            summary_lines.append(f"{root.name}: tests={count} {status}")
            test_results.append({
                "skill": root.name,
                "tests": count,
                "passed": ok,
                "stderr": proc.stderr.strip() if not ok else "",
            })
            all_ok = all_ok and ok
        else:
            summary_lines.append(f"{root.name}: tests=0 (no tests/ dir)")
            test_results.append({"skill": root.name, "tests": 0, "passed": True, "stderr": ""})

    lint_proc = run_cmd([sys.executable, str(LINTER)] + [str(Path(f).resolve()) for f in folders], Path.cwd())
    all_ok = all_ok and (lint_proc.returncode == 0)
    summary_lines.append(f"lint exit code={lint_proc.returncode}")
    report = lint_proc.stdout
    table_rows = [line for line in report.splitlines() if line.startswith("| ") and "Skill |" not in line]
    summary_lines.extend(table_rows)
    summary_lines.append(f"TOTAL tests={total_tests}")
    summary_lines.append(f"RESULT={'PASS' if all_ok else 'FAIL'}")

    return {
        "passed": all_ok,
        "total_tests": total_tests,
        "lint_exit_code": lint_proc.returncode,
        "tests": test_results,
        "summary_text": "\n".join(summary_lines) + "\n\n" + report,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run unit tests and skill_lint across skill folders.")
    ap.add_argument("folders", nargs="+", help="Skill folders to audit")
    ap.add_argument("--output", metavar="FILE", help="Write full audit report to FILE")
    ap.add_argument("--json", dest="json_path", metavar="OUT", help="Write JSON summary to OUT")
    args = ap.parse_args(argv)

    result = audit_skills(args.folders)
    sys.stdout.write(result["summary_text"])
    if args.output:
        Path(args.output).write_text(result["summary_text"], encoding="utf-8")
    if args.json_path:
        payload = {k: v for k, v in result.items() if k != "summary_text"}
        Path(args.json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
