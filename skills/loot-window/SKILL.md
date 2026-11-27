---
name: loot-window
description: Build a crisp pixel art loot window with 9-sliced tiled frame, code-drawn rarity-colored slots, stack count digits, sequential reveal animation (chest shake, lid opening, warm glow + light shafts, per-rarity landing sparkles/rings, legendary 2-frame flash), and verified Godot 4 / Unity exports.
---

# Pixel Art Loot Window

Opening a chest should feel rewarding instead of dumping items into a flat panel. Build a pixel art loot window drawn at real art resolution (`222 x 172`) and scaled by an integer factor (`4x` nearest neighbor — see [pixel-perfect](../pixel-perfect/SKILL.md)), with a `96 x 96` 9-sliced frame, code-drawn rarity slots, staggered reveal choreography, and warm screen-blended glow shafts.

Reference verifier, renderer, and code exporter: [loot_window.py](../../tools/loot_window.py).

---

## 1. Pre-Code Project Audit (Inspect Before Writing Code)

Before writing UI or animation code, inspect the project for:
1. **Engine & UI scaling:** How UI containers/canvases scale to the window (must enforce integer nearest-neighbor scaling with zero fractional smoothing).
2. **Item data model:** Existing item fields (`id`, `icon`, `rarity`, `stack_count` / `quantity`). Keep the project's existing rarity names and colors if present.
3. **Chest actor/prop:** How chests animate, open, and emit loot payloads.
4. **Audio playback:** How SFX clips play and whether pitch shifting / pooling is already available.

**Rules:**
- Fit into the existing UI and inventory system rather than inventing a parallel UI stack.
- If item rarity definitions, chest art, or UI assets are missing, ask before inventing them or choose one of the explicit art options below.

---

## 2. Art Options & Asset Rules

### Option A — Use Existing UI Art
- Check the frame texture size and cut margin: a `96 x 96` piece cut **`16 px` in from each edge** leaves a `64 x 64` repeatable center and `16 px` corners/edges.
- Verify the border art repeats cleanly every `64 px` (rivets, wood grain, bevels) so tiling shows no seams.

### Option B — Flat Programmatic Placeholders (Instant Wireframe)
- Generate exact-dimension placeholder sprites in code (`tools/loot_window.py` builds these automatically for testing):
  - `frame_96x96.png` (`96 x 96`, `16 px` corner brackets, repeating border ticks, dark `#14101c` interior)
  - `title_plate_64x18.png` (`64 x 18`, centered `7 px` above window top)
  - `button_80x20.png` (`80 x 20`, centered at `y = 136`)
  - `chest_48x40.png` + 8-frame lid flip (`24 fps`)

### Option C — Per-Piece SpriteCook / Pixel Art Prompts + SFX
- Generate each piece separately (frame, title plate, claim button, chest base + 8-frame lid, 32x32 item icons).
- **Strict generation/import rules:**
  - Frame center MUST be opaque dark fill (or solid mask) — never leave an alpha hole that bleeds world noise behind text.
  - Never bake slot boxes into the frame art; slots are drawn in code so **one item icon works at any rarity**.
  - Import all UI textures as `Nearest` filter, `Lossless` / uncompressed, no mipmaps.
- **Audio & Pitch Variation:**
  - Chest rattle loop (`0.00s`–`0.60s`), heavy latch/creak (`0.76s`), low shimmer (`1.10s`), per-item pop/chime (`1.38s + 0.15 * n`) with rising pitch (`0.96 + 0.025 * slot_index` up to `~1.18`, plus higher chime tier on Epic/Legendary).

---

## 3. Exact Geometry, Colors & Reveal Timeline

### Layout Geometry (Art Pixels, `222 x 172` Base)
| Element | Exact Value | Notes |
|---|---|---|
| Window size | `222 x 172` px | Scaled by whole number (`4x` -> `888 x 688`, inside `1280 x 880` stage) |
| 9-slice source | `96 x 96` px, border `b = 16` px | Corners stay `16 x 16`; edges/center **repeat (`Tile`)**, never stretch |
| Title plate | `64 x 18` px | Horizontally centered, `7 px` above window top (`y = -7`) |
| Collect button | `80 x 20` px | Horizontally centered at `y = 136` |
| Slot grid | `5 x 3` slots (`15` total) | Origin `(20, 22)`, slot `34 x 34` px, gap `3 px` (`step = 37`) |
| Slot `i` formula | `x = 20 + (i % 5) * 37`, `y = 22 + (i // 5) * 37` | Slot `14` (`col=4, row=2`) sits at `(168, 96)` |
| Item icon | `32 x 32` px | `1 px` inset inside `34 x 34` slot |
| Stack count | `3 x 5` pixel digits | Bottom-right corner with `1 px` dark outline; hidden when count `<= 1` |
| Chest sprite | `48 x 40` px | Centered below/before reveal; 8-frame lid animation at `24 fps` |

### Rarity Palette & Landing FX
Before an item lands in slot `n`, the slot waits in **Common gray** (`#5e6878` border, `#8b96a6` corner/light, `#26212e` fill). Once the item lands, the slot shifts to its rarity palette and triggers particles:

| Rarity | Border | Light / Corner Pip | Fill | Sparkles | Expanding Rings | Flash |
|---|---|---|---|---|---|---|
| `common` | `#5e6878` | `#8b96a6` | `#26212e` | `0` | `0` | `0` frames |
| `uncommon` | `#3a7d3a` | `#6cbf4a` | `#1c2a22` | `4` | `0` | `0` frames |
| `rare` | `#2f6fc4` | `#64b3f0` | `#1b2440` | `6` | `3` px | `0` frames |
| `epic` | `#6d3aa8` | `#a974e0` | `#261c3a` | `8` | `5` px | `0` frames (border light runs every `1.4s`) |
| `legendary` | `#d9a440` | `#f2d16b` | `#33261a` | `14` | `5` px | **`2` frames** solid white `(255,255,255)` + dense-to-sparse rays (`0.5s`) |

### Reveal Choreography (`t` in seconds)
1. **`0.00s` — Chest Shake (`0.60s`):** Horizontal jitter ramping linearly from `1 px` to `3 px`.
2. **`0.76s` — Lid Open (`8 frames @ 24 fps`):** Plays lid open + `4 px` hop on the chest.
3. **`1.00s` — Window Appear (`0.22s`):** Fade alpha `0.0 -> 1.0` and slide `y: 6 -> 0` art px.
4. **`1.10s` — Warm Glow Behind Window:** Color `(255, 178, 84)`, elliptical radial falloff + `7` light shafts, **Screen blend** (`1 - (1 - dst)*(1 - src)`). Peaks in `0.18s`, settles to half intensity by `0.80s` after glow start (`t = 1.90s`).
5. **`1.38s + 0.15 * n` — Item Landing:** Item `n` (`0`-indexed) lands from above (`12` items -> first at `1.38s`, last at `3.03s`, span = `1.65s`). Slot switches from Common gray to item rarity, triggers sparkles/rings (+ 2-frame white flash on Legendary), and plays pitched chime.
6. **Reveal Off / Instant Skip (`reveal=False`):** Window alpha is `1.0` at `t = 0.0`, all items and final rarity borders render immediately with zero delay.

---

## 4. Core Implementation Snippets

### Tiled 9-Slice (Never Stretch)
```python
# src: 96x96, b = 16 -> center repeatable tile is 64x64
# Copy 4 corners (0..16, w-16..w) verbatim.
# Tile top/bottom strips along x using (sx = b + (x - b) % (src_w - 2*b)).
# Tile left/right strips along y using (sy = b + (y - b) % (src_h - 2*b)).
# Tile interior center along both x and y using modulo (src_w - 2*b, src_h - 2*b).
```

### Warm Elliptical Glow + 7 Light Shafts (Screen Blend)
```glsl
// Godot 4 CanvasItem fragment logic (exported cleanly by tools/loot_window.py):
float dist = length((UV - vec2(0.5)) / vec2(0.42, 0.34));
float ellip = exp(-dist * dist * 2.4);
float angle = atan(UV.y - 0.5, UV.x - 0.5);
float shafts = pow(0.5 + 0.5 * cos(angle * 7.0 + TIME * 0.25), 3.0) * 0.35;
vec3 glow = vec3(1.0, 178.0 / 255.0, 84.0 / 255.0) * clamp((ellip + shafts * ellip) * intensity, 0.0, 1.0);
// Set CanvasItemMaterial blend_mode = BLEND_MODE_SCREEN (or blend in shader)
```

---

## 5. Common Pitfalls

1. **Using `NinePatchRect` with `STRETCH` instead of `TILE`:** Stretching smears rivets and wood grain into blurry streaks. Always set `axis_stretch_horizontal = TILE` and `axis_stretch_vertical = TILE` (Godot) or `Image.Type.Sliced` with tiled borders (Unity).
2. **Fractional UI scaling (`1.5x`, `3.7x`):** Causes shimmering 1px slot outlines and broken 3x5 digits. Pair UI root with integer viewport scaling (`4x` or nearest whole multiplier).
3. **Hardcoding rarity frames as textures:** Forces duplicating every item icon per rarity. Draw the `34 x 34` slot borders and fills in code so icons stay rarity-agnostic.
4. **Leaving pre-landed slots already colored:** Spoils the surprise before the item drops. Keep unlanded slots Common gray until `t >= 1.38 + 0.15 * n`.
5. **No instant/skip toggle:** Clicking during reveal or disabling animations in accessibility settings must snap the window to `alpha = 1.0` with all loot visible immediately.

---

## 6. CLI Verification, Demo Render & Engine Export

Run the self-contained tool in `C:\Users\duggy\.agents\game-dev-skills`:

```bash
# Run all 8 automated geometric/timing/FX/nearest-scale checks
python tools/loot_window.py verify --json

# Print curated ElevenLabs/SFX prompts (material pickup + rarity drop + pitch range 0.92..1.08)
python tools/loot_window.py sfx-prompts --json

# Render crisp 4x preview (loot_window_preview.png)
python tools/loot_window.py demo --out exports/loot_window --scale 4 --json

# Export Godot 4 (LootWindow.gd + loot_glow.gdshader) or Unity (LootWindowSlot.cs)
python tools/loot_window.py export-code --engine godot4 --out-dir out/godot4 --json
python tools/loot_window.py export-code --engine unity --out-dir out/unity --json
```

### Bundled Placeholder Assets (`assets/`)
Exact-dimension pixel-art placeholders are bundled under [`assets/`](assets/) (`frame.png` 96×96, `title_plate.png` 64×18, `button.png` 80×20, `chest_closed.png` + `chest_lid_0..7.png` 48×40, and 6× 32×32 icons in `assets/icons/`).

### Verification Checklist (All 8 Checks Enforced by `verify`)
1. `nine_slice(96x96, 96, 96)` matches source pixel-for-pixel.
2. Top edge of `222 x 172` window repeats `x = 16..79` cleanly at `x = 80..143`.
3. Slot `14` (`col = 4, row = 2`) computes to exact origin `(168, 96)`.
4. With `12` items, last item lands `1.65s` after the first, and slot `11` stays Common `#5e6878` until its landing tick.
5. Sparkle counts match `(0, 4, 6, 8, 14)` and ONLY `legendary` runs a `2`-frame solid `(255, 255, 255)` white flash.
6. With reveal animation off, window alpha is `1.0` and all `12` items render at `t = 0.0`.
7. Last slot (`14`) fits inside `222 px` width and finishes above Collect button (`y = 136`).
8. 4× nearest-neighbor upscale contains strictly uniform `4×4` pixel blocks (zero bilinear blur).
