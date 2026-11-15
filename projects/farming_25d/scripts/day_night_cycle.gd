extends Node3D
class_name DayNightCycle

## 24-Minute Game Day & Night Cycle System
## Controls 3D Sun/Moon rotation, ambient light shifts, and campfires/lanterns.

@export var day_length_seconds: float = 1440.0 # 24 minutes in real time
@export var current_time: float = 360.0 # Starts at 6:00 AM (dawn)

@onready var sun: DirectionalLight3D = $SunLight
@onready var world_env: WorldEnvironment = $WorldEnvironment

signal hour_passed(current_hour: int)
signal day_passed(day_number: int)

var day_count: int = 1
var last_hour: int = 6

func _process(delta: float) -> void:
    # Advance time
    current_time += (1440.0 / day_length_seconds) * delta
    if current_time >= 1440.0:
        current_time -= 1440.0
        day_count += 1
        emit_signal("day_passed", day_count)
        
    var current_hour = int(current_time / 60.0)
    if current_hour != last_hour:
        last_hour = current_hour
        emit_signal("hour_passed", current_hour)
        
    # Rotate Sun (0 to 360 degrees)
    var time_ratio = current_time / 1440.0
    var sun_angle = (time_ratio * 360.0) - 90.0
    if sun:
        sun.rotation_degrees.x = -sun_angle
        # Day vs Night light intensity
        if current_hour >= 6 and current_hour < 19:
            # Daytime
            sun.light_energy = lerp(sun.light_energy, 1.2, delta * 2.0)
            sun.light_color = Color(1.0, 0.95, 0.85)
        else:
            # Nighttime moonlight
            sun.light_energy = lerp(sun.light_energy, 0.25, delta * 2.0)
            sun.light_color = Color(0.4, 0.5, 0.8)
            
    # Trigger campfires and lanterns at dusk (19:00+)
    var is_night = current_hour >= 19 or current_hour < 6
    get_tree().call_group("night_lights", "set_visible", is_night)
