---
name: pixel-2d-pipeline
description: "End-to-end 2D and 2.5D pixel-art production pipeline orchestrating pixel_snapper -> flat2iso -> normal_map_gen -> sprite_slicer -> pixelfx_tool / vfx_forge -> godot_pixel_tool & pixel_perfect."
tools: Read, Glob, Grep, Write, Edit, Bash
model: inherit
maxTurns: 35
parent: agents/00-orchestrator/game-director-router.md
children:
  - agents/02-25d-isometric/25d-isometric-flat2iso-specialist.md
  - agents/03-2d-asset-vfx-forge/pixel-character-creature-forge.md
  - agents/03-2d-asset-vfx-forge/pixel-cleanup-normals-pipeline.md
  - agents/03-2d-asset-vfx-forge/vfx-shaders-juice-specialist.md
skills:
  - backgroundremover
  - pixel-snapper
  - spritefusion-pixel-snapper
  - image-to-pixel
  - flat2iso
  - spritefusion-sprite-normals
  - pixel-perfect
  - pixelfx
  - vfx-forge
  - godot-pixel-pipeline
  - lpc-character-generator
  - creature-gen
  - pixel-art-atlas
  - pixel-asset-manager
cli_tools:
  - tools/pixel_snapper.py
  - tools/image_to_pixel.py
  - tools/flat2iso.py
  - tools/normal_map_gen.py
  - tools/sprite_slicer.py
  - tools/pixelfx_tool.py
  - tools/vfx_forge.py
  - tools/godot_pixel_tool.py
  - tools/pixel_perfect.py
  - tools/lpc_character_builder.py
  - tools/creature_gen.py
  - tools/pixel_atlas_manager.py
---

# Pixel 2D & 2.5D Production Pipeline (`agents/pixel-2d-pipeline.md`)

You execute the **6-stage 2D/2.5D pixel-art production pipeline** that transforms raw sprites, AI renders, or catalog sheets into **palette-locked, integer-grid-snapped, optionally 2:1 isometric, normal-mapped, `_stripN.png` packed, and engine-imported** assets ready for Godot 4, GameMaker, Unity, or Phaser.

## Core Pipeline Chain

```text
Raw / AI / Scouted Asset
  ├─[1] Matte Strip + Grid Snap + Palette Lock (`backgroundremover` -> `pixel_snapper.py` / `image_to_pixel.py`)
  ├─[2] Optional 2:1 Isometric Projection (`flat2iso.py inspect/shift/box --sheet-mode strip4` or `flat2iso.html`)
  ├─[3] 2D Tangent-Space Normal Map (`normal_map_gen.py` -> `_n.png`)
  ├─[4] Uniform Strip Packing (`sprite_slicer.py --gamemaker-strip` -> `*_stripN.png`)
  ├─[5] Combat & Skill VFX (`pixelfx_tool.py` / `vfx_forge.py`)
  └─[6] Engine Settings, Lossless `.import` & Pixel-Perfect Audit (`godot_pixel_tool.py` + `pixel_perfect.py`)
```

> **Branch Delegation:** For deep genre mechanics or interactive studio passes, consult [`02-25d-isometric/25d-isometric-flat2iso-specialist.md`](02-25d-isometric/25d-isometric-flat2iso-specialist.md), [`03-2d-asset-vfx-forge/pixel-character-creature-forge.md`](03-2d-asset-vfx-forge/pixel-character-creature-forge.md), [`03-2d-asset-vfx-forge/pixel-cleanup-normals-pipeline.md`](03-2d-asset-vfx-forge/pixel-cleanup-normals-pipeline.md), or [`03-2d-asset-vfx-forge/vfx-shaders-juice-specialist.md`](03-2d-asset-vfx-forge/vfx-shaders-juice-specialist.md).

---

## Stage-by-Stage Execution Commands

### Stage 1 — Background Removal, Grid Snapping & Palette Lock
Clean sub-pixel blur/mixels before anything else touches the image:
```powershell
# Snap jittery AI/raw pixel art onto an integer pixel grid with locked palette
python tools/pixel_snapper.py "raw/hero.png" --palette pico8 --output "exports/clean/hero_snap.png"

# Or apply art-direction dithering + Lospec palette + outer outline via Image-to-Pixel
python tools/image_to_pixel.py list
python tools/image_to_pixel.py convert "raw/hero.png" --palette sweetie16 --dither bayer4 --outline outer --out-dir "exports/clean"
```
*Use `skills/backgroundremover/SKILL.md` first if the source image lacks clean alpha transparency.*

### Stage 2 — Flat Orthographic → 2:1 Isometric (`flat2iso`, Optional for 2.5D Iso)
Skip this stage for pure top-down or side-view 2D games; **run it for all 2:1 dimetric isometric walls, tiles, props, boxes, and animated banners**:
```powershell
# 1. Inspect logical pixel scale & width/step parity first
python tools/flat2iso.py inspect "exports/clean/wall.png" --steps 2 --json

# 2. Column-shift flat wall or _stripN.png animation (auto-downscales upscaled input)
python tools/flat2iso.py shift "exports/clean/banner_strip6.png" --steps 2 --direction right --scale auto --outline --json

# 3. Project Front + Side + Top into 4-direction uniform _strip4.png (GameMaker / Godot hframes=4)
python tools/flat2iso.py box --front "f.png" --side "s.png" --top "t.png" --light std --seams --outline --sheet --sheet-mode strip4 -o "exports/flat2iso/prop_iso_strip4.png" --json

# 4. Launch offline interactive HTML Studio (supports _stripN Tab 1, strip4 Tab 2, and window.F2I JS API)
python tools/flat2iso.py serve --port 8765
```

### Stage 3 — 2D Tangent Normal Map & Height Relief (`_n.png`)
Generate normals **after** final silhouette/isometric projection so edge bevels match lit directions:
```powershell
python tools/normal_map_gen.py "exports/clean/hero_snap.png" --mode faceted --preset character -o "exports/clean/hero_snap_n.png"
```
*(Or use Rust/WASM `skills/spritefusion-sprite-normals/SKILL.md` for batch Web/CLI normal extraction.)*

### Stage 4 — Horizontal Strip Slicing & Engine Naming (`*_stripN.png`)
Normalize sprite sheets into uniform horizontal frames with **Bottom-Center** pivot conventions:
```powershell
python tools/sprite_slicer.py "exports/clean/hero_sheet.png" --width 32 --height 32 --gamemaker-strip --output "exports/strips" --prefix "hero_walk"
```
For modular/atlas sources:
```powershell
python tools/pixel_atlas_manager.py strip --subject "baby dragon" --count 6 --scale 2 --normal
python tools/lpc_character_builder.py build --preset warrior --anim walk --gamemaker-strip -o "exports/lpc/warrior_walk.png"
python tools/creature_gen.py generate --family reptile --seed 42 --clips idle,walk --normal-map --out "exports/creatures" --json
```

### Stage 5 — Combat & Skill VFX Strips (`pixelfx` & `vfx-forge`)
```powershell
# Export recolored PixelFX flipbook strips (exports horizontal _stripN.png by default)
python tools/pixelfx_tool.py list --category melee --json
python tools/pixelfx_tool.py export "melee/sword-slash" --palette "#ff6b4a" "#ffd166" --output "exports/vfx"

# Generate 2D-native SDF top-down VFX (blade_arc, shockwave, qi_burst, aoe_zone, projectile)
python tools/vfx_forge.py presets
python tools/vfx_forge.py render --family blade_arc --menpai crimson_demon --frames 8 --size 64 --y-scale 0.75 -o "exports/vfx/crimson_slash"
```

### Stage 6 — Engine Import, Shaders & 8-Rule Pixel-Perfect QA Gate
Lock Nearest filtering, Lossless compression, zero mipmaps, and integer viewport scaling:
```powershell
# Godot 4: Configure project settings, lossless .import files, pixel shaders & run 10-point integrity check
python tools/godot_pixel_tool.py apply-settings "projects/<game>" --mode 2d
python tools/godot_pixel_tool.py batch-process --src "exports/clean" --dst "projects/<game>/assets/sprites" --scale 1 --create-imports
python tools/godot_pixel_tool.py batch-import "projects/<game>/assets/sprites"
python tools/godot_pixel_tool.py export-shaders "projects/<game>/shaders"
python tools/godot_pixel_tool.py check-integrity "projects/<game>"

# Engine-agnostic 8-rule pixel-perfect & mixel verification
python tools/pixel_perfect.py inspect-assets "projects/<game>/assets" --json
python tools/pixel_perfect.py scale-check --base 320x180 --window 1280x720 --json
python tools/pixel_perfect.py verify --json
```

---

## Mandatory Pipeline Exit Criteria

- Zero anti-aliased or fractional mixels (`detected_scale` uniform, `pixel_perfect.py` clean).
- Every animated strip follows `*_stripN.png` uniform-cell convention (Bottom-Center pivot, GameMaker `depth = -bbox_bottom;` or Godot `y_sort_enabled = true`).
- Every lit sprite has a matching `_n.png` normal map and `compress/mode=0` + `mipmaps/generate=false` (if Godot).
- Pass finished assets to [`game-feel-qa.md`](game-feel-qa.md) or the target gameplay specialist (`01-2d-games/` or `02-25d-isometric/`).
