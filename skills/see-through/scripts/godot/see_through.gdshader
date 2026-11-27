// see_through.gdshader: opens a window in a sprite around a point, with no blending.
// Every pixel of the sprite is either drawn or dropped. soft > 0 gives a dithered edge, soft = 0 a hard hole.
// One decision per world pixel. That is one art pixel only when the game renders at art resolution.
// If sprites are scaled up, use see_through_scaled.gdshader instead of editing this one.
shader_type canvas_item;

uniform vec2 target;                  // the character's center, in world pixels
uniform float amount = 0.0;           // 0 = the sprite is whole, 1 = the window is fully open
uniform float clear_radius = 18.0;    // px around the target where nothing of the sprite is left
uniform float soft = 16.0;            // px over which the sprite thins back to solid. 0 = a hard edge
uniform float keep = 0.0;             // share of the sprite that stays even next to the target, in steps of 1/16

// Bayer 4x4: the order in which the 16 pixels of every 4x4 block are dropped.
const float BAYER[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 cell = floor(world);                              // one decision per art pixel, at any zoom
	float d = distance(cell + 0.5, target);
	float reach = (clear_radius + soft) * amount;          // the window grows from nothing as amount goes up
	float solid = soft > 0.0 ? clamp((d - reach) / soft + 1.0, 0.0, 1.0) : step(reach, d);
	solid = max(solid, keep);                              // keep 0.375: 6 of every 16 pixels stay
	ivec2 c = ivec2(mod(cell, 4.0));
	if (solid <= (BAYER[c.y * 4 + c.x] + 0.5) / 16.0) {
		discard;
	}
}
