# Godot 3 → Godot 4 Migration Notes

The model knows most of this; this file holds the mappings that get mixed up most often.

| Godot 3 | Godot 4 |
|---------|---------|
| `export var x` | `@export var x` (enrich with `@export_range`, `@export_file`, etc.) |
| `onready var y` | `@onready var y` |
| `tool` | `@tool` (top of file) |
| `var hp setget set_hp, get_hp` | inline `set(value): ... get: ...` block |
| `yield(timer, "timeout")` | `await timer.timeout` |
| `connect("pressed", self, "_on_pressed")` | `pressed.connect(_on_pressed)` |
| `emit_signal("died")` | `died.emit()` |
| `$Tween.interpolate_property(...)` + `start()` | `var t := create_tween(); t.tween_property(...)` |
| `.function_name()` (parent call) | `super()` / `super.function_name()` |
| `KinematicBody2D` + `move_and_slide(velocity)` | `CharacterBody2D`, `velocity` is a member, `move_and_slide()` takes no args |
| `var enemies = []` | `var enemies: Array[Node] = []` |

## Setter example

```gdscript
var health: int:
    set(value):
        health = value
        health_changed.emit(health)
    get:
        return health
```

## Tween example

```gdscript
var tween := create_tween()
tween.tween_property($Sprite, "position", Vector2(100, 100), 1.0)
tween.parallel().tween_property($Sprite, "modulate:a", 0.0, 1.0)
```

## Common error

"Identifier 'Tween' is not a valid type" → Tween is no longer typed explicitly; use the return of `create_tween()` directly.
