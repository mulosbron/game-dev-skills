---
name: see-through
description: "Keeps 2D characters visible behind trees, fog, miasma, walls, and roofs using six context-routed looks: Fade, 4x4 Bayer Dither, Dithered Fade (keep 6/16), Hard Cutout, Clipped Flat Silhouette (with Stealth Alarm-Red state), and 1 px Clipped Outline. Use whenever the player disappears under a canopy or behind a building, or when asked for see-through, dither window, cutout, or x-ray sprite occlusion in Godot 4, Unity, or Web/Canvas/Phaser (`tools/see_through.py`)."
---

# 2D See-Through Occlusion (`see-through`)

Keeps the player (or active target) visible when walking behind occluders in 2D top-down / Y-sorted games—opening **only** the object that actually covers the character, with zero wasted bounding-box triggers.

---

## 1. Scenario Routing Matrix (A / B / C / D)

Choose the look by gameplay context (or ask the user if unspecified):

| Context | Mode | Look & Why |
|---|---|---|
| **A — Single isolated tree / simple obstacle** | `FADE` | Lowers object opacity (`fade_to = 0.4`). Simplest 1-line look; only mode that alpha-blends colors. |
| **B — Fog, mist, or dense canopy zone** | `DITHER` | 4×4 Bayer ordered pixel drop (`clear_radius = 18`, `soft = 16`). Soft retro transition with **0 new off-palette colors**. |
| **C — Magic sphere, lantern, energy/miasma zone** | `CUTOUT` | Hard circular hole (`hole_radius = 22`, `soft = 0`). Reveals player **plus nearby enemies/loot** inside the clear zone. |
| **D — Stealth / walls / buildings** | `SILHOUETTE` | Leaves occluder intact and draws a clipped flat-color silhouette on top (`(118, 214, 255)` calm $\rightarrow$ **`(239, 68, 68)` alarm red** when `alert_ratio >= alert_threshold`). |

---

## 2. Pre-Code Project Audit (Always Do This First)

Before writing code, inspect the project and confirm:
1. **Engine & Language:** Godot 4, Unity, Phaser/Web, or custom renderer.
2. **Depth Sorting & Origins:** How Y-sorting works and whether sprite origins sit at the **feet/base** (`feet.y < obj.base_y` = behind). If centered, adjust to feet or warn before applying.
3. **Individual Sprites vs Tilemap Layer:** Tiles on one `TileMapLayer` share one opacity—if trees/roofs are on a single tilemap layer, tell the user before splitting or switching to per-object sprites/shader.
4. **Existing Shaders:** A sprite holds one material. If an occluder already uses a wind or outline shader, **merge** the Bayer pixel-drop block into that shader instead of overwriting `material`.
5. **Render Scale:** Check whether sprites render at `1×` art resolution or are scaled up in the scene (`pixel_scale > 1.0`).

---

## 3. Numbers That Matter (Tuned for `20 × 36 px` Character)

Scale radii proportionally with `char_height / 36.0`, expose all parameters as inspector/shader settings, and guarantee that `fade_to = 1.0` or `radius = 0` disables the effect cleanly:

- **Behind Depth Test:** `feet.y < object.base_y` (smaller `y` in a Y-down scene).
- **Cover Test:** `3 × 4` grid over the character box; triggers when **`>= 3` of `12` (`cover_needed = 0.25`)** points hit opaque pixels (`is_pixel_opaque` / alpha mask). *Exception:* `SILHOUETTE` uses bounding-box overlap because the clip mask handles exact pixel clipping.
- **Ease:** `0.2 s` linear `move_toward` in both directions (`12` frames at `60 fps`; `ease_time = 0` snaps immediately).
- **Fade:** `fade_to = 0.4` (`40%` opacity).
- **Dither:** `clear_radius = 18.0 px`, `soft = 16.0 px` (fully solid beyond `34 px`), 4×4 Bayer matrix per art pixel.
- **Cutout:** `hole_radius = 22.0 px`, `soft = 0.0`.
- **Silhouette:** Calm `(118, 214, 255)` (`#76D6FF`) $\rightarrow$ Stealth Alarm `(239, 68, 68)` (`#EF4444`) when `alert_ratio >= alert_threshold` (default `0.7`). Pick colors unused elsewhere in the scene.

---

## 4. CLI Pipeline (`tools/see_through.py`)

Always pass `--json` in agent workflows:

```powershell
# 1. Run 10-point automated verification suite (depth, 3/12 cover, 60fps ease, Bayer/Cutout radii, stealth alarm, null check)
python tools/see_through.py verify --json

# 2. Render 5-panel visual comparison strip (Fade, Dither, Cutout, Silhouette Calm, Silhouette Alarm Red)
python tools/see_through.py demo --out-dir exports/see_through --upscale 2 --json

# 3. Export Godot 4 & Unity scripts/shaders
python tools/see_through.py export-code --target all --out-dir exports/see_through/code --json
```

### Bundled References & Multi-Engine Runtime Scripts
- **Deep References (`references/`):** [`project-fit.md`](references/project-fit.md), [`algorithm.md`](references/algorithm.md), [`engines.md`](references/engines.md), [`pitfalls.md`](references/pitfalls.md), [`acceptance.md`](references/acceptance.md).
- **Godot 4 (`scripts/godot/`):** `see_through.gd`, `see_through_math.gd`, `see_through.gdshader`, `see_through_scaled.gdshader`, `flat_color.gdshader`, `outline.gdshader` (1 px clipped outline look).
- **Unity (`scripts/unity/`):** `SeeThroughOccluder.cs`, `SeeThroughWindow.shader`, `SeeThroughWindow.hlsl`, `SeeThroughFlat.shader`, `SeeThroughOutline.shader`.
- **Web / Canvas / Phaser (`scripts/web/`):** `see-through.mjs` (zero-dependency ESM runtime) + `see-through.test.mjs` (`node skills/see-through/scripts/web/see-through.test.mjs`).

### Exported CLI Templates (`tools/see_through.py export-code`)
- `godot4-script` (`see_through.gd`): Per-object `ShaderMaterial`, `is_pixel_opaque` 3×4 cover test, `CLIP_CHILDREN_AND_DRAW` ghost sync (`animation`, `frame`, `flip_h`), and stealth `alert_ratio` alarm-red switching.
- `godot4-window-shader` (`see_through.gdshader`): Unified `DITHER` (`soft > 0`) + `CUTOUT` (`soft = 0`) with `pixel_scale` division so scaled scenes keep crisp art-pixel Bayer dots.
- `godot4-flat-shader` (`flat_color.gdshader`): Flat silhouette tint for the clipped character ghost.
- `unity-window-shader` (`SeeThroughWindow2D.shader`): HLSL `clip()` equivalent for Unity 2D sprites.

---

## 5. Pitfalls & Verification Checklist

### Common Pitfalls
- **Bounding-box trigger on Fade/Dither/Cutout:** Triggers too early (~10 px outside foliage); always test feet depth + `3 × 4` opaque pixel cover first.
- **Dithering the entire sprite:** Causes flickering and visual noise; only dither a local window around `center = feet - (0, char_height * 0.5)`.
- **Scaled scenes without `pixel_scale`:** `floor(world)` shrinks Bayer dots below art pixel size unless divided by `pixel_scale`.
- **Leaving silhouette clip/ghost active at `amount == 0`:** Always disable `clip_children` and hide the single child ghost when `amount == 0`.

### Verification Checklist
- [ ] Feet level with or in front of `base_y`: stays off. `1 px` behind + covered: turns on.
- [ ] Inside object bounding box over transparent corner (`0` opaque pixels): stays off.
- [ ] `3 / 12` cover points hidden: on; `2 / 12`: off.
- [ ] At `60 fps` (`ease_time = 0.2`): `amount == 0.5` at frame `6`, `1.0` at frame `12`, `0.0` after `12` false frames.
- [ ] `DITHER` / `CUTOUT` add `0` off-palette colors and `0` half-transparent pixels; `SILHOUETTE` adds `1` flat color (calm or alarm red) clipped strictly to object pixels.
- [ ] Two objects, character behind only one: only the occluding object opens.
- [ ] `fade_to = 1.0` or `radius = 0` matches the plain scene pixel-for-pixel.
