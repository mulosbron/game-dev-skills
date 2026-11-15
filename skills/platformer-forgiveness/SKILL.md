---
name: platformer-forgiveness
description: >-
  Add coyote time, jump buffering, and dual corner correction (ledge feet-lift + ceiling head-slide)
  to 2D and 2.5D platformer controllers. Uses exact fixed-physics-tick counters (_air_ticks, _press_ticks),
  pre-move swept collision checks (Godot test_move / Unity BoxCast), Unity Update->FixedUpdate input latching,
  dash/wall-jump/variable-jump interactions, and automated 60Hz tick verification via tools/platformer_forgiveness.py.
---

# Platformer Forgiveness (Coyote Time, Jump Buffering & Corner Correction)

Mathematically strict platformer controllers require jumping on the exact tick the character touches the ground, rejecting late ledge presses by one frame, early landing presses by a few milliseconds, or ledge/ceiling clips by `1–3 px`. Adding **coyote time**, **jump buffering**, and **dual corner correction** fixes all three silently while keeping the game's original speed, gravity, and jump height untouched.

---

## Pre-Code Project Audit (Mandatory)

Before writing code, inspect the existing project and fit into what is already there instead of building a second controller:
1. **Engine & language:** Godot 4 (`CharacterBody2D` / `CharacterBody3D`), Unity (`Rigidbody2D` / `CharacterController`), TypeScript/Phaser, or custom tile physics.
2. **Existing player controller:** Locate its ground check (`is_on_floor()`, `OverlapCircle`, box-cast), velocity integration, and movement call. **If there is no player controller yet, ask the user before inventing one.**
3. **Tick loop vs input reading:** Confirm movement runs in a fixed physics step (`_physics_process` in Godot, `FixedUpdate` in Unity). Never count rendered frames (`_process` / `Update`), or windows shrink at `144 Hz`+. If input is read per-frame (`Input.GetButtonDown`), latch it in `Update` and consume it in `FixedUpdate`.
4. **Keep existing feel:** Preserve current run speeds, gravity, jump velocity, and tile scale. Expose `coyote_time`, `jump_buffer`, and `corner_px` so every trick can be tweaked or disabled (`0`).

---

## Numbers That Matter (`60 ticks/s` Baseline)

| Setting | Default | Tweak Rule & Notes | Disabling (`0`) |
|---|---|---|---|
| **Coyote Time** | `0.1 s` (`6 ticks`) | Match Celeste (`JumpGraceTime = 0.1 s`). Keep `coyote_time * run_speed < character_width` (e.g. `0.1 * 150 = 15 px` vs `28 px` box). | `0.0` -> only `air_ticks == 0` can jump |
| **Jump Buffer** | `0.1 s` (`6 ticks`) | Too long causes stale accidental jumps upon landing. Clear on jump, death, respawn, and pause/menu close. | `0.0` -> only `press_ticks == 0` jumps |
| **Corner Size** | `4 px` (whole int) | Tested on `32 px` tiles (`1/8` tile); Celeste uses `4 px` on `8 px` tiles (`1/2` tile). `[tile/8 .. tile/2]` is safe. Corrects overlaps **strictly less than `corner_px`** (`3.99 px` passes, `>= 4 px` bonks/slides). | `0` -> no ledge or ceiling nudge |

---

## Canonical Fixed-Tick Pseudo Code

Initialize counters to `BIG` (`1000`) so a body spawned in mid-air cannot jump:

```text
air_ticks   = BIG
press_ticks = BIG

every fixed physics tick:
    air_ticks   = 0 if on_ground() else air_ticks + 1
    press_ticks = 0 if jump_pressed_this_tick() else press_ticks + 1

    can_jump   = air_ticks   <= round(coyote_time * ticks_per_second)
    wants_jump = press_ticks <= round(jump_buffer * ticks_per_second)
    if can_jump and wants_jump:
        velocity.y  = -jump_speed
        air_ticks   = BIG          # close coyote window: no double jump
        press_ticks = BIG          # consume press once
    else if not on_ground():
        apply gravity

    set horizontal velocity from input
    correct_corners()              # MUST run BEFORE move_and_slide()
    move the body with collisions

function correct_corners():
    if on_ground(): return
    side = (velocity.x * dt, 0)
    if side.x != 0 and blocked(position, side):
        for px in 1..corner_px:                      # ledge: lift feet onto it
            lift = (0, -px)
            if not blocked(position, lift) and not blocked(position + lift, side):
                position += lift
                break
    rise = (0, velocity.y * dt)
    if rise.y < 0 and blocked(position, rise):       # ceiling: slide around head clip
        ways = [sign(velocity.x)] if velocity.x != 0 else [-1, +1]
        for px in 1..corner_px:
            for way in ways:
                shift = (way * px, 0)
                if not blocked(position, shift) and not blocked(position + shift, rise):
                    position += shift
                    return
```

`blocked(from, motion)` maps directly to:
- **Godot 4:** `test_move(Transform2D(0, from), motion)` (or `global_transform.translated(...)`)
- **Unity:** `BoxCollider2D.Cast` / `Rigidbody2D.Cast` / `Physics2D.BoxCast`
- **Custom tile engine:** AABB swept box-against-solids check.

---

## Pitfalls & Existing Mechanic Interactions

- **Do not run corner correction after `move_and_slide()`:** By then `velocity.y` has already been zeroed by the ceiling collision (`is_on_ceiling()`). Run `_correct_corners(delta)` **before** `move_and_slide()` so upward momentum survives cleanly.
- **Always check BOTH `not blocked(pos, shift)` AND `not blocked(pos + shift, move)`:** Skipping the first check can push the character inside an adjacent wall/floor collider.
- **Only correct corners in the air:** On the ground, lifting `1..4 px` turns low terrain seams into staircase teleports.
- **Ceiling direction rule:** Only slide along `sign(velocity.x)` when moving horizontally (or try `[-1, +1]` only when `velocity.x == 0`). A player steering *into* a ceiling block must bonk.
- **No free double jump:** Reset `air_ticks = BIG` the instant a jump starts.
- **Clear `press_ticks` (and Unity latch) on death, respawn, and menu/pause close:** Otherwise the button pressed to dismiss a menu immediately fires a jump on resume.
- **Godot scripted input test quirk:** Calling `Input.action_press(...)` from code during a physics tick registers as `is_action_just_pressed()` on the **following** physics tick — account for that 1-tick offset in Godot integration tests.

### Interaction with Advanced Mechanics
- **Variable Jump Height:** Release cut (`velocity.y *= 0.5`) operates normally on `velocity.y < 0` regardless of whether the jump came from ground, coyote, or buffered landing.
- **Wall Jumps:** Do **not** let coyote time override wall-jump eligibility; handle wall contact (`wall_ticks`) cleanly as its own window and consume `press_ticks = BIG` when either ground/coyote jump or wall jump triggers.
- **Air Dash (Celeste style):** Disable coyote ground jumps during active dash states (`dash_timer > 0`), and optionally reuse the same `correct_corners()` loop with vertical nudges on horizontal dashes (`DashCornerCorrection`).
- **2.5D Platformers (`CharacterBody3D`):** Lock `velocity.z = 0` / `global_position.z = 0`, keep identical fixed-tick `_air_ticks` and `_press_ticks` logic, and run `test_move` with `corner_units / corner_steps` (e.g. `0.125` units in `4` steps). Note that capsule colliders naturally slide rounded shoulders slightly; use box/cylinder collider profiles if crisp 4-px corner determinism is needed.

---

## CLI Workflow (`tools/platformer_forgiveness.py`)

```bash
# Run all 6 automated 60Hz tick verification checks (plus 3.99px vs 4.0px & guards)
python tools/platformer_forgiveness.py verify --json

# Export tested Godot 4 (CharacterBody2D), Unity (FixedUpdate + Update latch), or Godot 2.5D scripts
python tools/platformer_forgiveness.py export-code --engine godot4 --out exports/platformer/player.gd
python tools/platformer_forgiveness.py export-code --engine unity --out exports/platformer/PlatformerForgivenessController.cs
python tools/platformer_forgiveness.py export-code --engine godot3d --out exports/platformer/player_25d.gd
```

---

## Verification Checklist (60 Ticks/s, Default `0.1 / 0.1 / 4`)

1. **Coyote cutoff:** Run off a ledge and press jump on tick `6` after leaving (`air_ticks == 6`) -> jumps; tick `7` -> does not jump.
2. **Jump buffer cutoff:** Press jump `6` ticks before the first grounded landing tick -> jumps on landing; `7` ticks before -> does not jump.
3. **No double jump:** Jump, then press jump `3` ticks later inside `0.1 s` -> no second jump (also spawned in air -> cannot jump; pause/respawn clears buffer).
4. **Ledge feet correction:** Sideways in air into a ledge overlapping feet by `3 px` (and `3.99 px`) -> lifts and lands on top; `4.0 px` / `5 px` -> slides down wall.
5. **Ceiling head correction:** Jump straight up with head overlapping ceiling end by `3 px` (and `3.99 px`) -> slides sideways past corner and keeps rising; `4.0 px` / `5 px` (or moving horizontally *into* block) -> bonks.
6. **Zero-out toggle:** Setting `coyote_time = 0`, `jump_buffer = 0`, `corner_px = 0` restores strict vanilla behavior while tick-0 ground jump still works.
