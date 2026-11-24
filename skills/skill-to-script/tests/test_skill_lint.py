#!/usr/bin/env python3
"""Unit tests for skill_lint and audit_skills. Run: python -m unittest tests/test_skill_lint.py"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_skills as aus  # noqa: E402
import skill_lint as sl  # noqa: E402

FM = "---\nname: sample-skill\ndescription: Sample skill. Use when user requests a sample.\n---\n"
BODY = (
    "# Sample\n\n## Workflow\n\n"
    "1. **Listen.** Clarify what the user wants from their own words.\n"
    "2. **Run the report.** `scripts/report.py` writes the summary; interpret it afterward.\n\n"
    "## Notes\n\nInterpretation is your job.\n"
)


def make_skill(root, fm=FM, body=BODY, scripts=("report.py",), tests=True, refs=()):
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(fm + body, encoding="utf-8")
    if scripts:
        (root / "scripts").mkdir()
        for name in scripts:
            (root / "scripts" / name).write_text("print('x')\n", encoding="utf-8")
    if tests and scripts:
        (root / "tests").mkdir()
        (root / "tests" / "test_x.py").write_text(
            "import unittest\n"
            + "\n".join(f"# {Path(s).stem}" for s in scripts)
            + "\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
    if refs:
        (root / "references").mkdir()
        for name in refs:
            (root / "references" / name).write_text("# reference\n", encoding="utf-8")
    return root


def findings(result, level=None):
    return [f["message"] for f in result["findings"] if level is None or f["level"] == level]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = sl.main(argv)
    return code, out.getvalue(), err.getvalue()


class FrontmatterTests(unittest.TestCase):
    def test_folded_description_and_quotes(self):
        fm, body = sl.parse_frontmatter(
            '---\nname: a-b\n  c\ndescription: "Long description\n  second line"\nlicense: MIT\n---\nBody\n'
        )
        self.assertEqual(fm, {"name": "a-b c", "description": "Long description second line", "license": "MIT"})
        self.assertEqual(body, "Body")

    def test_malformed_frontmatter(self):
        cases = (
            ("name: x\n", "does not start"),
            ("---\nname: x\n", "missing closing"),
            ("---\nname: x\nname: y\n---\n", "duplicate key"),
            ("---\n  indented\n---\n", "has no key"),
            ("---\nnameless line\n---\n", "key: value"),
        )
        for text, expected in cases:
            with self.assertRaises(ValueError) as ctx:
                sl.parse_frontmatter(text)
            self.assertIn(expected, str(ctx.exception), text)


class StructuralTests(unittest.TestCase):
    def test_clean_skill(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(Path(d) / "sample-skill", refs=("extra.md",))
            (root / "SKILL.md").write_text(FM + BODY + "Details: `references/extra.md`.\n", encoding="utf-8")
            s = sl.lint_skill(root)
        self.assertTrue(s["valid"])
        self.assertEqual((s["errors"], s["warnings"], s["suggestions"]), (0, 0, 0))
        self.assertEqual((s["line_count"], s["script_count"]), (7, 1))

    def test_name_folder_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(Path(d) / "other-name")
            s = sl.lint_skill(root)
        self.assertFalse(s["valid"])
        self.assertIn("'name' (sample-skill) does not match folder name (other-name)", findings(s, "ERROR")[0])

    def test_invalid_name_characters(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(Path(d) / "Sample_Skill", fm=FM.replace("sample-skill", "Sample_Skill"))
            s = sl.lint_skill(root)
        self.assertEqual(len(findings(s, "ERROR")), 1)
        self.assertIn("lowercase letters, digits, and hyphens", findings(s, "ERROR")[0])

    def test_description_missing_long_and_brackets(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(Path(d) / "sample-skill", fm=FM.replace("description:", "summary:"))
            self.assertIn("missing 'description' field", findings(sl.lint_skill(root), "ERROR")[0])
        with tempfile.TemporaryDirectory() as d:
            fm = "---\nname: sample-skill\ndescription: " + "a" * 1025 + "\n---\n"
            s = sl.lint_skill(make_skill(Path(d) / "sample-skill", fm=fm))
            self.assertIn("'description' is 1025 chars; limit is 1024", findings(s, "ERROR")[0])
        with tempfile.TemporaryDirectory() as d:
            fm = "---\nname: sample-skill\ndescription: fill <slot>\n---\n"
            s = sl.lint_skill(make_skill(Path(d) / "sample-skill", fm=fm))
            self.assertIn("angle brackets", findings(s, "ERROR")[0])

    def test_unknown_frontmatter_key(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(
                Path(d) / "sample-skill",
                fm=FM.replace("sample.\n---", "sample.\nversion: 2\n---"),
            )
            self.assertIn("unknown frontmatter key(s): version", findings(sl.lint_skill(root), "ERROR")[0])

    def test_body_over_500_lines(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(
                Path(d) / "sample-skill",
                body=BODY + "\n".join(f"Line {i}" for i in range(495)),
            )
            s = sl.lint_skill(root)
        self.assertTrue(any("limit is 500" in m for m in findings(s, "ERROR")), s["line_count"])

    def test_missing_skill_md(self):
        with tempfile.TemporaryDirectory() as d:
            s = sl.lint_skill(Path(d) / "missing")
        self.assertEqual((s["valid"], findings(s)), (False, ["SKILL.md not found"]))


class ContentTests(unittest.TestCase):
    def test_vague_word_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(
                Path(d) / "sample-skill",
                body=BODY + "\nDelete the file if needed. Do not generalize blindly.\n",
            )
            s = sl.lint_skill(root)
        self.assertEqual(len(findings(s, "WARNING")), 1)
        self.assertIn("'if needed' (body line 12)", findings(s, "WARNING")[0])

    def test_unmentioned_and_untested_scripts(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_skill(Path(d) / "sample-skill", scripts=("report.py", "hidden.py"), tests=False)
            s = sl.lint_skill(root)
        msgs = findings(s, "WARNING")
        self.assertIn("script exists but is not mentioned in SKILL.md: scripts/hidden.py", msgs)
        self.assertTrue(any("no test found for scripts/report.py" in m for m in msgs), msgs)
        self.assertTrue(any("no test found for scripts/hidden.py" in m for m in msgs), msgs)
        self.assertEqual(len(msgs), 3)

    def test_missing_referenced_files(self):
        with tempfile.TemporaryDirectory() as d:
            body = BODY + "See: `scripts/missing.py`, `references/missing.md`, `assets/missing.json`.\n"
            s = sl.lint_skill(make_skill(Path(d) / "sample-skill", body=body, refs=("unmentioned.md",)))
        msgs = findings(s, "WARNING")
        self.assertIn("script mentioned in SKILL.md does not exist: scripts/missing.py", msgs)
        self.assertIn("file mentioned in SKILL.md does not exist: references/missing.md", msgs)
        self.assertIn("file mentioned in SKILL.md does not exist: assets/missing.json", msgs)
        self.assertIn("reference file exists but is not mentioned in SKILL.md: references/unmentioned.md", msgs)
        self.assertEqual(len(msgs), 4)

    def test_no_scripts_suggestion(self):
        with tempfile.TemporaryDirectory() as d:
            body = BODY.replace(
                "**Run the report.** `scripts/report.py` writes the summary; interpret it afterward.",
                "**Interpret.** Decide what the findings mean.",
            )
            s = sl.lint_skill(make_skill(Path(d) / "sample-skill", body=body, scripts=()))
        self.assertEqual(s["suggestions"], 1)
        self.assertIn("no scripts/ folder found", findings(s, "SUGGESTION")[0])

    def test_candidate_steps(self):
        body = (
            "## Workflow\n\n"
            "1. **Convert the file.** Turn the input CSV into JSON.\n"
            "2. **Run the report.** `scripts/report.py` counts everything.\n"
            "3. **Compute totals with python CLI.**\n"
            "4. **Interpret.** Discuss what the output means with the user.\n"
        )
        with tempfile.TemporaryDirectory() as d:
            s = sl.lint_skill(make_skill(Path(d) / "sample-skill", body=body))
        self.assertEqual(s["suggestions"], 1)
        self.assertEqual(s["candidates"], [{"step": 1, "line": 3, "text": "**Convert the file.** Turn the input CSV into JSON."}])
        self.assertIn("step 1 (body line 3) contains an action verb", findings(s, "SUGGESTION")[0])

    def test_step_continuation_lines(self):
        body = "## Workflow\n\n1. **Move the log.**\n   Extra explanation on next line.\n\nParagraph is not a step.\n"
        with tempfile.TemporaryDirectory() as d:
            s = sl.lint_skill(make_skill(Path(d) / "sample-skill", body=body))
        self.assertEqual(s["candidates"][0]["text"], "**Move the log.** Extra explanation on next line.")


class CliAndAuditTests(unittest.TestCase):
    def test_report_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            good = make_skill(Path(d) / "sample-skill")
            bad = make_skill(Path(d) / "broken", scripts=())
            md, js = Path(d) / "r.md", Path(d) / "s.json"
            code, out, _ = run_cli([str(good), str(bad), "--output", str(md), "--json", str(js)])
            self.assertEqual((code, out), (1, ""))
            text = md.read_text(encoding="utf-8")
            self.assertIn("| sample-skill | 6 | 1 | 0 | 0 | 0 |", text)
            self.assertIn("| broken | 6 | 0 | 1 | 1 | 1 |", text)
            self.assertIn("## How to Read Findings", text)
            self.assertEqual(len(json.loads(js.read_text(encoding="utf-8"))), 2)
            code, out, _ = run_cli([str(good)])
            self.assertEqual((code, out.splitlines()[0]), (0, "# Skill Lint Report"))

    def test_missing_folder(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, _ = run_cli([str(Path(d) / "missing")])
            self.assertEqual(code, 1)
            self.assertIn("ERROR: SKILL.md not found", out)

    def test_audit_skills_runs_tests_and_lint(self):
        with tempfile.TemporaryDirectory() as d:
            good = make_skill(Path(d) / "sample-skill")
            res = aus.audit_skills([str(good)])
            self.assertTrue(res["passed"])
            self.assertEqual(res["total_tests"], 1)
            self.assertEqual(res["lint_exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
