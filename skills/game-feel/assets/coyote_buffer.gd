extends CharacterBody2D
## Coyote time + input buffering reference implementation (Godot 4, CharacterBody2D).
##
## Requires an Input Action named "jump". Frame order matches `simulate` in
## scripts/feel_sim.py and is verified by tests/test_game_feel.py:
##   1. Record input   2. Jump   3. Move   4. Update coyote counter   5. Tick buffer counter
##
## Numeric defaults are starting values only—compute jump_velocity and gravity
## with scripts/jump_physics.py and frame windows with scripts/feel_sim.py, then
## tune by watching players.

@export var jump_velocity: float = -420.0   # px/s (upward); v0 from jump_physics.py
@export var gravity: float = 1400.0         # px/s^2; gravity_up from jump_physics.py
@export var fall_multiplier: float = 1.0    # gravity * fall_multiplier while falling
@export var coyote_frames: int = 6          # frames after leaving ledge where jump works
@export var buffer_frames: int = 6          # frames before landing to queue jump input

var _coyote: int = 0
var _buffer: int = 0


func _physics_process(delta: float) -> void:
	# 1) Record input: capture player intent rather than requiring frame-perfect timing.
	if Input.is_action_just_pressed("jump"):
		# +1 because the buffer decrements at the end of this frame.
		_buffer = buffer_frames + 1

	# 2) Jump: consume buffered input if grounded or within coyote window.
	if _buffer > 0 and (is_on_floor() or _coyote > 0):
		velocity.y = jump_velocity
		_buffer = 0
		_coyote = 0

	# 3) Move: apply heavier gravity while falling (fall_multiplier > 1).
	var g: float = gravity * (fall_multiplier if velocity.y > 0.0 else 1.0)
	velocity.y += g * delta
	move_and_slide()

	# 4) Coyote counter: refill on floor, count down in air.
	_coyote = coyote_frames if is_on_floor() else max(_coyote - 1, 0)

	# 5) Buffer counter.
	_buffer = max(_buffer - 1, 0)
