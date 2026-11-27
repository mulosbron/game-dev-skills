# Headless math twin of tools/see_through_lib.py, for Godot 4.
#   godot --headless --script see_through_math.gd
# The pixel-drop rule does not need a renderer. A rendered frame is only needed
# to confirm the engine's discard matches this function.
extends SceneTree

const BAYER := [
	0, 8, 2, 10,
	12, 4, 14, 6,
	3, 11, 1, 9,
	15, 7, 13, 5,
]

func _init() -> void:
	var failed := 0
	failed += _check("ease frame 6", is_equal_approx(_ease(6, true, 0.0), 0.5))
	failed += _check("ease frame 12", is_equal_approx(_ease(12, true, 0.0), 1.0))
	failed += _check("ease off 12", is_equal_approx(_ease(12, false, 1.0), 0.0))
	failed += _check("feet level", not _depth(100.0, 100.0))
	failed += _check("feet in front", not _depth(101.0, 100.0))
	failed += _check("feet 1 behind", _depth(99.0, 100.0))
	failed += _check("cover 2", not _cover(2))
	failed += _check("cover 3", _cover(3))
	failed += _check("fade 0.4", is_equal_approx(lerpf(1.0, 0.4, 1.0), 0.4))
	failed += _check("dither inside", _drop(10.0, 0.0, 1.0, 18.0, 16.0, 0.0))
	failed += _check("dither outside", not _drop(40.0, 0.0, 1.0, 18.0, 16.0, 0.0))
	failed += _check("keep six", _kept_in_block() == 6)
	failed += _check("cutout inside", _drop(10.0, 0.0, 1.0, 22.0, 0.0, 0.0))
	failed += _check("cutout outside", not _drop(30.0, 0.0, 1.0, 22.0, 0.0, 0.0))
	failed += _check("radius 0", not _drop(0.0, 0.0, 1.0, 0.0, 0.0, 0.375))
	if failed == 0:
		print("see_through_math: ok")
		quit(0)
	else:
		push_error("see_through_math: %d failed" % failed)
		quit(1)


func _check(label: String, ok: bool) -> int:
	if not ok:
		push_error("FAIL " + label)
		return 1
	return 0


func _ease(frames: int, behind: bool, start: float) -> float:
	var amount := start
	var goal := 1.0 if behind else 0.0
	for _i in frames:
		amount = move_toward(amount, goal, (1.0 / 60.0) / 0.2)
	return amount


func _depth(feet_y: float, base_y: float) -> bool:
	return feet_y < base_y


func _cover(hidden: int) -> bool:
	return hidden > 0 and hidden >= 0.25 * 12.0


func _drop(x: float, y: float, amount: float, radius: float, soft: float, keep: float) -> bool:
	var cell := Vector2(floor(x), floor(y))
	var d := Vector2(cell.x + 0.5, cell.y + 0.5).distance_to(Vector2(0.5, 0.5))
	var reach := (radius + soft) * amount
	var solid := clampf((d - reach) / soft + 1.0, 0.0, 1.0) if soft > 0.0 else (1.0 if d >= reach else 0.0)
	solid = maxf(solid, keep)
	var c := Vector2i(posmod(int(cell.x), 4), posmod(int(cell.y), 4))
	return solid <= (float(BAYER[c.y * 4 + c.x]) + 0.5) / 16.0


func _kept_in_block() -> int:
	var kept := 0
	for y in 4:
		for x in 4:
			var cell := Vector2(x, y)
			var d := Vector2(cell.x + 0.5, cell.y + 0.5).distance_to(Vector2(2, 2))
			var solid := maxf(clampf((d - 34.0) / 16.0 + 1.0, 0.0, 1.0), 0.375)
			var b: int = BAYER[y * 4 + x]
			if solid > (float(b) + 0.5) / 16.0:
				kept += 1
	return kept
