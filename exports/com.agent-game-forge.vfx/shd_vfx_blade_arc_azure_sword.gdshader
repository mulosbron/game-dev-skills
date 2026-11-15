shader_type canvas_item;
// 2D-Native Top-Down Procedural Pixel VFX Shader (Nenly Architecture)
// Family: blade_arc | Default Menpai: azure_sword
// Attach to a ColorRect / Sprite2D. Supports Pixel Grid Quantization + Selective Glow output!

uniform int effect_family : hint_range(0, 4) = 0; // 0:blade_arc, 1:shockwave, 2:qi_burst, 3:aoe_zone, 4:projectile
uniform float progress : hint_range(0.0, 1.0) = 0.35;
uniform float y_perspective : hint_range(0.35, 1.0) = 0.65;
uniform float pixel_grid : hint_range(16.0, 256.0) = 96.0;
uniform float noise_amp : hint_range(0.0, 1.0) = 0.15;
uniform float glow_intensity : hint_range(0.0, 3.0) = 1.35;

uniform vec4 col_shadow : source_color = vec4(0.035, 0.082, 0.149, 1.0);
uniform vec4 col_dark   : source_color = vec4(0.086, 0.243, 0.361, 1.0);
uniform vec4 col_mid    : source_color = vec4(0.235, 0.639, 0.788, 1.0);
uniform vec4 col_bright : source_color = vec4(0.596, 0.902, 0.961, 1.0);
uniform vec4 col_core   : source_color = vec4(1.000, 1.000, 1.000, 1.0);

float fbm2(vec2 p, float t) {
    float n1 = sin(p.x * 3.7 + t) * cos(p.y * 3.7 - t * 0.7);
    float n2 = 0.5 * sin(p.x * 7.9 - p.y * 5.3 + t * 1.9);
    return (n1 + n2) / 1.5;
}

vec3 sample_menpai_palette(float v) {
    if (v >= 0.88) return col_core.rgb;
    if (v >= 0.68) return col_bright.rgb;
    if (v >= 0.42) return col_mid.rgb;
    if (v >= 0.20) return col_dark.rgb;
    return col_shadow.rgb;
}

void fragment() {
    // 1. Snap UV to crisp integer pixel grid
    vec2 snapped_uv = floor(UV * pixel_grid) / pixel_grid;
    vec2 p = snapped_uv * 2.0 - 1.0;

    // 2. Top-Down 2D Orthographic Ground Projection
    vec2 gp = vec2(p.x, p.y / y_perspective);
    float r = length(gp);
    float theta = atan(gp.y, gp.x);
    float n = fbm2(gp * 2.5, progress * 9.0) * noise_amp;

    float decay = clamp((1.0 - progress) / 0.32, 0.0, 1.0);
    float intensity = 0.0;
    float alpha = 0.0;
    float selective_glow = 0.0;

    if (effect_family == 0) {
        // 刀光 Blade Arc Sweep
        float sweep = 1.0 - pow(1.0 - progress, 2.4);
        float head_a = -2.4 + sweep * 4.2;
        float ang_diff = mod(head_a - theta + 9.42477, 6.28318) - 3.14159;
        float arc_u = clamp(1.0 - ang_diff / 1.85, 0.0, 1.0) * step(0.0, ang_diff);
        float thick = 0.14 * pow(arc_u, 0.55) * (1.0 + 0.25 * n);
        float blade = clamp(1.0 - abs(r - 0.65 + 0.04 * n) / max(0.015, thick), 0.0, 1.0) * arc_u * decay;
        intensity = blade;
        alpha = step(0.12, blade);
        selective_glow = pow(blade, 2.0) * arc_u * glow_intensity;
    } else if (effect_family == 1) {
        // 冲击波 Shockwave Ring
        float rt = 1.0 - pow(1.0 - progress, 2.1);
        float r_cur = 0.12 + rt * 0.76;
        float ring_w = 0.12 * (1.0 - 0.55 * rt);
        float ring = clamp(1.0 - abs(r + n * 0.08 - r_cur) / max(0.015, ring_w), 0.0, 1.0) * (1.0 - rt);
        intensity = ring;
        alpha = step(0.12, ring);
        selective_glow = pow(ring, 2.0) * glow_intensity;
    } else {
        // 气爆 / 驻留场 Radial Burst & Sigil
        float spikes = pow(abs(cos(theta * 5.0 + n * 1.8)), 1.8);
        float max_r = (0.38 + 0.45 * spikes) * (1.0 - pow(1.0 - progress, 3.0));
        float burst = clamp(1.0 - r / max(0.05, max_r), 0.0, 1.0) * decay;
        intensity = burst;
        alpha = step(0.12, burst);
        selective_glow = pow(burst, 1.8) * glow_intensity;
    }

    vec3 base_col = sample_menpai_palette(intensity);
    vec3 final_col = base_col + col_bright.rgb * selective_glow * 0.65;
    COLOR = vec4(final_col, alpha);
}
