# weapon_sprite.gd - Retro 2.5D FPS HUD Weapon Viewmodel Anchor
extends Sprite2D

@export var scale_factor: int = 4

func _ready() -> void:
	scale = Vector2(scale_factor, scale_factor)

func _process(_delta: float) -> void:
	if texture:
		var vp := get_viewport_rect().size
		var half := texture.get_size() * float(scale_factor) / 2.0
		position = Vector2(vp.x / 2.0 - half.x, vp.y - texture.get_size().y * float(scale_factor))
