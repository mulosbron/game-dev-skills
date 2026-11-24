#!/usr/bin/env python3
"""Fantasy-first design brief: validates a game concept and audits clone risk.

Performs two deterministic checks:
  1. Validates required fields and controlled vocabularies (type, category).
  2. Applies the "borrow friction solutions, rebuild in your own context, never clone
     identity" rule and outputs a verdict:
        valid       no issues
        warning     design risk to address
        clone_risk  identity element (art, IP, character, world) is being copied

Genre detection in the fantasy line and identity keyword scanning are heuristics that
raise warnings for review rather than hard blocks.

Usage:
  python fantasy_brief.py --template                 # print blank brief JSON
  python fantasy_brief.py brief.json                 # Markdown brief (stdout)
  python fantasy_brief.py brief.json --output brief.md --json score.json

Exit codes: 0 valid, 1 warning or clone_risk, 2 input error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

TYPES = ("solution", "identity")
SCALES = ("broad", "medium", "narrow")

# Solved non-core friction areas: borrow the pattern, do not reinvent the wheel.
CATEGORIES = {
    "quest_loop": "Quest loop",
    "upgrade_structure": "Upgrade structure (skill tree or physical switches)",
    "between_run_upgrades": "Between-run upgrade loop (slotting parts, stat balancing)",
    "currency_system": "Currency & economy system (e.g., single currency)",
    "interaction_layout": "Interaction readability (purpose obvious at a glance)",
    "diegetic_ui": "In-world (diegetic), tactile UI",
    "ui_conventions": "UI conventions (tabbed menus, expected layouts)",
    "main_menu": "Main menu",
    "settings_menu": "Settings menu",
    "health_checkpoints": "Health system and generous checkpoints",
}

# Heuristic lists: genre terms in the fantasy line suggest mechanics-first thinking.
GENRE_TERMS = [
    "platformer", "platform", "roguelike", "roguelite", "metroidvania", "deckbuilder", "deck builder",
    "card game", "idle", "incremental", "clicker", "bullet heaven", "tower defense",
    "visual novel", "rpg", "mmorpg", "fps", "first-person shooter", "first person shooter",
    "top-down", "top down", "twin-stick", "survivors", "match-3", "match 3", "puzzle",
    "simulator", "side-scroller", "side scroller", "runner", "turn-based", "stealth", "2d", "3d",
]
# Identity keywords in "borrowed" text suggest copying IP/art rather than friction solutions.
# ("world" is omitted intentionally because "in-world UI" / diegetic UI is a valid solution.)
IDENTITY_WORDS = ["character", "characters", "art", "artwork", "story", "narrative", "lore", "ip", "brand", "franchise"]
WORD_BOUNDARY = {"platform", "ip", "2d", "3d", "art", "story", "rpg", "fps"}

NEXT_STEPS = [
    "Define the player fantasy",
    "Find games selling a similar fantasy",
    "Identify what friction solutions work",
    "Strip away their identity/framing",
    "Rebuild the solutions in your own context",
]


def template():
    """Return a blank brief dict."""
    return {
        "game": "",
        "fantasy": "",
        "craving": "",
        "fantasy_scale": "",
        "target_audience": "",
        "mechanics": [],
        "inspirations": [
            {"game": "", "borrowed": "", "category": "", "type": "", "my_context": ""}
        ],
        "_help": {
            "fantasy": "Who does the player want to be or feel like? One sentence.",
            "craving": "What specific craving does this fantasy satisfy for someone browsing games?",
            "fantasy_scale": f"One of: {', '.join(SCALES)}. Every fantasy has a demand ceiling.",
            "inspirations[].type": "solution: borrowable friction solution. identity: art, IP, character, world (do not copy).",
            "inspirations[].category": f"One of or blank: {', '.join(CATEGORIES)}",
            "inspirations[].my_context": "How are you rebuilding this borrowed solution in your own setting?",
        },
    }


def _text(value):
    return str(value or "").strip()


def _matches(text, term):
    """Case-insensitive match; short/ambiguous terms use word boundaries."""
    lower = _text(text).lower()
    t = term.lower()
    if t in WORD_BOUNDARY or len(t) <= 3:
        return re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", lower) is not None
    return t in lower


def _genre_terms_in(fantasy):
    """Return genre terms found in fantasy, keeping longer term when one contains another."""
    found = [t for t in GENRE_TERMS if _matches(fantasy, t)]
    return sorted(t for t in found if not any(t != u and t in u for u in found))


def evaluate(brief):
    """Validate and audit a brief dict. Raises ValueError on schema/input errors."""
    if not isinstance(brief, dict):
        raise ValueError("Brief must be a JSON object")
    errors = []
    if not _text(brief.get("fantasy")):
        errors.append("fantasy: cannot be empty (who does the player want to be?)")
    if not _text(brief.get("craving")):
        errors.append("craving: cannot be empty (what craving does this fantasy satisfy?)")
    scale = _text(brief.get("fantasy_scale")).lower()
    if scale and scale not in SCALES:
        errors.append(f"fantasy_scale: invalid '{scale}'. Valid: {', '.join(SCALES)}")

    mechanics = brief.get("mechanics") or []
    if not isinstance(mechanics, list):
        errors.append("mechanics: must be a list of strings")
        mechanics = []

    inspirations = brief.get("inspirations") or []
    if not isinstance(inspirations, list):
        errors.append("inspirations: must be a list")
        inspirations = []
    rows = []
    for i, item in enumerate(inspirations):
        loc = f"inspirations[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{loc}: must be an object")
            continue
        typ = _text(item.get("type")).lower()
        cat = _text(item.get("category")).lower()
        if not _text(item.get("game")):
            errors.append(f"{loc}.game: cannot be empty")
        if not _text(item.get("borrowed")):
            errors.append(f"{loc}.borrowed: cannot be empty (what is being borrowed?)")
        if typ not in TYPES:
            shown = typ or "empty"
            errors.append(f"{loc}.type: invalid '{shown}'. Valid: {', '.join(TYPES)}")
        if cat and cat not in CATEGORIES:
            errors.append(f"{loc}.category: invalid '{cat}'. Valid: {', '.join(CATEGORIES)}")
        rows.append({
            "game": _text(item.get("game")),
            "borrowed": _text(item.get("borrowed")),
            "type": typ,
            "category": cat,
            "my_context": _text(item.get("my_context")),
        })
    if errors:
        raise ValueError("Invalid brief:\n  - " + "\n  - ".join(errors))

    clones, warnings = [], []
    fantasy = _text(brief["fantasy"])
    genre_hits = _genre_terms_in(fantasy)
    if genre_hits:
        warnings.append({
            "code": "mechanics_first",
            "message": (
                f"Fantasy statement contains genre/mechanic term(s): {', '.join(genre_hits)}. "
                "Starting with a genre locks the game into one shape prematurely. Phrase it as "
                "'Be / Feel like ...'; mechanics follow afterward."
            ),
        })
    if not mechanics:
        warnings.append({
            "code": "no_mechanics",
            "message": (
                "No mechanics are listed yet. Identify which mechanics sell this fantasy best; "
                "the same fantasy can succeed across multiple genres."
            ),
        })
    if not rows:
        warnings.append({
            "code": "no_inspirations",
            "message": (
                "No inspirations listed. Play games selling a similar fantasy and borrow their "
                "solved friction (quest loop, economy, UI) instead of reinventing the wheel."
            ),
        })

    for i, e in enumerate(rows):
        loc = f"inspirations[{i}] ({e['game']})"
        if e["type"] == "identity":
            clones.append(
                f"{loc}: '{e['borrowed']}' is marked as an identity element. Do not copy art, IP, "
                "characters, or world—that creates a clone. Extract a design principle instead."
            )
        elif len(e["my_context"]) < 15:
            warnings.append({
                "code": "missing_context",
                "message": (
                    f"{loc}: 'my_context' is empty or too short. Unless you rebuild the solution "
                    "in your own context, you are copying rather than adapting."
                ),
            })
        matched_id = sorted({k for k in IDENTITY_WORDS if _matches(e["borrowed"], k)})
        if e["type"] == "solution" and matched_id:
            warnings.append({
                "code": "type_mismatch",
                "message": (
                    f"{loc}: type is 'solution' but description mentions identity term(s) "
                    f"({', '.join(matched_id)}): \"{e['borrowed']}\". Verify this is a friction "
                    "solution rather than game identity."
                ),
            })

    covered = sorted({e["category"] for e in rows if e["category"]})
    uncovered = [k for k in CATEGORIES if k not in covered]
    verdict = "clone_risk" if clones else ("warning" if warnings else "valid")
    return {
        "verdict": verdict,
        "game": _text(brief.get("game")) or "(untitled)",
        "fantasy": fantasy,
        "craving": _text(brief["craving"]),
        "fantasy_scale": scale or None,
        "target_audience": _text(brief.get("target_audience")),
        "mechanics": [_text(m) for m in mechanics if _text(m)],
        "inspirations": rows,
        "clones": clones,
        "warnings": warnings,
        "covered": covered,
        "uncovered": uncovered,
        "steps": NEXT_STEPS,
    }


VERDICT_LABEL = {"valid": "VALID", "warning": "WARNING", "clone_risk": "CLONE RISK"}
SCALE_NOTE = {
    "broad": "A craving shared by millions (e.g., cheating to win the World Cup).",
    "medium": "A clear, substantial audience, though not universal.",
    "narrow": "A smaller niche wants this fantasy; still viable if an audience exists, or broaden the fantasy for wider reach.",
}


def format_report(s):
    out = [
        f"# Design Brief: {s['game']}",
        "",
        f"**Verdict: {VERDICT_LABEL[s['verdict']]}**",
        "",
        "## Fantasy",
        "",
        f"**{s['fantasy']}**",
        "",
        f"Craving: {s['craving']}",
    ]
    if s["target_audience"]:
        out.append(f"Target audience: {s['target_audience']}")
    if s["fantasy_scale"]:
        out.append(f"Fantasy scale: {s['fantasy_scale']}. {SCALE_NOTE[s['fantasy_scale']]}")
    out += ["", "## Mechanics", ""]
    out += [f"- {m}" for m in s["mechanics"]] or ["(none yet)"]
    out += [
        "",
        "## Borrowed Friction Solutions",
        "",
        "These are solved, non-core elements. Never copy them verbatim; rebuild each in your own context.",
        "",
        "| Reference Game | Borrowed | Area | My Context |",
        "|---|---|---|---|",
    ]
    for e in s["inspirations"]:
        area = CATEGORIES.get(e["category"], "—")
        out.append(f"| {e['game']} | {e['borrowed']} | {area} | {e['my_context'] or '—'} |")
    if not s["inspirations"]:
        out.append("| (none) | | | |")

    out += ["", "## Clone Risk", ""]
    out += [f"- {c}" for c in s["clones"]] or ["- None. All borrowed items are marked as friction solutions."]
    out += ["", "## Warnings", ""]
    if s["warnings"]:
        out += [f"- **{u['code']}**: {u['message']}" for u in s["warnings"]]
        out.append("")
        out.append("Genre and identity keyword checks are heuristics; dismiss false positives if justified.")
    else:
        out.append("- None.")
    out += ["", "## Uncovered Friction Areas", ""]
    out += [f"- {CATEGORIES[k]} (`{k}`)" for k in s["uncovered"]] or ["- None."]
    out += ["", "## Next Steps", ""]
    out += [f"{i}. {a}" for i, a in enumerate(s["steps"], 1)]
    out += ["", "The final step is decisive: never drop solutions in raw—rebuild them in your own context."]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fantasy-first game design brief validator.")
    ap.add_argument("brief", nargs="?", help="Completed brief JSON file")
    ap.add_argument("--template", action="store_true", help="Print blank brief JSON and exit")
    ap.add_argument("--output", metavar="FILE", help="Write Markdown brief to FILE instead of stdout")
    ap.add_argument("--json", metavar="FILE", help="Also write evaluation result to JSON file")
    args = ap.parse_args(argv)

    if args.template:
        json.dump(template(), sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    if not args.brief:
        ap.error("brief file is required (or pass --template)")

    try:
        brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
        brief.pop("_help", None)
        result = evaluate(brief)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read brief: {e}", file=sys.stderr)
        return 2
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    text = format_report(result)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["verdict"] == "valid" else 1


if __name__ == "__main__":
    sys.exit(main())
