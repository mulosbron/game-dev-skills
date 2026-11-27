# Godot 4 — atmospheric perspective shader

Tested in Godot 4.6 against the Python bake: the shader matches the Python
version on every pixel, within 1 of 255.

## The shader (`atmospheric_perspective.gdshader`)

Put this on each parallax layer's Sprite2D. The layer blends toward the sky
right behind it: `amount` everywhere, plus up to `mist` more toward the
bottom of its art.

```glsl
shader_type canvas_item;

uniform sampler2D sky_colors : filter_nearest;   // 1 pixel wide, the sky's color on each row
uniform float amount : hint_range(0.0, 1.0) = 0.0;
uniform float mist : hint_range(0.0, 1.0) = 0.0;
uniform float art_top = 0.0;      // UV.y where the layer's art starts
uniform float art_bottom = 1.0;   // UV.y where it ends

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	vec3 sky = texture(sky_colors, vec2(0.5, UV.y)).rgb;
	float y = clamp((UV.y - art_top) / (art_bottom - art_top), 0.0, 1.0);
	float k = clamp(amount + mist * y, 0.0, 1.0);
	COLOR = vec4(mix(c.rgb, sky, k), c.a);
}
```

If you expose the global strength slider, multiply it into `k`:
`float k = clamp(strength * (amount + mist * y), 0.0, 1.0);` with
`uniform float strength : hint_range(0.0, 1.0) = 1.0;`.

## Attach script (`hazed_layer.gd`)

Turns the sky into one color per row, hands each layer its numbers and works
out where its art starts and ends:

```gdscript
# hazed_layer.gd: put this on each layer's Sprite2D,
# with atmospheric_perspective.gdshader as its material.
extends Sprite2D

@export var sky: Texture2D                        # the sky layer, same height as this one
@export_range(0.0, 1.0) var amount := 0.0
@export_range(0.0, 1.0) var mist := 0.0


func _ready() -> void:
	var art := texture.get_image().get_used_rect()   # where the layer's art is
	var h := float(texture.get_height())
	material = material.duplicate()                   # every layer keeps its own numbers
	material.set_shader_parameter("sky_colors", sky_colors(sky.get_image()))
	material.set_shader_parameter("amount", amount)
	material.set_shader_parameter("mist", mist)
	material.set_shader_parameter("art_top", art.position.y / h)
	material.set_shader_parameter("art_bottom", art.end.y / h)


# The sky's average color on every row, as a texture 1 pixel wide.
static func sky_colors(img: Image) -> ImageTexture:
	var rows := Image.create(1, img.get_height(), false, Image.FORMAT_RGB8)
	for y in img.get_height():
		var sum := Vector3.ZERO
		for x in img.get_width():
			var c := img.get_pixel(x, y)
			sum += Vector3(c.r8, c.g8, c.b8)
		sum /= img.get_width()
		rows.set_pixel(0, y, Color8(roundi(sum.x), roundi(sum.y), roundi(sum.z)))
	return ImageTexture.create_from_image(rows)
```

Note `material.duplicate()`: sharing one ShaderMaterial between layers makes
them all use the same numbers. Every layer needs its own.

## Setup

1. Put each layer in a `Parallax2D` node (Godot 4.3+) with its scroll speed
   as `scroll_scale`.
2. Add a `Sprite2D` child with the layer's texture; set texture filter to
   **Nearest** for pixel art.
3. Give every layer's texture the **same height as the sky** and place it at
   the same y, so the rows line up. Cropped or atlas-packed layers break the
   row lookup — use the pixel's screen row instead.
4. Give the Sprite2D a ShaderMaterial with the shader, attach
   `hazed_layer.gd`, drag the sky texture into `sky`, and fill in `amount`
   and `mist` from the table in SKILL.md.

Ground, player and anything the play area touches stay at amount 0.
