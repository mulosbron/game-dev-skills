# see_through.gd: keeps a character visible while it walks behind this sprite.
# Attach it to the Sprite2D of a tree, wall or roof and point `target` at the character.
# Both need their origin at their feet, the usual Y sort setup. Pick the look with `mode`.
# Reference port of the SpriteCook guide (Godot 4). Do not switch dither/fade/cutout on by box overlap.
# If this sprite is scaled up in the scene, use see_through_scaled.gdshader and set pixel_scale.
extends Sprite2D

enum Mode { FADE, DITHER, CUTOUT, SILHOUETTE, OUTLINE }

@export var mode := Mode.DITHER
@export var target: Node2D                  # the character, origin at its feet
@export var target_sprite: Node2D           # its Sprite2D or AnimatedSprite2D, only read by SILHOUETTE and OUTLINE
@export var target_size := Vector2(20, 36)  # px, the character's visible size
@export var ease_time := 0.2                # s to switch on or off
@export var cover_grid := Vector2i(3, 4)    # points on the character that are tested against this sprite
@export var cover_needed := 0.25            # share of those points that must be hidden to switch on

@export_group("Looks")
@export var fade_to := 0.4                  # FADE: this sprite's opacity while the character is behind it
@export var clear_radius := 18.0            # DITHER: px around the character where nothing of this sprite is left
@export var soft := 16.0                    # DITHER: px over which it thins back to solid
@export var keep := 0.0                     # DITHER: share of this sprite kept even next to the character. 0.375 = 6 of 16
@export var hole_radius := 22.0             # CUTOUT: px
@export var silhouette := Color8(118, 214, 255)
@export var outline := Color8(250, 250, 240)
## World units per art pixel. 1 when the game draws at art resolution.
## Radii stay in art pixels. Only read by the scaled shader.
@export var pixel_scale := 1.0

const FLAT_SHADER := preload("flat_color.gdshader")
const OUTLINE_SHADER := preload("outline.gdshader")

var amount := 0.0                           # 0 = off, 1 = fully on
var _window := ShaderMaterial.new()         # one per sprite, so every tree opens on its own
var _ghost: Node2D                          # SILHOUETTE and OUTLINE: a copy of the character in one color

func _ready() -> void:
	# Swap in see_through_scaled.gdshader when pixel_scale is not 1.
	# At scale 1 the two shaders make the same decision.
	if pixel_scale != 1.0:
		_window.shader = preload("see_through_scaled.gdshader")
	else:
		_window.shader = preload("see_through.gdshader")


func _process(delta: float) -> void:
	var goal := 1.0 if target != null and is_behind() else 0.0
	amount = move_toward(amount, goal, delta / ease_time) if ease_time > 0.0 else goal
	var on := amount > 0.0
	# Fade at 100% (fade_to == 1) leaves the sprite untouched.
	self_modulate.a = lerpf(1.0, fade_to, amount) if mode == Mode.FADE else 1.0
	if mode == Mode.DITHER or mode == Mode.CUTOUT:
		material = _window
		_window.set_shader_parameter("target", _center())
		_window.set_shader_parameter("amount", amount)
		_window.set_shader_parameter("clear_radius", clear_radius if mode == Mode.DITHER else hole_radius)
		_window.set_shader_parameter("soft", soft if mode == Mode.DITHER else 0.0)
		_window.set_shader_parameter("keep", keep if mode == Mode.DITHER else 0.0)
		if pixel_scale != 1.0:
			_window.set_shader_parameter("pixel_scale", pixel_scale)
	elif material == _window:
		material = null
	_show_ghost(on and (mode == Mode.SILHOUETTE or mode == Mode.OUTLINE))


# True when this sprite is drawn over the character and really covers it.
func is_behind() -> bool:
	var feet := target.global_position
	if feet.y >= global_position.y:         # level with this sprite's foot or in front of it
		return false
	if mode == Mode.SILHOUETTE or mode == Mode.OUTLINE:   # the clip mask does the exact part, so the boxes are enough
		var box := Rect2(feet - Vector2(target_size.x * 0.5, target_size.y), target_size)
		return (get_global_transform() * get_rect()).intersects(box)
	var hidden := 0
	for ix in cover_grid.x:
		for iy in cover_grid.y:
			var at := Vector2((ix + 0.5) / cover_grid.x - 0.5, (iy + 0.5) / cover_grid.y - 1.0) * target_size
			if is_pixel_opaque(to_local(feet + at)):
				hidden += 1
	return hidden > 0 and hidden >= cover_needed * cover_grid.x * cover_grid.y


func _center() -> Vector2:
	return target.global_position - Vector2(0.0, target_size.y * 0.5) if target != null else Vector2.ZERO


# SILHOUETTE and OUTLINE: this sprite clips a one-color copy of the character, so the copy only shows where it is
# covered. SILHOUETTE fills the copy, OUTLINE draws only its edge pixels.
func _show_ghost(on: bool) -> void:
	clip_children = CLIP_CHILDREN_AND_DRAW if on else CLIP_CHILDREN_DISABLED
	if on and _ghost == null:
		_ghost = target_sprite.duplicate(0)
		_ghost.material = ShaderMaterial.new()
		add_child(_ghost)
	if _ghost != null:
		_ghost.visible = on
	if on:
		_ghost.material.shader = OUTLINE_SHADER if mode == Mode.OUTLINE else FLAT_SHADER
		_ghost.material.set_shader_parameter("color", outline if mode == Mode.OUTLINE else silhouette)
		_ghost.global_transform = target_sprite.global_transform
		if _ghost is AnimatedSprite2D:
			_ghost.animation = target_sprite.animation
		_ghost.frame = target_sprite.frame
		_ghost.flip_h = target_sprite.flip_h


## Debug. Call from _unhandled_input when the engine cannot render-test the looks.
## F6 cycles fade → dither → dithered fade (keep 0.375) → cutout → silhouette → outline → dither.
func cycle_mode() -> void:
	match mode:
		Mode.FADE:
			mode = Mode.DITHER
			keep = 0.0
		Mode.DITHER:
			if keep <= 0.0:
				keep = 0.375  # dithered fade, same mode, 6 of 16 pixels stay
			else:
				mode = Mode.CUTOUT
				keep = 0.0
		Mode.CUTOUT:
			mode = Mode.SILHOUETTE
		Mode.SILHOUETTE:
			mode = Mode.OUTLINE
		Mode.OUTLINE:
			mode = Mode.FADE
