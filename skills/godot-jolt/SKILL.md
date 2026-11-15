---
name: godot-jolt
description: Jolt Physics GDExtension integration for Godot 4.3–4.6 (JoltPhysicsServer3DExtension, custom Jolt joints, and CMake extension builds). Use when configuring Godot Jolt project settings, migrating 3D physics from GodotPhysics, using Jolt*Joint3D substitute nodes, troubleshooting shape/raycast/contact differences, or building godot-jolt from source.
---

# Godot Jolt (`godot-jolt` GDExtension)

Native GDExtension integrating Jolt Physics as a drop-in 3D physics backend for Godot **4.3–4.6** (MIT license).

> **Maintenance / Godot 4.4+ Note:** Starting in Godot 4.4, Jolt is also integrated as a built-in engine module (`JoltPhysics3D`). To avoid symbol and setting collisions, `godot-jolt` **0.15.0+** renamed its server class to `JoltPhysicsServer3DExtension`, its engine display name to `"Jolt Physics (Extension)"`, and its settings prefix to `physics/jolt_physics_extension_3d/*`. Only the extension exposes the `Jolt*Joint3D` substitute nodes (`JoltHingeJoint3D`, etc.).

## Enabling & Switching the 3D Physics Engine

1. Extract the extension into `addons/godot-jolt/` and restart Godot.
2. Open **Project Settings** and enable **Advanced Settings** (top-right toggle).
3. Set **Physics -> 3D -> Physics Engine** (`physics/3d/physics_engine`) to **`Jolt Physics (Extension)`**.
4. Restart Godot for the server change to take effect.

### Supported vs. Ignored Godot Project Settings

`godot-jolt` honors `physics/common/*` (`physics_ticks_per_second`, `max_physics_steps_per_frame`, `enable_object_picking`) and `physics/3d/*` (`default_gravity`, `default_gravity_vector`, `default_linear_damp`, `default_angular_damp`).

These default Godot 3D settings are **ignored** (configure their `physics/jolt_physics_extension_3d/*` equivalents instead):
- `physics/3d/run_on_separate_thread` (unsupported — physics server is **not thread-safe**)
- `sleep_threshold_linear`, `sleep_threshold_angular`, `time_before_sleep` -> use `sleep/*`
- `solver/solver_iterations`, `solver/contact_max_allowed_penetration`, `contact_recycle_radius`, `contact_max_separation`, `default_contact_bias` -> use `solver/*`

## Key Extension Settings (`physics/jolt_physics_extension_3d/*`)

| Category | Setting | Default | Caveat / Effect |
|---|---|---|---|
| `sleep` | `enabled`, `velocity_threshold`, `time_threshold` | `true`, `0.03`, `0.5` | Controls body sleeping on bounding-box point velocity. |
| `collisions` | `use_shape_margins` | `true` | Applies only to `BoxShape3D`, `CylinderShape3D`, `ConvexPolygonShape3D`; disable for `0` margin (sharper normals, lower perf). |
| `collisions` | `use_enhanced_internal_edge_removal` | `true` | Smooths `RigidBody3D` motion over triangle/grid internal edges. Separate toggles exist under `kinematics/` (`true`) and `queries/` (`false`). |
| `collisions` | `report_all_kinematic_contacts` | `false` | Allows `FREEZE_MODE_KINEMATIC` `RigidBody3D` with `max_contacts_reported > 0` to report static/kinematic contacts (heavy cost on concave/heightmap geometry—restrict via layers/masks). |
| `collisions` | `body_pair_cache_enabled` | `true` | Caches contacts across ticks when relative transform change is below distance (`0.001`) and angle (`2°`). |
| `joints` | `world_node` | `Node A` | Which node acts as world anchor in single-body joints (`Node A` by default; GodotPhysics uses `Node B`). |
| `queries` | `use_legacy_ray_casting` | `false` | When `false`, matches GodotPhysics (`hit_back_faces` applies only to `ConcavePolygonShape3D` with `backface_collision`). |
| `queries` | `enable_ray_cast_face_index` | `false` | Populates `face_index` in `intersect_ray` / `RayCast3D.get_collision_face_index()`; adds ~25% memory overhead to `ConcavePolygonShape3D`. |
| `solver` | `velocity_iterations`, `position_iterations` | `10`, `2` | Per-tick solver iteration counts (`position_correction = 20%`, `active_edge_threshold = 50°`, `contact_speculative_distance = 0.02`). |
| `limits` | `max_bodies`, `max_body_pairs`, `max_contact_constraints`, `max_temporary_memory` | `10240`, `65536`, `20480`, `32 MiB` | Hard pre-allocated Jolt limits (`max_bodies` also applies inside the editor; exceeding `max_temporary_memory` falls back to slow heap allocations). |
| `limits` | `world_boundary_shape_size` | `2000.0` | `WorldBoundaryShape3D` is backed by a finite `JPH::PlaneShape` (`half_size = size / 2`). |

## Behavioral Differences & Caveats vs. GodotPhysics

- **Determinism & Threading:** Not guaranteed deterministic across runs/platforms; physics server is **not** thread-safe (`run_on_separate_thread` unsupported). Memory usage is not tracked in Godot's performance monitors.
- **Recommended Scale / Speed Limits (Jolt):** Keep dynamic objects roughly `0.1–10 m`, speeds `0–500 m/s`, gravity `0–10 m/s²`, and static objects `0.1–2000 m` for stability.
- **Scale & Shape Mutations:** Uniform/non-uniform scale is respected on bodies, shapes, and shape queries (except `SoftBody3D`). Modifying a body's shapes while inside the `SceneTree` is expensive.
- **Shape Quirks:**
  - `HeightMapShape3D`: requires `width >= 2` and `depth >= 2` (`heights.size() == width * depth`). Uses Jolt's `HeightFieldShape` when `width == depth` and `width / 2 >= 2`, otherwise **falls back to a double-sided triangle mesh**.
  - `WorldBoundaryShape3D`: finite plane (`limits/world_boundary_shape_size`); normal cannot be zero.
  - `ConvexPolygonShape3D`: computes a more accurate center of mass and inertia tensor than GodotPhysics.
  - `SoftBody3D`: does **not** interact with `Area3D`; ignores node scaling.
- **Contact Impulses & Shape-Casts:** Contact impulses are approximations when colliding with multiple bodies; shape-cast cost scales with cast distance.

## Jolt Joint Substitutes & Joint Differences

Godot's standard `Joint3D` nodes work, plus `godot-jolt` registers optional `JoltJoint3D` subclass nodes that expose Jolt-native features:

- `JoltPinJoint3D`
- `JoltHingeJoint3D` (adds limit springs + motor max torque)
- `JoltSliderJoint3D` (adds limit toggles/springs + linear motor target velocity/max force)
- `JoltConeTwistJoint3D` (adds swing/twist limit toggles + swing/twist velocity motors & max torques)
- `JoltGeneric6DOFJoint3D` (implements linear/angular spring frequency, damping, equilibrium point, max force/torque, and linear motors—springs/linear motors are also wired for standard `Generic6DOFJoint3D`)

Common `JoltJoint3D` capabilities:
- Per-joint solver overrides: `solver_velocity_iterations`, `solver_position_iterations`
- Force/torque telemetry for breakable joints: `get_applied_force()`, `get_applied_torque()` (on `JoltPinJoint3D`, `JoltHingeJoint3D`, `JoltSliderJoint3D`, `JoltConeTwistJoint3D`)
- `enabled` and `exclude_nodes_from_collision` toggles
- **Single-body joint pitfall:** By default `joints/world_node` is `Node A`, meaning omitting `node_a` anchors `node_b` to the world (opposite of GodotPhysics). Switching `world_node` to `Node B` restores GodotPhysics parity but can cause unintuitive 6DOF linear+angular behavior.

## Building from Source (`CMakeLists.txt` & `CMakePresets.json`)

Prerequisites: CMake >= 3.22, Python >= 3.8, Git >= 2.25. Dependencies (`godot-cpp`, Jolt fork, `mimalloc`) are fetched automatically via `ExternalProject` during build.

```sh
# Windows (MUST run from "x64 Native Tools Command Prompt", NOT x86 Developer PowerShell/Prompt)
cmake --preset windows-msvc-x64
cmake --build --preset windows-msvc-x64-distribution
cmake --build --preset windows-msvc-x64-editor-distribution
cmake --install build/windows-msvc-x64 --config Distribution --prefix /path/to/godot_project
cmake --install build/windows-msvc-x64 --config EditorDistribution --prefix /path/to/godot_project
```

Preset targets: `windows-msvc-{x64,x86}`, `windows-clangcl-{x64,x86}`, `linux-gcc-{x64,x86}`, `linux-clang-{x64,x86}`, `macos-clang` (universal), `macos-ios`, `windows-android-{arm64,arm32,x64,x86}` (requires `ANDROID_NDK_ROOT`). Append `-debug`, `-development`, `-distribution`, or `-editor-{debug,development,distribution}` for `--build --preset`.

### Key CMake Options (`cmake/GodotJoltOptions.cmake`)

| Option | Default | Notes |
|---|---|---|
| `GDJ_DOUBLE_PRECISION` | `FALSE` | Compiles with 64-bit world position precision (`-DGDJ_DOUBLE_PRECISION=TRUE`); required if targeting double-precision Godot builds. |
| `GDJ_X86_INSTRUCTION_SET` | `SSE2` | `NONE`, `SSE2`, `AVX`, `AVX2`, `AVX512` (not used on Apple/Android). Raising above `SSE2` drops older x86 CPUs. |
| `GDJ_INTERPROCEDURAL_OPTIMIZATION` | `TRUE` | Enables LTO/LTCG on optimized configs (`Development`/`Distribution`). |
| `GDJ_STATIC_RUNTIME_LIBRARY` | `TRUE` | Static C++ runtime on Windows/Linux (unavailable on Apple/Android). |
| `GDJ_USE_MIMALLOC` | `TRUE` | Uses `mimalloc` allocator (unavailable on iOS/Android). |
| `GDJ_PRECOMPILE_HEADERS` | `TRUE` | Speeds up builds by precompiling external headers. |
| `GDJ_INSTALL_DEBUG_SYMBOLS` | `FALSE` | Installs `.pdb`/debug symbols alongside binaries. |

### Build & Runtime Troubleshooting
- **`Mismatched target architectures` on Windows:** You ran CMake from Visual Studio's default "Developer Command Prompt/PowerShell" (which exposes x86) while targeting `x64`. Delete the `build/` folder and re-run inside **x64 Native Tools Command Prompt**.
- **Linux binary fails to load on older distros:** Prebuilt Linux binaries require **glibc >= 2.35** (Ubuntu 22.04+); compile on target if older glibc is needed.
- **Coexisting with Godot 4.4+ built-in Jolt:** Check `physics/3d/physics_engine`—choose either `"Jolt Physics (Extension)"` (for `Jolt*Joint3D` nodes) or Godot's built-in `"JoltPhysics3D"`, and verify settings under `physics/jolt_physics_extension_3d/*`.
