---
name: new-game-developer
description: Maps a newcomer's existing skills (music, drawing, 3D, writing, film editing, programming) onto three core game-dev foundations—balanced composition, complexity tolerance, and practical developer skill—and recommends one clear next step. Use when someone asks "which engine should I start with?", "I want to make games but don't know where to start", "I only know music/drawing, is that wasted?", "engines feel overwhelming", or "with AI making games easy, is there any point?"
---

# New Game Developer

Games combine nearly every art form at once. Jumping straight into a full game engine and juggling mechanics, UX, music, and visuals simultaneously makes the climb unnecessarily steep. Learning another art form or a simpler complex tool first actually shortens the path—not as gatekeeping or a multi-year prerequisite, but as a calmer ramp-up.

Knowing "just one thing" is never a failure. Even if you only make music or only draw, you are not behind and you have not wasted time. This skill maps your existing background onto three foundations deterministically via `scripts/skill_inventory.py` and selects one concrete next step.

## When to Use Which Tool

Run commands from this skill's directory (`skills/new-game-developer/`):

| Situation | Action / Script |
|---|---|
| User asks "where should I start?" without sharing background | Ask about three areas first: any art (music, drawing, video), programming, and complex tools or dense reading |
| User shared their skills, resume, or background | `python scripts/skill_inventory.py template` to generate blank JSON, fill `domain` and `level` for each skill |
| Inventory JSON is ready | `python scripts/skill_inventory.py evaluate inventory.json --json result.json --output report.md` |
| User asks a direct technical question (engine choice, language) | Answer the technical question directly; append this skill's next-step recommendation in one sentence without blocking the answer |

The script exits with a list of valid values if an unknown `domain` or `level` is supplied; common aliases (`visual art`, `drawing`, `3d`, `pico-8`, `engine`, `music`) are normalized automatically.

## The Three Foundations

- **Balanced composition.** Combining elements into a cohesive, appealing whole—instruments in music, texture/color/shape in visual art, or even structuring an application. Game development is balancing mechanics, UX, audio, and visuals together.
- **Complexity tolerance.** The discipline to sit down with a complex tool or dense text and extract meaning instead of quitting at the first wall of panels. Music DAWs, 3D modeling, and challenging books build this tolerance before you tackle a full game engine.
- **Practical developer skill.** Being able to speak a specialist's language (asking an artist for shaders or tweaks), editing delivered assets yourself, mixing audio levels without clipping, and solving real problems with small scripts.

## Workflow

1. **Gather background without judgment.** Include things the user dismisses as "unrelated to games": music, drawing, video editing, heavy reading, spreadsheet formulas, SQL. Never invent gaps—ask if unclear.
2. **Set levels together.** `beginner` (just started), `comfortable` (uses it comfortably), `advanced` (deep proficiency). Accept self-reported levels without arguing.
3. **Run the inventory.** `scripts/skill_inventory.py` maps each skill to the foundations it feeds and identifies any foundation below `comfortable`.
4. **Give one next step.** Share the exercise from the report's "Next Step" section: any art form for balanced composition, a simpler-than-engine complex tool for complexity tolerance, or small problem-solving programs (e.g., Pico-8) for practical skill. If all three foundations are at least `comfortable`, no foundation gap remains—give one concrete first engine step (such as a single moving square scene).
5. **Connect the road ahead.** Once ready to design, pair with `../fantasy-first-design/SKILL.md` to start from player fantasy, `../game-feel/SKILL.md` to establish responsive feel early, and `../sustainable-indie-dev/SKILL.md` for realistic scoping.

## Explain Where Taste Comes From

The three foundations combine not into a checklist, but into *taste*. When everyone uses the same tutorials or AI tools to build average versions of trending genres, what differentiates your game is the unique perspective you bring from other disciplines. AI made "average" cheap—winners were never average.

## Caveats (What Scripts Cannot Do)

- The domain-to-foundation table reflects one developer's path (music, Pico-8, Blender, Roblox, engines), not a universal law; the "film editing -> complexity tolerance" mapping is inferred from a single remark and marked as such in the report.
- Requiring `comfortable` across all three foundations is the tool's rule of thumb, not a hard numeric gate.
- The inventory counts self-reported levels; do not present the report as a formal certification.
- Never discourage someone from making games—the goal is pacing, not postponement.

## Tests

After modifying `scripts/skill_inventory.py`, run:

```bash
python -m unittest tests/test_skill_inventory.py
```

`assets/sample_inventory.json` provides a sample two-skill inventory ("Ece") to preview output.
