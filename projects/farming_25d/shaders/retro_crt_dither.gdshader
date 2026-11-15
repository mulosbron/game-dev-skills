shader_type canvas_item;
render_mode unshaded;

// Retro 480x270 Phosphor CRT & Bayer 4x4 Dither Shader
// Conforms to GDD Section 8.4 Visual Direction (Retro FPS + CRT Aesthetic)

uniform float scanline_strength : hint_range(0.0, 1.0) = 0.15;
uniform float dither_strength : hint_range(0.0, 1.0) = 0.10;
uniform float phosphor_tint_strength : hint_range(0.0, 1.0) = 0.05;
uniform vec3 phosphor_color : source_color = vec3(0.16, 0.78, 0.43); // CRT Phosphor Green #28C76F

// 4x4 Bayer Dither Matrix normalized to [-0.5, 0.5]
const float bayer4[16] = float[16](
    -0.5000,  0.0000, -0.3750,  0.1250,
     0.2500, -0.2500,  0.3750, -0.1250,
    -0.3125,  0.1875, -0.4375,  0.0625,
     0.4375, -0.0625,  0.3125, -0.1875
);

void fragment() {
    vec4 screen_tex = texture(TEXTURE, UV);
    vec3 col = screen_tex.rgb;
    
    // Pixel coordinate on 480x270 virtual buffer
    ivec2 pix = ivec2(UV / TEXTURE_PIXEL_SIZE);
    
    // 1. Scanlines (subtle darkening on alternate lines)
    if (pix.y % 2 == 1) {
        col *= (1.0 - scanline_strength);
    }
    
    // 2. Bayer 4x4 Dither
    int bayer_idx = (pix.x % 4) + (pix.y % 4) * 4;
    float dither_val = bayer4[bayer_idx] * dither_strength;
    col += vec3(dither_val);
    
    // 3. Subtle Phosphor CRT Tint
    col = mix(col, col * phosphor_color, phosphor_tint_strength);
    
    COLOR = vec4(clamp(col, 0.0, 1.0), screen_tex.a);
}
