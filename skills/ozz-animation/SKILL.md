---
name: ozz-animation
description: ozz-animation C++17 skeletal animation runtime and offline asset pipeline guidance. Use when integrating Skeleton/Animation loading, SamplingJob, BlendingJob, LocalToModelJob, IKAimJob/IKTwoBoneJob, SkinningJob, root motion (MotionExtractor/MotionBlendingJob), SIMD SoaTransform math, or gltf2ozz/fbx2ozz and CMake options.
---

# ozz-animation

Open-source C++17 skeletal animation library (v0.17.0, MIT) split into zero-OS-dependency runtime libraries (`ozz_base`, `ozz_animation`, `ozz_geometry`) and offline conditioning tools (`ozz_animation_offline`, `gltf2ozz`, `fbx2ozz`). Tested on Windows, Linux, macOS, and WebAssembly across x86/x64/ARM.

## CMake Targets & Build Options

Requires **CMake >= 3.30** and C++17 (`build-utils/cmake/compiler_settings.cmake` enables `CMAKE_COMPILE_WARNING_AS_ERROR ON`).

- **Runtime Targets:** `ozz_base`, `ozz_animation`, `ozz_geometry` (`SkinningJob`). Depend only on the C/C++ standard library.
- **Offline & Tool Targets:** `ozz_animation_offline`, `ozz_animation_tools`, `ozz_animation_fbx`, `gltf2ozz`, `fbx2ozz`.

| CMake Option | Default | Effect |
| :--- | :--- | :--- |
| `BUILD_SHARED_LIBS` | `OFF` | Build shared libraries instead of static archives |
| `ozz_build_tools` | `ON` | Build `ozz_animation_tools` (`import2ozz`) and importers |
| `ozz_build_gltf` | `ON` | Build `gltf2ozz` converter |
| `ozz_build_fbx` | `ON` | Build `ozz_animation_fbx` & `fbx2ozz` (auto-disabled if FBX SDK 2020 missing) |
| `ozz_build_simd_ref` | `OFF` | Force scalar math reference (`OZZ_BUILD_SIMD_REF`) instead of SIMD |
| `ozz_build_msvc_rt_dll` | `OFF` | Use `/MD` MSVC DLL runtime (forced `ON` on WIN32 when shared) |
| `ozz_build_samples` / `howtos` / `tests` | `ON` | Build sample apps, howtos, and unit tests (`ozz_build_data` defaults `OFF`) |
| `ozz_build_postfix` | `ON` | Append debug/configuration postfixes to built binaries |

## Runtime Loading & Core Pipeline

1. **Deserialize Binary Archives (`ozz/base/io/archive.h`):**
   ```cpp
   ozz::io::File file(filename, "rb");
   ozz::io::IArchive archive(&file);
   if (archive.TestTag<ozz::animation::Skeleton>()) {
     archive >> skeleton; // same pattern for ozz::animation::Animation
   }
   ```
   - `ozz::animation::Skeleton` (`include/ozz/animation/runtime/skeleton.h`): Up to `kMaxJoints = 1024` (`kMaxSoAJoints = (kMaxJoints + 3) / 4`), joints stored in depth-first parent-before-child order (`kNoParent = -1`). Provides `joint_rest_poses()`, `joint_parents()`, `joint_names()`, `num_joints()`, `num_soa_joints()`.
   - `ozz::animation::Animation` (`include/ozz/animation/runtime/animation.h`): GV4 iframe-compressed keyframes sorted by time then track (translation/rotation/scale tracks); exposes `duration()`, `num_tracks()`, `num_soa_tracks()`.
2. **Sample (`SamplingJob`):** Set `animation`, persistent `SamplingJob::Context` (caches keyframes for forward frame-coherent playback), normalized `ratio` in `[0, 1]`, and `output` span of `ozz::math::SoaTransform`. Call `Validate()` / `Run()`.
3. **Blend (`BlendingJob`):** Configure `layers` (each `BlendingJob::Layer` has `weight`, `transform` SoA span, and optional per-joint `joint_weights` mask for upper/lower-body masking), optional `additive_layers`, `rest_pose`, `threshold` (default `0.1f` for normalization/culling), and `output`.
4. **Local-to-Model (`LocalToModelJob`):** Converts blended local `SoaTransform` poses into model-space `ozz::math::Float4x4` matrices using `skeleton`. Supports optional `root` matrix injection and partial tree updates (`from`, `to`, `from_excluded`).
5. **Skinning (`ozz::geometry::SkinningJob`):** Applies linear-blend vertex skinning from model matrices and inverse-bind matrices into output vertex buffers.

## Inverse Kinematics & Root Motion

- **Aim IK (`IKAimJob`):** Computes local `SimdQuaternion` `joint_correction` (and optional `reached` flag) to point a joint's local `forward` axis (with `up`, `offset`, `pole_vector`, `twist_angle`, and `weight`) toward a model-space `target`, given the current model-space `joint` matrix.
- **Two-Bone IK (`IKTwoBoneJob`):** Solves a 3-joint ancestor chain (`start_joint`, `mid_joint`, `end_joint`) given `mid_axis`, `pole_vector`, `twist_angle`, `soften`, and `weight`, writing `start_joint_correction` and `mid_joint_correction` (plus optional `reached`).
- **Root Motion (`MotionExtractor` + `MotionBlendingJob`):**
  - *Offline (`include/ozz/animation/offline/motion_extractor.h`):* `MotionExtractor` extracts root translation (`RawFloat3Track`) and rotation (`RawQuaternionTrack`) tracks from a `RawAnimation` (`Reference::kAbsolute | kSkeleton | kAnimation`, `bake` option to remove extracted motion from root joint, `loop`, XZ translation / Y yaw defaults).
  - *Runtime (`include/ozz/animation/runtime/motion_blending_job.h`):* `MotionBlendingJob` blends per-layer `ozz::math::Transform` root deltas by layer weights.

## SIMD SoA Math Layout

- `ozz::math::SoaTransform` (`include/ozz/base/maths/soa_transform.h`) packs **4 joints per struct** (`SoaFloat3 translation`, `SoaQuaternion rotation`, `SoaFloat3 scale`, where each axis is `SimdFloat4` holding 4 joints simultaneously). Allocate `skeleton.num_soa_joints()` elements for sampling/blending buffers.
- `include/ozz/base/maths/internal/simd_math_config.h` auto-enables x86/x64 SIMD (SSE2 through AVX2/FMA). **Note:** `OZZ_SIMD_ARM_NEON` is commented out in v0.17.0, so ARM targets currently fall back to the scalar reference path (also explicitly selectable via `-Dozz_build_simd_ref=ON`).

## Offline Pipeline & `gltf2ozz` / `fbx2ozz`

- Offline classes (`SkeletonBuilder`, `AnimationBuilder`, `AnimationOptimizer`, `AdditiveAnimationBuilder`, `OzzImporter`) convert `RawSkeleton` and `RawAnimation` into compact runtime `.ozz` files.
- CLI converters (`import2ozz`):
  - `--file=<input>`: Source `.gltf`/`.glb` or `.fbx` asset.
  - `--config=<json>` or `--config_file=<path>` (mutually exclusive): Controls skeleton/animation names, optimization tolerances, additive mode, and motion extraction.
  - `--config_dump_reference`: Prints a complete reference JSON configuration.
  - `--endian=native|little|big`, `--log_level=silent|standard|verbose`.

## Pitfalls

- Do not resize output `SoaTransform` buffers by `skeleton.num_joints()`; always use `skeleton.num_soa_joints()`.
- Reuse a dedicated `SamplingJob::Context` per playing clip instance (do not share one `Context` across multiple clips/entities, or keyframe caching thrashes).
- Warnings are compiled as errors (`CMAKE_COMPILE_WARNING_AS_ERROR ON`); watch compiler flags when vendoring `ozz` directly into stricter parent builds.
