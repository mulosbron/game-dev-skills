---
name: pixel-perfect
description: Configure 2D pixel art games so every game pixel renders as a crisp square of identical integer size (fixes blurry Linear filtering, lumpy fractional scaling, and mixed-size mixels). Covers 384x216 / 320x180 integer_scale math, GCD pixel_size mixel detection, all 8 pixel-perfect rules, Godot 4 viewport/integer/Nearest/snap setup + PixelAudit.gd, Unity Pixel Perfect Camera + Point/Lossless setup, Web Canvas offscreen blitting, and tools/pixel_perfect.py verifier.
---

# Pixel-Perfect Rendering Setup (Rules, Integer Scale & Audit)

Pixel art looks blurry, lumpy while panning, or pasted-together when rendering settings violate whole-number pixel grids. Fix the project settings **first** before touching art or game code, keeping existing assets and base resolution intact.

> **Related Skills:** Use [godot-pixel-pipeline](../godot-pixel-pipeline/SKILL.md) for Godot batch `.import` patching and PSX/Bayer dithering shaders, and [pixel-snapper](../pixel-snapper/SKILL.md) when rebuilding irregular AI sprites onto an integer grid.

---

## Pre-Code Project Audit (Mandatory)

Inspect these before changing code or resizing sprites:
1. **Engine & version:** Godot `4.2+` (supports `scale_mode = "integer"`), Unity (Built-in / URP 2D), Web Canvas / Phaser / custom engine.
2. **Current window, viewport, import & camera settings:** Check stretch mode, filter mode, mipmaps, compression, camera zoom, and UI scaling. Change project settings **before** code.
3. **Art pixel sizes:** Run `python tools/pixel_perfect.py inspect-assets <dir> --json` to compute `pixel_size(image)` for sprites and tiles. **If the project has mixed pixel sizes or irregular AI grids, list the offending files and ask the user before resizing anything.**

---

## Why Art Breaks & Exact Numbers

| Symptom | Root Cause | Fix & Numbers |
|---|---|---|
| **Blurry** | Linear texture filter, mipmaps, or lossy compression blends neighbors | Texture filter **Nearest** (`Point` in Unity), **Lossless** (`Compression None`), **Mipmaps Off** everywhere |
| **Lumpy / Crawling** | Fractional stretch (`5.45x`) makes alternating `5 px` and `6 px` columns | Scale by **integer multiples** only, centered with black bars (`integer_scale`) |
| **Pasted / Mixels** | One sprite scaled `2x` or UI at `2x` over a `1x` world | Keep **one pixel size** across sprites, tiles, VFX, particles, and UI (`scale = 1`; sign flips `-1` allowed) |

### Reference Base Resolutions
- **`384 x 216`**: `1080p -> 5x (0, 0)`, `4K -> 10x (0, 0)`, `1440p -> 6x` with `(128, 72)` black bars, `1366x768 -> 3x` with `(107, 60)` bars.
- **`320 x 180`**: Fills `1080p` (`6x`), `1440p` (`8x`), and `4K` (`12x`) with zero bars.

---

## The 8 Pixel-Perfect Rules

1. Texture filter **Nearest** everywhere; no mipmaps, no lossy compression on sprites.
2. One base resolution, scaled only by whole numbers (`max(1, min(floor(W/bw), floor(H/bh)))`), black bars for leftovers (**never** stretch to fill bars).
3. Snap camera and sprite positions to whole game pixels when drawing.
4. One pixel size everywhere: total node/parent scale magnitude `== 1` (`(-1, 1)` flips are valid).
5. No runtime sprite rotation except `90°` multiples (`0°, 90°, 180°, 270°`) or pre-drawn rotations.
6. Pixel fonts rendered at native size with antialiasing disabled (`FONT_ANTIALIASING_NONE`).
7. Particles and VFX rendered on the exact same pixel grid.
8. Measure `pixel_size(image)` against `1x` tiles before adding new assets (`gcd` of horizontal/vertical equal-color run lengths).

---

## Engine Setup

### Godot `4.2+` (`project.godot` + Runtime Audit)
```ini
[display]
window/size/viewport_width=384
window/size/viewport_height=216
window/size/window_width_override=1920
window/size/window_height_override=1080
window/stretch/mode="viewport"
window/stretch/scale_mode="integer"

[rendering]
textures/canvas_textures/default_texture_filter=0
2d/snap/snap_2d_transforms_to_pixel=true
2d/snap/snap_2d_vertices_to_pixel=true
```
- Import sprites **Lossless**, fonts **Antialiasing = None**.
- Setting project defaults does **not** catch nodes with manual `Linear` overrides, scaled parents, `30°` rotations, fractional `Camera2D.zoom`, or default antialiased labels -> run `PixelAudit.audit(get_tree().root)` exported via `tools/pixel_perfect.py export-code --engine godot4`.

### Unity (`2D` / `URP`)
- Sprites: `Filter Mode = Point (no filter)`, `Compression = None`, `Generate Mip Maps = Off`, uniform `Pixels Per Unit` everywhere.
- Camera: `Pixel Perfect Camera` set to base resolution + same `Pixels Per Unit`; Quality/URP `Anti Aliasing = Disabled`.

### Web / Custom Engines
- Render the entire game + HUD to an offscreen target at `(base_w, base_h)`, then blit once to `(bar_x, bar_y)` at `scale` with `NEAREST` / `ctx.imageSmoothingEnabled = false` and CSS `image-rendering: pixelated`.

---

## Pitfalls

- **Parent scaling propagates:** Checking only `node.scale` misses a clean child under a `1.5x` parent — always check `global_scale` / `lossyScale`.
- **Per-node filter overrides:** Default `Nearest` does not override a Sprite/Material explicitly set to `Linear`.
- **AI "pixel art" false `1`:** Diffusion models produce misaligned irregular clusters, so `pixel_size()` often returns `1` even when blocks look chunky. Flag those assets to the user rather than blind nearest-downscaling.
- **2x HUD over 1x gameplay:** Always render UI inside the base-resolution viewport.

---

## CLI Workflow (`tools/pixel_perfect.py`)

```bash
# Run all 5 automated checks (resolutions, GCD pixel_size 1/2/1, 1366x768 bars & uniform 3x3 blocks, 6-offender scene audit, default-project 5-error audit)
python tools/pixel_perfect.py verify --json

# Evaluate integer scales and black bar sizes for any base resolution
python tools/pixel_perfect.py scale-check --base 384x216 --window 1366x768 --json

# Scan PNG assets to report native dimensions & GCD pixel_size (catches 2x mixels)
python tools/pixel_perfect.py inspect-assets path/to/sprites --json

# Export Godot 4 (PixelAudit.gd + project.godot block), Unity (PixelPerfectAudit.cs), or Web (pixelViewport.ts)
python tools/pixel_perfect.py export-code --engine godot4 --out-dir exports/pixel_perfect --json
```
