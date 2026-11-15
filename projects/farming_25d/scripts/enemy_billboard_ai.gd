extends CharacterBody3D
class_name EnemyBillboardAI

## Guns 'n Goblins Style 2D Billboard Enemy AI
## Operates as a 2D Y-billboard planar sprite in 3D space, chasing the player,
## taking damage with hit flashes, and dropping loot pickups upon death.

@export var max_health: float = 60.0
@export var move_speed: float = 3.2
@export var attack_range: float = 1.4
@export var attack_damage: float = 12.0
@export var attack_cooldown: float = 1.2

@onready var sprite: Sprite3D = $Sprite3D
@onready var anim_player: AnimationPlayer = $AnimationPlayer

var current_health: float
var player: Node3D = null
var attack_timer: float = 0.0
var is_dead: bool = false
var knockback_velocity: Vector3 = Vector3.ZERO

func _ready() -> void:
    current_health = max_health
    add_to_group("enemies")
    
    # Locate player
    player = get_tree().get_first_node_in_group("player")
    
    # Configure Y-billboard sprite properties
    if sprite:
        sprite.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
        sprite.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
        sprite.centered = true
        sprite.offset.y = 16.0 # Bottom-center anchor

func _physics_process(delta: float) -> void:
    if is_dead:
        return

    # Apply gravity
    if not is_on_floor():
        velocity.y -= 14.0 * delta

    # Recover from knockback
    if knockback_velocity.length() > 0.1:
        velocity.x = knockback_velocity.x
        velocity.z = knockback_velocity.z
        knockback_velocity = knockback_velocity.lerp(Vector3.ZERO, delta * 8.0)
    elif player:
        var dist = global_position.distance_to(player.global_position)
        var dir = (player.global_position - global_position).normalized()
        dir.y = 0.0
        
        if dist > attack_range:
            # Chase player
            velocity.x = dir.x * move_speed
            velocity.z = dir.z * move_speed
        else:
            # Within attack range
            velocity.x = 0.0
            velocity.z = 0.0
            attack_timer -= delta
            if attack_timer <= 0.0:
                _perform_attack()
                attack_timer = attack_cooldown

    move_and_slide()

func take_damage(amount: float, knockback_dir: Vector3 = Vector3.ZERO) -> void:
    if is_dead:
        return
        
    current_health -= amount
    knockback_velocity = knockback_dir * 5.0
    
    # Red hit flash
    if sprite:
        var orig_mod = sprite.modulate
        sprite.modulate = Color(1.0, 0.2, 0.2, 1.0)
        var tween = create_tween()
        tween.tween_property(sprite, "modulate", orig_mod, 0.12)
        
    if current_health <= 0.0:
        die()

func _perform_attack() -> void:
    if player and player.has_method("take_damage"):
        player.take_damage(attack_damage)

func die() -> void:
    is_dead = true
    velocity = Vector3.ZERO
    
    # Fade or drop loot
    var tween = create_tween()
    tween.tween_property(sprite, "scale", Vector3(1.2, 0.2, 1.2), 0.2)
    tween.tween_property(sprite, "modulate:a", 0.0, 0.3)
    tween.tween_callback(queue_free)
