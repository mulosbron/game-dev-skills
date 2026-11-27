// outline.gdshader: draws only the edge pixels of a sprite's shape in one color.
// An edge pixel is an opaque pixel with a transparent pixel above, below, left or right of it.
// Every frame of the character sheet needs a clear border of at least 1 px, or the
// edge reads the next frame. Check with: python3 tools/see_through.py border-check sheet.png ...
shader_type canvas_item;

uniform vec4 color : source_color = vec4(0.98, 0.98, 0.941, 1.0);

void fragment() {
	vec2 px = TEXTURE_PIXEL_SIZE;
	float inside = step(0.5, texture(TEXTURE, UV).a);
	float around = min(min(texture(TEXTURE, UV + vec2(px.x, 0.0)).a, texture(TEXTURE, UV - vec2(px.x, 0.0)).a),
			min(texture(TEXTURE, UV + vec2(0.0, px.y)).a, texture(TEXTURE, UV - vec2(0.0, px.y)).a));
	COLOR = vec4(color.rgb, inside * (1.0 - step(0.5, around)) * color.a);
}
