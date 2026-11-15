---
name: phantom-camera
description: Phantom Camera Godot 4 dynamic 2D/3D camera addon (Cinemachine-style virtual cameras, priority switching, follow/look-at modes, tweening, camera shake, C# wrappers). Use when configuring PhantomCameraHost, PhantomCamera2D/3D, transitions, dead zones, limits, noise emitters, or resolving C#/interpolation caveats in Godot 4.4+.
---

# Phantom Camera (Godot 4.4+)

GDScript Cinemachine-style virtual camera addon (`addons/phantom_camera`, checked against `0.11.0.3`, requires **Godot 4.4+**). A single `PhantomCameraHost` drives Godot's `Camera2D` or `Camera3D` toward whichever matching `PhantomCamera2D` / `PhantomCamera3D` currently has the highest priority.

## Core Architecture & Setup

1. **Autoload singleton:** Enabling the plugin registers `PhantomCameraManager` as an autoload singleton (`Engine.get_singleton("PhantomCameraManager")` in GDScript; `PhantomCamera.Manager.PhantomCameraManager` in C#).
2. **Host placement (mandatory):** Add `PhantomCameraHost` as a **direct child** of your scene's active `Camera2D` or `Camera3D`.
   - Only the **first** `PhantomCameraHost` child on a camera is used; attaching it to any other node triggers a configuration warning and disables tracking.
   - `PhantomCameraHost` automatically disables `Camera2D.position_smoothing_enabled` and sets `camera_3d.physics_interpolation_mode = Node.PHYSICS_INTERPOLATION_MODE_OFF` to prevent double-smoothing/jitter against Phantom Camera's own damping and interpolation.
3. **Virtual cameras:** Add `PhantomCamera2D` (`Node2D`) or `PhantomCamera3D` (`Node3D`) anywhere in the scene tree. They calculate target transforms independently (setting `top_level = true` whenever `follow_mode != FollowMode.NONE`) and never move scene cameras directly unless activated through a host.
4. **Visibility & layer filtering:** A `PhantomCameraHost` only considers PCams where:
   - `(pcam.host_layers & host.host_layers) != 0` (20-bit layer bitmasks)
   - `pcam.visible == true` (hidden PCams are ignored and force priority re-evaluation)

## Priority Switching & Transitions

- **Priority rules:** `priority: int` is clamped `>= 0` in `set_priority()`. Higher value wins.
- **Tie-breaker:** When another PCam's `priority` becomes **greater than or equal to** (`>=`) the currently active PCam's priority, the newly updated PCam takes control. On scene load, the last PCam in `PhantomCameraManager` list order with the highest priority becomes active.
- **`priority_override` (Editor only):** Forces activation in the editor/Viewfinder; stripped/disabled in exported builds.
- **`tween_resource` (`PhantomCameraTween`):** Controls camera transition when a PCam becomes active:
  - `duration: float` (default `1.0`), `transition: TransitionType` (`LINEAR`, `SINE`, `QUINT`, `QUART`, `QUAD`, `EXPO`, `ELASTIC`, `CUBIC`, `CIRC`, `BOUNCE`, `BACK`), `ease: EaseType` (`EASE_IN`, `EASE_OUT`, `EASE_IN_OUT`, `EASE_OUT_IN`).
  - Disable `tween_on_load` on spawn/player cameras so initial scene entry snaps immediately instead of tweening from origin.
- **`PhantomCameraTweenDirector` + `TweenDirectorResource`:** Overrides the destination PCam's tween for specific **From -> To** pairs, matching by `NodePath` (`PHANTOM_CAMERA`), saved `PhantomCameraTween` `.tres` reference (`TWEEN_RESOURCE` — resources **must** be saved to disk), or `ANY`.

```gdscript
# Instant cut vs smooth transition + avoiding damping lag on teleports
cutscene_pcam.tween_resource.duration = 1.2
cutscene_pcam.priority = 20

# Teleport target + snap camera immediately without damping catch-up
player.global_position = spawn_point.global_position
player_pcam.teleport_position()
```

## Follow Modes & Look-At Modes

### `FollowMode` (`PhantomCamera2D` & `PhantomCamera3D`)

| Mode | Behavior & Required Properties | Notes / Caveats |
|---|---|---|
| `NONE` | Static transform at node placement | Resets `top_level = false` |
| `GLUED` | Locks directly onto `follow_target` | Zero offset/damping |
| `SIMPLE` | Tracks `follow_target` + `follow_offset` | Supports `follow_damping`, `follow_axis_lock`, velocity lookahead |
| `GROUP` | Tracks center of `follow_targets` array | 2D: `auto_zoom` (`_min`, `_max`, `_margin` `Vector4` L/T/R/B)<br>3D: `auto_follow_distance` (`_min`, `_max`, `_divisor`), `follow_distance` |
| `PATH` | Clamps `follow_target` onto closest point on `follow_path` (`Path2D`/`Path3D`) | Requires valid `follow_path` and `follow_target` |
| `FRAMED` | Holds still inside `dead_zone_width` / `dead_zone_height` (plus `dead_zone_depth` in 3D) | `dead_zone_reached` signal; `center_on_active` centers target when tweening in; `interactive_dead_zone` allows dragging in Viewfinder/runtime |
| `THIRD_PERSON` *(3D only)* | Orbits `follow_target` using an internal `ShapeCast3D` spring arm | `spring_length`, `collision_mask`, `margin`, `shape` (auto-creates camera pyramid frustum shape via `Camera3D.get_pyramid_shape_rid` if `null`), `vertical_rotation_offset`, `horizontal_rotation_offset` |

### Third-Person Rotation Helpers (`PhantomCamera3D`)

Mutate the internal `ShapeCast3D` gimbal with dedicated methods rather than `rotation` directly:
- `set_third_person_rotation(rad_vec3)` / `get_third_person_rotation()`
- `set_third_person_rotation_degrees(deg_vec3)` / `get_third_person_rotation_degrees()`
- `set_third_person_quaternion(quat)` / `get_third_person_quaternion()`

### `LookAtMode` (`PhantomCamera3D` only)

| Mode | Behavior | Key Properties |
|---|---|---|
| `NONE` | Uses node's own orientation (or Third Person gimbal) | — |
| `MIMIC` | Copies `look_at_target` rotation | `look_at_target` |
| `SIMPLE` | Rotates toward `look_at_target` | `look_at_offset`, `look_at_damping`, `look_at_lookahead`, `up` / `up_target` |
| `GROUP` | Looks at midpoint of `look_at_targets` | `look_at_targets`, `up` / `up_target` |

> **Caveat:** Combining both `follow_mode != NONE` and `look_at_mode != NONE` on the same `PhantomCamera3D` triggers an upstream warning ("has not been fully tested yet"); disable via Project Settings `phantom_camera/tips/show_mixed_mode_tips` or keep follow and look-at roles separate where possible.

## 2D & 3D Camera Overrides, Limits & Shake

### 2D-Specific (`PhantomCamera2D`)
- `zoom: Vector2` (overridden automatically when `FollowMode.GROUP` + `auto_zoom = true`), `snap_to_pixel: bool` (pixel-art snapping), `rotate_with_target: bool` (requires `Camera2D.ignore_rotation = false`).
- **Limits:** Set `limit_left/top/right/bottom` manually OR assign `limit_target` to a `TileMapLayer` (updates after `TileSet` changes / closing TileMap panel) or `CollisionShape2D` (live in editor; static at runtime for performance) + `limit_margin: Vector4i` (L, T, R, B). Enable `draw_limits` for editor preview.

### 3D-Specific (`PhantomCamera3D`)
- **`camera_3d_resource: Camera3DResource`:** Overrides `Camera3D` `keep_aspect`, `cull_mask`, `h_offset`, `v_offset`, `projection` (`PERSPECTIVE`, `ORTHOGONAL`, `FRUSTUM`), `fov`, `size`, `frustum_offset`, `near`, `far` when active.
- **`attributes: CameraAttributes`**, **`environment: Environment`**, **`compositor: Compositor`:** Applied dynamically on activation.

### Noise & Camera Shake
- **Resources (`PhantomCameraNoise2D` / `PhantomCameraNoise3D`):** Built on `FastNoiseLite` (`TYPE_PERLIN`). Configure `amplitude`, `frequency`, `randomize_noise_seed` / `noise_seed`, `positional_noise`, `rotational_noise`, and per-axis multipliers.
- **Continuous camera noise:** Assign directly to `pcam.noise` (runs continuously after transition completes).
- **One-shot / triggered emitters (`PhantomCameraNoiseEmitter2D` / `PhantomCameraNoiseEmitter3D`):**
  - Match emitter `noise_emitter_layer` bitmask with target PCam `noise_emitter_layer` (note: default `noise_emitter_layer` on emitters is `1`, while on PCams it defaults to `0` — you must enable the matching layer on the PCam!).
  - Configure `growth_time`, `duration`, `decay_time`, `continuous`, and call `emitter.emit()`, `emitter.stop(should_decay)`, or `emitter.toggle()`.
- **Custom shake:** Call `pcam.emit_noise(transform_2d_or_3d)` to inject external noise patterns.

## Update Timing (`InterpolationMode`) & Performance

- `PhantomCameraHost.interpolation_mode`:
  - `AUTO` *(default)*: Runs in `_physics_process` when the active PCam's follow/look-at target is physics-driven (`CharacterBody`, `RigidBody`), otherwise `_process`. Host sets `process_priority = 300` / `process_physics_priority = 300` so cameras update after movement scripts.
  - `IDLE` / `PHYSICS`: Force idle or physics tick updates.
  - `MANUAL`: Disables automatic processing; drive manually with `host.process(delta)`.
- Set `inactive_update_mode = InactiveUpdateMode.NEVER` on secondary PCams when they do not need background tracking while inactive.

## C# Wrappers & Troubleshooting

Phantom Camera provides typed C# wrapper classes (wrapping GDScript nodes/resources via `GodotObject.Call`/`Get`/`Set` — attach the `.gd` scripts in scenes as normal, then wrap in C#):

```csharp
using Godot;
using PhantomCamera;
using PhantomCamera.Manager;

var host = GetNode<Node>("Camera3D/PhantomCameraHost").AsPhantomCameraHost();
var pcam = GetNode<Node3D>("PhantomCamera3D").AsPhantomCamera3D();
pcam.Priority = 10;
pcam.FollowMode = FollowMode3D.ThirdPerson;
pcam.SetThirdPersonRotationDegrees(new Vector3(-20f, yaw, 0f));

// Creating a tween resource from C#
var tween = PhantomCameraTween.New();
tween.Duration = 0.6f;
tween.Transition = TransitionType.Cubic;
pcam.TweenResource = tween;
```

**Verified caveats:**
- **C# `Manual` mode host call:** `PhantomCameraHost.cs` defines `public void Process()` with no `delta` parameter even though `phantom_camera_host.gd` expects `func process(delta: float)`. If using `InterpolationMode.Manual` from C#, invoke `host.Node.Call(PhantomCameraHost.MethodName.Process, (float)delta)` directly.
- **Signals on `PhantomCameraHost` & `PhantomCamera`:** Connect using the C# wrapper events (`PCamBecameActive`, `BecameActive`, `DeadZoneReached`, `TweenCompleted`, etc.) or Godot signal names in snake_case (`pcam_became_active`, `became_active`, `tween_completed`).
- **Noise emitters not shaking camera:** Verify `pcam.noise_emitter_layer` shares at least one bit with the emitter's `noise_emitter_layer` (PCams default to `0`, emitters default to `1`).
