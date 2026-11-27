// row_bend.gdshader: bends a sprite by sliding its rows sideways by whole pixels, the top the most and the foot
// not at all. For thin things that really bend: a pine's trunk, tall grass, reeds.
shader_type canvas_item;

uniform float lean = 0.0;       // px the top row moves
uniform float power = 2.0;      // 1 = a straight slant, 2 = a curve that keeps the foot stiff

void fragment() {
	float up = 1.0 - UV.y;                                  // 0 at the foot, 1 at the top
	float shift = round(lean * pow(up, power));             // whole pixels only
	vec2 uv = UV - vec2(shift * TEXTURE_PIXEL_SIZE.x, 0.0);
	COLOR = texture(TEXTURE, uv);
	if (uv.x < 0.0 || uv.x > 1.0) {
		COLOR.a = 0.0;                                      // leave empty margin left and right of the art
	}
}
