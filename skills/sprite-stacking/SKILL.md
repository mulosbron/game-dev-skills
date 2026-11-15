---
name: sprite-stacking
description: Sprite stacking for fake-3D rotating pixel art cars, props, and buildings in top-down games. Includes 4-view orthographic visual-hull slicer (minimal 2-file slices_strip.png + preview.gif output by default), Godot 4 / Unity / Canvas draw_stack templates, camera squash & spacing tuning, and tools/sprite_stacker.py verifier.
---

# Sprite Stacking (Fake-3D Rotating Pixel Art)

Turn top-down cars, props, and buildings to any angle from one horizontal slice strip (`ground` slice on the left, `top` slice on the right), lifted `1 px` per height layer and rotated together with **Nearest-neighbor** sampling.

---

## Pre-Code Project Audit (Mandatory)

Before writing code, inspect the project and fit into what is already there instead of building a separate rendering pipeline:
1. **Engine & language:** Godot 4 (`Node2D._draw()`), Unity (`SpriteRenderer` stack / `RenderTexture`), Phaser/Canvas, or custom engine.
2. **Sorting & pixel scale:** Check how objects are sorted today (always sort **whole stacks by their ground contact `pos.y`**, never slice-by-slice) and keep positions snapped to **whole screen pixels**.
3. **Art readiness — ask the user if no slice sheet exists yet:**
   1. **MagicaVoxel / voxel editor:** Export layers directly as a horizontal slice strip.
   2. **Four orthographic flat views (`top`, `side`, `front`, `back`):** Carve voxel slices via visual hull (`tools/sprite_stacker.py slice --sheet views.png` or `--views ...`).
   3. **Image-gen 2x2 sheet (e.g. Nano Banana Pro / `gemini-3-pro-image`, pixel art mode, `32x32`):** Ask for strictly orthographic 2x2 layout (Top pointing **DOWN**, Side pointing **LEFT**, Front, Back), bold `1 px` dark outline, flat solid fills, no perspective/shadows/labels. Verify before slicing: Top view is tallest, Side view is widest and faces left.

---

## Core Numbers & Pseudo Code

- **Strip order:** Ground slice (`z = 0`) on the left, top slice (`z = count - 1`) on the right.
- **Spacing:** `1.0` screen px per slice (`lift_y = -round(z * spacing)`). Setting `spacing = 0, squash = 1` flattens all slices to height `h` with the top slice on top.
- **Camera squash:** `0.75` for a lower angled top-down camera (`1.0` = straight down; below `~0.6` roofs get thin).
- **Reference car (`15` slices of `24 x 43 px`):** `squash=1` covers `24 x 52 px` (`24 x 57` for full-height box); `squash=0.75` covers `24 x 41 px`; turned `90°` covers `43 px` wide.
- **Heading from velocity (down-facing sheet `+y`):**
  ```text
  turn = atan2(velocity.y, velocity.x) - PI / 2
  ```
  When reversing, drive `turn` from the vehicle's **heading** rather than velocity vector so it does not flip backwards `180°`.

```text
function draw_stack(sheet, count, pos, turn, squash = 0.75, spacing = 1.0):
    w = sheet.width / count
    h = sheet.height
    rect = (-floor(w / 2), -floor(h / 2), w, h)
    for z in 0 .. count - 1:
        transform = translate(round(pos))
                  * translate(0, -round(z * spacing))
                  * scale(1, squash)
                  * rotate(turn)
        draw_region(sheet, source = (z * w, 0, w, h), dest = rect, transform, filter = NEAREST)
```

---

## Common Pitfalls

- **Outlines inside the body:** Keeping a `1 px` dark outline inside every stacked slice draws dark speckles/lines through the middle on diagonals. Strip outlines from input views (`--outline-strip auto`), disable per-slice borders, and draw **one outline around the finished stack** (e.g. offscreen buffer / `SubViewport` or `render --outline on`).
- **Soft art smears:** Soft anti-aliased edges, gradients, and 1-px stripes blur when rotated and overlapped; keep flat fills and `>= 2 px` stripes.
- **Slow-turn pixel jitter:** Nearest-neighbor rotation steps visibly on low-res sprites. Render at a larger integer scale (`--scale 6`–`10`) or test RotSprite (`Scale2x` 8x) on long straight silhouettes (note: RotSprite rounds tiny vehicles).
- **Overhangs & truck beds fill in:** Carving from 4 flat orthographic silhouettes cannot carve concave hollows/arches underneath spoilers or pickup beds — edit those slices manually after carving.
- **Static props performance:** Never re-draw hundreds of static stacked trees/crates every frame; bake static props once at load time (`render --turn DEG`) into plain sprites.

---

## CLI Workflow (`tools/sprite_stacker.py`)

By default, `slice` and `demo` produce **only 2 clean files** (`slices_strip.png` + `preview.gif`) instead of flooding disk with ~200 individual slice/frame files (pass `--emit-all` only if you explicitly want `slices/`, `frames/`, `turntable.png`, and `meta.json`).

```bash
# Run all 6 automated pixel/dimension/heading/carve tests
python tools/sprite_stacker.py verify --json

# Slice a 4-view orthographic sheet into slices_strip.png + rotating preview.gif
python tools/sprite_stacker.py slice --sheet views.png -o out/ --shade 0.25 --colors 24 --scale 6 --json

# Slice 4 individual view files (top faces down, side faces left)
python tools/sprite_stacker.py slice --views top.png side.png front.png back.png -o out/ --json

# Bake a single static angle PNG from an existing strip
python tools/sprite_stacker.py render --strip out/slices_strip.png --slices 15 --turn 35 --squash 0.75 --outline on -o out/baked.png

# Generate demo voxel car (slices_strip.png + preview.gif)
python tools/sprite_stacker.py demo -o exports/sprite_stack_demo --scale 6 --json

# Export engine code (godot4 Node2D, unity SpriteRenderer stack, typescript Canvas)
python tools/sprite_stacker.py export-code --engine godot4 --out SpriteStack2D.gd
```

---

## Verification Checklist

1. `squash=1, turn=0` output matches manual bottom-to-top `1 px` slice pasting pixel-for-pixel (`width == w`, box `height == h + count - 1`).
2. `squash=0.75` output is shorter than `squash=1`; `turn=90°` width equals `slice_height` (`43 px`).
3. `spacing=2` is taller than `spacing=1`; `spacing=0, squash=1` flattens cleanly to `height == h` matching the top slice.
4. Moving in a circle computes `atan2(vy, vx) - PI / 2` across all 4 quadrants and preserves heading when reversing.
5. Four-view carving produces non-empty slices (`outline_stripped == True`) and writes only `slices_strip.png` + `preview.gif` in default minimal mode.
6. Final stack outlining touches only outer rim pixels, leaving interior slice fills untouched.
