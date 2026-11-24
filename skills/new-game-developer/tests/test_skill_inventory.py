#!/usr/bin/env python3
"""Unit tests for new-game-developer scripts. Run: python -m unittest tests/test_skill_inventory.py"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import skill_inventory as si  # noqa: E402

SAMPLE_PATH = ROOT / "assets" / "sample_inventory.json"
SAMPLE = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = si.main(argv)
    return code, out.getvalue(), err.getvalue()


def make_inv(*rows):
    return {"person": "Tester", "skills": [{"domain": d, "level": l} for d, l in rows]}


def foundations_map(result):
    return {f["key"]: (f["level"], f["status"]) for f in result["foundations"]}


class DomainTableTests(unittest.TestCase):
    def test_every_foundation_reachable_from_at_least_one_domain(self):
        for f in si.FOUNDATIONS:
            self.assertTrue(any(f in d[1] for d in si.DOMAINS.values()), f)
            self.assertIn(f, si.RECOMMENDATIONS)
            self.assertTrue(si.RECOMMENDATIONS[f])

    def test_every_domain_has_four_fields(self):
        self.assertEqual(len(si.DOMAINS), 8)
        for key, (name, gained, in_games, rationale) in si.DOMAINS.items():
            self.assertTrue(name and in_games and rationale, key)
            self.assertTrue(gained and set(gained) <= set(si.FOUNDATIONS), key)

    def test_template(self):
        code, out, _ = run_cli(["template"])
        self.assertEqual(code, 0)
        tpl = json.loads(out)
        self.assertEqual(tpl["_help"]["domain"][:len(si.DOMAINS)], list(si.DOMAINS))
        self.assertEqual(tpl["_help"]["level"], ["beginner", "comfortable", "advanced"])


class EvaluationTests(unittest.TestCase):
    def test_sample_inventory(self):
        s = si.evaluate(SAMPLE)
        self.assertEqual(s["person"], "Alex (sample data)")
        self.assertEqual(
            foundations_map(s),
            {"composition": (2, "comfortable"), "complexity": (1, "beginner"), "practical": (2, "comfortable")},
        )
        self.assertEqual(
            [f["sources"] for f in s["foundations"]],
            [["Digital Illustration"], ["Godot"], ["Digital Illustration", "Godot"]],
        )
        self.assertEqual(s["next_step"]["key"], "complexity")
        self.assertFalse(s["single_domain"])

    def test_highest_level_wins_when_multiple_skills_feed_same_foundation(self):
        s = si.evaluate(make_inv(("literature", "beginner"), ("game_engine", "advanced")))
        self.assertEqual(foundations_map(s)["complexity"], (3, "advanced"))
        self.assertEqual(
            [f["sources"] for f in s["foundations"]][1],
            ["Reading / Writing Complex Texts", "Game Engine (Godot, Unity, Roblox)"],
        )

    def test_case_insensitive_and_aliases_accepted(self):
        s = si.evaluate({
            "skills": [
                {"domain": "MUSIC", "level": "Starting"},
                {"domain": "Film", "level": "COMFORTABLE"},
                {"domain": "Visual art", "level": "beginner"},
                {"domain": "Pico-8", "level": "Advanced"},
                {"domain": "Blender", "level": "comfortable"},
                {"domain": "game engine", "level": "comfortable"},
            ]
        })
        self.assertEqual(foundations_map(s)["composition"], (2, "comfortable"))
        self.assertEqual(foundations_map(s)["practical"], (3, "advanced"))
        self.assertEqual(
            [b["domain"] for b in s["skills"]],
            ["music", "film", "visual_art", "small_programs", "3d", "game_engine"],
        )
        self.assertFalse(s["single_domain"])

    def test_all_comfortable_has_no_next_step_gap(self):
        s = si.evaluate(make_inv(("music", "comfortable")))
        self.assertIsNone(s["next_step"])
        self.assertTrue(s["single_domain"])

    def test_tie_breaks_in_canonical_foundation_order(self):
        s = si.evaluate(make_inv(("small_programs", "comfortable")))
        self.assertEqual([f["key"] for f in s["foundations"] if f["level"] == 0], ["composition", "complexity"])
        self.assertEqual(s["next_step"]["key"], "composition")

    def test_extra_foundations(self):
        v = make_inv(("literature", "advanced"))
        v["skills"][0]["extra_foundations"] = ["Composition"]
        s = si.evaluate(v)
        self.assertEqual(foundations_map(s)["composition"], (3, "advanced"))
        self.assertEqual(s["skills"][0]["foundations"], ["composition", "complexity"])

    def test_missing_name_defaults_to_domain_name(self):
        s = si.evaluate(make_inv(("music", "comfortable")))
        self.assertEqual(s["skills"][0]["name"], "Music / Audio")


class ValidationTests(unittest.TestCase):
    def test_all_errors_reported(self):
        v = make_inv(("music", "comfortable"))
        v["skills"] += [
            {"domain": "yoga", "level": "comfortable"},
            {"domain": "film", "level": "master"},
            {"domain": "film", "level": "comfortable", "extra_foundations": "composition"},
            "x",
        ]
        with self.assertRaises(ValueError) as ctx:
            si.evaluate(v)
        msg = str(ctx.exception)
        self.assertIn("skills[2]: unknown domain 'yoga'", msg)
        self.assertIn("skills[3]: invalid level 'master'", msg)
        self.assertIn("skills[4]: extra_foundations must be a list", msg)
        self.assertIn("skills[5]: must be an object", msg)
        self.assertNotIn("skills[1]", msg)

    def test_empty_or_invalid_root(self):
        for bad in ({}, {"skills": []}, [], {"skills": "music"}):
            with self.assertRaises(ValueError):
                si.evaluate(bad)


class CliTests(unittest.TestCase):
    def test_report(self):
        code, out, _ = run_cli(["evaluate", str(SAMPLE_PATH)])
        self.assertEqual(code, 0)
        self.assertIn("# Skill Inventory: Alex (sample data)", out)
        self.assertIn("| Digital Illustration | Visual Art (drawing, digital painting) | comfortable | balanced composition, practical developer skill |", out)
        self.assertIn("| Complexity Tolerance | beginner | Godot |", out)
        self.assertIn("Weakest foundation: **Complexity Tolerance** (beginner). Recommended exercise:", out)
        self.assertIn("complex tool simpler than a full engine", out)
        self.assertNotIn("single domain", out)
        self.assertIn("## Mapping Rationale", out)

    def test_single_domain_note(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "e.json"
            path.write_text(json.dumps(make_inv(("music", "comfortable"))), encoding="utf-8")
            code, out, _ = run_cli(["evaluate", str(path)])
            self.assertEqual(code, 0)
            self.assertIn("single domain", out)
            self.assertIn("at least comfortable across all three foundations", out)

    def test_output_files(self):
        with tempfile.TemporaryDirectory() as d:
            md, js = Path(d) / "r.md", Path(d) / "s.json"
            code, out, _ = run_cli(["evaluate", str(SAMPLE_PATH), "--output", str(md), "--json", str(js)])
            self.assertEqual((code, out), (0, ""))
            self.assertIn("# Skill Inventory", md.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(js.read_text(encoding="utf-8"))["next_step"]["key"], "complexity")

    def test_error_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "b.json"
            bad.write_text("{ bad", encoding="utf-8")
            code, out, err = run_cli(["evaluate", str(bad)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("could not read file", err)
            unk = Path(d) / "e.json"
            unk.write_text(json.dumps(make_inv(("yoga", "comfortable"))), encoding="utf-8")
            code, out, err = run_cli(["evaluate", str(unk)])
            self.assertEqual((code, out), (2, ""))
            self.assertIn("unknown domain 'yoga'", err)
            self.assertEqual(run_cli(["evaluate", str(Path(d) / "missing.json")])[0], 2)


if __name__ == "__main__":
    unittest.main()
