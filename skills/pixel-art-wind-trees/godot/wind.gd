# wind.gd: add it as an autoload named "Wind".
# Gusts are patches of stronger wind that cross the map, each on its own schedule. Between them the air is still.
extends Node

const LOOP := 20.0          # the gust pattern repeats after this many seconds
const WAVE_PERIOD := 1.54   # seconds for a leaf clump to walk its loop once
const WAVE_LENGTH := 69.0   # px between two crests of the leaf wave, along the wind

# [second it enters at the left, speed px/s, centre y, half height (0 = the whole map), length px, strength]
var gusts := [
	[18.6, 65.0, 0.0, 0.0, 44.0, 1.25],   # the big one
	[19.8, 65.0, 0.0, 0.0, 26.0, 0.5],    # and its tail
	[1.5, 60.0, 95.0, 45.0, 30.0, 0.6],   # a quick one through the middle
	[6.0, 55.0, 150.0, 60.0, 34.0, 0.75], # a medium one along the front
	[7.3, 55.0, 145.0, 65.0, 30.0, 0.9],  # with a second hit right behind it
	[8.5, 50.0, 50.0, 55.0, 30.0, 0.55],  # a light puff at the back
]
var time := 0.0


func _process(delta: float) -> void:
	time += delta


# How far along the wind a point is. The wind blows right and a little toward the camera.
func along(p: Vector2) -> float:
	return p.x + 0.25 * p.y


func _field(p: Vector2, spread: float) -> float:
	var total := 0.0
	for g in gusts:
		var path: float = g[1] * LOOP
		var d := fposmod(along(p) - g[1] * (time - g[0]) + path / 2.0, path) - path / 2.0
		var a: float = g[5] * exp(-pow(d / (g[4] * spread), 2.0))
		if g[3] > 0.0:
			a *= exp(-pow((p.y - g[2]) / (g[3] * (1.6 if spread > 1.0 else 1.0)), 2.0))
		total += a
	return total


# 0 in still air, about 1 inside a big gust.
func gust(p: Vector2) -> float:
	return _field(p, 1.0)


# The wide, soft area around a gust, 0 to 1: leaves start moving before it arrives and stop soon after.
func breeze(p: Vector2) -> float:
	return minf(1.6 * _field(p, 2.2), 1.0)


# Where a leaf clump at p is in its loop. The phase travels with the wind, so the clumps go one after another.
func wave_phase(p: Vector2) -> float:
	return TAU * (time / WAVE_PERIOD - along(p) / WAVE_LENGTH)
