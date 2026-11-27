# wind_tree.gd: put it on the tree's Node2D, with its origin at the foot of the trunk.
# Children: the trunk and inside sprites, and a node named "Clumps" with one Sprite2D per leaf clump.
# All layers are cut from the same canvas, so they share one position.
extends Node2D

@export var push := 2.2              ## px a full gust pushes the loosest clump
@export var spring_period := 2.2     ## seconds per swing: big trees slow, bushes quick
@export var damping := 0.35          ## higher settles sooner
@export var inner_stiffness := 0.35  ## how much a clump at the canopy's centre moves (1 = as much as the edge)
@export var trunk_bend := 0.0        ## 0 = the trunk stays put (oak), 1 = it bends and the layers ride it (pine)
@export var trunk: Sprite2D          ## only needed when trunk_bend is above 0 (it gets row_bend.gdshader)

const POSE_TIME := 0.1               # leaves change pose 10 times a second, like a hand-drawn loop

var lean := 0.0
var lean_speed := 0.0
var pose_clock := 0.0
var clumps: Array = []               # [sprite, rest position, centre, weight, height 0..1]


func _ready() -> void:
	var box := Rect2()
	for s: Sprite2D in $Clumps.get_children():
		var used := Rect2(s.texture.get_image().get_used_rect())
		var corner := s.position - (s.texture.get_size() / 2.0 if s.centered else Vector2.ZERO)
		var centre := corner + used.get_center()
		box = Rect2(centre, Vector2.ZERO) if clumps.is_empty() else box.expand(centre)
		clumps.append([s, s.position, centre, 1.0, 0.0])
	var height := maxf(-box.position.y, 1.0)
	for c in clumps:
		var d: Vector2 = (c[2] - box.get_center()) / (box.size / 2.0).max(Vector2.ONE)
		c[3] = lerpf(inner_stiffness, 1.0, minf(d.length(), 1.0))    # stiff in the middle, loose at the edge
		c[4] = clampf(-c[2].y / height, 0.0, 1.0)


func _process(delta: float) -> void:
	# The whole tree is one spring that the gust pushes: it leans, swings back a little past upright and settles.
	var w0 := TAU / spring_period
	var target := push * Wind.gust(global_position)
	lean_speed += (w0 * w0 * (target - lean) - 2.0 * damping * w0 * lean_speed) * delta
	lean += lean_speed * delta

	pose_clock += delta
	if pose_clock < POSE_TIME:
		return
	pose_clock -= POSE_TIME
	for c in clumps:
		var p: Vector2 = global_position + c[2]
		var gust := Wind.gust(p)
		var breeze := Wind.breeze(p)
		var a := Wind.wave_phase(p)
		var w: float = c[3]
		var ride: float = lean * lerpf(w, pow(c[4], 2.0), trunk_bend)
		# the loop: up, right, down, back. 1 px in a breeze, wider in a gust. Whole pixels only.
		var dx := ride + w * (0.9 * breeze + 1.3 * gust) * (0.5 - 0.5 * cos(a))
		var dy := -w * (0.75 * breeze + 0.5 * gust) * maxf(sin(a), 0.0)
		c[0].position = c[1] + Vector2(roundf(dx), roundf(dy))
	if trunk_bend > 0.0 and trunk:
		(trunk.material as ShaderMaterial).set_shader_parameter("lean", lean * trunk_bend)
