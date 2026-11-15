---
name: blender-kiln
description: "Build, clean, UV-unwrap, texture, rig, animate, validate, and optimize real-size 3D models in headless Blender 5.2 using Blender Kiln 3.0 (libraries/com.github.elithril.blender-kiln + tools/blender_kiln.py). Includes 6-view Colour & Clay review sheets, UV/3D-print checks, Kiln Studio, and a 3D-to-2D Pixel Art + Normal Map bridge."
---

# Blender Kiln 3.0 — The 3D Asset Forge & 3D-to-2D Pixel Bridge (`blender-kiln`)

Turns object descriptions or reference photos into clean, named, real-world-sized (`1 unit = 1m`), grounded (`Z=0`) editable Blender `.blend` and `.glb` models using **local headless Blender 5.2 LTS** (`tools/blender_kiln.py` + `libraries/com.github.elithril.blender-kiln`, MIT License). **Requires zero AI diffusion weights and zero GPU.**

---

## 🔥 The 8-Phase Kiln Production Pipeline

1. **Source & Scale (`1 unit = 1m`):** Plan parts at real physical dimensions with bottom-center grounded at `Z=0`.
2. **Model (Clean Named Parts):** Script clean geometry in Blender (`SM_<Asset>_<Part>`), keeping separate logical parts editable.
3. **Cleanup (Kiln Iron Rule 10):** Apply transforms (`location`, `rotation`, `scale`), merge doubles keeping sharp normals, recalculate outside normals, and run Smart UV Project (`island_margin=0.02`).
4. **Texture (PBR / CC0 Scans):** Assign `Principled BSDF` materials (`Base Color`, `Metallic`, `Roughness`, `Emission`, `Transmission`) or PolyHaven CC0 textures.
5. **Rig & Animate (Optional):**
   * Humanoids: `libraries/com.github.elithril.blender-kiln/plugin/tools/autorig.py` + 22 built-in motions.
   * Quadrupeds: `libraries/com.github.elithril.blender-kiln/plugin/tools/quadruped.py` (`idle`, `walk`).
   * Articulated Props: `libraries/com.github.elithril.blender-kiln/plugin/tools/bind_rigid_parts.py`.
6. **UV Audit & 6-View Colour + Clay Review Sheets:**
   * Run `uv_check.py` to check for missing, collapsed, overlapping, stretched, or flipped UVs.
   * Run `review_sheet.py` in EEVEE Khronos PBR Neutral to render a **6-View Colour Sheet (`_review_sheet.png`)** and a **6-View Clay Geometry Sheet (`_review_sheet_clay.png`)** so the AI agent visually inspects its own 3D work!
7. **GLB Forge Optimization & Compare Studio:**
   * Compress with `tools/glb_forge.py` (Meshopt/Draco + WebP) and generate a standalone Split-Screen 3D Compare Studio HTML.
8. **3D-to-2D Pixel Art + Normal Map Bridge (`--to-pixel`):**
   * Automatically pipes the transparent 3D render through `tools/image_to_pixel.py` + `tools/normal_map_gen.py` to produce a matching 2D Pixel Art sprite, Faceted Normal Map (`_n.png`), and Dynamic Lighting GIF!

---

## ⚡ CLI Usage (`tools/blender_kiln.py`)

### 1. Verify Local Blender 5.2+ & Run Kiln's API Verification Suite (`doctor`)
```powershell
python tools/blender_kiln.py doctor
```

### 2. Run Full 3D Build + 6-View Review Sheets + GLB Optimization + 2D Pixel Sprite (`build`)
```powershell
python tools/blender_kiln.py build --preset iron-lantern --to-pixel --pixel-profile dark-fantasy
```

### 3. Render 6-View Colour & Clay Review Sheets for Any `.glb` or `.blend` (`review-sheet`)
```powershell
python tools/blender_kiln.py review-sheet "exports/com.github.elithril.blender-kiln/iron-lantern/iron-lantern_original.glb"
```

### 4. Audit UV Maps on Any `.glb` or `.blend` (`uv-check`)
```powershell
python tools/blender_kiln.py uv-check "exports/com.github.elithril.blender-kiln/iron-lantern/iron-lantern_original.glb"
```

### 5. Validate 3D Printability (`print-check`)
```powershell
python tools/blender_kiln.py print-check "path/to/model.glb"
```

### 6. Launch Local Kiln Studio Web Viewer & Pinboard (`studio`)
```powershell
python tools/blender_kiln.py studio --dir "exports/com.github.elithril.blender-kiln"
```

---

## 📚 Detailed Kiln Reference Docs
For advanced character rigging, photo-projection (`photo_project.py`), and review rounds, read the reference guides inside `libraries/com.github.elithril.blender-kiln/plugin/references/`:
* `SKILL.md` — 26 Iron Rules of Blender production
* `references/pipeline-import-cleanup.md` — Topology & normal preservation rules
* `references/pipeline-rig-animate.md` — Biped, quadruped, and articulated prop animation
* `references/photo-projection.md` — Rebuilding a 3D asset measured against a single photo
* `references/print.md` — Watertight FDM/Resin 3D printing rules
