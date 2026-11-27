---
name: wang-tiles
description: "Eliminates visible tile grid repetition and repeating ground patterns across 2D game terrains (grass, sand, stone floor, water interiors) using 2-color edge-matched 16-tile Wang sets. Use whenever the user mentions Wang tiles, edge-matched tiles, tilemap repetition, a visible grid on ground/terrain, ground texture variety, cutting tiles from a seamless texture, or procedural/chunked terrain tiling in Godot 4, Unity, Phaser/PixiJS, LÖVE (Love2D), or custom engines — even if they never say 'Wang' (`tools/wang_tiles.py`)."
---

# Edge Wang Tiles (`wang-tiles`)

Replaces single-tile repetition across large terrain interiors with **16 edge-matched Wang tiles** (`2 × 2 × 2 × 2`) so ground surfaces have zero visible lattice or repeating patterns without searching, backtracking, or fallback tiles.

> **Role Separation Rule:** Edge Wang tiles add organic variety **inside one solid terrain**. Where two terrains meet (e.g., grass-to-dirt or shore), keep your **autotile / dual-grid transition tileset** and fill the solid interior with Wang tiles.

---

## 1. Pre-Code Project Audit (Always Do This First)

Before writing game code, inspect the user's project and report:
1. **Engine & Language:** Godot 4 (`TileMapLayer` / GDScript), Unity (`Tilemap` / C#), Phaser / Web Canvas (TS/JS), LDtk / Tiled, or custom renderer.
2. **Existing Ground Pipeline:** Current tile size (e.g., `16`, `32`), coordinate convention (Y-down vs Y-up), whether maps are finite, looping, or streamed in chunks, and whether an autotile/transition layer already exists.
3. **Existing Art Check:** Does the project already have a 16-tile (`4 × 4`) Wang atlas?
   - **Yes (in index order):** Wire directly via `col = i % 4`, `row = floor(i / 4)`.
   - **Yes (custom order):** Build an explicit `(top, right, bottom, left) -> tile_coord` lookup table; never assume layout order.
   - **No:** Present the **3 Art Options** below (cheapest first) and confirm which the user wants.

### Art Acquisition Options (Cheapest First)
1. **Ready-made 32 px 4×4 grass atlas / demo:** Use an existing project sheet, `https://www.spritecook.ai/blog/wang-tiles-explained/wang-grass-tiles-32px.png` (if online/approved), or synthesize a test meadow via `python tools/wang_tiles.py cut --demo`.
2. **Cut 16 tiles from one seamless terrain texture:** Run `python tools/wang_tiles.py cut <texture.png> --tile-size 32 --preview-map 20x20 --json`. Auto-selects the plainest edge strips and stitches middles with Efros & Freeman minimum-error boundary cuts.
3. **Generate a seamless top-down base texture first:** Generate via `generate2dmedia` / `generate2dsprite` (or SpriteCook MCP if available in session), snap/quantize with `tools/pixel_snapper.py` if needed, then cut the 4×4 atlas with `tools/wang_tiles.py cut`.

---

## 2. Core Math & Contract

- **Colors live on the edges between cells**, not on the cells themselves (`0` or `1`).
- **Horizontal edges** (`h_edges`, tops/bottoms) and **vertical edges** (`v_edges`, left/right sides) are independent sets. A top `0` and a left `0` are different edges.
- **Canonical 4-bit Index (`0..15`):**
  ```text
  index = top + 2 * right + 4 * bottom + 8 * left
  ```
- **4×4 Atlas Coordinates:**
  ```text
  atlas_col = index % 4
  atlas_row = floor(index / 4)
  ```
- **Guarantee:** Because all 16 combinations exist, every cell has **exactly one** valid tile. Neighboring cells share the exact same edge array entry / hash bit, so shared seams always match.

---

## 3. Placement Variants

### A) Finite Stored Map (`rows × cols`)
Generate edges **once** per map from a seed (never per-frame or on every draw):
- `h_edges[rows + 1][cols]` (`h_edges[r][c]` = top edge of cell `(r, c)`)
- `v_edges[rows][cols + 1]` (`v_edges[r][c]` = left edge of cell `(r, c)`)

### B) Looping / Toroidal Map (`rows × cols`)
Allocate `h_edges[rows][cols]` and `v_edges[rows][cols]`, then wrap the far edge:
- `bottom = h_edges[(r + 1) % rows][c]`
- `right  = v_edges[r][(c + 1) % cols]`

### C) Infinite / Chunked World (Stateless Edge Hash — Recommended for Streaming)
Do **not** store edge arrays across chunks. Compute each edge bit deterministically from `(world_seed, edge_x, edge_y, axis)` (`axis=0` horizontal, `axis=1` vertical) using a 64-bit SplitMix hash:
- Cell `(r, c)` reads:
  - `top    = edge_color(seed, c, r, 0)`
  - `bottom = edge_color(seed, c, r + 1, 0)`
  - `left   = edge_color(seed, c, r, 1)`
  - `right  = edge_color(seed, c + 1, r, 1)`
- Adjacent chunks evaluate identical inputs on shared borders and agree without inter-chunk communication.

---

## 4. CLI Pipeline (`tools/wang_tiles.py`)

Always pass `--json` in agent workflows for machine-readable coordinates, seam MAE metrics, and invariant checks.

```powershell
# 1. Cut a 4x4 Wang atlas from one seamless texture + render a 20x20 zoom-out preview & debug overlays
python tools/wang_tiles.py cut path/to/seamless_grass.png --tile-size 32 --preview-map 20x20 --debug-atlas exports/wang_tiles/debug_atlas.png --debug-map exports/wang_tiles/debug_map.png -o exports/wang_tiles/grass_wang.png --json

# 1b. Run built-in 280x298 pixel-art meadow demo
python tools/wang_tiles.py cut --demo --tile-size 32 --preview-map 20x20 --debug-atlas exports/wang_tiles/demo_debug_atlas.png -o exports/wang_tiles/demo_atlas.png --json

# 2. Generate & verify a deterministic map / chunk (finite, looping, or chunked)
python tools/wang_tiles.py map --mode chunked --rows 20 --cols 20 --chunk-x 1 --chunk-y -2 --seed 42 --atlas exports/wang_tiles/demo_atlas.png --debug-overlay exports/wang_tiles/chunk_debug.png -o exports/wang_tiles/chunk.png --json

# 3. Audit an existing 4x4 Wang atlas (64 H + 64 V joins), map JSON, and/or math self-test
python tools/wang_tiles.py verify --selftest --json
python tools/wang_tiles.py verify --atlas exports/wang_tiles/demo_atlas.png --tile-size 32 --json

# 4. Print drop-in engine code (godot4, unity, typescript, python, love2d)
python tools/wang_tiles.py snippet --engine godot4 --json
python tools/wang_tiles.py snippet --engine love2d --json
```

### References & Evals
- **Art & Cutting Guide:** [`references/art.md`](references/art.md) (3 art acquisition options, plainest-spot anchor rules, Efros & Freeman quilting, 47-tile blob autotile note).
- **Engine Integration Notes:** [`references/engines.md`](references/engines.md) (Godot 4 `TileMapLayer`, Unity Y-up `-r` flip, Phaser/PixiJS/Canvas, LÖVE/Love2D, stateless chunk hashing).
- **Skill Evals:** [`evals/evals.json`](evals/evals.json) (Godot repeating grass, atlas cutting + verification, Unity infinite chunked Y-up world).

---

## 5. Engine Integration Rules & Pitfalls

| Engine / Layer | Critical Rule |
|---|---|
| **Godot 4 (`TileMapLayer`)** | `layer.set_cell(Vector2i(col, row), source_id, Vector2i(tile % 4, tile / 4))`. Use `Nearest` texture filter (`godot-pixel-pipeline`). |
| **Unity (`Tilemap`)** | Unity's Y axis points **up**: map row `r` to `new Vector3Int(col, -r, 0)` with `wangTiles[tile]`. **Do not swap top and bottom.** |
| **Tiled / LDtk / Web** | Keep `tile_indices` as data; use `col = idx % 4`, `row = Math.floor(idx / 4)` for spritesheet lookup. |

### Pitfalls to Prevent
1. **Busy / Floral Edge Strips:** An edge strip lands on ~50% of edges in its direction—a flower or rock on an edge strip creates a brand-new visible grid. Always cut edge strips from the **plainest** part of the texture (`tools/wang_tiles.py cut` auto-scores `2*edge_width × tile_size` bands to avoid busy regions).
2. **Loud Middle Features:** A rock or bright clump in one tile's middle repeats ~1 in 16 cells. Keep Wang tiles to the even base material and scatter rocks, flowers, and bushes on a separate prop/decoration layer.
3. **Oversized Shapes:** Features wider than `tile_size` (e.g., large dark grass patches) get sliced off inside a single tile. Model large terrain regions as a separate terrain with autotile transitions.
4. **Regenerating Edges Every Frame:** Causes flickering ground. Generate once per map or hash from `(world_seed, edge_x, edge_y, axis)`.
5. **Scope Creep to 3 Colors:** 3 colors per direction requires `3^4 = 81` tiles—stick to 2 colors (16 tiles) unless specifically requested.

---

## 6. Verification Checklist (Before Accepting)

- [ ] **Neighbor Invariant Assert:** Across the entire map (and wrapped borders if looping, or chunk boundaries if chunked), `left.right == right.left` and `top.bottom == bottom.top` for every adjacent pair (`mismatch_count == 0`).
- [ ] **Debug Overlay Inspection:** Render with orange (`0`) / blue (`1`) edge bars (`--debug-map` / `--debug-overlay`) and confirm every shared edge shows two bars of the **same color**.
- [ ] **20×20 Zoom-Out Check:** Inspect a `≥ 20 × 20` rendered preview zoomed out—zero visible grid lines, zero seams, no repeating flowers/rocks forming rows or columns.
- [ ] **Atlas Seam Audit:** `tools/wang_tiles.py verify` reports clean dimensions (`4*T × 4*T`) and low spatial edge variance.
- [ ] **Seed Determinism:** Running the same `seed` twice produces identical `tile_indices`.
