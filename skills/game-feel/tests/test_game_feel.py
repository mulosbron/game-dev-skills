#!/usr/bin/env python3
"""Unit tests for game-feel scripts. Run: python -m unittest tests/test_game_feel.py"""

import contextlib
import io
import json
import math
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import feel_sim  # noqa: E402
import game_feel_audit  # noqa: E402
import jump_physics  # noqa: E402

SAMPLE_SURVEY = Path(__file__).resolve().parent.parent / "assets" / "sample_audit.json"


class LedgeScenarioTests(unittest.TestCase):
    def test_late_jump_window_exact_c_frames(self):
        for c in range(0, 10):
            rows = feel_sim.sweep_ledge(c, 4)
            for r in rows:
                self.assertEqual(r["jumped"], r["offset"] <= c, f"coyote={c} delay={r['offset']}")

    def test_falls_outside_coyote_window(self):
        rows = {r["offset"]: r["jumped"] for r in feel_sim.sweep_ledge(6, 6)}
        self.assertTrue(rows[6])
        self.assertFalse(rows[7])

    def test_coyote_disabled_only_grounded_jumps(self):
        rows = {r["offset"]: r["jumped"] for r in feel_sim.sweep_ledge(0, 6)}
        self.assertEqual(rows, {0: True, 1: False, 2: False, 3: False})


class LandingScenarioTests(unittest.TestCase):
    def test_early_jump_window_exact_b_frames(self):
        for b in range(0, 10):
            for r in feel_sim.sweep_landing(4, b):
                self.assertEqual(r["jumped"], r["offset"] <= b, f"buffer={b} early={r['offset']}")
                if r["jumped"]:
                    self.assertEqual(r["jump_frame"], feel_sim.LANDING_FRAME)

    def test_too_early_jump_expires_cleanly(self):
        ground = [False] * 20 + [True] * 10
        self.assertEqual(feel_sim.simulate(ground, {16}, 6, 2), [])

    def test_buffer_disabled_only_landing_frame(self):
        rows = {r["offset"]: r["jumped"] for r in feel_sim.sweep_landing(6, 0)}
        self.assertTrue(rows[0])
        self.assertFalse(rows[1])


class SimulationReportTests(unittest.TestCase):
    def test_configured_windows_match_effective_windows(self):
        for c in range(0, 9):
            for b in range(0, 9):
                s = feel_sim.run_sim(c, b, 60)
                self.assertTrue(s["consistent"], f"coyote={c} buffer={b}")
                self.assertEqual((s["coyote_window_frames"], s["buffer_window_frames"]), (c, b))

    def test_millisecond_conversion(self):
        s = feel_sim.run_sim(6, 6, 30)
        self.assertAlmostEqual(s["frame_sec"], 1 / 30)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = feel_sim.main(["--coyote-frames", "6", "--fps", "30"])
        self.assertEqual(code, 0)
        self.assertIn("200 ms", out.getvalue())

    def test_invalid_inputs(self):
        for arg in (["--coyote-frames", "-1"], ["--fps", "0"]):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(feel_sim.main(arg), 2)


class JumpPhysicsTests(unittest.TestCase):
    def test_closed_form_equations(self):
        s = jump_physics.calculate(96, 0.28)
        self.assertAlmostEqual(s["initial_velocity"], 2 * 96 / 0.28)
        self.assertAlmostEqual(s["gravity_up"], 2 * 96 / 0.28 ** 2)
        self.assertAlmostEqual(s["initial_velocity"] ** 2 / (2 * s["gravity_up"]), 96)
        self.assertAlmostEqual(s["fall_time_sec"], s["time_to_apex_sec"])
        self.assertAlmostEqual(s["total_air_time_sec"], 0.56)

    def test_fall_multiplier_shortens_descent(self):
        sym = jump_physics.calculate(96, 0.28)
        heavy = jump_physics.calculate(96, 0.28, fall_multiplier=1.6)
        self.assertAlmostEqual(heavy["fall_time_sec"], sym["fall_time_sec"] / math.sqrt(1.6))
        self.assertLess(heavy["total_air_time_sec"], sym["total_air_time_sec"])

    def test_euler_verification_close_to_target(self):
        s = jump_physics.calculate(96, 0.28, 1.6, 60, 32)
        self.assertAlmostEqual(s["height_in_characters"], 3.0)
        self.assertLess(s["euler_height"], 96)
        self.assertLess(abs(s["euler_error_pct"]), 10)
        fine = jump_physics.calculate(96, 0.28, 1.6, 3600)
        self.assertLess(abs(fine["euler_error_pct"]), 1)
        self.assertGreater(fine["euler_height"], s["euler_height"])

    def test_invalid_inputs(self):
        for kw in (
            {"height": 0, "time_to_apex": 0.3},
            {"height": 10, "time_to_apex": 0},
            {"height": 10, "time_to_apex": 0.3, "fall_multiplier": 0},
            {"height": 10, "time_to_apex": 0.3, "fps": 0},
            {"height": 10, "time_to_apex": 0.3, "character_height": -1},
        ):
            with self.assertRaises(ValueError):
                jump_physics.calculate(**kw)


class AuditScoringTests(unittest.TestCase):
    def test_sample_file_scores_correctly(self):
        survey = json.loads(SAMPLE_SURVEY.read_text(encoding="utf-8"))
        result = game_feel_audit.score_survey(survey)
        scores = {p["id"]: p["score"] for p in result["pillars"]}
        # input: no(0) + no(0) + partial(1) + na + partial(1) = 2 / 8
        self.assertEqual(scores["input"], 25.0)
        # playtest: 0 + 2 + 1 + 2 + 1 = 6 / 10
        self.assertEqual(scores["playtest"], 60.0)
        # micro_animation: 2 / 10
        self.assertEqual(scores["micro_animation"], 20.0)
        # movement_momentum: 2 + 1 + 2 = 5 / 6
        self.assertEqual(scores["movement_momentum"], 83.3)
        # atmosphere: 1 + 0 + 2 + 2 + 1 = 6 / 10
        self.assertEqual(scores["atmosphere"], 60.0)
        expected = sum(scores.values()) / 5
        self.assertAlmostEqual(result["total"], round(expected, 1), places=1)

    def test_all_yes_scores_100(self):
        survey = game_feel_audit.template()
        for p in survey["answers"].values():
            for k in p:
                p[k] = "yes"
        result = game_feel_audit.score_survey(survey)
        self.assertEqual(result["total"], 100.0)
        self.assertEqual(game_feel_audit.action_items(result), [])

    def test_na_excluded_from_scoring(self):
        survey = game_feel_audit.template()
        survey["answers"]["movement_momentum"] = {
            k: "na" for k in survey["answers"]["movement_momentum"]
        }
        for name, p in survey["answers"].items():
            if name != "movement_momentum":
                for k in p:
                    p[k] = "partial"
        result = game_feel_audit.score_survey(survey)
        scores = {p["id"]: p["score"] for p in result["pillars"]}
        self.assertIsNone(scores["movement_momentum"])
        self.assertEqual(result["total"], 50.0)

    def test_missing_answers_raise_error(self):
        survey = game_feel_audit.template()
        del survey["answers"]["atmosphere"]["parallax"]
        del survey["answers"]["input"]
        with self.assertRaises(ValueError) as ctx:
            game_feel_audit.score_survey(survey)
        msg = str(ctx.exception)
        self.assertIn("answers.atmosphere.parallax", msg)
        self.assertIn("answers.input", msg)

    def test_invalid_values_raise_error(self):
        survey = game_feel_audit.template()
        survey["answers"]["input"]["coyote_time"] = "maybe"
        survey["answers"]["input"]["unknown_key"] = "yes"
        with self.assertRaises(ValueError) as ctx:
            game_feel_audit.score_survey(survey)
        self.assertIn("maybe", str(ctx.exception))
        self.assertIn("unknown_key", str(ctx.exception))

    def test_case_and_whitespace_normalized(self):
        status, _ = game_feel_audit.parse_answer("Partial", "input", "coyote_time")
        self.assertEqual(status, "partial")
        status, _ = game_feel_audit.parse_answer({"status": " N/A "}, "input", "coyote_time")
        self.assertEqual(status, "na")
        status, _ = game_feel_audit.parse_answer("NO", "input", "coyote_time")
        self.assertEqual(status, "no")

    def test_action_items_ordering(self):
        survey = json.loads(SAMPLE_SURVEY.read_text(encoding="utf-8"))
        result = game_feel_audit.score_survey(survey)
        items = game_feel_audit.action_items(result)
        self.assertEqual(items[0]["pillar_id"], "micro_animation")
        statuses = [x["status"] for x in items if x["pillar_id"] == "micro_animation"]
        self.assertEqual(statuses, ["no"] * 4)
        self.assertTrue(all(x["status"] in ("no", "partial") for x in items))
        self.assertEqual(len(items), 15)

    def test_template_outputs_valid_json(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(game_feel_audit.main(["--template"]), 0)
        survey = json.loads(out.getvalue())
        self.assertEqual(set(survey["answers"]), {p["id"] for p in game_feel_audit.PILLARS})
        self.assertEqual(len(game_feel_audit.ALL_ITEMS), 23)

    def test_below_threshold_exits_one(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(game_feel_audit.main([str(SAMPLE_SURVEY), "--threshold", "70"]), 1)
            self.assertEqual(game_feel_audit.main([str(SAMPLE_SURVEY), "--threshold", "10"]), 0)
            self.assertEqual(game_feel_audit.main([str(SCRIPTS_DIR / "game_feel_audit.py")]), 2)

    def test_report_includes_english_status_labels(self):
        result = game_feel_audit.score_survey(json.loads(SAMPLE_SURVEY.read_text(encoding="utf-8")))
        text = game_feel_audit.format_report(result)
        self.assertIn("| no |", text)
        self.assertIn("| partial |", text)
        self.assertIn("| yes |", text)


if __name__ == "__main__":
    unittest.main()
