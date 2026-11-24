#!/usr/bin/env python3
"""Unit tests for playtest scripts. Run: python -m unittest tests/test_playtest.py"""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import playtest_report as pr  # noqa: E402

SAMPLE = ROOT / "assets" / "sample_observations.csv"
TEMPLATE = ROOT / "assets" / "observation_template.csv"
HEADER = "session,tester,build,second,event,location,note,assisted"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = pr.main(argv)
    return code, out.getvalue(), err.getvalue()


def temp_csv(content):
    d = tempfile.TemporaryDirectory()
    path = Path(d.name) / "g.csv"
    path.write_text(content, encoding="utf-8")
    return d, path


class SampleFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = {b["build"]: b for b in pr.summarize(pr.read_observations(SAMPLE))}

    def test_two_builds_present(self):
        self.assertEqual(sorted(self.summary), ["0.2.0", "0.3.0"])

    def test_under_five_testers_warning(self):
        self.assertEqual(self.summary["0.2.0"]["tester_count"], 4)
        self.assertTrue(any("4 tester(s)" in w and "at least 5 testers" in w for w in self.summary["0.2.0"]["warnings"]))
        self.assertEqual(self.summary["0.3.0"]["tester_count"], 5)
        self.assertFalse(any("at least 5 testers" in w for w in self.summary["0.3.0"]["warnings"]))

    def test_issues_sorted_and_compared(self):
        s = self.summary["0.2.0"]["issues"]
        self.assertEqual(
            [(x["location"], x["event"], x["count"], x["tester_count"]) for x in s],
            [("Warehouse", "stuck", 5, 4), ("2nd Bridge", "died", 3, 2), ("Warehouse", "confused", 1, 1)],
        )
        self.assertEqual(s[0]["testers"], ["T01", "T02", "T03", "T04"])
        self.assertEqual(s[0]["tester_ratio"], 1.0)
        self.assertEqual(s[0]["first_second"], 35)
        self.assertEqual(
            s[0]["notes"],
            [
                "Did not notice the door could be opened",
                "Told player to go to the door",
                "Wandered around the door for three minutes",
                "Thought the door was locked",
            ],
        )
        self.assertEqual(self.summary["0.3.0"]["issues"][0]["tester_ratio"], 1.0)
        prev = {(x["location"], x["event"]): x.get("previous") for x in self.summary["0.3.0"]["issues"]}
        self.assertEqual(prev[("2nd Bridge", "died")]["tester_count"], 2)
        self.assertEqual(prev[("Warehouse", "stuck")]["tester_count"], 4)
        self.assertNotIn("previous", self.summary["0.2.0"]["issues"][0])
        top = self.summary["0.3.0"]["issues"][0]
        self.assertEqual((top["location"], top["event"], top["tester_count"], top["count"]), ("2nd Bridge", "died", 5, 5))

    def test_positive_reactions(self):
        pos = {x["location"]: x for x in self.summary["0.3.0"]["positive"]}
        self.assertEqual(pos["Warehouse"]["count"], 4)
        self.assertEqual(pos["Tower"]["tester_count"], 2)

    def test_assistance_violation(self):
        b = self.summary["0.2.0"]
        self.assertEqual(len(b["assistance_violations"]), 1)
        self.assertEqual(b["assistance_violations"][0]["second"], 70)
        self.assertEqual(b["assisted_sessions"], ["0.2-T01"])
        self.assertTrue(any("guided the player" in w for w in b["warnings"]))
        self.assertEqual(self.summary["0.3.0"]["assistance_violations"], [])

    def test_quits_and_median_duration(self):
        b = self.summary["0.2.0"]
        self.assertEqual([x["second"] for x in b["quits"]], [420, 540])
        self.assertEqual(b["session_durations"], {"0.2-T01": 420, "0.2-T02": 600, "0.2-T03": 480, "0.2-T04": 540})
        self.assertEqual(b["median_duration_sec"], 510)
        self.assertEqual(self.summary["0.3.0"]["median_duration_sec"], 650)

    def test_report_markdown_formatting(self):
        text = pr.format_report(list(self.summary.values()))
        self.assertIn("2 build(s), 28 observation(s).", text)
        self.assertIn("| Warehouse | Stuck | 5 | T01, T02, T03, T04 | 4/4 (100%) | 0:35 |", text)
        self.assertIn("median session duration: 8:30", text)
        self.assertIn("1. `2nd Bridge`: 'died' in 5 tester(s) (5 time(s); previous build 2/4). Redesign this area.", text)
        self.assertIn("| 0.2.0: 4/4 |", text)
        self.assertIn("## Next Steps (build 0.3.0)", text)
        self.assertNotIn("`Warehouse`: 4 tester(s)", text.split("## Next Steps")[1])
        self.assertEqual(sum(1 for line in text.splitlines() if line[:2] in ("1.", "2.", "3.")), 2)


class CsvParsingTests(unittest.TestCase):
    def test_semicolon_and_utf8_bom(self):
        d, path = temp_csv("\ufeff" + HEADER.replace(",", ";") + "\nS1;T1;0.1;10;stuck;A;note;x\n")
        with d:
            recs = pr.read_observations(path)
        self.assertEqual(len(recs), 1)
        self.assertEqual((recs[0]["event"], recs[0]["tester"], recs[0]["second"]), ("stuck", "T1", 10))
        self.assertEqual(recs[0]["assisted"], "x")
        self.assertEqual(pr.summarize(recs)[0]["assistance_violations"], [])

    def test_blank_rows_skipped(self):
        d, path = temp_csv(HEADER + "\n\n   \nS1,T1,0.1,10,positive,A,,\n")
        with d:
            self.assertEqual(len(pr.read_observations(path)), 1)

    def test_invalid_events_listed(self):
        d, path = temp_csv(HEADER + "\nS1,T1,0.1,10,jumped,A,,\nS1,T1,0.1,20,died,A,,\nS1,T1,0.1,abc,died,A,\n")
        with d:
            code, out, err = run_cli([str(path)])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("line 2: unknown event 'jumped'", err)
        self.assertIn("line 4: second must be an integer", err)
        self.assertNotIn("line 3", err)

    def test_missing_columns(self):
        d, path = temp_csv("session,tester,build,second,event\n")
        with d:
            code, _, err = run_cli([str(path)])
        self.assertEqual(code, 2)
        self.assertIn("Missing column(s): location", err)

    def test_empty_csv(self):
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "b.csv"
            empty.write_text(HEADER + "\n", encoding="utf-8")
            code, out, _ = run_cli([str(empty)])
            self.assertEqual(code, 0)
            self.assertIn("No observations found", out)
            self.assertEqual(run_cli([str(Path(d) / "missing.csv")])[0], 2)

    def test_build_filter(self):
        b = pr.summarize([r for r in pr.read_observations(SAMPLE) if r["build"] == "0.3.0"])
        self.assertEqual(len(b), 1)
        self.assertNotIn("previous", b[0]["issues"][0])

    def test_natural_build_sorting(self):
        tags = ["0.10.0", "0.9.0", "0.2.0", "alpha", "0.2.1"]
        self.assertEqual(sorted(tags, key=pr._natural_sort_key), ["0.2.0", "0.2.1", "0.9.0", "0.10.0", "alpha"])

    def test_template_file_reads_cleanly(self):
        self.assertEqual(pr.read_observations(TEMPLATE), [])
        code, out, _ = run_cli(["--template"])
        self.assertEqual((code, out.strip()), (0, HEADER))


if __name__ == "__main__":
    unittest.main()
