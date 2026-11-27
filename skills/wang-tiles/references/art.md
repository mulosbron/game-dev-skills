# Wang tile art

The skill needs **one 4 x 4 atlas of 16 tiles in index order** (column = index % 4, row = floor(index / 4)), tile size matching the project's tile size. Three ways to get it, cheapest first. Present them to the user when the art is missing and let them choose.

## Option 1 — Free 32 px grass set

A ready 128 x 128 atlas (32 px tiles, index order, orange/blue edge bars in the guide picture):

`https://www.spritecook.ai/blog/wang-tiles-explained/wang-grass-tiles-32px.png`

Use only if the terrain really is grass and the tile size is 32 px. Verify the layout against the index formula before trusting it (spot-check tile 6: top 0, right 1, bottom 1, left 0 → column 2, row 1).

## Option 2 — Cut a set from one seamless texture (recommended)

Works for any material — grass, sand, stone floor, dirt — from a single seamless top-down texture of the terrain. `tools/wang_tiles.py cut` does the whole procedure:

```
python tools/wang_tiles.py cut texture.png --tile-size 32 -o atlas.png --seed 0 --json
```

What it does, and why:

1. **Pick one source spot per edge color.** Two spots for the top/bottom (h) colors, two for the left/right (v) colors. It picks the **plainest** T x T windows automatically (lowest gradient energy), because detail in an edge strip repeats at regular steps all over the map and builds a new grid. You can override with `--anchors h0x,h0y,h1x,h1y,v0x,v0y,v1x,v1y`.
2. **Cut each edge strip from its color's spot.** A tile's top strip starts at its top color's spot row; the tile above cuts its bottom strip ending right above that row. Two neighbors therefore continue the same patch of texture across the edge they share — that is what makes the seam invisible. Left/right work the same way. All strips of one color come from that color's single anchor, so every combination joins.
3. **Give every tile its own middle.** 16 different middle patches (seeded, spread out, away from the edge anchors) — this is where the variety comes from.
4. **Minimum-error boundary cut** (image quilting, Efros & Freeman 2001): each strip is joined to the tile's middle along a dynamic-programming path with the smallest color difference, instead of a straight line. The joins follow the grass instead of running in straight lines.

Notes on the output:

- **Horizontal edge matching is pixel-perfect everywhere.** Vertical edges match except inside the small corner overlap squares (up to `--overlap` px, default 8, at the four cell corners), where the h strip wins the boundary pixel. On organic textures (grass, sand, stone) this is invisible; on hard-edged, structured art, lower `--overlap` or hand-fix the corners.
- The script prints the anchors and middle spots it chose; feed them back via `--anchors`/`--mids` to reproduce or tweak a set.
- The source texture should be seamless (tiling). If it is not, the map is still grid-free but tiles will not wrap around a looping map's border.

After cutting, run the acceptance test:

```
python tools/wang_tiles.py map --atlas atlas.png --tile-size 32 --rows 24 --cols 24 --seed 1 -o map.png --debug-overlay map_debug.png --json
```

It asserts edge-color consistency and renders the map; open the PNG and look at it zoomed out — no seams, no rows or columns lining up, and with `--debug-overlay` every shared edge shows two bars of the same color.

## Option 3 — Generate the texture first, then cut

If image-generation tools are available in the session (e.g. an image-generation skill or MCP tool), generate a seamless top-down texture of the terrain first — prompt for "seamless tileable top-down pixel art grass texture, even base material, no large distinctive features" — then cut it exactly as in Option 2. Generation rarely produces a truly seamless texture; if the borders don't wrap, still cut from it (the map won't loop, but the interior is grid-free).

## Art rules that prevent a new grid

- **Edge strips from plain spots only.** A flower in a strip lands on about half the edges in its direction and lines up into a lattice. This is the single most common way a Wang set still shows a pattern.
- **No loud feature in a middle.** A rock or dark clump repeats wherever that tile lands, about once every 16 cells. Keep tiles to the even base material; place rocks, bushes, flowers as separate decoration objects/instances.
- **Big shapes don't fit in a tile.** Patches wider than one tile must be their own terrain with transition tiles, not squeezed into the Wang set.
- **Two colors per direction is usually enough.** Three colors would give 3^4 = 81 tiles — more variety, a lot more art to check.

## If the project already has tiles

- 16 tiles but not in index order: build a lookup table from (top, right, bottom, left) to the tile's atlas coordinates. Verify by hand on a small map with the debug overlay.
- More than 16 tiles (e.g. a 47-tile blob autotile set): those are corner-based autotiles, not edge Wang tiles. They can still work — map the 16 edge cases onto the matching autotile pieces — but the simplest correct path is a proper 16-tile atlas.

Source and full illustrated guide: https://www.spritecook.ai/blog/wang-tiles-explained
