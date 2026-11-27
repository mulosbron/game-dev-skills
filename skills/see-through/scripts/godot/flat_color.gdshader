// flat_color.gdshader: draws a sprite's shape in one color. Used for the silhouette copy of the character.
shader_type canvas_item;

uniform vec4 color : source_color = vec4(0.463, 0.839, 1.0, 1.0);

void fragment() {
	COLOR = vec4(color.rgb, step(0.5, texture(TEXTURE, UV).a) * color.a);
}
