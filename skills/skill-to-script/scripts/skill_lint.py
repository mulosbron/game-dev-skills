#!/usr/bin/env python3
"""Skill linter: checks how much of an agent skill is vague prose vs. deterministic scripts.

Rules:
  ERROR       Structural flaw: malformed frontmatter, name mismatch, body >= 500 lines.
  WARNING     Script omitted from SKILL.md, missing referenced file, script lacking tests,
              or vague hedging words ("if needed", "as appropriate").
  SUGGESTION  Numbered workflow step containing an action verb without calling a script.

Exit codes: 0 no errors, 1 at least one ERROR, 2 unreadable folder.

Usage:
  python skill_lint.py SKILL_DIR [SKILL_DIR ...]
  python skill_lint.py SKILL_DIR --json result.json --output report.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

ALLOWED_KEYS = ("name", "description", "license", "allowed-tools", "metadata", "compatibility")
BODY_LIMIT = 500
DESC_LIMIT = 1024
NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")
SCRIPT_EXTS = (".py", ".sh", ".js")

# Hedging phrases that invite inconsistent model interpretation.
VAGUE_TERMS = (
    "if needed",
    "as needed",
    "as appropriate",
    "appropriately",
    "if possible",
    "generally",
    "optional",
    "optionally",
    "as you see fit",
    "roughly",
)
# Deterministic action verbs in numbered steps that may be script candidates.
ACTION_VERBS = (
    "run",
    "print",
    "dump",
    "sort",
    "convert",
    "move",
    "rename",
    "copy",
    "check",
    "verify",
    "validate",
    "calculate",
    "compute",
    "collect",
    "compare",
    "create",
    "replace",
)
ALREADY_SCRIPT = re.compile(r"scripts/[\w.-]+\.(?:py|sh|js)|python3?\s")


def _error(msg):
    return {"level": "ERROR", "message": msg}


def _warning(msg):
    return {"level": "WARNING", "message": msg}


def _suggestion(msg):
    return {"level": "SUGGESTION", "message": msg}


def _snippet(text, start, before=25, after=35):
    return text[max(0, start - before):start + after].replace("\n", " ")


def parse_frontmatter(text):
    """Split SKILL.md into (frontmatter_dict, body). Raises ValueError if malformed."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("file does not start with '---'")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("missing closing '---' line for frontmatter")
    fm, key = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            if key is None:
                raise ValueError(f"indented line has no key: {line.strip()!r}")
            fm[key] += " " + line.strip()
            continue
        if ":" not in line:
            raise ValueError(f"not in 'key: value' format: {line.strip()!r}")
        key, val = line.split(":", 1)
        key = key.strip()
        if key in fm:
            raise ValueError(f"duplicate key: {key}")
        fm[key] = val.strip()
    for k, v in list(fm.items()):
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            fm[k] = v[1:-1]
    return fm, "\n".join(lines[end + 1:])


def _script_files(root):
    folder = root / "scripts"
    if not folder.is_dir():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix in SCRIPT_EXTS and not p.name.startswith("_")
    )


def _numbered_steps(body):
    """Return numbered steps as (step_num, body_line_no, text) tuples."""
    steps, active = [], False
    for line_no, line in enumerate(body.splitlines(), start=1):
        m = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if m:
            active = True
            steps.append((int(m.group(1)), line_no, m.group(2).strip()))
        elif active and line[:1].isspace() and line.strip():
            num, start_no, prev = steps[-1]
            steps[-1] = (num, start_no, prev + " " + line.strip())
        elif line.strip():
            active = False
    return steps


def _is_tested(root, module_stem):
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return False
    return any(module_stem in t.read_text(encoding="utf-8") for t in sorted(tests_dir.glob("*.py")))


def lint_skill(root):
    """Lint one skill folder and return a structured findings dict."""
    root = Path(root)
    skill_md = root / "SKILL.md"
    if not skill_md.is_file():
        return _result(root.name, [_error("SKILL.md not found")], [], 0, 0)
    text = skill_md.read_text(encoding="utf-8")
    try:
        fm, body = parse_frontmatter(text)
    except ValueError as e:
        return _result(root.name, [_error(f"invalid frontmatter: {e}")], [], 0, 0)

    findings, candidates = [], []
    name = fm.get("name", "")
    if not name:
        findings.append(_error("missing 'name' field"))
    elif not NAME_PATTERN.match(name):
        findings.append(_error(f"'name' must use lowercase letters, digits, and hyphens only: {name!r}"))
    elif name != root.name:
        findings.append(_error(f"'name' ({name}) does not match folder name ({root.name})"))

    desc = fm.get("description", "")
    if not desc:
        findings.append(_error("missing 'description' field"))
    else:
        if len(desc) > DESC_LIMIT:
            findings.append(_error(f"'description' is {len(desc)} chars; limit is {DESC_LIMIT}"))
        if "<" in desc or ">" in desc:
            findings.append(_error("'description' contains angle brackets (< or >)"))
    unknown_keys = [k for k in fm if k not in ALLOWED_KEYS]
    if unknown_keys:
        findings.append(_error(f"unknown frontmatter key(s): {', '.join(unknown_keys)}"))

    line_count = sum(1 for line in body.splitlines() if line.strip())
    if line_count >= BODY_LIMIT:
        findings.append(_error(f"SKILL.md body has {line_count} non-empty lines; limit is {BODY_LIMIT}"))

    lower_body = body.lower()
    for term in VAGUE_TERMS:
        for m in re.finditer(r"(?<!\w)" + re.escape(term) + r"(?!\w)", lower_body):
            line_no = body[:m.start()].count("\n") + 1
            findings.append(
                _warning(f"vague term {term!r} (body line {line_no}): ...{_snippet(lower_body, m.start())}...")
            )

    scripts = _script_files(root)
    mentioned_scripts = set(re.findall(r"scripts/([\w.-]+\.(?:py|sh|js))", text))
    for p in scripts:
        if p.name not in mentioned_scripts:
            findings.append(_warning(f"script exists but is not mentioned in SKILL.md: scripts/{p.name}"))
        if not _is_tested(root, p.stem):
            findings.append(_warning(f"no test found for scripts/{p.name} (no file in tests/ references {p.stem})"))
    for name_ in sorted(mentioned_scripts - {p.name for p in scripts}):
        findings.append(_warning(f"script mentioned in SKILL.md does not exist: scripts/{name_}"))
    for folder_name, file_name in sorted(set(re.findall(r"(references|assets)/([\w.-]+)", text))):
        if not (root / folder_name / file_name).exists():
            findings.append(_warning(f"file mentioned in SKILL.md does not exist: {folder_name}/{file_name}"))
    if (root / "references").is_dir():
        for p in sorted((root / "references").glob("*.md")):
            if p.name not in text:
                findings.append(_warning(f"reference file exists but is not mentioned in SKILL.md: references/{p.name}"))

    if not scripts:
        findings.append(
            _suggestion("no scripts/ folder found: skill is pure prose. Move repeatable deterministic steps into scripts.")
        )
    for num, line_no, step_text in _numbered_steps(body):
        if ALREADY_SCRIPT.search(step_text):
            continue
        lower_step = step_text.lower()
        if any(re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", lower_step) for v in ACTION_VERBS):
            candidates.append({"step": num, "line": line_no, "text": step_text[:160]})
            findings.append(
                _suggestion(f"step {num} (body line {line_no}) contains an action verb—script candidate: {step_text[:90]}")
            )
    return _result(root.name, findings, candidates, line_count, len(scripts))


def _result(skill, findings, candidates, line_count, script_count):
    return {
        "skill": skill,
        "valid": not any(f["level"] == "ERROR" for f in findings),
        "line_count": line_count,
        "script_count": script_count,
        "errors": sum(f["level"] == "ERROR" for f in findings),
        "warnings": sum(f["level"] == "WARNING" for f in findings),
        "suggestions": sum(f["level"] == "SUGGESTION" for f in findings),
        "candidates": candidates,
        "findings": findings,
    }


def format_report(results):
    out = [
        "# Skill Lint Report",
        "",
        f"{len(results)} skill(s) linted.",
        "",
        "| Skill | Body Lines | Scripts | ERROR | WARNING | SUGGESTION |",
        "|---|---|---|---|---|---|",
    ]
    for s in results:
        out.append(
            f"| {s['skill']} | {s['line_count']} | {s['script_count']} | "
            f"{s['errors']} | {s['warnings']} | {s['suggestions']} |"
        )
    for s in results:
        out += ["", f"## {s['skill']}", ""]
        out += [f"- {f['level']}: {f['message']}" for f in s["findings"]] or ["- No findings."]
    out += [
        "",
        "## How to Read Findings",
        "",
        "- ERROR: the skill may fail to load or trigger improperly; fix immediately.",
        "- WARNING: reduces reliability or leaves scripts undocumented/untested; resolve or document why.",
        "- SUGGESTION: if the step produces the same result on every run, convert it to a script; if it requires judgment, keep it as prose.",
        "",
    ]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint agent skills for determinism and structure.")
    ap.add_argument("folders", nargs="+", help="Skill folders (each containing SKILL.md)")
    ap.add_argument("--json", dest="json_path", metavar="OUT", help="Also write lint results to JSON file")
    ap.add_argument("--output", metavar="FILE", help="Write Markdown report to FILE instead of stdout")
    args = ap.parse_args(argv)

    try:
        results = [lint_skill(f) for f in args.folders]
    except OSError as e:
        print(f"ERROR: could not read folder: {e}", file=sys.stderr)
        return 2
    text = format_report(results)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if any(s["errors"] for s in results) else 0


if __name__ == "__main__":
    sys.exit(main())
