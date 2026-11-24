#!/usr/bin/env python3
"""Game feel audit: scores the 5-pillar survey and produces a prioritized action list.

Scoring is deterministic so identical answers always produce identical outputs.
The agent populates the survey (via conversation or codebase inspection), runs this
script, and interprets the resulting report.

Usage:
  python game_feel_audit.py --template                    # print blank survey JSON
  python game_feel_audit.py survey.json                   # Markdown report (stdout)
  python game_feel_audit.py survey.json --json result.json
  python game_feel_audit.py survey.json --threshold 70    # exit 1 if total < threshold

Valid answers: yes (2 pts), partial (1 pt), no (0 pts), na (excluded from score).
Each item may include an optional "note" string for rationale.
"""

import argparse
import json
import sys
from pathlib import Path

SCORE = {"yes": 2, "partial": 1, "no": 0}
NA = "na"
VALID_STATUSES = set(SCORE) | {NA}

PILLARS = [
    {
        "id": "input",
        "name": "Anticipate intended player input",
        "description": (
            "When a player presses a button to jump, attack, or act, that action should "
            "trigger even if timing is slightly off. That perceived responsiveness is the "
            "foundation of great game feel."
        ),
        "items": [
            {
                "id": "coyote_time",
                "question": "Can the player still jump briefly after stepping off a ledge (coyote time)?",
                "suggestion": "Allow jumping for a few frames after leaving ground. Test windows with feel_sim.py.",
            },
            {
                "id": "input_buffer",
                "question": "Are early inputs queued while busy and executed as soon as the character is ready (input buffering)?",
                "suggestion": "Buffer jump and attack presses; consume when ready. See assets/coyote_buffer.gd.",
            },
            {
                "id": "hold_duration",
                "question": "Does jump height vary based on how long the jump button is held?",
                "suggestion": "Cut upward velocity on early release for low hops vs. full-height jumps.",
            },
            {
                "id": "rapid_repeat",
                "question": "Does the game respond smoothly when players tap inputs rapidly in succession?",
                "suggestion": "Convert rapid taps into intentional follow-up actions instead of dropping inputs.",
            },
            {
                "id": "accidental_press",
                "question": "Are common accidental button presses intentionally ignored or guarded against?",
                "suggestion": "Identify accidental inputs during playtesting and guard against unintended triggers.",
            },
        ],
    },
    {
        "id": "playtest",
        "name": "Playtest continuously",
        "description": (
            "The game does not need polished art first; put it in front of someone else "
            "and watch where they struggle with things you assumed were obvious."
        ),
        "items": [
            {
                "id": "five_testers_per_build",
                "question": "Is every build tested with at least five different players?",
                "suggestion": "Recruit at least five testers per build, tune based on findings, and re-test.",
            },
            {
                "id": "live_observation",
                "question": "Do you observe players live in real time during their first playthrough?",
                "suggestion": "Players rarely verbalize everything; facial expressions and posture reveal true engagement.",
            },
            {
                "id": "no_handholding",
                "question": "Do you refrain from telling stuck players what to do during playtests?",
                "suggestion": "Do not coach testers; 99% of players will play without you there.",
            },
            {
                "id": "designer_ownership",
                "question": "Do you treat gameplay friction as a design issue rather than player error?",
                "suggestion": "If players behave differently from your expectation, fix the design, not the player.",
            },
            {
                "id": "iteration_loop",
                "question": "Do you continuously run the playtest -> fix -> new build -> playtest loop?",
                "suggestion": "Track observations across builds with playtest_report.py in the playtest skill.",
            },
        ],
    },
    {
        "id": "micro_animation",
        "name": "Use micro-animation",
        "description": (
            "The same movement code feels dramatically more alive with tuned curves and "
            "micro-animations. These small transitions give a game its premium feel."
        ),
        "items": [
            {
                "id": "locomotion_animations",
                "question": "Are there distinct animations for walking and running?",
                "suggestion": "Give each movement mode its own animation and cadence.",
            },
            {
                "id": "turn_pivot",
                "question": "Is there a brief turn/pivot animation when reversing direction?",
                "suggestion": "Play a snappy pivot frame or tilt instead of flipping instantly.",
            },
            {
                "id": "jump_squash_stretch",
                "question": "Is squash and stretch applied on jump takeoff and landing?",
                "suggestion": "Stretch vertically on launch and squash briefly on landing.",
            },
            {
                "id": "fall_animation",
                "question": "Does falling play a distinct stretch/pose animation separate from rising?",
                "suggestion": "Separate rising and falling poses instead of reusing one static air animation.",
            },
            {
                "id": "subtle_details",
                "question": "Are there subtle state-transition details (e.g., head turn on wall slide)?",
                "suggestion": "Add small secondary details at state boundaries to make transitions readable.",
            },
        ],
    },
    {
        "id": "movement_momentum",
        "name": "Design movement and momentum deliberately",
        "description": (
            "Some games feel tight and snappy; others feel loose and momentum-driven. "
            "What matters is choosing intentionally—or deliberately mixing both where the "
            "desired emotion shifts from control to freedom."
        ),
        "items": [
            {
                "id": "deliberate_feel_target",
                "question": "Was tight vs. loose movement chosen intentionally for the target emotion?",
                "suggestion": "Document whether movement aims for precise control or momentum-driven freedom.",
            },
            {
                "id": "documented_parameters",
                "question": "Are jump height, time-to-apex, and fall multiplier documented and reproducible?",
                "suggestion": "Compute exact parameters with jump_physics.py and record them in design docs.",
            },
            {
                "id": "intentional_exceptions",
                "question": "Are power-ups or sections with altered movement feel designed intentionally?",
                "suggestion": "State the emotional reason for each movement exception, or remove it.",
            },
        ],
    },
    {
        "id": "atmosphere",
        "name": "Design atmosphere and sense of place",
        "description": (
            "Do not just make the game look pretty—give it a sense of place. Answer: "
            "'Does this feel like a real place, or just colors painted on a screen?'"
        ),
        "items": [
            {
                "id": "impact_particles",
                "question": "Are there impact particles reinforcing landings, hits, and bursts?",
                "suggestion": "Spawn pooled dust, spark, or debris particles on landings, hits, and explosions.",
            },
            {
                "id": "ambient_particles",
                "question": "Are there floating ambient particles giving air a sense of volume?",
                "suggestion": "Add drifting dust motes, snow, spores, or embers to give air tangible depth.",
            },
            {
                "id": "parallax",
                "question": "Do background layers scroll with parallax depth?",
                "suggestion": "Scroll background layers at distinct depth ratios to create spatial separation.",
            },
            {
                "id": "lighting",
                "question": "Is a lighting/shadow system enhancing mood and readability?",
                "suggestion": "Use directional lighting, rim highlights, or soft shadows to ground sprites in space.",
            },
            {
                "id": "sense_of_place",
                "question": "Do you have a concrete answer to 'Does this feel like a real place?'",
                "suggestion": "Write the answer in 'note'; if you cannot, the visual language lacks spatial identity.",
            },
        ],
    },
]

ALL_ITEMS = {item["id"]: p["id"] for p in PILLARS for item in p["items"]}


def template():
    """Return an empty survey dict."""
    return {
        "game": "",
        "build": "",
        "answers": {
            p["id"]: {item["id"]: "" for item in p["items"]} for p in PILLARS
        },
    }


def parse_answer(value, pillar_id, item_id):
    """Parse one answer into (status, note); raise ValueError if invalid."""
    loc = f"answers.{pillar_id}.{item_id}"
    if isinstance(value, dict):
        status = value.get("status", "")
        note = str(value.get("note", "") or "").strip()
    elif isinstance(value, str):
        status, note = value, ""
    else:
        raise ValueError(
            f"{loc}: answer must be 'yes'/'partial'/'no'/'na' or {{'status': ..., 'note': ...}}"
        )
    status = str(status or "").strip().lower()
    if status == "n/a":
        status = NA
    if status not in VALID_STATUSES:
        raise ValueError(
            f"{loc}: invalid value '{status}'. Valid values: {', '.join(sorted(VALID_STATUSES))}"
        )
    return status, note


def score_survey(survey):
    """Score a survey dict. Raises ValueError on missing/invalid entries."""
    if not isinstance(survey, dict):
        raise ValueError("Survey must be a JSON object")
    answers = survey.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("'answers' field is missing or not an object. Run --template for a blank survey")
    unknown_pillars = set(answers) - {p["id"] for p in PILLARS}
    if unknown_pillars:
        raise ValueError(
            f"Unknown pillar(s): {', '.join(sorted(unknown_pillars))}. "
            f"Valid: {', '.join(p['id'] for p in PILLARS)}"
        )

    missing, invalid = [], []
    result = {"game": survey.get("game", ""), "build": survey.get("build", ""), "pillars": []}
    for p in PILLARS:
        provided = answers.get(p["id"])
        if not isinstance(provided, dict):
            missing.append(f"answers.{p['id']}")
            provided = {}
        missing += [f"answers.{p['id']}.{item['id']}" for item in p["items"] if item["id"] not in provided]
        unknown_items = set(provided) - {item["id"] for item in p["items"]}
        if unknown_items:
            invalid.append(f"answers.{p['id']}: unknown item(s) {', '.join(sorted(unknown_items))}")
        rows = []
        for item in p["items"]:
            if item["id"] not in provided:
                continue
            try:
                status, note = parse_answer(provided[item["id"]], p["id"], item["id"])
            except ValueError as e:
                invalid.append(str(e))
                continue
            rows.append({
                "id": item["id"],
                "question": item["question"],
                "status": status,
                "note": note,
                "score": None if status == NA else SCORE[status],
                "suggestion": item["suggestion"],
            })
        scored = [r["score"] for r in rows if r["score"] is not None]
        pct = 100.0 * sum(scored) / (2 * len(scored)) if scored else None
        result["pillars"].append({
            "id": p["id"],
            "name": p["name"],
            "description": p["description"],
            "score": round(pct, 1) if pct is not None else None,
            "items": rows,
        })
    if missing or invalid:
        lines = []
        if missing:
            lines.append("Missing answers (or set to 'na'):\n  - " + "\n  - ".join(missing))
        if invalid:
            lines.append("Invalid values:\n  - " + "\n  - ".join(invalid))
        raise ValueError("\n".join(lines))

    pillar_scores = [p["score"] for p in result["pillars"] if p["score"] is not None]
    result["total"] = round(sum(pillar_scores) / len(pillar_scores), 1) if pillar_scores else None
    return result


def action_items(result):
    """Return prioritized action items: 'no' before 'partial', weakest pillar first."""
    names = {p["id"]: p["name"] for p in result["pillars"]}
    ordered = sorted(result["pillars"], key=lambda p: (p["score"] is None, p["score"] if p["score"] is not None else 0))
    items = []
    for p in ordered:
        for item in sorted(p["items"], key=lambda m: m["score"] if m["score"] is not None else 9):
            if item["score"] is not None and item["score"] < 2:
                items.append({
                    "pillar": names[p["id"]],
                    "pillar_id": p["id"],
                    "item": item["question"],
                    "status": item["status"],
                    "note": item["note"],
                    "suggestion": item["suggestion"],
                })
    return items


def format_report(result):
    """Render a scored audit result as Markdown."""
    lines = [f"# Game Feel Audit: {result['game'] or '(untitled)'}"]
    if result.get("build"):
        lines.append(f"Build: {result['build']}")
    lines.append("")
    total = result["total"]
    lines.append(
        f"**Total Score: {total:.0f}/100**"
        if total is not None
        else "**Total Score: N/A (no scorable items)**"
    )
    lines.append("")
    lines.append("| Pillar | Score |")
    lines.append("|---|---|")
    for p in sorted(result["pillars"], key=lambda x: x["score"] if x["score"] is not None else 999):
        val = "—" if p["score"] is None else "%.0f/100" % p["score"]
        lines.append(f"| {p['name']} | {val} |")
    lines.append("")
    todo = action_items(result)
    lines.append("## Prioritized Action List")
    lines.append("")
    if todo:
        lines.append(
            "Ordered from the weakest pillar. Each row is a design task: when players behave "
            "differently from what you intended, adjust the game design."
        )
        lines.append("")
        for i, entry in enumerate(todo, 1):
            lines.append(f"{i}. **{entry['pillar']}** — {entry['item']}")
            lines.append(f"   - Status: {entry['status']}. Suggestion: {entry['suggestion']}")
            if entry["note"]:
                lines.append(f"   - Note: {entry['note']}")
    else:
        lines.append("No scored items are 'no' or 'partial'. Next step: run a playtest with at least five new players.")
    lines.append("")
    lines.append("## Item Details")
    lines.append("")
    for p in result["pillars"]:
        lines.append(f"### {p['name']}")
        lines.append("")
        val = "—" if p["score"] is None else "%.0f/100" % p["score"]
        lines.append(f"Score: {val}")
        lines.append("")
        lines.append("| Question | Status | Note |")
        lines.append("|---|---|---|")
        for m in p["items"]:
            lines.append(f"| {m['question']} | {m['status']} | {m['note']} |")
        lines.append("")
    lines.append(
        "> Scores summarize reported answers; only watching real players in a playtest reveals how the game truly feels."
    )
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="5-pillar game feel audit.")
    ap.add_argument("survey", nargs="?", help="Completed survey JSON file")
    ap.add_argument("--template", action="store_true", help="Print blank survey JSON and exit")
    ap.add_argument("--json", metavar="FILE", help="Also write scored results to JSON file")
    ap.add_argument("--threshold", type=float, default=None, help="Exit 1 if total score is below threshold")
    args = ap.parse_args(argv)

    if args.template:
        json.dump(template(), sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if not args.survey:
        ap.error("survey file is required (or pass --template)")

    try:
        survey = json.loads(Path(args.survey).read_text(encoding="utf-8"))
        result = score_survey(survey)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read survey: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"ERROR: invalid survey.\n{e}", file=sys.stderr)
        return 2

    sys.stdout.write(format_report(result))
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.threshold is not None and (result["total"] is None or result["total"] < args.threshold):
        print(f"Total score is below threshold ({args.threshold}).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
