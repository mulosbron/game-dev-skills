---
name: game-feel
description: Audits and improves game feel (juice, responsiveness, and feedback layers) using a 5-pillar audit, closed-form jump physics calculation, coyote-time/input-buffering simulation, and 3-channel (visual/audio/temporal) per-genre minimums. Use when a game works but feels dead, stiff, sluggish, unresponsive, or when jumping, movement, momentum, or atmosphere feel off—even if "game feel" or "juice" is not mentioned.
---

# Game Feel

If a mechanic works, half the job is done. The other half is how it feels. Players can usually tell whether a game's feel was designed intentionally, and that layer often decides whether the game succeeds.

This skill combines **concrete per-genre feedback minimums** with a **deterministic 5-pillar audit**, **jump physics calculator**, and **coyote-time / input-buffering simulator**. Scoring, math, and frame simulation live in Python scripts so results are reproducible; your job is to fill the survey accurately, adapt numbers to the game's scale, and give a concise prioritized action plan.

## When to Use Which Tool

Run commands from this skill's directory (`skills/game-feel/`):

| Need | Action / Script |
|---|---|
| General game feel audit ("why does this feel flat?") | `python scripts/game_feel_audit.py --template` to generate a blank survey, fill it, then `python scripts/game_feel_audit.py survey.json` |
| Compute jump velocity and gravity from height & apex time | `python scripts/jump_physics.py --height H --time-to-apex T [--fall-multiplier M]` |
| Choose & verify coyote time / input buffer frame windows | `python scripts/feel_sim.py --coyote-frames N --buffer-frames N --fps 60` |
| Minimal Godot 4 coyote + buffer reference script | `assets/coyote_buffer.gd` (plug in values from `jump_physics.py` and `feel_sim.py`) |
| Production Godot/Unity forgiveness + corner correction | See `../platformer-forgiveness/SKILL.md` (`tools/platformer_forgiveness.py`) |
| Production 8-reaction hitstop, flash, knockback & shake | See `../hit-feedback/SKILL.md` (`tools/hit_feedback.py`) |
| Collect and prioritize player playtest observations | See `../playtest/SKILL.md` (`playtest_report.py`) |

Every script supports `--json FILE` for structured output; if another step consumes the results, read the JSON instead of parsing stdout Markdown.

## Every Player Action Gets a Response on Three Channels

- **Visual:** flash, scale/squash tween, particles, trail.
- **Audio:** at least 3 variations per event, random pitch ±10%.
- **Temporal:** hitstop (2–4 frames for light impacts; see `hit-feedback` for heavy), short decaying screen shake (50–200 ms). Use sparingly—if everything shakes, nothing shakes.

## Per-Genre Minimums

- **Platformer (3 Forgiveness Mechanics Required):** coyote time (~100 ms), jump buffering (~100 ms), corner/ceiling correction (2–5 px nudge), variable jump height, landing squash. See `../platformer-forgiveness/SKILL.md`.
- **Hits / Damage:** hitstop, white flash, knockback, screen shake, impact particles & spark, slash trail, damage numbers. See `../hit-feedback/SKILL.md`.
- **Top-Down / Shooter:** muzzle flash, shell casing, recoil pushing the camera, bullet trail.
- **UI:** every click gets a sound + 100 ms scale tween; menu transitions are 150–250 ms, never instant.
- **Camera:** lerp-follow the player, look-ahead in the movement direction, never jitter. See `../camera-follow-2d/SKILL.md`.

## Performance Boundary & Definition of Done

- **60 FPS = 16.67 ms.** The feel layer must not eat this budget: pool particles, preload sounds, and apply shake as a single camera offset.
- **30-second test:** If someone watching the game silently does not go "ooh" in the first 30 seconds, it is not done. Make the 30-second core loop fun first; content, menus, and save systems come after.

## Audit Workflow

1. **Fill the survey.** Pull answers from conversation context or inspect project code (e.g., check if a counter tracks frames after `is_on_floor()`). Ask the user for anything unknown—never invent answers. Use `yes`, `partial`, `no`, or `na`, and document reasoning in `note`.
2. **Score and inspect.** Run `scripts/game_feel_audit.py` to compute pillar scores and an action list ordered from the weakest pillar. If answers are missing or invalid, the script lists every problem and exits non-zero; fix and re-run.
3. **Compute physics & timing numbers.** Get target jump height and time-to-apex from the user and compute parameters with `scripts/jump_physics.py`. Compare candidate frame windows with `scripts/feel_sim.py`; if a player's "I pressed it in time" moment falls outside the window, widen it.
4. **Deliver a focused plan.** Present at most five action items starting with the weakest pillar—one concrete change per item—and leave the full breakdown in the output file.

## The Five Pillars

- **Anticipate intended player input.** If a player presses an action button with slightly imperfect timing, honor the intent: coyote time, input buffering, variable jump height, and ignoring accidental mispresses.
- **Playtest continuously.** Put every build in front of at least five real testers, watch their first playthrough live without guiding them, and treat gameplay friction as a design bug, not player error.
- **Use micro-animation.** Separate walk/run, pivot turns, jump stretch, fall stretch, landing squash, and subtle state transitions (like head turns on wall slide) turn identical physics into responsive craft.
- **Design movement and momentum deliberately.** Tight vs. loose is a conscious choice—tight conveys control and precision; momentum-heavy conveys speed and joy—and a single game can intentionally blend both across abilities.
- **Build atmosphere and sense of place.** Impact particles, ambient floating dust/snow/embers, parallax layers, and lighting answer: *"Does this feel like a real place, or just colors painted on a screen?"*

## Caveats (What Scripts Cannot Do)

- Survey scores summarize reported answers; they do not measure how the game actually feels. Always end with a playtest recommendation—watching a real player is the only truth.
- `assets/coyote_buffer.gd` defaults are starting points calibrated to match `scripts/feel_sim.py` and verified by unit tests, not universal constants; test ledge and landing behavior directly inside the target engine.
- Non-platformer games should mark jump-specific items as `na` and apply the remaining pillars.

## Tests

After editing any script, run:

```bash
python -m unittest tests/test_game_feel.py
```

`assets/sample_audit.json` provides a complete sample survey ("Lighthouse Keeper") to preview report output.
