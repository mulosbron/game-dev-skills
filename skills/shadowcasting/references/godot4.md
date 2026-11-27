# Godot 4 — shadowcasting, light, fog of war and enemy sight

Tested on Godot 4.6. Three pieces: a static `Shadowcast` class, an
`ImageTexture` light/fog multiplied over the scene in a `canvas_item` shader,
and a one-line enemy sight check.

## Deciding what to cast on

- Art drawn on the tile grid (plain tileset, walls aligned to cells) → cast
  **per tile**: `w`/`h` are the TileMapLayer's cell counts.
- Dual-grid tiles, freehand wall sprites, or any art not on the tile grid →
  cast **per pixel** on the wall layer image. Per-tile visibility scaled up
  gives square light that cuts through the drawn walls.
- If the project already uses Godot 2D lights with `LightOccluder2D`
  polygons, STOP and ask the user before adding a second system.

## Building the walls grid

```gdscript
# From a wall layer Image (opaque pixel = wall):
var walls := Shadowcast.from_image(wall_image)

# From a TileMapLayer (a cell with any source is a wall):
var walls := PackedByteArray()
walls.resize(map_w * map_h)
for y in map_h:
	for x in map_w:
		walls[y * map_w + x] = 1 if wall_layer.get_cell_source_id(Vector2i(x, y)) != -1 else 0
```

`walls` means "blocks light", not "blocks movement": update it when a door
opens, then recast.

## shadowcast.gd

```gdscript
# shadowcast.gd: which cells a light (or an enemy's eyes) at `origin` can see.
# Use: var seen := Shadowcast.visible(walls, size, origin, radius)
class_name Shadowcast
extends RefCounted

# The 8 slices around the origin, as [xx, xy, yx, yy].
const OCTANTS := [[1, 0, 0, 1], [0, 1, 1, 0], [0, -1, 1, 0], [-1, 0, 0, 1],
		[-1, 0, 0, -1], [0, -1, -1, 0], [0, 1, -1, 0], [1, 0, 0, -1]]

# One byte per cell, row by row: 1 where the image is opaque (a wall).
static func from_image(img: Image) -> PackedByteArray:
	var walls := PackedByteArray()
	walls.resize(img.get_width() * img.get_height())
	for y in img.get_height():
		for x in img.get_width():
			walls[y * img.get_width() + x] = 1 if img.get_pixel(x, y).a > 0.0 else 0
	return walls

# Returns the same layout as walls, with 1 for every cell the origin can see.
# Copy the scan loop EXACTLY (float division included) — rewritten from
# memory, the slopes go wrong.
static func visible(walls: PackedByteArray, size: Vector2i, origin: Vector2i, radius: int) -> PackedByteArray:
	var w := size.x
	var h := size.y
	if radius <= 0 or origin.x < 0 or origin.y < 0 or origin.x >= w or origin.y >= h:
		var none := PackedByteArray()
		none.resize(w * h)
		return none
	var seen := PackedByteArray()
	seen.resize(w * h)
	seen[origin.y * w + origin.x] = 1
	for o in OCTANTS:
		var stack := [[1, 1.0, 0.0]]   # [first row, start slope, end slope]
		while not stack.is_empty():
			var item: Array = stack.pop_back()
			var start: float = item[1]
			var end: float = item[2]
			if start < end:
				continue
			var new_start := 0.0
			for j in range(item[0], radius + 1):   # rows, moving away from the origin
				var dy := -j
				var blocked := false
				for dx in range(-j, 1):            # cells in the row, outer edge first
					var left := (dx - 0.5) / (dy + 0.5)
					var right := (dx + 0.5) / (dy - 0.5)
					if start < right:
						continue
					if end > left:
						break
					var x: int = origin.x + dx * o[0] + dy * o[1]
					var y: int = origin.y + dx * o[2] + dy * o[3]
					var inside := x >= 0 and x < w and y >= 0 and y < h
					if inside and dx * dx + dy * dy < radius * radius:
						seen[y * w + x] = 1
					var wall := not inside or walls[y * w + x] == 1
					if blocked:
						if wall:
							new_start = right
						else:
							blocked = false        # out of the wall: narrower range
							start = new_start
					elif wall and j < radius:
						blocked = true             # next row gets the open part before the wall
						stack.append([j + 1, start, left])
						new_start = right
				if blocked:
					break
	return seen

# Move an origin that sits inside a wall to the nearest open cell (ties:
# earliest in scan order). A torch held in front of a character hugging a
# wall can land in one; from there the light only reaches 8 neighbors, or
# leaks through a 1-cell-thin wall.
static func resolve_origin(walls: PackedByteArray, size: Vector2i, origin: Vector2i) -> Vector2i:
	var w := size.x
	var h := size.y
	if origin.x >= 0 and origin.y >= 0 and origin.x < w and origin.y < h \
			and walls[origin.y * w + origin.x] == 0:
		return origin
	for r in range(1, 3):
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				var p := origin + Vector2i(dx, dy)
				if p.x >= 0 and p.y >= 0 and p.x < w and p.y < h \
						and walls[p.y * w + p.x] == 0:
					return p
	return origin
```

Per tile (23 x 11 cells) a call takes about 0.04 ms in GDScript; per pixel
(368 x 176, radius 92) about 1.6 ms. Per pixel, recast **only when the
origin moves to a new pixel-cell**, or port to C# for every-frame use.

## Use 1 — torchlight

1. Cast when the light's cell changes: `seen = Shadowcast.visible(walls, size, Shadowcast.resolve_origin(walls, size, origin_cell), light_radius)`.
2. Per pixel only: write `seen` into an `Image` and dilate the wall tops
   `WALL_DILATION` px (spread into wall cells touching a seen cell, plain
   Manhattan distance), or a wall facing the light gets a 1 px lit edge.
   Scale `WALL_DILATION = 5 * tile_size / 16`.
3. Build the light `ImageTexture`: per seen pixel
   `t = pow(clamp(1.0 - dist / radius, 0.0, 1.0), 0.8)`,
   `v = ceil(t * 6.0) / 6.0` (6 flat bands; clamp the ceil — `1.0 * 6` can
   come out as `6.000000000000001` and produce a 7th band), 0 elsewhere.
4. Multiply over the scene with a `canvas_item` shader:

```glsl
shader_type canvas_item;
uniform sampler2D light_tex;                  // the banded light, same size as the screen-space scene
uniform vec3 ambient = vec3(0.045, 0.05, 0.09);
uniform vec3 torch_color = vec3(1.0, 0.80, 0.55) * 1.15;
void fragment() {
	vec4 scene = texture(TEXTURE, UV);        // a full-screen ColorRect under the lights, or the map itself
	vec3 light = texture(light_tex, UV).rgb;
	COLOR = vec4(scene.rgb * (ambient + light * torch_color), scene.a);
}
```

If the project already has a lighting pass or its own ambient/torch colors,
use those — keep the user's colors and radius.

## Use 2 — fog of war

```gdscript
var explored := PackedByteArray()             # once, when the level loads
explored.resize(w * h)

# every time `seen` changes:
for i in explored.size():
	explored[i] = 1 if (explored[i] == 1 or seen[i] == 1) else 0
```

Draw each cell: `seen` → lit as above; `explored and not seen` →
`gray(scene_color) * vec3(0.30, 0.32, 0.40)` where
`gray = (r + g + b) / 3.0`; otherwise black. **Save `explored` with the
level and never clear it on a recast** — it only ever grows.

## Use 3 — enemy line of sight

```gdscript
var sight := Shadowcast.visible(walls, size,
		Shadowcast.resolve_origin(walls, size, enemy_cell), sight_range)
var enemy_sees_player := sight[player_cell.y * size.x + player_cell.x] == 1
```

Cast **from the enemy**, not the player: this shadowcasting is not
symmetric (16% of per-tile pairs that see each other only see one way on
the guide's map). If stealth must play fair both ways, ask the user and use
symmetric shadowcasting (Albert Ford) instead.

## Settings to expose

`light_radius` (cells), `sight_range` (cells), falloff `power` 0.8, `bands`
6, `wall_dilation` 5 px per 16 px tile, fog tint `(0.30, 0.32, 0.40)`,
ambient, torch color. Tell the user where they live.

## Verify in-engine

Mirror `scripts/verify_shadowcast.py` (the numbers there all pass) with a
debug view that draws `seen` bright and everything else dark; add a toggle
that switches the feature off and restores the old plain radial light.
