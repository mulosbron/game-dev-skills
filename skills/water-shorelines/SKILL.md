---
name: water-shorelines
description: "Replaces flat 2D top-down water with pixel-grid distance field shorelines: depth bands (shoal, shallow, mid, deep), breathing foam lines, and incoming coastal wave rings baked once per level or chunk using Felzenszwalb-Huttenlocher 2D Euclidean Distance Transforms and smooth wobble noise. Covers pre-code project audit, Godot 4 (ShoreDistance.gd + canvas_item shader), Unity (Point-filtered Sprite shader), TypeScript/Web 2D, incremental dirty-window coast updates, chunk border margins, and automated EDT/band/foam verification (`tools/water_shorelines.py`)."
---

# 2D Water Shoreline Distance Fields (`water-shorelines`)

Transforms flat single-color 2D water into dynamic **depth bands, breathing coastal foam, and incoming wave rings** driven by an 8-bit per-pixel Euclidean distance map baked at level load (never per frame).

---

## 1. Pre-Code Project Audit (Always Do This First)

Before writing code, inspect the project and confirm:
1. **Engine & Language:** Godot 4 (`TileMapLayer` / `SubViewport` / GDScript), Unity (`Tilemap` / C#), Phaser / Web Canvas / Custom engine.
2. **Drawing & Scaling Setup:** Tile size, art resolution, screen scaling (`canvas_items` / integer scale / camera zoom), and whether land and water share an origin.
3. **Land Mask Transparency Check (Critical):**
   - Are the land tiles **transparent (`alpha == 0`) where the water is**?
   - **If water is painted directly into the land tiles:** **Stop and ask the user** before guessing—offer:
     1. Build the mask from per-tile land masks or key out the water color (`--mask-mode chroma --key-color #RRGGBB`), or
     2. Generate/replace with a top-down land tileset with transparent water edges (`generate2dmedia` / `generate2dsprite`, or SpriteCook MCP if available).
4. **Static vs Dynamic Coast:** Does the coastline change during play (digging, land placement) or stream in chunks?

Fit into the existing layer order: draw the distance-field water sprite/layer **under** the existing land layer at the exact same origin and art-pixel resolution.

---

## 2. Numbers That Matter (Tuned at `16 px` Tiles)

Scale distances proportionally if `tile_size != 16` (`scale = tile_size / 16.0`), expose them as shader uniforms/settings, and document where they live:

| Parameter | Default (`16 px` tile) | Notes |
|---|---|---|
| `MAX_DIST` | `32.0 px` | Must match identically in bake and shader (`8-bit` step = `1/8 px`). |
| `Wobble` | `~±3 px` | Gaussian white noise (`sigma = 8 px`, `std = 2 px`) or `FastNoiseLite` (`FRACTAL_NONE`, `freq = 0.03`, `* 4.0`). |
| `Depth bands` | Shoal `< 5`, Shallow `< 13`, Mid `< 26`, Deep `>= 26` | Evaluated in art pixels (`texture(TEXTURE, UV).r * max_dist`). |
| `Foam` | `d < 2.2 + 1.1 * sin(time * 2.5)` | Breathes out and back every `~2.5 s` (`1 px` to `3 px` on straight coast). |
| `Waves` | Spacing `11.0 px`, Speed `4.4 px/s`, Thickness `1.6 px` | Visible only in `4.0 < d < 20.0 px`; moves toward coast, repeats every `2.5 s`. |

### Default 6-Color Water Palette (Unless Project Has Its Own)
- `deep`: `#1C4A80` (`vec4(0.110, 0.290, 0.502, 1.0)`)
- `mid`: `#226296` (`vec4(0.133, 0.384, 0.588, 1.0)`)
- `shallow`: `#348CB0` (`vec4(0.204, 0.549, 0.690, 1.0)`)
- `shoal`: `#60BEC4` (`vec4(0.376, 0.745, 0.769, 1.0)`)
- `wave`: `#96D6DA` (`vec4(0.588, 0.839, 0.855, 1.0)`)
- `foam`: `#ECF6F4` (`vec4(0.925, 0.965, 0.957, 1.0)`)

---

## 3. CLI Pipeline (`tools/water_shorelines.py`)

Always pass `--json` in agent workflows for machine-readable output paths and verification reports.

```powershell
# 1. Bake 8-bit grayscale distance map from a transparent-water land PNG (+ preview & 5px contour debug)
python tools/water_shorelines.py bake path/to/land_layer.png -o exports/water_shorelines/shore_distance.png --preview exports/water_shorelines/preview.png --contour-debug exports/water_shorelines/contour.png --json

# 1b. Run built-in 360x322 sand island + cove demo
python tools/water_shorelines.py bake --demo --preview exports/water_shorelines/demo_preview.png --contour-debug exports/water_shorelines/demo_contour.png --save-land exports/water_shorelines/demo_land.png -o exports/water_shorelines/demo_dist.png --time 0.4 --json

# 2. Render frames (or flat-water A/B comparison / band-only debug)
python tools/water_shorelines.py render exports/water_shorelines/demo_dist.png --land exports/water_shorelines/demo_land.png --time 0.4 -o exports/water_shorelines/frame.png --json

# 3. Incremental coast edit (recomputes 2*MAX_DIST window, writes back MAX_DIST region)
python tools/water_shorelines.py update-region --land updated_land.png --dist-map shore_distance.png --bbox 96,96,128,128 -o shore_distance_updated.png --json

# 4. Run automated verification suite (EDT vs brute-force, bands, waves, foam, 6-color check, chunk seams)
python tools/water_shorelines.py verify --json

# 5. Export Godot 4 / Unity / TypeScript baker & shader files
python tools/water_shorelines.py export-code --target all --out-dir exports/water_shorelines/code --json
```

---

## 4. Runtime, Dynamic Coasts & Chunked Worlds

1. **Godot 4 Runtime Bake + Shader:**
   - Export `shore_distance.gd` (`ShoreDistance.bake(land_image)`) and `water_shoreline.gdshader`.
   - For `TileMapLayer`: render the land layer once in a transparent `SubViewport`, read `get_texture().get_image()`, assign `ShoreDistance.bake(img)` to a `Sprite2D` under the land layer, and set **`texture_filter = Nearest`**.
2. **Unity:**
   - Use an Unlit Sprite Shader (or Shader Graph) with the baked `R8` texture set to **`FilterMode.Point`** and sample at art resolution.
3. **Changing Coasts (Digging / Building):**
   - Recompute the distance transform on a bounding window expanded by **`2 × MAX_DIST`** around the edit, and copy back **only** the inner window within **`MAX_DIST`** of the edit (`tools/water_shorelines.py update-region`).
4. **Chunked / Infinite Worlds:**
   - Bake each chunk with **`MAX_DIST` pixels of neighbor land** padded around all 4 sides, crop back to the chunk interior, and sample wobble from **world-space coordinates** (`--wobble-mode world --world-offset x,y --margin-crop 32`) so bands never break at chunk borders.

---

## 5. Pitfalls & Verification Checklist

### Common Pitfalls
- **No wobble:** Bands copy every stair-step of the coastline and look like an outline.
- **Per-tile distance:** Computing distance on the tile grid instead of art pixels makes blocky bands that ignore actual sand edges.
- **Linear texture filtering:** Produces thin smooth curves between pixels instead of crisp pixel-art bands. Keep `1 texel = 1 art pixel` with `Nearest` / `Point` filtering.
- **Origin/size mismatch:** The water distance sprite must match the land layer's origin and pixel dimensions.

### Verification Checklist (Before Accepting)
- [ ] **Brute-force EDT parity:** `tools/water_shorelines.py verify` passes `edt_matches_bruteforce` (`max_pixel_error == 0.0`) and `chunked_margin_seam_match` (`max_diff_vs_full_bake == 0`).
- [ ] **Band accuracy:** With wobble, waves, and foam disabled, pixels at `4, 12, 25, 27 px` match `shoal`, `shallow`, `mid`, `deep`.
- [ ] **Wave & foam bounds:** Waves only appear in `4 < d < 20 px` and repeat every `2.5 s`; straight-coast foam is `1 px` at min and `3 px` at max.
- [ ] **Pixel-grid palette audit:** Screenshot of the water contains strictly the 6 water colors (no blended anti-aliased edge pixels).
- [ ] **Toggle check:** Disabling the shader/effect cleanly restores the original flat water.
