# Engine integration notes

Read the section that matches the user's engine. The math is identical everywhere; only the final "set this tile" call differs.

## Godot (4.x, TileMapLayer)

The Wang index maps straight to atlas coordinates:

```gdscript
# h_edges[r][c] is the top edge of cell (r, c); v_edges[r][c] the left edge.
func wang_tile(r: int, c: int) -> int:
    return h_edges[r][c] + 2 * v_edges[r][c + 1] + 4 * h_edges[r + 1][c] + 8 * v_edges[r][c]

# after building the atlas as a TileSet with one source, 4x4 atlas coords in index order:
layer.set_cell(Vector2i(c, r), source_id, Vector2i(i % 4, i / 4))
```

- Godot's y points down and matches the pseudo code's row order — no flip needed.
- Put the 16 tiles in one TileSet atlas source, 4 columns x 4 rows, in index order (column = i % 4, row = i / 4). Integer division.
- For a looping map, generate edges with `rows` x `cols` arrays and wrap `(r + 1) % rows` / `(c + 1) % cols`.

## Unity (Tilemap, y points up)

Keep the 16 tiles in an array in index order and flip the row:

```csharp
int top    = hEdges[r, c];
int bottom = hEdges[r + 1, c];
int left   = vEdges[r, c];
int right  = vEdges[r, c + 1];
int i = top + 2 * right + 4 * bottom + 8 * left;
tilemap.SetTile(new Vector3Int(c, -r, 0), wangTiles[i]);
```

- The `-r` is the whole Y-axis trap: Unity tilemaps grow upward. If top and bottom get swapped, the ground looks mirrored and seams show. Double-check with the debug overlay before shipping.
- Store `hEdges` as `int[rows + 1, cols]` and `vEdges` as `int[rows, cols + 1]`.
- If sprites are individual tiles (not one atlas sprite), just order the array 0..15; if they are one atlas, slice with `Sprite.Create` or a `Grid` sprite sheet import with 4x4 and full rect.

## Phaser / PixiJS / custom HTML5 canvas

```js
// index -> atlas source rect, 4x4 atlas of tilePx x tilePx
const i = wangTile(r, c);
const sx = (i % 4) * tilePx, sy = Math.floor(i / 4) * tilePx;
ctx.drawImage(atlasCanvas, sx, sy, tilePx, tilePx, c * tilePx - camX, r * tilePx - camY, tilePx, tilePx);
```

- y points down; no flip.
- If the game already blits one terrain tile per cell, this is a drop-in change of the source rect only.

## LÖVE (Love2D)

```lua
local i = wangTile(r, c)
local col, row = i % 4, math.floor(i / 4)
local q = love.graphics.newQuad(col * T, row * T, T, T, atlasW, atlasH)
love.graphics.draw(atlas, q, c * T, r * T)
```

## Infinite / chunked worlds — hash-based edges

Do not store edges. Each edge color is one bit from a hash of its integer coordinates plus the world seed. Because the hash depends only on world-space position, any chunk can recompute the edges it shares with its neighbors and they always agree — no chunk-to-chunk communication, no seams at chunk borders.

```python
import hashlib, struct

def hash_edge(seed: int, x: int, y: int, horizontal: bool) -> int:
    # horizontal=True -> the h edge above cell (x, y), i.e. between cells (x, y-1) and (x, y)
    # horizontal=False -> the v edge left of cell (x, y), i.e. between cells (x-1, y) and (x, y)
    key = struct.pack("<qqqB", seed, x, y, 1 if horizontal else 0)
    return hashlib.sha256(key).digest()[0] & 1

def wang_tile_hash(seed: int, x: int, y: int) -> int:
    top    = hash_edge(seed, x, y, True)
    bottom = hash_edge(seed, x, y + 1, True)
    left   = hash_edge(seed, x, y, False)
    right  = hash_edge(seed, x + 1, y, False)
    return top + 2 * right + 4 * bottom + 8 * left
```

Rules that keep it consistent:

- **Coordinate convention matters.** An h edge lives at integer y between cells y-1 and y; a v edge at integer x between cells x-1 and x. Pick this once and never change it — a different convention in two places silently desynchronizes neighbors.
- The seed must be the same for every chunk and every session. Derive it from the save/world id, never from `time()` or `random`.
- Hash per edge, not per cell: hashing per cell and reusing its bits for edges breaks the "colors live on edges" property and neighbors disagree at chunk borders.
- 50/50 split comes free from taking one bit of a cryptographic hash.

## Where to hook in

The integration point is wherever the current code chooses the terrain tile, e.g.:

- A `set_ground_tile(r, c)` / `_update_tile()` / `paintCell()` function: replace the single atlas coordinate with the Wang lookup.
- A chunk mesher or tile builder: same, per cell, using the hash mode for edge colors.
- If the terrain id per cell lives in a separate data layer (Godot: another TileMapLayer; Unity: a serialized ground map), read the terrain id from it and apply Wang tiles only to cells whose terrain id matches the tiled one. Transition tiles keep handling the borders.
