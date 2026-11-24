#!/usr/bin/env python3
"""Skill inventory: maps a newcomer's prior skills onto three game-dev foundations.

Before jumping straight into a full game engine, prior creative or technical practice
builds three foundations:
  composition  Balanced composition (bringing parts together into a cohesive whole)
  complexity   Complexity tolerance (sitting with a complex tool until it clicks)
  practical    Practical developer skill (audio mixing, asset tweaks, scripting)

Together, those three form taste that sets your game apart.

Usage:
  python skill_inventory.py template
  python skill_inventory.py evaluate inventory.json
  python skill_inventory.py evaluate inventory.json --json result.json --output report.md
"""

import argparse
import json
import sys
from pathlib import Path

# domain: (display name, foundations fed, how it helps in games, rationale note)
DOMAINS = {
    "music": (
        "Music / Audio",
        ("composition", "complexity", "practical"),
        "You can compose audio, design SFX, and mix levels cleanly without harsh peaks.",
        "Years in DAWs taught both balanced composition and patience with complex interfaces.",
    ),
    "visual_art": (
        "Visual Art (drawing, digital painting)",
        ("composition", "practical"),
        "You balance texture, color, and form, and can edit or fix external art assets yourself.",
        "Visual art is balancing textures, colors, and shapes into a coherent whole.",
    ),
    "3d": (
        "3D (Blender and similar)",
        ("composition", "complexity", "practical"),
        "You can direct 3D artists using accurate terminology and modify meshes or shaders yourself.",
        "Composing scenes with 3D forms trains both visual taste and tolerance for complex tools.",
    ),
    "literature": (
        "Reading / Writing Complex Texts",
        ("complexity",),
        "Discipline to sit with an intimidating problem and extract clarity.",
        "Working through dense, difficult texts built stamina for solving hard game-dev bugs.",
    ),
    "film": (
        "Video / Film Editing",
        ("composition", "complexity"),
        "Organizing a large project end-to-end—similar to structuring a game's architecture.",
        "Organizing a full film edit mirrors organizing a game project (inferred mapping).",
    ),
    "programming": (
        "Programming (apps, tools)",
        ("composition", "complexity", "practical"),
        "You write game logic yourself and feel at home in an engine's scripting layer.",
        "Balanced composition can even be learned by programming an app; complex toolchains build stamina.",
    ),
    "small_programs": (
        "Small Programs (Pico-8 and similar)",
        ("practical",),
        "A low-friction first step into programming by solving small, real problems.",
        "Pico-8 is recommended as a focused first step: small programs that solve concrete problems.",
    ),
    "game_engine": (
        "Game Engine (Godot, Unity, Roblox)",
        ("complexity", "practical"),
        "Familiarity with the core assembly tool: scripts, scene trees, and resource organization.",
        "Modern game engines are among the most complex tools available; tolerating them is half the battle.",
    ),
}

FOUNDATIONS = {
    "composition": (
        "Balanced Composition",
        "balanced composition",
        "Bringing mechanics, UX, audio, and visuals together into an appealing, cohesive whole.",
    ),
    "complexity": (
        "Complexity Tolerance",
        "complexity tolerance",
        "Discipline to sit down with a complex tool or dense material until it makes sense.",
    ),
    "practical": (
        "Practical Developer Skill",
        "practical developer skill",
        "Working hands-on with audio, visuals, or code and speaking the same language as specialists.",
    ),
}

RECOMMENDATIONS = {
    "composition": "Pick any art form—drawing, painting, or music—and finish a small piece with balanced structure.",
    "complexity": "Spend time with a complex tool simpler than a full engine: a DAW, 3D modeling, or finishing a challenging book.",
    "practical": "Write small programs that solve a real problem in your life, or build tiny prototypes in Pico-8.",
}

LEVEL_VALUE = {"beginner": 1, "starting": 1, "comfortable": 2, "advanced": 3}
LEVEL_NAME = {0: "none", 1: "beginner", 2: "comfortable", 3: "advanced"}
COMFORTABLE = 2

ALIASES = {
    "3d_art": "3d",
    "blender": "3d",
    "pico8": "small_programs",
    "pico_8": "small_programs",
    "engine": "game_engine",
    "visual": "visual_art",
    "drawing": "visual_art",
    "painting": "visual_art",
    "art": "visual_art",
    "audio": "music",
    "sound": "music",
    "video": "film",
    "editing": "film",
    "writing": "literature",
    "reading": "literature",
    "coding": "programming",
    "code": "programming",
}


def _norm(x):
    return str(x or "").strip().lower().replace(" ", "_").replace("-", "_")


def _text(x):
    return str(x or "").strip()


def template():
    return {
        "person": "",
        "skills": [
            {"name": "", "domain": "", "level": "", "note": ""},
            {"name": "", "domain": "", "level": "", "note": "", "extra_foundations": []},
        ],
        "_help": {
            "domain": list(DOMAINS) + [f"{k} ({v})" for k, v in ALIASES.items()],
            "level": ["beginner", "comfortable", "advanced"],
            "extra_foundations": "Add any foundation you believe this skill also feeds: " + ", ".join(FOUNDATIONS),
        },
    }


def parse_skill(skill, loc):
    """Validate one skill entry and return (domain, level_int, foundations_set)."""
    domain = _norm(skill.get("domain"))
    domain = ALIASES.get(domain, domain)
    if domain not in DOMAINS and "_" in domain:
        first = domain.split("_")[0]
        domain = ALIASES.get(first, first)
    if domain not in DOMAINS:
        raise ValueError(f"{loc}: unknown domain '{domain or 'empty'}'. Valid: {', '.join(DOMAINS)}")
    level = _norm(skill.get("level"))
    if level not in LEVEL_VALUE:
        raise ValueError(f"{loc}: invalid level '{level or 'empty'}'. Valid: {', '.join(LEVEL_VALUE)}")
    extra = skill.get("extra_foundations") or []
    if not isinstance(extra, list):
        raise ValueError(f"{loc}: extra_foundations must be a list")
    gained = set(DOMAINS[domain][1])
    for f in extra:
        f_norm = _norm(f)
        if f_norm not in FOUNDATIONS:
            raise ValueError(f"{loc}: invalid extra_foundations '{f_norm}'. Valid: {', '.join(FOUNDATIONS)}")
        gained.add(f_norm)
    return domain, LEVEL_VALUE[level], gained


def evaluate(data):
    """Map an inventory dict onto the three foundations. Raises ValueError listing all issues."""
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON object")
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("'skills' list is missing or empty. Run `template` to generate a blank file")
    rows, errors = [], []
    for i, item in enumerate(skills, start=1):
        loc = f"skills[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{loc}: must be an object")
            continue
        try:
            domain, level, gained = parse_skill(item, loc)
        except ValueError as e:
            errors.append(str(e))
            continue
        rows.append({
            "name": _text(item.get("name")) or DOMAINS[domain][0],
            "domain": domain,
            "domain_name": DOMAINS[domain][0],
            "level": level,
            "foundations": [k for k in FOUNDATIONS if k in gained],
            "in_games": DOMAINS[domain][2],
            "rationale": DOMAINS[domain][3],
            "note": _text(item.get("note")),
        })
    if errors:
        raise ValueError("Invalid inventory:\n  - " + "\n  - ".join(errors))

    foundations = []
    for key, (name, _, desc) in FOUNDATIONS.items():
        sources = [r for r in rows if key in r["foundations"]]
        lvl = max((r["level"] for r in sources), default=0)
        foundations.append({
            "key": key,
            "name": name,
            "description": desc,
            "level": lvl,
            "status": LEVEL_NAME[lvl],
            "sources": [r["name"] for r in sources],
            "recommendation": RECOMMENDATIONS[key],
        })
    weak = [f for f in foundations if f["level"] < COMFORTABLE]
    return {
        "person": _text(data.get("person")) or "(anonymous)",
        "skills": rows,
        "foundations": foundations,
        "next_step": weak[0] if weak else None,
        "single_domain": len({r["domain"] for r in rows}) == 1,
    }


def format_report(s):
    out = [
        f"# Skill Inventory: {s['person']}",
        "",
        "| Skill | Domain | Level | Foundations Fed | How It Helps in Games |",
        "|---|---|---|---|---|",
    ]
    for b in s["skills"]:
        out.append(
            f"| {b['name']} | {b['domain_name']} | {LEVEL_NAME[b['level']]} | "
            f"{', '.join(FOUNDATIONS[k][1] for k in b['foundations'])} | {b['in_games']} |"
        )
    out += ["", "## The Three Foundations", "", "| Foundation | Status | Source Skills |", "|---|---|---|"]
    for f in s["foundations"]:
        out.append(f"| {f['name']} | {f['status']} | {', '.join(f['sources']) or '—'} |")
    out += ["", "What each foundation means:", ""]
    out += [f"- **{f['name']}**: {f['description']}" for f in s["foundations"]]
    out += ["", "## Next Step", ""]
    nxt = s["next_step"]
    if nxt is None:
        out.append("You are at least comfortable across all three foundations. Nothing stands in your way—start building a tiny playable scene.")
    else:
        out.append(f"Weakest foundation: **{nxt['name']}** ({nxt['status']}). Recommended exercise:")
        out.append(f"> {nxt['recommendation']}")
    if s["single_domain"]:
        out.append("")
        out.append("You currently draw from a single domain. That time is never wasted, though your distinctive taste grows stronger when fed by a second discipline.")
    out += ["", "## Mapping Rationale", ""]
    seen = []
    for b in s["skills"]:
        if b["domain"] not in seen:
            seen.append(b["domain"])
            out.append(f"- **{b['domain_name']}**: {b['rationale']}")
    out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="New game developer skill inventory.")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("template", help="Print a blank inventory JSON")
    ev = sub.add_parser("evaluate", help="Evaluate a completed inventory JSON")
    ev.add_argument("file", help="Inventory JSON file")
    ev.add_argument("--json", metavar="OUT", help="Also write evaluation result to JSON file")
    ev.add_argument("--output", metavar="FILE", help="Write Markdown report to FILE instead of stdout")
    args = ap.parse_args(argv)

    if args.command == "template":
        json.dump(template(), sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 0
    try:
        result = evaluate(json.loads(Path(args.file).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read file: {e}", file=sys.stderr)
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
