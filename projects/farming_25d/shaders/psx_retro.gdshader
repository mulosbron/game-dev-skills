// psx_retro.gdshader - PS1 Era Spatial Shader
// Features: Vertex snapping, Affine texture mapping, Color posterization.
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, shadows_disabled;

uniform sampler2D base_tex : source_color, filter_nearest, repeat_enable;
uniform float vertex_snap_res : hint_range(120.0, 1080.0) = 240.0; // Virtual vertical resolution
uniform bool affine_mapping = true;
uniform float color_levels : hint_range(2.0, 256.0) = 32.0;

varying vec2 uv_affine;
varying float clip_w;

void vertex() {
    vec4 clip = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
    if (clip.w > 0.0001) {
        // Vertex snapping in NDC space
        vec3 ndc = clip.xyz / clip.w;
        float half_res = vertex_snap_res * 0.5;
        ndc.xy = floor(ndc.xy * half_res + 0.5) / half_res;
        clip.xyz = ndc * clip.w;
    }
    POSITION = clip;
    uv_affine = UV * clip.w;
    clip_w = max(clip.w, 0.0001);
}

void fragment() {
    vec2 uv = affine_mapping ? uv_affine / clip_w : UV;
    vec3 col = texture(base_tex, uv).rgb * COLOR.rgb;
    col = floor(col * color_levels + 0.5) / color_levels; // Posterize
    ALBEDO = col;
}
