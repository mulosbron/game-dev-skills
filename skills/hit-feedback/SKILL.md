---
name: hit-feedback
description: Make 2D combat hits feel heavy from one centralized hit() call combining 8 fixed-tick reactions (hit stop, shader hit flash, eased knockback with collision, pixel-rounded screen shake, directional blood/spark particles, 4-ray impact spark, receding slash trail, blinking damage numbers) plus killing-blow slow-mo. Includes Godot 4 hit_feel.gd + hit_flash.gdshader, Unity FixedUpdate manager, and tools/hit_feedback.py 60Hz verifier.
---

# 2D Hit Feedback (Heavy Impact System)

When sword/projectile hits only subtract HP, combat feels weightless. Route every contact event through **one centralized `hit()` call** firing eight coordinated fixed-tick reactions (plus an amplified killing blow), keeping damage, speed, and animations untouched.

---

## Pre-Code Project Audit (Mandatory)

Before editing combat files, inspect the existing project and fit into what is already there:
1. **Engine & language:** Godot 4 (`GDScript`/`.gdshader`), Unity (`C#`), TypeScript/Phaser, or custom engine.
2. **Hit detection point:** Locate the exact tick/callback where melee hitboxes or projectiles connect with an enemy. **If no melee or projectile hit exists yet, ask the user before inventing combat logic.**
3. **Enemy movement, AI, death & camera:** Check how enemies move (and ensure enemy AI does not overwrite knockback velocity during the `8`-tick push), whether targets queue-free on death (defer deletion until freeze ends!), and whether camera already uses `offset` (add/subtract shake deltas rather than overwriting!).
4. **Heavy vs light attacks:** Ask which attacks are light fast multi-hits (use fewer freeze ticks, e.g. `2-3`) vs heavy/finisher strikes (`5` / `9` ticks).

---

## The 8 Reactions & Reference Numbers (`60 ticks/s`, ~`320x180 px` art, `50-70 px` sprites)

Scale pixel distances linearly with sprite/art scale. Setting any parameter to **`0`** (`kill_slow = 1.0`) disables that reaction individually:

| # | Effect | Normal Hit (`@ 60Hz`) | Killing Blow | Starts / Timing Rule |
|---|---|---|---|---|
| 1 | **Hit Stop** | `5` skipped ticks | `9` skipped ticks | **Only the two fighters freeze** (`age = 1..stop`). Other effects keep running so it reads as impact, not lag! |
| 2 | **Hit Flash** | `2` frames pure white | Same (`2` frames) | Runs through freeze (`age = 0, 1` -> white `1.0`, `age = 2` -> `0.0`). Shader `mix(c.rgb, 1.0, flash)` preserves alpha (**never `modulate`**). |
| 3 | **Knockback** | `12 px` over `8` ticks | Same (`move_and_collide`) | Starts **after freeze** (`k = age - stop = 1..8`). Cubic ease-out `1 - (1 - t)^3` (`3.96 px` on tick 1). Moves with wall collision. |
| 4 | **Screen Shake** | `3 px` over `10` ticks | Same | Runs through freeze: `amp = 3 * (1 - k/10)^2`, whole-px rounded X alternating (`3, -2, 2, -1, 1, -1, 0...`), Y random `[-0.6..0.6] * amp`. Additive; returns strictly to `(0, 0)`. |
| 5 | **Particles** | `10` drops, `~140°` fan back/up | `28` drops, `360°` omni | Spawns **first tick after freeze** (`age == stop + 1`) at contact `at`. `90-200 px/s`, `2-3 px`, damped out in `0.26 s`. |
| 6 | **Impact Spark** | `4` frames `[5, 9, 7, 3] px` | Same | 4 cardinal warm rays on `at`, diagonals at half length, `3x3` white core. |
| 7 | **Slash Trail** | `100°` arc ending at `at` | Same | Full during freeze, then shrinks from trailing end over `6` ticks (`trail_ticks`). |
| 8 | **Damage Number** | `46` ticks, white | `46` ticks, yellow `(1, 0.93, 0.47)` | Rises `8 * (1 - (1 - h)^2) + 2*sin(PI*h) + age*0.08` (`+9 px` at frame 10), hidden every odd tick for last 6 (`age = 41, 43, 45`). |
| + | **Kill Slow-Mo** | `1.0` (off) | `time_scale = 0.3` for `12` ticks | Starts **after freeze** (`age == stop + 1`), restores `1.0` at `stop + 1 + 12`. |

---

## Pitfalls

- **Never freeze with global `time_scale = 0` during hit stop:** That halts the flash, spark, screen shake, and unfreeze timers. Pause only `attacker` and `target` (`process_mode = PROCESS_MODE_DISABLED` in Godot with manager `process_physics_priority = -100`; disabled scripts + `Animator.speed = 0` in Unity).
- **Overlapping multi-hit freezes:** Keep a **per-fighter freeze counter** (`max(cur, ticks + 1)`), otherwise an earlier hit's unfreeze callback wakes a fighter prematurely during a newer hit's freeze.
- **No squash & stretch scaling in pixel art:** Scaling sprites distorts the pixel grid; draw dedicated frames instead if smear/squash is desired.
- **Deferred death cleanup:** When `kill = true`, disable enemy AI/hitbox immediately or delete after `stop` ends — never leave `target` freed mid-knockback without `is_instance_valid()` guards.
- **Camera offset overwrite:** Track `_last_shake` and subtract before adding so existing camera look-ahead/aim offsets remain intact.

---

## CLI Workflow (`tools/hit_feedback.py`)

```bash
# Run all 8 automated 60Hz tick checks (freeze counts, flash frames, 3.96px/12px knockback + wall, shake [3,-2,2,-1,1,-1,0], particles, 46-frame number, kill 0.3x slow-mo, zero-toggle)
python tools/hit_feedback.py verify --json

# Export tested Godot 4 (hit_feel.gd + hit_flash.gdshader) or Unity (HitFeedbackManager.cs) scripts
python tools/hit_feedback.py export-code --engine godot4 --out-dir exports/hit_feedback --json
python tools/hit_feedback.py export-code --engine unity --out-dir exports/hit_feedback --json
```

---

## Verification Checklist (`60 ticks/s`)

1. Attacker and target skip exact `5` fixed updates (`9` on killing blow).
2. Target sprite `flash == 1` on hit frame & next frame, `0` on frame 3.
3. `0 px` movement during freeze; `3.96 px` on tick 1 after freeze; `12.0 px` after 8 ticks (stops cleanly at `6 px` wall).
4. Camera shake X offset sequence `[3, -2, 2, -1, 1, -1, 0, ...]`, returning to `(0, 0)` from tick 10 onward.
5. `10` particles spawn on first tick after freeze at contact point (`28` on killing blow).
6. Damage number survives `46` frames (`age = 0..45`), reaches `+9 px` at frame 10, hides at frames `41, 43, 45`.
7. Killing blow sets `time_scale = 0.3` for `12` post-freeze ticks, then `1.0`.
8. All settings at `0` (`kill_slow = 1.0`) leaves every effect silent and alters only HP.
