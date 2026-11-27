// Same window as see_through.gdshader, but one decision per art pixel when the
// sprite is drawn larger than its texture. pixel_scale is world units per art pixel.
// At pixel_scale = 1 this is the tested shader. Radii stay in art pixels.
shader_type canvas_item;

uniform vec2 target;
uniform float amount = 0.0;
uniform float clear_radius = 18.0;
uniform float soft = 16.0;
uniform float keep = 0.0;
uniform float pixel_scale = 1.0;

const float BAYER[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 art = world / pixel_scale;
	vec2 cell = floor(art);
	float d = distance(cell + 0.5, target / pixel_scale);
	float reach = (clear_radius + soft) * amount;
	float solid = soft > 0.0 ? clamp((d - reach) / soft + 1.0, 0.0, 1.0) : step(reach, d);
	solid = max(solid, keep);
	ivec2 c = ivec2(mod(cell, 4.0));
	if (solid <= (BAYER[c.y * 4 + c.x] + 0.5) / 16.0) {
		discard;
	}
}
