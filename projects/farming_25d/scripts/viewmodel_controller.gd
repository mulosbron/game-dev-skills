extends Node3D
class_name ViewmodelController

## Manages first-person tool swings, gun firing animations, dynamic muzzle flashes, and weapon sway.

@export var sway_amount: float = 0.0015
@export var sway_smooth: float = 8.0
@export var recoil_distance: float = 0.08
@export var recoil_recovery: float = 12.0

@onready var sprite: Sprite3D = $ViewmodelSprite
@onready var muzzle_light: PointLight3D = $MuzzleFlashLight

var default_position: Vector3
var target_sway: Vector3 = Vector3.ZERO
var current_recoil: float = 0.0
var is_animating: bool = false
var animation_timer: float = 0.0

# Textures for each tool / weapon viewmodel
var viewmodel_textures = {
    FPSPlayer.ItemType.HOE: preload("res://sprites_2d/viewmodels/VM_02_Capa_Gold_frame0.png"),
    FPSPlayer.ItemType.PICKAXE: preload("res://sprites_2d/viewmodels/VM_01_Kazma_Gold_frame0.png"),
    FPSPlayer.ItemType.WATERING_CAN: preload("res://sprites_2d/viewmodels/VM_03_Sulama_Gold_frame0.png"),
    FPSPlayer.ItemType.SCYTHE: preload("res://sprites_2d/viewmodels/VM_04_Tirpan_Gold_frame0.png"),
    FPSPlayer.ItemType.PISTOL: preload("res://sprites_2d/viewmodels/VM_05_Tabanca_Chrome_frame0.png"),
    FPSPlayer.ItemType.SHOTGUN: preload("res://sprites_2d/viewmodels/VM_05_Tabanca_Chrome_frame1.png"),
    FPSPlayer.ItemType.SEED_PACKET: preload("res://sprites_2d/props_and_ui/item_seed_bugday.png")
}

func _ready() -> void:
    default_position = position
    if muzzle_light:
        muzzle_light.visible = false

func _process(delta: float) -> void:
    # 1. Recover recoil
    if current_recoil > 0.0:
        current_recoil = lerp(current_recoil, 0.0, recoil_recovery * delta)
        
    # 2. Smooth weapon sway
    position.x = lerp(position.x, default_position.x + target_sway.x, sway_smooth * delta)
    position.y = lerp(position.y, default_position.y + target_sway.y - current_recoil * 0.5, sway_smooth * delta)
    position.z = lerp(position.z, default_position.z + current_recoil, sway_smooth * delta)
    
    target_sway = lerp(target_sway, Vector3.ZERO, delta * 5.0)

func _input(event: InputEvent) -> void:
    if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
        target_sway.x = clamp(target_sway.x - event.relative.x * sway_amount, -0.05, 0.05)
        target_sway.y = clamp(target_sway.y + event.relative.y * sway_amount, -0.05, 0.05)

func set_equipped_item(item_type: FPSPlayer.ItemType) -> void:
    if sprite and viewmodel_textures.has(item_type):
        sprite.texture = viewmodel_textures[item_type]

func play_action(item_type: FPSPlayer.ItemType) -> void:
    # Trigger recoil
    current_recoil = recoil_distance
    
    # Gun muzzle flash
    if item_type == FPSPlayer.ItemType.PISTOL or item_type == FPSPlayer.ItemType.SHOTGUN:
        _flash_muzzle()
    else:
        # Tool swing rotational tilt
        _swing_tool()

func _flash_muzzle() -> void:
    if muzzle_light:
        muzzle_light.visible = true
        muzzle_light.light_energy = 2.5
        var tween = create_tween()
        tween.tween_property(muzzle_light, "light_energy", 0.0, 0.08)
        tween.tween_callback(func(): muzzle_light.visible = false)

func _swing_tool() -> void:
    var tween = create_tween()
    tween.tween_property(self, "rotation_degrees:x", -25.0, 0.08)
    tween.tween_property(self, "rotation_degrees:x", 0.0, 0.14)
