---
name: atmospheric-perspective
description: "Adds atmospheric perspective (distance haze) to 2D parallax platformers and 2.5D / Limbo-style layered games by blending each background plane toward the average RGB color of the sky on its matching vertical row, plus base mist for mountain ridge separation and global strength control. Use whenever the user mentions atmospheric perspective, haze, distance fade, depth cueing, parallax depth, layers looking flat or too sharp, far mountains looking like a wall behind the trees, 'my background looks flat', 'add depth to my parallax', or 'make mountains fade into the sky' in Godot 4, Unity, or custom 2D engines (`tools/atmospheric_perspective.py`)."
---

# Atmospheric Perspective for 2D Parallax & 2.5D Depth (`atmospheric-perspective`)

Pushes distant background layers into depth by blending each layer pixel-by-pixel toward the **sky color directly behind its row** (`sky_rows[row]`) while keeping alpha solid and keeping the playable ground/character at full contrast. Works identically for **2D parallax platformers** and **2.5D / Limbo-style depth-card side-scrollers** (using a moody twilight/monochrome sky gradient).

---

## 1. Pre-Code Project Audit (Always Do This First)

Before writing code, inspect the project and confirm:
1. **Engine & Language:** Godot 4 (`Parallax2D`, `ParallaxBackground`, `Sprite3D` 2.5D cards), Unity, Phaser/Web, or custom renderer.
2. **Layers & Scroll Speeds / Z-Depth:** List existing layers, their `scroll_scale` (or Z distance in 2.5D), draw order, and whether they accept custom shaders. Fit into existing layers—**keep scroll speeds, layer order, and art**.
3. **Sky Source:** Image, vertical gradient, or flat color. If there are no separate layers or no sky, **ask the user before inventing them**.
4. **Cropped / Atlas / Vertically Moving Layers:** Row-aligned `UV.y` lookup assumes each layer shares the sky's height and Y origin. If layers are cropped, packed in an atlas, or shift vertically relative to the sky, switch lookup to screen row (`SCREEN_UV.y`) and tell the user.
5. **Pre-Baked Haze Check:** If any layer already has haze/blue tint painted in, warn the user (it cannot be turned down later). When generating new layers with AI (`generate2dmedia` / SpriteCook MCP), include `"no haze, no fog, no blue tint"` plus the shared style line in every prompt.

---

## 2. Tested Numbers by Scroll Speed (`global_strength` `[0..1]`)

Start from the closest background line and leave sky (`0.03`) and ground/player (`1.0`) at `0`:

| Layer | Scroll Speed | `amount` | `mist` (at `art_bottom`) |
|---|---|---|---|
| Sky | `0.03` | `0.00` (none) | `0.00` |
| Far snowy peaks | `0.08` | `0.80` | `0.20` |
| High clouds | `0.10` | `0.74` | `0.00` |
| Jagged range | `0.13` | `0.66` | `0.22` |
| Lower range | `0.19` | `0.52` | `0.22` |
| Cloud bank | `0.23` | `0.46` | `0.00` |
| Forested ridge | `0.27` | `0.40` | `0.20` |
| Hills | `0.38` | `0.28` | `0.00` |
| Trees right behind player | `0.60` | `0.04` | `0.00` (more washes out play area) |
| Playable ground & player | `1.00` | `0.00` (none) | `0.00` |

### 2.5D / Limbo-Style Depth Planes
- Arrange silhouetted/toned art cards along `-Z` (e.g. `Sprite3D` / `QuadMesh` in Godot `Node3D` or Unity 3D orthographic/narrow-FOV camera).
- Map Z-distance to `amount` (`0.04..0.85`, keeping playable plane at `0.0`) and use a moody twilight/monochrome sky gradient as `sky_colors` (`SCREEN_UV.y` lookup via `atmospheric_25d_card.gdshader`).
- Because `mix` pulls both lights and darks toward the sky row instead of multiplying or fading alpha, overlapping dark planes separate cleanly without ghosting.

---

## 3. CLI Pipeline (`tools/atmospheric_perspective.py`)

Always pass `--json` in agent workflows:

```powershell
# 1. Run 6-point automated verification suite
python tools/atmospheric_perspective.py verify --json

# 2. Render before/after comparison demos (daylight 2D or limbo 2.5D)
python tools/atmospheric_perspective.py demo --style daylight --out-dir exports/atmospheric_perspective --upscale 2 --json
python tools/atmospheric_perspective.py demo --style limbo --out-dir exports/atmospheric_perspective --upscale 2 --json

# 3. Bake static atmospheric haze into one layer (+ clean patchy dark AI outlines)
python tools/atmospheric_perspective.py bake-layer --sky sky.png --layer far_peaks.png --amount 0.80 --mist 0.20 --clean-outline --save-sky-rows sky_rows.png -o far_peaks_hazed.png --json

# 3b. Batch-bake an entire parallax stack from a layers.json manifest (see assets/layers.example.json)
python tools/atmospheric_perspective.py bake-stack --sky sky.png --layers layers.json --out-dir exports/atmospheric_perspective/hazed --save-sky-rows exports/atmospheric_perspective/sky_rows.png --composite exports/atmospheric_perspective/preview.png --json

# 4. Fix patchy dark exterior outlines on a far silhouette layer only
python tools/atmospheric_perspective.py clean-outline far_peaks.png -o far_peaks_clean.png --json

# 5. Export Godot 4 (2D + 2.5D Limbo card) & Unity shaders/scripts
python tools/atmospheric_perspective.py export-code --target all --out-dir exports/atmospheric_perspective/code --json
```

### Engine References, Example Manifest & Evals
- **Godot 4:** [`references/godot.md`](references/godot.md) (`atmospheric_perspective.gdshader`, `hazed_layer.gd` with `material.duplicate()` and `get_used_rect()`, `Parallax2D` setup).
- **Unity:** [`references/unity.md`](references/unity.md) (Shader Graph `Sprite Unlit` node recipe + URP HLSL fragment shader).
- **Batch Manifest Template:** [`assets/layers.example.json`](assets/layers.example.json) (tested 10-layer scroll-speed config for `bake-stack`).
- **Skill Evals:** [`evals/evals.json`](evals/evals.json) (Godot `Parallax2D`, custom JS Canvas export bake, Unity `SpriteRenderer` depth).

---

## 4. Pitfalls & Verification Checklist

### Common Pitfalls
- **Single horizon haze color:** Makes high far peaks paler than the deeper blue sky directly behind them—always look up `sky_rows[row]`.
- **Lowering opacity (`alpha`):** Makes mountains semi-transparent ghosts with layers behind showing through.
- **Multiplying / `modulate`:** Only darkens, keeping harsh shadows and contrast on far layers instead of pushing them back.
- **Hazing the playable layer:** Keep `ground`, platforms, and characters at `0.0`.
- **Sharing one `ShaderMaterial`:** Duplicate material per layer (`material = material.duplicate()`) so each layer keeps its own `amount`, `mist`, `art_top`, and `art_bottom`.
- **Patchy dark outlines on far peaks:** Read as dotted lines in the distance—replace border pixels with interior neighbor fill via `clean-outline`.

### Verification Checklist
- [ ] `amount = 0, mist = 0`: output matches source art pixel-for-pixel.
- [ ] `amount = 1`: every opaque pixel equals `sky_rows[row]` RGB.
- [ ] `amount = 0.80, mist = 0.20`: top art row blend `k = 0.80 + 0.20 * 0.5 / (art_bottom - art_top)` matches within `1/255` per channel.
- [ ] Alpha channel is identical before and after (`max_alpha_diff == 0`).
- [ ] Ground and player are untouched with effect on vs off.
- [ ] `global_strength = 0` restores the original un-hazed background.
