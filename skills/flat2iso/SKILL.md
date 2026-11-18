---
name: flat2iso
description: "Headless, zero-anti-aliasing 2:1 isometric (dimetric) pixel art converter and 4-direction box builder (Flat2Iso Studio). Supports column shifting (Lotovik/Incursio 1:1, 2:1, 3:1, 4:1, split-center, _stripN.png animation strips), 3/5-face orthographic-to-isometric box projection with inverse-mapped top diamonds, 3-face lighting with outline color preservation, depth-aware seams, logical pixel-scale auto-detection, --json machine-readable outputs, and an offline HTML studio."
---

# Flat2Iso Studio (`flat2iso`)

Converts flat orthographic 2D pixel art into crisp **2:1 isometric (dimetric, ~26.57°)** game sprites and **4-direction isometric boxes** with zero anti-aliasing (`tools/flat2iso.py` + offline UI at `skills/flat2iso/assets/flat2iso.html`).

---

## Core Pixel Rules (Enforced Automatically)

1. **Zero Anti-Aliasing / Nearest-Neighbor Only:** Every source pixel maps to an exact integer destination pixel. Upscaled inputs (e.g., 4× or 8× AI/preview renders) should pass `--scale auto` so they are reduced to 1× native pixel art before projection, then scaled back up with `--export-scale N` if needed.
2. **Parity Rule (`shift`):** Even sprite widths pair cleanly with even `--steps` (`2`, `4`); odd widths pair cleanly with odd `--steps` (`1`, `3`). `inspect` and `shift --json` report `parity_compatible` automatically.
3. **Box Dimension Contract (`box`):**
   - `front` = `W × H` (optional `back` = `W × H`, defaults to horizontal mirror of `front`)
   - `side` (right side) = `D × H` (optional `left` = `D × H`, defaults to horizontal mirror of `side`)
   - `top` = `W × D`, oriented so **bottom edge touches `front`** and **right edge touches `side`**.
4. **GameMaker / Godot Strip Conventions:**
   - Passing a `_stripN.png` (or `--frames N`) to `shift` shifts every frame independently and repacks a uniform-cell `_stripN.png` anchored bottom-center.
   - `box --sheet --sheet-mode strip4` exports all 4 rotations (`0°`, `90°`, `180°`, `270°`) into a uniform-cell `_strip4.png` ready for GameMaker or Godot `Sprite2D` (`hframes = 4`, `Nearest` texture filter).

---

## Headless AI-Friendly CLI (`tools/flat2iso.py`)

Always pass `--json` in agent pipelines to receive exact dimensions, detected scale, parity warnings, and output paths.

### 1. Inspect Scale & Parity (`inspect`)
```powershell
python tools/flat2iso.py inspect "path/to/sprite.png" --steps 2 --json
```

### 2. Column-Shift a Flat Sprite or `_stripN.png` (`shift`)
```powershell
# Standard 2:1 dimetric wall/tile rising to the right (auto-detect upscaled source):
python tools/flat2iso.py shift "path/to/wall.png" --steps 2 --direction right --scale auto --json

# Corner/pillar split from center column + 1px silhouette outline:
python tools/flat2iso.py shift "path/to/pillar.png" --steps 2 --direction split --outline -o exports/flat2iso/pillar_iso.png --json

# Animated strip (auto-detects _strip6 or pass --frames 6):
python tools/flat2iso.py shift "path/to/banner_strip6.png" --steps 2 --direction right --json

# Built-in 16x14 crate demo:
python tools/flat2iso.py shift --demo --outline --json
```

### 3. Build a 2:1 Isometric Box & 4-Direction Sheet (`box`)
```powershell
# Project Front + Side + Top with classic 3-face lighting, protected outlines & depth seams:
python tools/flat2iso.py box --front front.png --side side.png --top top.png --light std --seams --outline --sheet --sheet-mode strip4 --json

# Include explicit Back & Left faces and export all 4 rotations + strip4:
python tools/flat2iso.py box --front front.png --side side.png --top top.png --back back.png --left left.png --rot all --sheet --out-dir exports/flat2iso/crate --json

# Built-in 16x14x10 wooden crate demo (exports 4-dir _strip4.png):
python tools/flat2iso.py box --demo --seams --sheet-only -o exports/flat2iso/demo_box_strip4.png --json
```

### 4. Interactive & Scriptable HTML Studio (`serve` / `flat2iso.html`)
```powershell
python tools/flat2iso.py serve --port 8765
```
Or open `skills/flat2iso/assets/flat2iso.html` directly in any browser (100% offline, zero dependencies). The HTML studio has full 1:1 parity with `tools/flat2iso.py`:
- **Tab 1 — Column Shift:** Supports drag/drop/paste, `Auto` logical pixel-scale detection, `Strip frames` (`#shiftFrames`, auto-parsed from `*_stripN.png` filenames), parity check per frame, 1px silhouette outline, and `Send result to Box →`.
- **Tab 2 — Box Builder:** Validates `Front`/`Right Side`/`Top` (plus optional `Back`/`Left Side`) dimensions, applies 3-face lighting with outline protection & depth-aware seams, and exports either `Uniform _strip4.png` (bottom-center anchored cells ready for GameMaker or Godot `hframes = 4`) or `Compact preview sheet (2px gap)`.
- **Programmatic Browser API (`window.F2I`):** Exposes `{ columnShift, shiftStrip, packUniformStrip, buildBox, facesForRotation, buildBox4Dir, inspectPix, newPix, set, get, demoFront, demoSide, demoTop, detectScale, trim, addOutline, mirrorX, rot90 }` for Playwright/browser automation or unit verification.
