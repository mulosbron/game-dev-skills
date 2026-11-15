---
name: godot
description: Use when writing games in Godot 4 / GDScript, porting a Godot 3 project to 4, or applying this set's Godot house style.
---

# Godot

This set's Godot 4 house style lives in `playbook.md`: ready code for state machine, autoload / event bus, Resource-based data, object pool, components (Health / Hitbox / Hurtbox), scene manager and save system. Before writing a new system, open the matching section and use the same shape; consistency across the project is worth more than reinventing each time.

If you see Godot 3 code or old syntax like `yield`, `setget`, `export var`, `$Tween`, open `migration-3-to-4.md`.

## No deviation in this project
- Every variable and return type is annotated (`var x: int`, `-> void`). In GDScript 2.0, types mean speed.
- Signals are connected as objects: `pressed.connect(_on_pressed)`, `health_changed.emit(hp)`. No string-named signals.
- No `$Node` lookups inside `_process`; cache with `@onready`.
- Anything spawned/destroyed often (bullets, particles, enemies) comes from a pool.
- Cross-scene communication goes through the EventBus autoload, not direct references.
