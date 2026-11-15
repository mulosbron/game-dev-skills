extends CharacterBody3D
class_name FPSPlayer

## Retro 2.5D FPS Controller for Farming Simulation & Horde Shooter
## Implements first-person movement, tool/weapon raycasting, head bob, and viewmodel sway.

@export_group("Movement")
@export var walk_speed: float = 4.5
@export var sprint_speed: float = 7.0
@export var jump_velocity: float = 4.8
@export var gravity: float = 14.0
@export var acceleration: float = 12.0
@export var friction: float = 10.0

@export_group("Look & Camera")
@export var mouse_sensitivity: float = 0.0022
@export var max_pitch: float = 85.0 # Degrees
@export var bob_frequency: float = 8.0
@export var bob_amplitude: float = 0.04

@export_group("Interaction & Farming")
@export var raycast_range: float = 3.5

# Node references
@onready var camera: Camera3D = $Camera3D
@onready var raycast: RayCast3D = $Camera3D/RayCast3D
@onready var viewmodel_anchor: Node3D = $Camera3D/ViewmodelAnchor
@onready var viewmodel_controller = $Camera3D/ViewmodelAnchor/ViewmodelController

# Internal state
var camera_pitch: float = 0.0
var bob_timer: float = 0.0
var original_camera_y: float = 0.0
var is_sprinting: bool = false
var active_hotbar_slot: int = 1

# Equipped item definitions
enum ItemType {
    HOE,          # Çapa (Tilling soil)
    WATERING_CAN, # Sulama Kabı (Watering crops)
    PICKAXE,      # Kazma (Mining ores / rocks)
    SCYTHE,       # Tırpan (Harvesting crops / cutting grass)
    PISTOL,       # Tabanca (Single-target high-damage combat)
    SHOTGUN,      # Pompalı (Spread horde control)
    SEED_PACKET   # Tohum Paketi (Planting crops)
}

var equipped_item: ItemType = ItemType.HOE

func _ready() -> void:
    Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
    original_camera_y = camera.position.y
    _update_equipped_item()

func _unhandled_input(event: InputEvent) -> void:
    # Toggle mouse capture
    if event.is_action_pressed("ui_cancel"):
        if Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
            Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
        else:
            Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
            
    # Mouse Look
    if event is InputEventMouseMotion and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
        rotate_y(-event.relative.x * mouse_sensitivity)
        camera_pitch -= event.relative.y * mouse_sensitivity
        camera_pitch = clamp(camera_pitch, deg_to_rad(-max_pitch), deg_to_rad(max_pitch))
        camera.rotation.x = camera_pitch
        
    # Hotbar number keys (1-7)
    if event is InputEventKey and event.pressed:
        var key_idx = event.keycode - KEY_1
        if key_idx >= 0 and key_idx < 7:
            active_hotbar_slot = key_idx + 1
            equipped_item = key_idx as ItemType
            _update_equipped_item()
            
    # Primary Action (Left Click)
    if event.is_action_pressed("primary_action") and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
        _perform_primary_action()
        
    # Secondary Action (Right Click)
    if event.is_action_pressed("secondary_action") and Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED:
        _perform_secondary_action()

func _physics_process(delta: float) -> void:
    # 1. Apply Gravity
    if not is_on_floor():
        velocity.y -= gravity * delta

    # 2. Jump
    if Input.is_action_just_pressed("jump") and is_on_floor():
        velocity.y = jump_velocity

    # 3. Sprinting
    is_sprinting = Input.is_key_pressed(KEY_SHIFT)
    var current_speed = sprint_speed if is_sprinting else walk_speed

    # 4. Movement Input Vector
    var input_dir = Input.get_vector("move_left", "move_right", "move_forward", "move_backward")
    var direction = (transform.basis * Vector3(input_dir.x, 0, input_dir.y)).normalized()

    if direction != Vector3.ZERO:
        velocity.x = lerp(velocity.x, direction.x * current_speed, acceleration * delta)
        velocity.z = lerp(velocity.z, direction.z * current_speed, acceleration * delta)
        
        # Head bobbing
        if is_on_floor():
            bob_timer += delta * (bob_frequency * (1.4 if is_sprinting else 1.0))
            camera.position.y = original_camera_y + sin(bob_timer) * bob_amplitude
    else:
        velocity.x = lerp(velocity.x, 0.0, friction * delta)
        velocity.z = lerp(velocity.z, 0.0, friction * delta)
        camera.position.y = lerp(camera.position.y, original_camera_y, delta * 8.0)
        bob_timer = 0.0

    move_and_slide()

func _perform_primary_action() -> void:
    # Trigger viewmodel animation
    if viewmodel_controller:
        viewmodel_controller.play_action(equipped_item)
        
    # Raycast hit resolution
    if raycast.is_colliding():
        var hit_collider = raycast.get_collider()
        var hit_point = raycast.get_collision_point()
        var hit_normal = raycast.get_collision_normal()
        
        # Combat: Hit enemy
        if hit_collider.is_in_group("enemies"):
            var damage = 25.0 if equipped_item == ItemType.PISTOL else 45.0
            hit_collider.take_damage(damage, (hit_collider.global_position - global_position).normalized())
            return
            
        # Farming & Mining: Hit ground / interactable
        var farming_mgr = get_tree().get_first_node_in_group("farming_manager")
        if farming_mgr:
            farming_mgr.handle_tile_interaction(hit_point, equipped_item)

func _perform_secondary_action() -> void:
    if raycast.is_colliding():
        var hit_collider = raycast.get_collider()
        var hit_point = raycast.get_collision_point()
        
        # Interact with Workbenches or Campfire
        if hit_collider.is_in_group("interactables"):
            hit_collider.interact(self)
            return
            
        # Secondary farming: Quick plant
        var farming_mgr = get_tree().get_first_node_in_group("farming_manager")
        if farming_mgr:
            farming_mgr.handle_secondary_interaction(hit_point)

func _update_equipped_item() -> void:
    if viewmodel_controller:
        viewmodel_controller.set_equipped_item(equipped_item)
