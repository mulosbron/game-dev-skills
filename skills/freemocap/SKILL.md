---
name: freemocap
description: "Markerless multi-camera 3D motion capture pipeline (FreeMoCap v2.0+) for capturing human performance from standard webcams/videos and exporting game-ready FBX, BVH, and Blender (.blend) skeletal animations for Godot 4, Unity, Unreal, and Blender Rigify/UniRig/Ozz-Animation. Use whenever the user mentions FreeMoCap, markerless mocap, webcam motion capture, recording character animations from video, calibrating ChArUco cameras, or exporting mocap FBX/BVH/Blender rigs (`tools/freemocap_tool.py`)."
---

# FreeMoCap 3D Motion Capture Pipeline (`freemocap`)

Captures 3D human skeletal motion from consumer webcams or synchronized video files without suits or markers, then exports rigged `.blend`, `.fbx`, and `.bvh` animations ready for retargeting into Godot 4, Unity, Unreal Engine, or Ozz-Animation.

Companion CLI: [`tools/freemocap_tool.py`](../../tools/freemocap_tool.py).

---

## 1. Installation & Startup (`uv` Recommended)

FreeMoCap v2.0 pulls `skellytracker` and `skellycam` via [`uv`](https://github.com/astral-sh/uv). Plain `pip install freemocap` omits the tracker unless you pass `[cuda]` or `[cpu]`:

```powershell
# Option A — From source repo with uv (recommended)
cd freemocap
uv venv
uv sync                                        # NVIDIA CUDA on Windows/Linux, CPU on macOS
# Or force CPU-only on Windows/Linux without a supported GPU:
uv sync --no-default-groups --group cpu

# Launch local Python FastAPI server (http://localhost:8005)
uv run python freemocap/__main__.py

# Optional: launch Electron/React GUI in a second terminal
cd freemocap-ui && npm install && npm run dev

# Option B — PyPI install (Python 3.9–3.11)
pip install "freemocap[cuda]"   # or freemocap[cpu]
freemocap
```

---

## 2. Capture-to-Engine Pipeline

1. **ChArUco Camera Calibration (`/calibration/*`):** Calibrate 2+ synchronized cameras using a printed ChArUco board so multi-view 2D detections triangulate accurately into 3D world space.
2. **Record or Post-Hoc Process (`/mocap/*`, `/posthoc/*`):** Capture live multi-camera takes or run post-hoc triangulation on existing synchronized videos to produce 3D skeletal trajectories (`output_data/*.npy`, `*.csv`).
3. **Export to Blender + FBX / BVH (`/blender/export`):** Run the FreeMoCap Blender addon headless to construct the rigged armature in `tpose` or `apose`, write `<recording>.blend`, and export `<recording>.fbx` and `<recording>.bvh` under `3d_models/`.
4. **Game Engine Retargeting:**
   - **Godot 4:** Import `.fbx` (or `.glb` re-exported from the generated `.blend`) and retarget onto a `SkeletonProfileHumanoid` (`AnimationLibrary`).
   - **Unity:** Import `.fbx` / `.bvh` with `Animation Type = Humanoid` to map directly to Avatar bones.
   - **Blender / UniRig / Ozz:** Pair with [`unirig`](../unirig/SKILL.md) for auto-rigging target meshes and [`ozz-animation`](../ozz-animation/SKILL.md) for runtime skeletal blending.

---

## 3. Blender Export Options (`BlenderExportConfig`)

| Option (JSON alias) | Default | Notes |
|---|---|---|
| `formats` | `["fbx", "bvh"]` | Writes sibling files under `<recording>/3d_models/`. **Note:** Do not request `gltf` directly from the addon — its animation branch is unexposed/broken; convert from `.blend`/`.fbx` instead. |
| `restPose` | `"tpose"` | `"tpose"` or `"apose"` — match your target game rig's rest pose before retargeting. |
| `applyFootLocking` | `false` | Optional cleanup pass that locks planted feet to reduce foot skate (rewrites marker positions). |
| `limitHandMarkersRangeOfMotion` | `false` | Optional hand/finger range-of-motion clamp to tame noisy finger tracking. |

---

## 4. CLI Workflow (`tools/freemocap_tool.py`)

Always pass `--json` in agent workflows:

```powershell
# 1. Verify CLI config schema & offline recording inspector
python tools/freemocap_tool.py verify --json

# 2. Check if local FreeMoCap FastAPI server (http://localhost:8005) is reachable
python tools/freemocap_tool.py health --json

# 3. Detect local Blender executable (via server or local PATH / standard install paths)
python tools/freemocap_tool.py detect-blender --json

# 4. Inspect a FreeMoCap recording folder (videos, 3D npy/csv data, .blend, 3d_models FBX/BVH)
python tools/freemocap_tool.py inspect-recording path/to/recording_session --json

# 5. Trigger headless Blender + FBX/BVH export on a processed recording
python tools/freemocap_tool.py export-blender --recording path/to/recording_session --formats fbx,bvh --rest-pose tpose --foot-locking --no-open --json
```

---

## 5. Common Pitfalls & License Note

- **Broken direct glTF export:** Always export `fbx` and/or `bvh` from FreeMoCap, then convert to `.glb` inside Blender or Godot if needed.
- **Rest-pose mismatch:** Exporting `tpose` onto an `apose` game skeleton causes twisted shoulders during retargeting — pass `--rest-pose apose` when targeting A-pose rigs.
- **Foot sliding:** Enable `--foot-locking` for locomotion clips (idle/walk/run) and inspect ground contact in Blender before baking into engine clips.
- **License (AGPLv3):** FreeMoCap itself is AGPLv3; exported motion-capture data files (`.fbx`, `.bvh`, `.blend`) are your creative assets, while modifying/redistributing FreeMoCap source code follows AGPLv3 terms.
