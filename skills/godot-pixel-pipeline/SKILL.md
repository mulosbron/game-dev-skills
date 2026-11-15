---
name: godot-pixel-pipeline
description: "Godot 4.x pixel-art texture pipeline for 2D, 3D low-poly, 2.5D FPS (Doom-style), and 2.5D Top-Down (HD-2D / Y-sort). Automates project settings, lossless/no-mipmap imports, pixel-perfection audits, PSX and Bayer dither shaders, and nearest-neighbor quantization."
---

# Godot 4.x Pixel Texture Pipeline Skill

Complete reference, CLI automation, and shader toolkit for authoring and verifying pixel-art games in Godot 4.3+ (2D, 3D low-poly, 2.5D FPS, and 2.5D Top-Down / HD-2D).

Master reference document: [`docs/godot-pixel-texture-rehberi.md`](file:///C:/Users/duggy/.agents/game-dev-skills/docs/godot-pixel-texture-rehberi.md).

---

## 🧭 Quick Decision Matrix

| Game Genre | Root Node | Source of Pixel Look | Critical 3 Settings |
| :--- | :--- | :--- | :--- |
| **2D** | `Node2D` | Canvas filter + stretch options | Default Filter = Nearest, Stretch Mode = `canvas_items`, Scale Mode = `integer` |
| **3D (low-poly)** | `Node3D` | Material filter + texel density | Material Texture Filter = `Nearest`, Mipmaps = `Off`, Shading = `Per-vertex` |
| **2.5D FPS** | `Node3D` + `CanvasLayer` | Sprite3D billboard + SubViewport render | Billboard = `Enabled`, Alpha Cut = `Discard`, SubViewport `stretch_shrink` |
| **2.5D Top-Down** | `Node2D` (Y-sort) or `Node3D` (HD-2D) | Y-sort sorting or Sprite3D billboard | `y_sort_enabled`, Sprite3D Billboard = `Fixed Y`, pivot = feet |

---

## ⚡ CLI Pipeline Tool (`tools/godot_pixel_tool.py`)

Run the dedicated automation tool from workspace root:

### 1. Apply Pixel-Perfect Project Settings
Automatically updates `project.godot` with Nearest default filter, integer scale, 2D transform pixel snapping, and disabled MSAA/ScreenSpaceAA:
```powershell
python tools/godot_pixel_tool.py apply-settings projects/<Project_Name> --mode fps
# Modes available: 2d, 3d, fps, topdown
```

### 2. Audit Project Integrity (10-Point Checklist)
Audits `project.godot`, `.import` files, `.gdignore` in raw folders, and materials:
```powershell
python tools/godot_pixel_tool.py check-integrity projects/<Project_Name>
```

### 3. Batch Generate / Patch `.import` Files
Guarantees `compress/mode=0` (Lossless), `mipmaps/generate=false`, and `detect_3d/compress_to=0` across all textures:
```powershell
python tools/godot_pixel_tool.py batch-import projects/<Project_Name>/sprites_2d
```

### 4. Batch Process & Quantize Textures (Pillow Engine)
Nearest-neighbor integer scaling, hard alpha snapping (threshold 128), and palette quantization (Pico-8, DB16, Sweetie16, GameBoy, or custom PNG):
```powershell
python tools/godot_pixel_tool.py batch-process --src raw_assets --dst projects/<Project_Name>/sprites_2d --scale 2 --palette sweetie16 --create-imports
```

### 5. Export Shaders & Scripts
Installs PSX retro spatial shader, 2D Bayer 4x4 dither shader, pixel-perfect camera, and auto-nearest scripts:
```powershell
python tools/godot_pixel_tool.py export-shaders projects/<Project_Name>/shaders
python tools/godot_pixel_tool.py export-scripts projects/<Project_Name>/scripts
```

---

## 📐 The Three Golden Rules

1. **One Palette Everywhere:** 16–64 locked colors across all assets. Export PNG only (no lossy JPG).
2. **Consistent Pixel Density (PPU):** Choose one PPU (e.g. 16, 32, 48) and never mix.
   * 2D: `zoom = Vector2(scale, scale)`
   * 3D / Sprite3D: `pixel_size = 1 / PPU` (PPU=32 $\to$ 0.03125 m/px).
   * 3D Walls: $\text{texel size} = \frac{\text{mesh length}}{\text{texture resolution}}$.
3. **Nearest Filtering at Every Layer:**
   * Project: `rendering/textures/canvas_textures/default_texture_filter = 0` (Nearest).
   * Material: `BaseMaterial3D.texture_filter = TEXTURE_FILTER_NEAREST` (0).
   * Shader: `sampler2D base_tex : source_color, filter_nearest`.

---

## 🎨 Shaders & Architecture

### PSX Retro Spatial Shader (`shaders/psx_retro.gdshader`)
* **Vertex Snapping:** NDC grid locking using `vertex_snap_res` (match to SubViewport height, e.g. 180 or 240).
* **Affine Texture Mapping:** Disables GPU perspective correction via `uv_affine / clip_w` for retro texture wobble.
* **Color Posterization:** Quantizes channels to `color_levels` (16–32).

### 2D Posterize + 4x4 Bayer Dither (`shaders/posterize_dither.gdshader`)
* Applies ordered Bayer matrix thresholding per pixel for classic CRT/GameBoy aesthetic.

---

## 🛠️ Troubleshooting Matrix

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| **Blurry 2D sprites** | Default project filter is Linear | Set `default_texture_filter = 0` via `apply-settings` |
| **Blurry 3D model** | Material defaults to Linear With Mipmaps | Run `set_nearest_materials.gd` EditorScript |
| **Texture turns into messy blocks** | VRAM Compressed import | Run `batch-import` to set `compress/mode = 0` (Lossless) |
| **Texture suddenly corrupts in 3D** | Godot's Detect 3D auto-reimport | Ensure `detect_3d/compress_to = 0` in `.import` |
| **Sprite3D z-fighting / sorting glitch** | Alpha Cut is Disabled (blend mode) | Set `Sprite3D.alpha_cut = DISCARD` (enum 1) |
| **Subpixel jitter during camera move** | Floating-point camera coordinates | Enable `snap_2d_transforms_to_pixel` & use `pixel_camera_2d.gd` (`floor()`) |
| **Uneven pixel widths on resize** | Fractional window scaling | Set `display/window/stretch/scale_mode = "integer"` |
