---
name: glb-forge
description: "Shrink, inspect, validate, and prepare 3D GLB/glTF models for Three.js, Godot, and game engines. Compresses textures to WebP/PNG, compresses geometry with Meshopt or Draco, generates multi-level LOD chains, exports Three.js TSL procedural node materials, and builds a Split-Screen 3D Compare Studio HTML."
---

# GLB Forge — 3D Model Inspector, Optimizer, LOD & TSL Studio (`glb-forge`)

Provides a local-first, 100% MIT/Apache-2.0 open-source 3D `.glb` pipeline (`tools/glb_forge.py` backed by `libraries/com.github.donmccurdy.gltf-transform`: `@gltf-transform/*`, `meshoptimizer`, `draco3dgltf`, `sharp`, and `gltf-validator`).

---

## 🛠️ Core Capabilities

1. **Deep 3D Model X-Ray (`inspect`):**
   * Reports exact file size, triangle count, vertex count, draw calls (primitives), materials, physical dimensions in meters, grounded pivot check (`Y=0`), per-texture resolution/disk size/estimated GPU VRAM, and **Khronos `gltf-validator`** errors/warnings.
2. **Measured Geometry & Texture Optimization (`optimize`):**
   * Runs `dedup`, `instance` (GPU instancing), `weld`, `simplify` (`MeshoptSimplifier`), `resample`, `prune`, `textureCompress` (WebP/PNG/JPEG resizing), and **Meshopt (`EXT_meshopt_compression`)** or **Draco (`KHR_draco_mesh_compression`)** encoding.
   * Outputs the optimized `.glb`, a JSON report, a visual **Before/After Report Card PNG (`_report_card.png`)**, and a standalone **Split-Screen 3D Compare Studio HTML (`_compare_studio.html`)**.
3. **Automated Multi-Level LOD Generation (`lod`):**
   * Generates `LOD0` (100%), `LOD1` (50%), and `LOD2` (20-25%) `.glb` chains with progressive texture downscaling.
4. **Three.js Shading Language (TSL) Node Material Export (`tsl-material`):**
   * Generates WebGPU/WebGL2 `MeshPhysicalNodeMaterial` TSL code (`animated-noise-lava`, `crystal-coat-glass`, `hologram-scanline`).
5. **Standalone Split-Screen 3D Compare Studio (`_compare_studio.html`):**
   * Double-click in any browser (zero server required—models are embedded + drag-and-drop enabled) to inspect **Original vs Optimized** side-by-side with linked cameras and 5 surface modes (`Final PBR`, `Wireframe`, `Normals`, `UV Checker`, `Procedural Shader`).

---

## ⚡ CLI Usage (`tools/glb_forge.py`)

### 1. Inspect a `.glb` Model & Run Khronos glTF Validation
```powershell
python tools/glb_forge.py inspect "assets/com.amazon.berkeley.abo/models/B003DQ5B2U.glb"
```

### 2. Optimize a `.glb` Model (`web-mobile`, `desktop-hd`, `draco-ultra`, `roblox-lowpoly`)
```powershell
python tools/glb_forge.py optimize "assets/com.amazon.berkeley.abo/models/B003DQ5B2U.glb" --preset draco-ultra
```

### 3. Generate a 3-Level LOD Chain (`LOD0`, `LOD1`, `LOD2`)
```powershell
python tools/glb_forge.py lod "assets/com.threejsassets/models/apartment-block-01.glb" --ratios "1.0,0.5,0.2"
```

### 4. Export Three.js TSL Procedural Node Materials
```powershell
python tools/glb_forge.py tsl-material --preset animated-noise-lava
```

### 5. Run Full Showcase Suite Across ABO & ThreeJS Assets
```powershell
python tools/glb_forge.py showcase
```
