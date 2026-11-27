---
name: shadowcasting
description: "2D shadowcasting (Bergstrom 8-octant stack FOV) for torchlight that stops at walls, fog of war (explored gray-blue vs never-seen black), and enemy line of sight in 2D top-down dungeons and 2D platformer caves/stealth. Use whenever the user mentions shadows blocking light, light passing/bleeding through walls, line of sight, enemy vision/detection, fog of war, explored map memory, torch/lantern radius, or roguelike visibility in Godot 4, Unity, TypeScript, or custom 2D engines — even if they never say 'shadowcasting' (`tools/shadowcasting.py`)."
---

# 2D Shadowcasting (Torchlight, Fog of War & Line of Sight)

Replaces naive radial lights that bleed through walls with **Bjorn Bergstrom's 8-octant stack-based shadowcasting**. One compact pass drives:
1. **Torchlight** that stops cleanly at walls while illuminating wall faces/tops (`+5 px` dilation).
2. **Fog of War** (`explored |= seen`) distinguishing live sight, cool gray-blue explored memory, and pitch-black unexplored space.
3. **Enemy Line of Sight (LOS)** across both **2D top-down** dungeons/stealth games and **2D platformer** caves, sentry cones, or ceiling/platform occluders.

---

## Pre-Code Project Audit

Before modifying existing lighting or AI code, inspect the project and fit into what is already there instead of building a duplicate grid system:

1. **Engine & language:** Godot 4 (`GDScript`/`.gdshader`), Unity (`C#`), TypeScript/Canvas/Phaser, or Python/Pygame.
2. **Wall / occluder representation:**
   - Single `TileMapLayer` / tile grid (extract solid wall booleans from tile physics or custom data).
   - **Dual-grid / marching squares** walls (note whether visual corners sit offset by `0.5` tiles from collision cells).
   - **2D Platformers:** Convert solid platform/cave tiles (`TileMapLayer` or merged static colliders) into the same boolean occluder grid; optionally mask shadowcast output by a directional facing cone for patrols.
3. **Existing lighting & fog layers:** Check whether `PointLight2D`, a full-screen `CanvasItem` shader, a multiplicative darkness `SubViewport`, or a tile overlay already renders light.
4. **Stealth fairness requirement:** Ask whether enemy vision must be strictly two-way symmetric (`enemy sees player <=> player sees enemy`). If yes, upgrade the slope checks to **Albert Ford symmetric shadowcasting** instead of standard Bergstrom.

---

## Core Algorithm & Exact Numbers

### 1. 8-Octant Stack Scan (`OCTANTS`)

Split the circle into eight 45-degree octants scanned identically via `(xx, xy, yx, yy)`:

```python
OCTANTS = [
    (1, 0, 0, 1),   (0, 1, 1, 0),   (0, -1, 1, 0),  (-1, 0, 0, 1),
    (-1, 0, 0, -1), (0, -1, -1, 0), (0, 1, -1, 0),  (1, 0, 0, -1),
]
```

- Always use **floating-point division** for cell slopes (never integer `/` truncation):
  - `left = (dx - 0.5) / (dy + 0.5)`
  - `right = (dx + 0.5) / (dy - 0.5)`
- Strict interior radius cutoff: `(dx * dx + dy * dy) < (radius * radius)`.
- Guard early on invalid inputs: if `radius <= 0` or origin `(ox, oy)` is outside `[0, width) x [0, height)`, return an empty mask with zero cells visible.
- Mark the origin cell `(ox, oy)` visible before scanning rows `1..radius`.

### 2. Stepped Torchlight & Wall-Top Dilation

- **Falloff:** `t = clamp(1.0 - dist_px / radius_px, 0.0, 1.0) ** 0.8`
- **Stepped pixel-art quantization (`6` bands):** `light = ceil(t * 6.0) / 6.0 * lit_mask` (`steps = 0` gives continuous smooth falloff).
- **Colors (linear `0..1`):**
  - `ambient = (0.045, 0.05, 0.09)` (cool dark indigo in unlit rooms)
  - `torch_color = (1.0, 0.80, 0.55) * 1.15` -> `(1.15, 0.92, 0.6325)`
- **Wall-top / dual-grid illumination:** Expand the pixelized `seen` mask into adjacent `wall` pixels by `5 px` at a `16 px` tile baseline (`seen_px | (dilate(seen_px, 5) & wall_px)`). Without this, front wall bricks and dual-grid rims stay muddy black right beside the torch.

### 3. Fog of War & Enemy Line of Sight

| State | Rule | Visual / Behavior |
|---|---|---|
| **Live Sight** (`seen`) | Recomputed every tick or grid step | Full torch + dynamic entities visible |
| **Explored Memory** (`explored & ~seen`) | `explored \|= seen` (monotonically grows) | Desaturated terrain: `scene.mean(-1, keepdims=True) * (0.30, 0.32, 0.40)`; dynamic enemies hidden |
| **Unexplored** (`~explored`) | Never seen yet | Pure black `(0, 0, 0)` |
| **Enemy LOS** | `has_line_of_sight(walls, ex, ey, px, py, radius)` | Same `shadowcast` check plus `(dx^2 + dy^2) < radius^2` (optional dot-product cone filter for directional guards / platformer sentries) |

---

## Common Pitfalls

- **Dual-grid / per-pixel alignment:** Lighting only whole `seen` cells makes front-facing wall edges or half-tile dual-grid bevels look abruptly clipped. Upscale to pixel resolution (or shader `fov_mask`) and dilate into walls by `~5 px` (`tile_size * 5 / 16`).
- **Integer division bugs:** Writing `(dx - 1) / (dy + 1)` with integers breaks octant slopes immediately in GDScript, C#, or C++. Cast explicitly to `float`.
- **Origin inside a wall or out of bounds:** An origin inside a wall (e.g., torch held in front of a character hugging a wall) lights only 8 neighbors (thick wall) or leaks through both sides (1-cell-thin wall). Always call `resolve_origin(walls, ox, oy)` first to shift to the nearest open floor cell, plus bounds-check every `(gx, gy)`.
- **Phantom 7th light band:** Floating-point `ceil(1.0 * 6)` can evaluate to `7` — always clamp `min(1.0, ceil(t * bands) / bands)`.
- **`walls` != movement grid:** `walls` means "blocks light", not "blocks movement" (half-height barriers block movement but not light; glass doesn't block light). Ask the user when unclear, and update + recast when doors open.
- **Clearing `explored` on recast:** Never clear `explored` on recast — it only ever grows (`explored |= seen`) and should be saved with the level.
- **2D Platformer differences:** Gravity pulls characters onto tiles whose collision edge may sit right under `feet_y`; cast from the character/torch chest/head tile (`center_y - 0.5 * tile`) rather than foot contact coordinates so floor tiles don't immediately self-occlude octant 0.
- **Asymmetric peeks in Bergstrom:** Bergstrom favors fast roguelike lighting where one tile at an oblique corner can occasionally be slightly asymmetric (`seen[B]` from `A` != `seen[A]` from `B`). For strict player-vs-guard stealth checks, enable **Albert Ford symmetric shadowcasting** (center-to-center + bevel-corner symmetric rules) so players never feel cheated behind cover.

---

## CLI Workflow (`tools/shadowcasting.py`)

```bash
# Run all 11 automated unit checks (octant counts, symmetry, single-wall shadow, corner bounds, vault leak, LOS, fog, toggle, resolve_origin, 6-band clamp)
python tools/shadowcasting.py verify --json

# Render side-by-side comparison PNGs (plain radial vs shadowcast + fog of war)
python tools/shadowcasting.py demo --out-dir exports/shadowcasting --json

# Render per-pixel light mask, banded light, fog walk & enemy sight from a real wall-layer PNG (ideal for dual-grid art)
python tools/shadowcasting.py render path/to/walls_layer.png --light 120 88 92 --enemy 210 88 --sight-range 80 --walk 60,88 90,88 --scale 3 --out-dir exports/shadowcasting/preview --json

# Export ready-to-paste engine code (godot4 GDScript + shader, unity C#, or typescript)
python tools/shadowcasting.py export-code --engine godot4 --out exports/shadowcasting/Shadowcast.gd
python tools/shadowcasting.py export-code --engine unity --out exports/shadowcasting/Shadowcast2D.cs
```

### Engine References & Evals
- **Godot 4:** [`references/godot4.md`](references/godot4.md) (`Shadowcast.gd` with `resolve_origin`, `ImageTexture` multiply shader, fog persistence, enemy LOS).
- **Unity:** [`references/unity.md`](references/unity.md) (`Shadowcast.cs` with bottom-up texture row-flip warning, `FilterMode.Point`, `Unlit/Multiply` shader).
- **Custom Engines (C++/SDL2/Raylib/LÖVE):** [`references/custom-engine.md`](references/custom-engine.md) (collision vs light-blocking grid separation, CPU/GPU composite).
- **Skill Evals:** [`evals/evals.json`](evals/evals.json) (Godot tilemap torch/fog, dual-grid per-pixel fix, enemy LOS one-way pitfall).

---

## Verification Checklist

When integrating shadowcasting into a project, confirm all 9 properties pass:
1. Empty `11x11` from `(5,5)` matches exact counts (`r=3 -> 25`, `r=4 -> 45`, `r=5 -> 69`) and is invariant under `90°` rotation.
2. Strict radius (`< r^2`): at `r=4`, `(8,5)` is visible (`3^2 < 16`) and `(9,5)` is not (`4^2 == 16`).
3. Single wall at `(7,5)` with `r=6`: `106` cells visible, wall `(7,5)` itself lit, `(8,5)`, `(9,5)`, `(10,5)` shadowed.
4. `7x7` all-walls grid from `(3,3)` at `r=3` lights exactly `9` cells (`(3,3)` + 8 neighbors).
5. Corner `(0,0)` on `6x6` at `r=4` lights `15` cells with no OOB errors; `radius <= 0` or OOB origin returns `0` cells.
6. Closed room with no door leaks `0` interior floor cells.
7. Enemy LOS across a blocking column returns `false`, and flips to `true` as soon as the doorway tile opens.
8. Fog `explored` state grows monotonically and renders memory in gray-blue `(0.30, 0.32, 0.40)` and unseen cells in pure black.
9. Disabling shadowcasting cleanly restores standard unoccluded radial falloff.
