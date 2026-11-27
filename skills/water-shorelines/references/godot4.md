# Godot 4 — bake at load + water shader

Tested on Godot 4.6. Two pieces: a static bake helper (`ShoreDistance`) and a
`canvas_item` shader for the Sprite2D that draws the water.

## Scene setup

1. Render your land layer (TileMapLayer) once into a SubViewport with a
   transparent background to get the land Image (see "Getting the land mask"
   in SKILL.md). Skip this if you already have the land as an Image.
2. Bake at load: `$Water.texture = ShoreDistance.bake(land_image)`.
3. The water is a Sprite2D with the baked map as texture, **under** the
   TileMapLayer, same position/transform as it.
4. Texture filter on the Sprite2D: **Nearest**. This is the pitfall people
   hit most: with linear filtering at screen resolution the bands become thin
   smooth curves that ignore the art's pixel grid.
5. Add a debug toggle that shows the raw map texture itself.

## shore_distance.gd

```gdscript
# shore_distance.gd: bakes the distance map for the water shader at load time.
# Use: $Water.texture = ShoreDistance.bake(land_image)
class_name ShoreDistance
extends RefCounted

const MAX_DIST := 32.0   # px, the same max_dist as in the shader

# land: your land layer as an Image, transparent where the water is.
static func bake(land: Image) -> ImageTexture:
	var w := land.get_width()
	var h := land.get_height()
	var dist := distance(land)
	var noise := FastNoiseLite.new()
	noise.fractal_type = FastNoiseLite.FRACTAL_NONE
	noise.frequency = 0.03
	var img := Image.create(w, h, false, Image.FORMAT_L8)
	for y in h:
		for x in w:
			var d := dist[y * w + x] + noise.get_noise_2d(x, y) * 4.0   # the wobble
			var v := clampf(d / MAX_DIST, 0.0, 1.0)
			img.set_pixel(x, y, Color(v, v, v))
	return ImageTexture.create_from_image(img)

# px from every pixel to the nearest land pixel, like scipy's distance_transform_edt.
static func distance(land: Image) -> PackedFloat32Array:
	var w := land.get_width()
	var h := land.get_height()
	var d := PackedFloat32Array()
	d.resize(w * h)
	for y in h:
		for x in w:
			d[y * w + x] = 0.0 if land.get_pixel(x, y).a > 0.0 else 1e20
	for x in w:
		_pass(d, x, w, h)       # squared distance down each column
	for y in h:
		_pass(d, y * w, 1, w)   # then along each row
	for i in d.size():
		d[i] = sqrt(d[i])
	return d

# Exact 1D squared distance over n values, `step` apart from `start`
# (Felzenszwalb and Huttenlocher's lower envelope of parabolas).
static func _pass(d: PackedFloat32Array, start: int, step: int, n: int) -> void:
	var f := PackedFloat32Array()
	f.resize(n)
	for i in n:
		f[i] = d[start + i * step]
	var v := PackedInt32Array()   # the parabolas in the envelope
	v.resize(n)
	var z := PackedFloat32Array() # where each one takes over
	z.resize(n + 1)
	var k := 0
	z[0] = -INF
	z[1] = INF
	for q in range(1, n):
		var s := _meet(f, q, v[k])
		while s <= z[k]:
			k -= 1
			s = _meet(f, q, v[k])
		k += 1
		v[k] = q
		z[k] = s
		z[k + 1] = INF
	k = 0
	for q in n:
		while z[k + 1] < q:
			k += 1
		d[start + q * step] = (q - v[k]) * (q - v[k]) + f[v[k]]

static func _meet(f: PackedFloat32Array, q: int, p: int) -> float:
	return ((f[q] + q * q) - (f[p] + p * p)) / (2.0 * (q - p))
```

The GDScript transform is exact: it matches `scipy.ndimage.distance_transform_edt`
on every pixel. Bake cost is O(area); about 100 ms for a 360x322 map on a
desktop PC — fine at level load, not per frame.

## water_shoreline.gdshader

```glsl
shader_type canvas_item;

// Put this on a Sprite2D whose texture is the baked distance map, drawn
// under the land. Texture filter: Nearest, so every band stays on the pixel grid.
uniform float max_dist = 32.0;     // the MAX_DIST the map was baked with
uniform vec4 deep : source_color = vec4(0.110, 0.290, 0.502, 1.0);
uniform vec4 mid : source_color = vec4(0.133, 0.384, 0.588, 1.0);
uniform vec4 shallow : source_color = vec4(0.204, 0.549, 0.690, 1.0);
uniform vec4 shoal : source_color = vec4(0.376, 0.745, 0.769, 1.0);
uniform vec4 wave : source_color = vec4(0.588, 0.839, 0.855, 1.0);
uniform vec4 foam : source_color = vec4(0.925, 0.965, 0.957, 1.0);
uniform float wave_spacing = 11.0; // px between waves
uniform float wave_speed = 4.4;    // px per second, towards the coast

void fragment() {
	float d = texture(TEXTURE, UV).r * max_dist;   // px to the nearest land

	vec4 c = deep;
	if (d < 26.0) c = mid;
	if (d < 13.0) c = shallow;
	if (d < 5.0) c = shoal;

	float phase = mod(d + TIME * wave_speed, wave_spacing);
	if (phase < 1.6 && d > 4.0 && d < 20.0) c = wave;

	if (d < 2.2 + 1.1 * sin(TIME * 2.5)) c = foam;   // breathes in and out

	COLOR = c;
}
```

Colors are the same palette as the skill (deep `#1C4A80`, mid `#226296`,
shallow `#348CB0`, shoal `#60BEC4`, wave `#96D6DA`, foam `#ECF6F4`) — replace
them if the project has its own water palette.

## Changing coasts and chunked worlds

- Coast edits (digging, building): the stored map can only change within
  MAX_DIST of the edit. Re-run the bake on a window around the edit with
  2 x MAX_DIST of margin, and copy back the part within MAX_DIST of it.
- Chunked worlds: bake each chunk with MAX_DIST of its neighbors' land around
  it, and take the wobble from **world** position
  (`noise.get_noise_2d(world_x, world_y)`), or the bands break at chunk
  borders.

## In-engine checks

- Debug view of the raw map (toggle the Sprite2D's shader off / show texture).
- Water 4, 12, 25, 27 px from land is shoal, shallow, mid, deep (with wobble
  and foam off — set the noise amplitude to 0 for the test bake).
- Wave pixels only 4-20 px from land, moving toward the coast, period 2.5 s.
- Effect off → old flat water back.
