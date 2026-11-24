#!/usr/bin/env python3
"""Unit tests for fantasy-first-design scripts. Run: python -m unittest tests/test_fantasy_brief.py"""

import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fantasy_brief  # noqa: E402

SAMPLE = ROOT / "assets" / "sample_brief.json"


def valid_brief():
    return {
        "game": "Test",
        "fantasy": "Be a vampire bank robber",
        "craving": "Outsmarting a high-security vault and getting away with it",
        "fantasy_scale": "broad",
        "target_audience": "Tactical heist players",
        "mechanics": ["turn-based stealth"],
        "inspirations": [
            {
                "game": "Armored Core 6",
                "borrowed": "Single-currency economy",
                "category": "currency_system",
                "type": "solution",
                "my_context": "Single currency is 'blood'; every upgrade spends blood directly",
            },
            {
                "game": "PVKK",
                "borrowed": "In-world tactile UI",
                "category": "diegetic_ui",
                "type": "solution",
                "my_context": "Safe-cracking rig uses physical dials and levers on the vault door",
            },
        ],
    }


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fantasy_brief.main(argv)
    return code, out.getvalue(), err.getvalue()


class ValidBriefTests(unittest.TestCase):
    def test_clean_brief_is_valid(self):
        s = fantasy_brief.evaluate(valid_brief())
        self.assertEqual(s["verdict"], "valid")
        self.assertEqual((s["clones"], s["warnings"]), ([], []))
        self.assertEqual(s["covered"], ["currency_system", "diegetic_ui"])
        self.assertEqual(len(s["uncovered"]), len(fantasy_brief.CATEGORIES) - 2)
        self.assertEqual(s["steps"][-1], "Rebuild the solutions in your own context")

    def test_valid_exit_code_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "b.json"
            path.write_text(json.dumps(valid_brief()), encoding="utf-8")
            code, out, _ = run_cli([str(path)])
            self.assertEqual(code, 0)
            self.assertIn("**Verdict: VALID**", out)
            self.assertIn("Be a vampire bank robber", out)
            self.assertIn("| Armored Core 6 | Single-currency economy | Currency & economy system", out)
            out_md = Path(d) / "b.md"
            code, out, _ = run_cli([str(path), "--output", str(out_md), "--json", str(Path(d) / "s.json")])
            self.assertEqual(code, 0)
            self.assertEqual(out, "")
            self.assertIn("# Design Brief: Test", out_md.read_text(encoding="utf-8"))
            self.assertEqual(json.loads((Path(d) / "s.json").read_text(encoding="utf-8"))["verdict"], "valid")


class CloneRiskTests(unittest.TestCase):
    def test_identity_triggers_clone_risk(self):
        b = valid_brief()
        b["inspirations"].append({
            "game": "Armored Core 6",
            "borrowed": "Mecha design",
            "type": "identity",
            "my_context": "",
        })
        s = fantasy_brief.evaluate(b)
        self.assertEqual(s["verdict"], "clone_risk")
        self.assertEqual(len(s["clones"]), 1)
        self.assertIn("Armored Core 6", s["clones"][0])

    def test_identity_exits_one(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "b.json"
            b = valid_brief()
            b["inspirations"] = [{"game": "X", "borrowed": "Characters", "type": "identity"}]
            path.write_text(json.dumps(b), encoding="utf-8")
            code, out, _ = run_cli([str(path)])
            self.assertEqual(code, 1)
            self.assertIn("**Verdict: CLONE RISK**", out)

    def test_sample_file_catches_clone_risk(self):
        s = fantasy_brief.evaluate(json.loads(SAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(s["verdict"], "clone_risk")
        self.assertEqual(len(s["clones"]), 1)
        self.assertIn("Mecha design", s["clones"][0])
        self.assertEqual(s["warnings"], [])


class WarningTests(unittest.TestCase):
    def codes(self, b):
        return [u["code"] for u in fantasy_brief.evaluate(b)["warnings"]]

    def test_short_context_warns(self):
        b = valid_brief()
        b["inspirations"][0]["my_context"] = "same thing"
        self.assertEqual(self.codes(b), ["missing_context"])

    def test_type_mismatch(self):
        b = valid_brief()
        b["inspirations"][0]["borrowed"] = "Main character art style"
        self.assertEqual(self.codes(b), ["type_mismatch"])
        # "In-world tactile UI" is a legitimate solution and must not trigger false positive.
        b = valid_brief()
        b["inspirations"][0]["borrowed"] = "In-world tactile UI"
        self.assertEqual(self.codes(b), [])

    def test_mechanics_first_fantasy(self):
        b = valid_brief()
        b["fantasy"] = "Cute bunny platformer"
        codes = self.codes(b)
        self.assertIn("mechanics_first", codes)
        msg = fantasy_brief.evaluate(b)["warnings"][0]["message"]
        self.assertIn("platformer", msg)
        self.assertNotIn("'platform',", msg)

    def test_clean_fantasy_has_no_warning(self):
        self.assertEqual(self.codes(valid_brief()), [])

    def test_no_mechanics_and_no_inspirations(self):
        b = valid_brief()
        b["mechanics"] = []
        b["inspirations"] = []
        self.assertEqual(sorted(self.codes(b)), ["no_inspirations", "no_mechanics"])

    def test_word_boundary_matching(self):
        self.assertTrue(fantasy_brief._matches("Take the game's IP", "ip"))
        self.assertTrue(fantasy_brief._matches("Same IP", "IP"))
        self.assertFalse(fantasy_brief._matches("skip the intro", "ip"))
        self.assertFalse(fantasy_brief._matches("start a party", "art"))
        self.assertFalse(fantasy_brief._matches("A cute bunny", "2d"))
        self.assertTrue(fantasy_brief._matches("A 2D world", "2d"))


class InputErrorTests(unittest.TestCase):
    def test_missing_fields_listed(self):
        b = valid_brief()
        b["fantasy"] = ""
        del b["craving"]
        b["fantasy_scale"] = "massive"
        b["inspirations"][0]["type"] = "maybe"
        b["inspirations"][1]["category"] = "unknown"
        with self.assertRaises(ValueError) as ctx:
            fantasy_brief.evaluate(b)
        msg = str(ctx.exception)
        for expected in ("fantasy:", "craving:", "fantasy_scale:", "inspirations[0].type:", "inspirations[1].category:"):
            self.assertIn(expected, msg)

    def test_input_error_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "b.json"
            path.write_text(json.dumps({"game": "X"}), encoding="utf-8")
            code, out, err = run_cli([str(path)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("craving:", err)
            path.write_text("{bad json", encoding="utf-8")
            self.assertEqual(run_cli([str(path)])[0], 2)
            self.assertEqual(run_cli([str(ROOT / "SKILL.md")])[0], 2)

    def test_filled_template_is_valid(self):
        code, out, _ = run_cli(["--template"])
        self.assertEqual(code, 0)
        b = json.loads(out)
        self.assertIn("_help", b)
        self.assertEqual(len(b["inspirations"]), 1)
        b.update({"fantasy": "Be a lighthouse keeper", "craving": "Guiding ships safely through storms on a lonely island"})
        b["inspirations"] = []
        s = fantasy_brief.evaluate(b)
        self.assertEqual(s["verdict"], "warning")
        self.assertEqual([u["code"] for u in s["warnings"]], ["no_mechanics", "no_inspirations"])

    def test_input_not_mutated(self):
        b = valid_brief()
        snapshot = copy.deepcopy(b)
        fantasy_brief.evaluate(b)
        self.assertEqual(b, snapshot)


if __name__ == "__main__":
    unittest.main()
