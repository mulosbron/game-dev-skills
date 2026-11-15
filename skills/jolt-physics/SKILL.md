---
name: jolt-physics
description: Multi-core C++17 3D rigid-body, soft-body, character, constraint, and vehicle physics engine (Jolt Physics v5.7.0, MIT). Use when integrating JoltPhysics via CMake, configuring broadphase/object layer filters, simulating bodies/constraints/ragdolls/characters/vehicles/hair/buoyancy, enabling double precision or cross-platform determinism, or troubleshooting linker/RTTI/LTO build issues.
---

# Jolt Physics (`JoltPhysics` v5.7.0)

Multi-core friendly C++17 3D physics and collision detection library (MIT license) used in Horizon Forbidden West, Death Stranding 2, and Godot Physics.

Source repository: `https://github.com/jrouwe/JoltPhysics` (CMake root is `Build/CMakeLists.txt`).

## Core Capabilities

- **Rigid bodies & CCD:** Continuous collision detection (`EMotionQuality::LinearCast`) and speculative contacts.
- **Shapes:** Sphere, Box, Capsule, Tapered-capsule, Cylinder, Tapered-cylinder, Convex hull, Plane, Compound (static/mutable), Mesh (triangle), Terrain (height field), plus Scaled/Rotated/Offset decorators.
- **Constraints & motors:** Fixed, Point, Distance, Hinge, Slider (prismatic), Cone, Rack-and-pinion, Gear, Pulley, Six-DOF, Path, Swing-twist; powered linear/angular motors.
- **Collision queries:** Ray casts, shape casts, transformed shape casts, broadphase AABB/ray/sphere/box queries, and concurrent read-only queries during simulation.
- **Sensors & characters:** Trigger volumes (`IsSensor`), Ragdolls, `Character` (rigid body) and `CharacterVirtual` (predictive collision response with moving platforms).
- **Vehicles & advanced systems:** Wheeled, tracked, and motorcycle vehicle controllers; Soft bodies (cloth/deformable); GPU-accelerated strand hair simulation; buoyancy impulse calculations; Double precision (`DOUBLE_PRECISION=ON`) for large worlds.
- **Bindings & integrations:** C, C#, Java/Kotlin, JavaScript/WASM (`JoltPhysics.js`), Rust, Python, Zig, Jai, Nim; native Godot integration and Unreal/Source plugins.

## C++17 Integration Lifecycle

Jolt enforces strict header ordering and startup/teardown sequence:

1. **Always `#include <Jolt/Jolt.h>` first** in every `.cpp` or precompiled header before any other `<Jolt/...>` header. Do not compile Jolt with RTTI or C++ exceptions unless explicitly enabled consistently in both library and app.
2. **Startup sequence:**
   - Call `RegisterDefaultAllocator()` (or register custom hooks) **before any other Jolt call**.
   - Optionally assign `Trace` and `JPH_IF_ENABLE_ASSERTS(AssertFailed = ...)`.
   - `Factory::sInstance = new Factory();`
   - `RegisterTypes();` (after custom `PhysicsMaterial::sDefault` if overridden).
   - Instantiate `TempAllocatorImpl` (e.g., 10 MB pre-allocated) and a `JobSystem` (`JobSystemThreadPool` for testing, or custom engine scheduler implementing `JobSystem`).
   - Implement and keep alive (longer than `PhysicsSystem`): `BroadPhaseLayerInterface`, `ObjectVsBroadPhaseLayerFilter`, and `ObjectLayerPairFilter` (or use the `*Table` / `*Mask` helpers).
   - Call `physics_system.Init(cMaxBodies, cNumBodyMutexes, cMaxBodyPairs, cMaxContactConstraints, broad_phase_layer_interface, object_vs_broadphase_layer_filter, object_vs_object_layer_filter)`.
3. **Simulation & body management:**
   - Use `physics_system.GetBodyInterface()` (locking) or `GetBodyInterfaceNoLock()` for creating/adding/removing/moving bodies.
   - Batch-insert bodies when streaming levels; call `physics_system.OptimizeBroadPhase()` after initial world load (never every frame).
   - Step with `physics_system.Update(cDeltaTime, cCollisionSteps, &temp_allocator, &job_system)` (1 collision step per `1/60`s).
   - Use `RVec3` / `0.0_r` (`using namespace JPH::literals;`) for world positions so code compiles under both single- and double-precision modes.
   - Stack-allocated `RefTarget` subclasses (e.g., `BoxShapeSettings`) require `.SetEmbedded()` so ref-counting does not delete stack memory.
4. **Teardown sequence:** `RemoveBody` -> `DestroyBody` for bodies -> `UnregisterTypes()` -> `delete Factory::sInstance; Factory::sInstance = nullptr;`.

## CMake Build Options (`Build/CMakeLists.txt`, CMake >= 3.20)

| Option | Default | Effect / Pitfall |
|---|---|---|
| `INTERPROCEDURAL_OPTIMIZATION` | `ON` | Enables LTO/IPO on Jolt targets. Calling project **must** also enable LTO/IPO or set this `OFF`, or static linking (`libJolt.a`) fails. |
| `DOUBLE_PRECISION` | `OFF` | Uses double precision for world coordinates (`RVec3`/`RMat44`/`Real`). |
| `CROSS_PLATFORM_DETERMINISTIC` | `OFF` | Bit-exact determinism across CPU/OS/compilers (SSE/NEON/FMA differences). |
| `OBJECT_LAYER_BITS` | `16` | `ObjectLayer` width (`16`, `32`, or `64`). |
| `USE_ASSERTS` | `OFF` | Enables internal Jolt assertions even in non-Debug builds (`Debug` enables them automatically unless overridden). |
| `JPH_BUILD_SHARED_LIBS` | `OFF` | Builds shared library instead of static library. |
| `CPP_RTTI_ENABLED` / `CPP_EXCEPTIONS_ENABLED` | `OFF` | Must match the consumer target settings. |
| `OVERRIDE_CXX_FLAGS` | `ON` | Controls whether Jolt sets its own compiler flags (`-Wall`, SIMD, etc.). |
| `USE_SSE4_1` / `USE_SSE4_2` / `USE_AVX` / `USE_AVX2` / `USE_AVX512` | `ON` (`AVX512` `OFF`) | x86 SIMD instruction sets (`SSE2` minimum); match target CPU baseline. |

## Concurrency & Determinism Rules

- Bodies **do not** automatically wake up when a neighbor is removed or modified; explicitly wake affected bodies (`BodyInterface::ActivateBodiesInAABox` or `ActivateBody`) when deleting support geometry.
- `BodyActivationListener` and `ContactListener` callbacks fire from worker threads during `Update()` — never call locking `BodyInterface` methods inside listeners, and keep shared state thread-safe.
- Never stream bodies one-by-one if loading a large scene; use `BodyInterface::AddBodiesPrepare` / `AddBodiesFinalize` from background threads or batches.
