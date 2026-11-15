---
name: camera-follow-2d
description: Eight 2D camera follow modes (locked, smooth, dead zone, rooms, look-ahead, points of interest, aim, two targets) scaled by viewport size @ 60Hz, with Godot 4 Camera2D (physics ordering + drag margins) and Unity Cinemachine 3 (Damping = 4.605/rate, RoomFocus, PoiFocus, CameraPoi, AimFocus) implementations + tools/camera_follow_2d.py verifier. For the Godot PhantomCamera addon specifically, see skills/phantom-camera/SKILL.md.
---

# 2D Camera Follow (8 Core Modes)

Choose the camera behavior that matches your game's pacing rather than locking straight onto the player or inventing an over-engineered rig. All reference constants below scale linearly with viewport size from a **`128 x 128 px` viewport at `60 Hz`** (`multiply px lengths by view_size / 128`).

> **Note for Godot 4 Addon Users:** If the project uses the third-party `addons/phantom_camera` plugin (`PhantomCamera2D`, `PhantomCameraHost`), read [phantom-camera](../phantom-camera/SKILL.md) as well. Use this skill for vanilla `Camera2D`, Unity Cinemachine 3, custom engines, and exact numerical tuning.

---

## Pre-Code Project Audit

Before writing camera code, inspect what exists in the project:
1. **Engine & language:** Godot 4 `Camera2D`, Unity Cinemachine 3 (`CinemachineCamera`, `CinemachineTargetGroup`, `CinemachinePositionComposer`), Phaser/Canvas/TypeScript, or custom engine.
2. **Existing camera setup & callback timing:** Verify whether player movement runs in `_physics_process` (`FixedUpdate`) or `_process` (`Update`), and run camera tracking **immediately after** player movement (e.g., Godot `process_physics_priority = 300`, Unity `LateUpdate`) to eliminate 1-frame jitter.
3. **Viewport / pixel-art resolution:** Measure logical camera width/height in world/art pixels (`view_w`, `view_h`) and scale pixel thresholds from the `128x128` baseline.

---

## The 8 Follow Modes & Reference Numbers (`128x128 @ 60 Hz`)

| # | Mode | Formula / Behavior | Reference Tuning (`128x128`) | Fallback / Guard |
|---|---|---|---|---|
| 1 | `locked` | `cam = target` | Exact lock every tick | Used automatically when offset/distance = `0` |
| 2 | `smooth` | `cam += (target - cam) * (1 - exp(-rate * dt))` | `rate = 2.6 / s` | **`rate <= 0` snaps immediately (`alpha = 1`) — never freeze!** |
| 3 | `dead_zone` | Camera stays stationary inside safe box around center | `±22 px` X, `±18 px` Y (`drag_margin_h = 22/64 = 0.34375`, `v = 18/64 = 0.28125`) | `half_x == 0 && half_y == 0` -> `locked` |
| 4 | `rooms` | Grid-aligned rooms `(floor(x/rw), floor(y/rh))`, smoothstep transition on exit | `128x128` rooms, `0.55 s` (`33 ticks`) smoothstep | **Snap immediately on tick 1 / spawn** |
| 5 | `look_ahead` | Velocity/facing lead smoothed with exponential filter | `lead = 32 px`, `rate = 3.4 / s` (`30.9 px` after `1 s` walk, `1.0 px` after `1 s` rest) | `lead_dist == 0` -> `locked`; `rate <= 0` snaps |
| 6 | `points` | Closest/strongest POI in group `camera_poi` pulls camera | `smoothstep(60 -> 24 px)`, `pull = 0.6`, `rate = 3.5 / s` (`0` at `60 px`, `14.0` at `40 px`, `14.4` at `24 px`) | `pull == 0` -> `locked` |
| 7 | `aim` | Blend camera between player and world mouse cursor | `share = 0.45`, `rate = 8.0 / s` (`27 px` at `60 px` steady; `44.2 / 45 px` at `100 px` after `0.5 s`) | `share == 0` -> `locked`; `rate <= 0` snaps |
| 8 | `two_targets` | Follow midpoint; scale span = `clamp(max(\|dx\|,\|dy\|) + pad, min, max)` | `pad = 104`, clamp `[128, 240]`, `move_rate = 4.5`, `zoom_rate = 3.5` (`204 px / 0.627` zoom at `100 px`, `240 px / 0.533` at `200 px`) | Clamp zoom cleanly; zero separation stays at `min_span` (`1.0x`) |

---

## Engine Mappings

### Godot 4 (`Camera2D`)
- Place `CameraFollow2D.gd` directly on the scene's `Camera2D` (`process_physics_priority = 300`).
- **Dead Zone drag margins:** Godot expresses drag margins normalized against half-viewport (`half_px / (view_px * 0.5)`), so `±22 px` X and `±18 px` Y on `128x128` map to `0.34375` (`left`/`right`) and `0.28125` (`top`/`bottom`).
- **Rooms:** Snap `global_position` on `_ready` / tick 1 before enabling `0.55 s` smoothstep transitions so level entry never sweeps from `(0, 0)`.

### Unity (`Cinemachine 3`)
- **Damping conversion:** Cinemachine's `Damping` represents approximate settle time (~99% decay, `exp(-4.605) = 0.01`):
  $$\text{Damping} = \frac{4.605}{\text{rate}}$$
  (e.g., `smooth rate 2.6 -> Damping 1.771`, `aim rate 8.0 -> Damping 0.576`).
- **Four Drop-In Proxy Scripts** exported via `tools/camera_follow_2d.py export-code --engine unity`:
  - `RoomFocus.cs`: Track target Transform for `128x128` grid rooms + `0.55 s` `Mathf.SmoothStep`.
  - `CameraPoi.cs`: Scene component marking POI radii (`60 -> 24 px`) and `pullStrength = 0.6`.
  - `PoiFocus.cs`: Blends player position with active `CameraPoi` markers at `rate = 3.5 / s`.
  - `AimFocus.cs`: Blends player and world mouse position (`share = 0.45`, `rate = 8.0 / s`).
- **`two_targets`:** Use `CinemachineTargetGroup` + Framing/Position Composer orthographic size framing mapped to `[128, 240]` viewport span.

---

## Common Pitfalls

- **`rate == 0` freezing the camera:** If an exponential filter checks `if rate > 0`, leaving `rate = 0` locks the camera motionless. Explicitly treat `rate <= 0` as `alpha = 1.0` (instant snap).
- **1-frame jitter against pixel art:** Updating the camera in `_process` when the player moves in `_physics_process` (or before the player script runs) causes sub-pixel trembling. Match the player's tick loop and set higher priority (`300`).
- **Look-ahead whipping on tap turnaround:** Smooth direction transitions via velocity filtering (`rate = 3.4 / s`) rather than flipping the offset abruptly on a 1-frame keypress.

---

## CLI Workflow (`tools/camera_follow_2d.py`)

```bash
# Run 60Hz numerical verification across all 8 modes + edge fallbacks
python tools/camera_follow_2d.py verify --json

# Export Godot 4 Camera2D script (CameraFollow2D.gd)
python tools/camera_follow_2d.py export-code --engine godot4 --out-dir exports/camera_follow_2d --json

# Export Unity Cinemachine 3 scripts (RoomFocus.cs, CameraPoi.cs, PoiFocus.cs, AimFocus.cs)
python tools/camera_follow_2d.py export-code --engine unity --out-dir exports/camera_follow_2d --json
```
