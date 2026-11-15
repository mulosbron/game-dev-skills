# pixel_camera_2d.gd - Pixel-perfect Camera2D with integer scaling and floor snapping
class_name PixelCamera2D
extends Camera2D

@export var pixel_scale: int = 4  # PPU zoom multiplier

func _ready() -> void:
	zoom = Vector2(pixel_scale, pixel_scale)

func _physics_process(_delta: float) -> void:
	# Lock camera coordinates to integer pixel boundaries to eliminate subpixel jitter
	global_position = global_position.floor()
