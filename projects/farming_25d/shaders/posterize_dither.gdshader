// posterize_dither.gdshader - CanvasItem 4x4 Bayer Dither & Posterize
shader_type canvas_item;

uniform float levels : hint_range(2.0, 64.0) = 8.0;          // Quantization steps per channel
uniform float dither_strength : hint_range(0.0, 1.0) = 1.0;  // 0 = flat posterize, 1 = full Bayer dither

// 4x4 Bayer matrix
const mat4 BAYER = mat4(
    vec4(0.000, 0.500, 0.125, 0.625),
    vec4(0.750, 0.250, 0.875, 0.375),
    vec4(0.188, 0.688, 0.062, 0.562),
    vec4(0.812, 0.312, 0.938, 0.438)
);

void fragment() {
    vec4 c = COLOR;
    ivec2 px = ivec2(FRAGCOORD.xy) % 4;
    float d = (BAYER[px.x][px.y] - 0.5) * dither_strength;
    c.rgb = floor((c.rgb + d / levels) * levels + 0.5) / levels;
    COLOR = c;
}
