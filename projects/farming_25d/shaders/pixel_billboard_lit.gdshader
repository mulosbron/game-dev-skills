shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_toon, specular_disabled;

// 2.5D FPS Y-Billboard Pixel Shader with Tangent-Space Normal Mapping
// Enforces Y-billboarding, crisp pixel textures, and dynamic 3D lighting highlights

uniform sampler2D albedo_texture : source_color, filter_nearest;
uniform sampler2D normal_texture : hint_normal, filter_nearest;
uniform float normal_depth : hint_range(0.0, 5.0) = 1.8;
uniform float alpha_threshold : hint_range(0.0, 1.0) = 0.20;
uniform vec4 hit_flash_color : source_color = vec4(1.0, 0.2, 0.2, 1.0);
uniform float hit_flash_strength : hint_range(0.0, 1.0) = 0.0;

void vertex() {
    // Lock rotation around the vertical Y axis (Y-Billboard)
    // Preserves sprite height and upright grounding in FPS perspective
    MODELVIEW_MATRIX = VIEW_MATRIX * mat4(
        vec4(normalize(cross(vec3(0.0, 1.0, 0.0), INV_VIEW_MATRIX[2].xyz)), 0.0),
        vec4(0.0, 1.0, 0.0, 0.0),
        vec4(normalize(cross(INV_VIEW_MATRIX[0].xyz, vec3(0.0, 1.0, 0.0))), 0.0),
        MODEL_MATRIX[3]
    );
    MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
}

void fragment() {
    vec4 tex_color = texture(albedo_texture, UV);
    
    // Alpha scissor cutoff - strictly eliminates blurry fringes
    if (tex_color.a < alpha_threshold) {
        discard;
    }
    
    // Apply damage hit flash
    vec3 final_color = mix(tex_color.rgb, hit_flash_color.rgb, hit_flash_strength);
    
    ALBEDO = final_color;
    ALPHA = 1.0;
    
    // Normal map for dynamic 3D lighting from lanterns, campfires, and muzzle flashes
    vec3 normal_sample = texture(normal_texture, UV).rgb;
    NORMAL_MAP = normal_sample;
    NORMAL_MAP_DEPTH = normal_depth;
    
    ROUGHNESS = 0.85;
    METALLIC = 0.0;
}
