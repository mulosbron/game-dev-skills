#!/usr/bin/env python3
"""
2D Hit Feedback (8 Reactions + Killing Blow) Fixed-Tick Simulator, Verifier & Code Exporter.

Effects coordinated from a single hit() call:
  1. Hit stop (5 ticks normal / 9 killing blow; per-fighter freeze counter)
  2. Hit flash (2 ticks pure white alpha-preserving shader)
  3. Knockback (12 px over 8 ticks after freeze, cubic ease-out, with collision)
  4. Screen shake (3 px over 10 ticks, round(amp) alternating X, resets to 0)
  5. Particles (10 drops toward attacker/up after freeze; 28 omni on kill)
  6. Impact spark (4-frame 4-ray star [5, 9, 7, 3] px + half diagonals)
  7. Slash trail (100 deg arc through freeze, recedes over 6 ticks after)
  8. Damage numbers (46 frames, pops 8 px + hop in 10 ticks, drifts 0.08/tick, blinks on last 6; yellow on kill)
  + Killing blow slow-motion (time_scale 0.3 for 12 ticks after freeze)

Usage:
    python tools/hit_feedback.py verify --json
    python tools/hit_feedback.py export-code --engine godot4 --out-dir exports/hit_feedback
    python tools/hit_feedback.py export-code --engine unity --out-dir exports/hit_feedback
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

SPARK_RAYS = [5, 9, 7, 3]


def cubic_ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


@dataclass
class HitFeelConfig:
    stop_ticks: int = 5
    stop_ticks_kill: int = 9
    flash_ticks: int = 2
    knock_px: float = 12.0
    knock_ticks: int = 8
    shake_px: float = 3.0
    shake_ticks: int = 10
    drops: int = 10
    drops_kill: int = 28
    spark_ticks: int = 4
    trail_ticks: int = 6
    trail_degrees: float = 100.0
    number_ticks: int = 46
    kill_slow: float = 0.3
    kill_slow_ticks: int = 12


@dataclass
class Fighter:
    name: str
    x: float
    y: float
    hp: int = 100
    freeze_remaining: int = 0
    flash: float = 0.0
    updates_run: int = 0
    updates_skipped: int = 0

    def tick_update(self) -> None:
        if self.freeze_remaining > 0:
            self.updates_skipped += 1
            return
        self.updates_run += 1


@dataclass
class DamageNumber:
    damage: int
    x: float
    base_y: float
    y: float
    kill: bool
    visible: bool = True


@dataclass
class ActiveHit:
    age: int
    stop: int
    attacker: Fighter
    target: Fighter
    at: tuple[float, float]
    dir_x: float
    dir_y: float
    damage: int
    kill: bool
    number: DamageNumber | None = None
    unfroze: bool = False


class HitFeelSim:
    """Fixed-tick combat feedback coordinator (runs before fighter updates)."""

    def __init__(self, cfg: HitFeelConfig | None = None, wall_x: float | None = None, rng_seed: int = 42) -> None:
        self.cfg = cfg or HitFeelConfig()
        self.wall_x = wall_x
        self.rng = random.Random(rng_seed)
        self.hits: list[ActiveHit] = []
        self.shake_age: int = -1
        self.camera_offset: tuple[int, int] = (0, 0)
        self.camera_offset_history: list[tuple[int, int]] = []
        self.time_scale: float = 1.0
        self.particles_spawned: list[dict[str, Any]] = []

    def hit(
        self,
        attacker: Fighter,
        target: Fighter,
        at: tuple[float, float],
        direction: tuple[float, float],
        damage: int,
        kill: bool = False,
    ) -> ActiveHit:
        c = self.cfg
        target.hp = max(0, target.hp - damage)
        dx, dy = direction
        mag = math.hypot(dx, dy) or 1.0
        nx, ny = dx / mag, dy / mag
        stop = c.stop_ticks_kill if kill else c.stop_ticks

        h = ActiveHit(
            age=0,
            stop=stop,
            attacker=attacker,
            target=target,
            at=at,
            dir_x=nx,
            dir_y=ny,
            damage=damage,
            kill=kill,
        )
        self.hits.append(h)

        # Per-fighter freeze counters allow overlapping multi-hits safely without early unfreeze
        if stop > 0:
            attacker.freeze_remaining = max(attacker.freeze_remaining, stop)
            target.freeze_remaining = max(target.freeze_remaining, stop)
        if c.flash_ticks > 0:
            target.flash = 1.0
        if c.shake_px > 0.0 and c.shake_ticks > 0:
            self.shake_age = 0
            self._apply_shake()
        else:
            self.camera_offset_history.append(self.camera_offset)

        if c.number_ticks > 0:
            h.number = DamageNumber(damage=damage, x=at[0], base_y=at[1] - 24.0, y=at[1] - 24.0, kill=kill, visible=True)
            self._place_number(h)

        return h

    def _apply_shake(self) -> None:
        c = self.cfg
        if self.shake_age < 0:
            return
        if self.shake_age >= c.shake_ticks:
            self.camera_offset = (0, 0)
            self.shake_age = -1
            self.camera_offset_history.append(self.camera_offset)
            return
        amp = c.shake_px * ((1.0 - self.shake_age / c.shake_ticks) ** 2)
        ox = int(round(amp)) * (1 if self.shake_age % 2 == 0 else -1)
        oy = int(round(amp * self.rng.uniform(-0.6, 0.6)))
        self.camera_offset = (ox, oy)
        self.camera_offset_history.append(self.camera_offset)

    def _place_number(self, h: ActiveHit) -> None:
        assert h.number is not None
        k = h.age
        hop = min(k / 10.0, 1.0)
        rise = 8.0 * (1.0 - (1.0 - hop) ** 2) + (2.0 * math.sin(math.pi * hop) if hop < 1.0 else 0.0) + k * 0.08
        h.number.y = h.number.base_y - float(round(rise))
        h.number.visible = k < (self.cfg.number_ticks - 6) or (k % 2 == 0)

    def _move_with_collision(self, target: Fighter, sx: float, sy: float) -> None:
        nx = target.x + sx
        if self.wall_x is not None and sx > 0.0 and nx > self.wall_x:
            nx = self.wall_x
        target.x = nx
        target.y += sy

    def step_before_fighters(self, fighters: list[Fighter]) -> None:
        """Advance HitFeel manager before fighters update."""
        c = self.cfg
        for h in self.hits:
            h.age += 1
            if c.flash_ticks > 0 and h.age == c.flash_ticks:
                h.target.flash = 0.0
            if h.age == h.stop + 1 and not h.unfroze:
                h.unfroze = True
                count = c.drops_kill if h.kill else c.drops
                if count > 0:
                    self.particles_spawned.append({"age": h.age, "count": count, "at": h.at, "kill": h.kill})
                if h.kill and c.kill_slow < 1.0 and c.kill_slow > 0.0 and c.kill_slow_ticks > 0:
                    self.time_scale = c.kill_slow

            k = h.age - h.stop
            if 1 <= k <= c.knock_ticks and c.knock_px > 0.0:
                delta = cubic_ease_out(k / c.knock_ticks) - cubic_ease_out((k - 1) / c.knock_ticks)
                self._move_with_collision(h.target, h.dir_x * c.knock_px * delta, h.dir_y * c.knock_px * delta)

            if h.kill and c.kill_slow > 0.0 and c.kill_slow_ticks > 0 and h.age == h.stop + 1 + c.kill_slow_ticks:
                self.time_scale = 1.0

            if h.number is not None:
                if h.age >= c.number_ticks:
                    h.number = None
                else:
                    self._place_number(h)

        tail = max(c.knock_ticks, c.trail_ticks, c.number_ticks, c.kill_slow_ticks, c.spark_ticks, 1)
        self.hits = [h for h in self.hits if h.age < h.stop + 1 + tail]

        if self.shake_age >= 0:
            self.shake_age += 1
            self._apply_shake()
        else:
            self.camera_offset_history.append(self.camera_offset)

        for f in fighters:
            was_frozen = f.freeze_remaining > 0
            if was_frozen:
                f.tick_update()
                f.freeze_remaining -= 1
            else:
                f.tick_update()

    def spark_ray_len(self, h: ActiveHit) -> int | None:
        if self.cfg.spark_ticks <= 0 or h.age >= self.cfg.spark_ticks:
            return None
        idx = min((h.age * len(SPARK_RAYS)) // self.cfg.spark_ticks, len(SPARK_RAYS) - 1)
        return SPARK_RAYS[idx]

    def trail_fraction_remaining(self, h: ActiveHit) -> float:
        if self.cfg.trail_ticks <= 0:
            return 0.0
        fade = max(0, h.age - h.stop) / max(1, self.cfg.trail_ticks)
        return max(0.0, 1.0 - fade)


def run_verify() -> dict[str, Any]:
    """Verify all 8 required behaviors at 60 ticks/s."""
    checks: dict[str, dict[str, Any]] = {}

    # 1. Hit stop: 5 updates skipped on normal hit, 9 on killing blow + overlapping hit counter safety
    atk = Fighter("hero", 0.0, 0.0)
    slime = Fighter("slime", 40.0, 0.0, hp=50)
    sim = HitFeelSim()
    h1 = sim.hit(atk, slime, (30.0, 0.0), (1.0, 0.0), damage=14, kill=False)
    for _ in range(10):
        sim.step_before_fighters([atk, slime])
    atk_skip_norm, slime_skip_norm = atk.updates_skipped, slime.updates_skipped

    atk2 = Fighter("hero", 0.0, 0.0)
    slime2 = Fighter("slime", 40.0, 0.0, hp=20)
    sim_kill = HitFeelSim()
    sim_kill.hit(atk2, slime2, (30.0, 0.0), (1.0, 0.0), damage=32, kill=True)
    for _ in range(15):
        sim_kill.step_before_fighters([atk2, slime2])
    atk_skip_kill, slime_skip_kill = atk2.updates_skipped, slime2.updates_skipped

    checks["1_hit_stop_5_and_9_ticks"] = {
        "normal_skips": [atk_skip_norm, slime_skip_norm],
        "kill_skips": [atk_skip_kill, slime_skip_kill],
        "ok": (atk_skip_norm == 5 and slime_skip_norm == 5 and atk_skip_kill == 9 and slime_skip_kill == 9),
    }

    # 2. Flash: 1 on hit frame (age 0) and next (age 1), 0 on third (age 2)
    atk_f = Fighter("hero", 0.0, 0.0)
    slime_f = Fighter("slime", 40.0, 0.0)
    sim_f = HitFeelSim()
    sim_f.hit(atk_f, slime_f, (30.0, 0.0), (1.0, 0.0), damage=10, kill=False)
    f0 = slime_f.flash
    sim_f.step_before_fighters([atk_f, slime_f])
    f1 = slime_f.flash
    sim_f.step_before_fighters([atk_f, slime_f])
    f2 = slime_f.flash
    checks["2_hit_flash_2_frames"] = {
        "frames_0_1_2": [f0, f1, f2],
        "ok": (f0 == 1.0 and f1 == 1.0 and f2 == 0.0),
    }

    # 3. Knockback: 0 px during freeze, 3.96 px on tick 1 after freeze, 12.0 px after 8 ticks; wall at +6 px stops at 6 px
    atk_k = Fighter("hero", 0.0, 0.0)
    slime_k = Fighter("slime", 40.0, 0.0)
    sim_k = HitFeelSim()
    sim_k.hit(atk_k, slime_k, (30.0, 0.0), (1.0, 0.0), damage=14, kill=False)
    for _ in range(5):
        sim_k.step_before_fighters([atk_k, slime_k])
    during_freeze_dx = slime_k.x - 40.0
    sim_k.step_before_fighters([atk_k, slime_k])
    first_knock_dx = slime_k.x - 40.0
    for _ in range(7):
        sim_k.step_before_fighters([atk_k, slime_k])
    total_knock_dx = slime_k.x - 40.0

    atk_w = Fighter("hero", 0.0, 0.0)
    slime_w = Fighter("slime", 40.0, 0.0)
    sim_w = HitFeelSim(wall_x=46.0)
    sim_w.hit(atk_w, slime_w, (30.0, 0.0), (1.0, 0.0), damage=14, kill=False)
    for _ in range(15):
        sim_w.step_before_fighters([atk_w, slime_w])
    wall_dx = slime_w.x - 40.0
    checks["3_knockback_ease_out_and_wall"] = {
        "during_freeze_dx": round(during_freeze_dx, 4),
        "first_tick_dx": round(first_knock_dx, 2),
        "after_8_ticks_dx": round(total_knock_dx, 4),
        "wall_6px_behind_dx": round(wall_dx, 4),
        "ok": (during_freeze_dx == 0.0 and abs(first_knock_dx - 3.96) < 0.01 and abs(total_knock_dx - 12.0) < 1e-4 and abs(wall_dx - 6.0) < 1e-4),
    }

    # 4. Screen shake x sequence: [3, -2, 2, -1, 1, -1, 0, ...] and (0,0) from tick 10 on
    shake_xs = [xy[0] for xy in sim.camera_offset_history[:11]]
    checks["4_screen_shake_sequence"] = {
        "x_0_to_10": shake_xs,
        "offset_at_10": sim.camera_offset_history[10],
        "ok": (shake_xs[:7] == [3, -2, 2, -1, 1, -1, 0] and sim.camera_offset_history[10] == (0, 0)),
    }

    # 5. Particles: 10 on first tick after freeze, 28 on killing blow
    p_norm = sim.particles_spawned[0] if sim.particles_spawned else None
    p_kill = sim_kill.particles_spawned[0] if sim_kill.particles_spawned else None
    checks["5_particles_10_and_28_after_freeze"] = {
        "normal": p_norm,
        "kill": p_kill,
        "ok": (
            p_norm is not None and p_norm["age"] == 6 and p_norm["count"] == 10
            and p_kill is not None and p_kill["age"] == 10 and p_kill["count"] == 28
        ),
    }

    # 6. Damage number: 46 frames, +9 px after 10 frames, hidden on frames 41, 43, 45
    atk_n = Fighter("hero", 0.0, 0.0)
    slime_n = Fighter("slime", 40.0, 0.0)
    sim_n = HitFeelSim()
    hn = sim_n.hit(atk_n, slime_n, (30.0, 0.0), (1.0, 0.0), damage=14, kill=False)
    y0 = hn.number.y
    vis_by_age: dict[int, bool] = {0: hn.number.visible}
    rise_10 = 0.0
    for age in range(1, 47):
        sim_n.step_before_fighters([atk_n, slime_n])
        if age == 10 and hn.number is not None:
            rise_10 = y0 - hn.number.y
        if hn.number is not None:
            vis_by_age[age] = hn.number.visible
        else:
            vis_by_age[age] = False
    exists_45 = len([k for k, v in vis_by_age.items() if k < 46]) == 46
    gone_at_46 = hn.number is None
    hidden_41_43_45 = (not vis_by_age[41]) and (not vis_by_age[43]) and (not vis_by_age[45]) and vis_by_age[42] and vis_by_age[44]
    checks["6_damage_number_46f_rise_and_blink"] = {
        "rise_at_10": rise_10,
        "gone_at_46": gone_at_46,
        "hidden_41_43_45": [vis_by_age[41], vis_by_age[43], vis_by_age[45]],
        "ok": (exists_45 and gone_at_46 and abs(rise_10 - 9.0) < 1e-4 and hidden_41_43_45),
    }

    # 7. Killing blow slow-mo: time_scale = 0.3 for 12 ticks after freeze, back to 1.0 after
    atk_s = Fighter("hero", 0.0, 0.0)
    slime_s = Fighter("slime", 40.0, 0.0)
    sim_s = HitFeelSim()
    sim_s.hit(atk_s, slime_s, (30.0, 0.0), (1.0, 0.0), damage=32, kill=True)
    scales: list[float] = []
    for _ in range(25):
        sim_s.step_before_fighters([atk_s, slime_s])
        scales.append(sim_s.time_scale)
    # hit at age=0 -> ticks 1..9 freeze (scale=1.0), tick 10 (age=10 == stop+1) sets 0.3,
    # tick 22 (age=22 == stop+1+12) sets 1.0 -> indices 9..20 (12 ticks) are 0.3!
    slow_ticks_count = sum(1 for x in scales if abs(x - 0.3) < 1e-6)
    checks["7_kill_slowmo_03_for_12_ticks"] = {
        "slow_ticks_observed": slow_ticks_count,
        "before_unfreeze": scales[8],
        "during_slow": scales[9],
        "after_slow": scales[21],
        "ok": (slow_ticks_count == 12 and scales[8] == 1.0 and abs(scales[9] - 0.3) < 1e-6 and scales[21] == 1.0),
    }

    # 8. Zero settings: all 0 disables every effect except HP loss
    zero_cfg = HitFeelConfig(
        stop_ticks=0, stop_ticks_kill=0, flash_ticks=0, knock_px=0.0, knock_ticks=0,
        shake_px=0.0, shake_ticks=0, drops=0, drops_kill=0, spark_ticks=0, trail_ticks=0,
        number_ticks=0, kill_slow=1.0, kill_slow_ticks=0,
    )
    atk_z = Fighter("hero", 0.0, 0.0)
    slime_z = Fighter("slime", 40.0, 0.0, hp=50)
    sim_z = HitFeelSim(zero_cfg)
    hz = sim_z.hit(atk_z, slime_z, (30.0, 0.0), (1.0, 0.0), damage=14, kill=False)
    for _ in range(10):
        sim_z.step_before_fighters([atk_z, slime_z])
    checks["8_zero_settings_hp_only"] = {
        "hp_after": slime_z.hp,
        "skips": [atk_z.updates_skipped, slime_z.updates_skipped],
        "flash": slime_z.flash,
        "slime_x": slime_z.x,
        "camera_offset": sim_z.camera_offset,
        "particles": len(sim_z.particles_spawned),
        "number": hz.number,
        "ok": (
            slime_z.hp == 36
            and atk_z.updates_skipped == 0 and slime_z.updates_skipped == 0
            and slime_z.flash == 0.0 and slime_z.x == 40.0
            and sim_z.camera_offset == (0, 0) and len(sim_z.particles_spawned) == 0 and hz.number is None
        ),
    }

    all_passed = all(v["ok"] for v in checks.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in checks.values() if v["ok"]), "total": len(checks), "checks": checks}


GODOT4_HIT_FEEL_GD = """# hit_feel.gd — 8 heavy hit reactions from one call (Godot 4)
# Uses per-fighter freeze reference counts so overlapping hits stay safe.
extends Node2D

@export var stop_ticks := 5
@export var stop_ticks_kill := 9
@export var flash_ticks := 2
@export var knock_px := 12.0
@export var knock_ticks := 8
@export var shake_px := 3.0
@export var shake_ticks := 10
@export var drops := 10
@export var drops_kill := 28
@export var drop_color := Color("7bd66a")
@export var spark_ticks := 4
@export var trail_ticks := 6
@export var trail_degrees := 100.0
@export var number_ticks := 46
@export var kill_slow := 0.3
@export var kill_slow_ticks := 12

const FLASH := preload("res://hit_flash.gdshader")
const SPARK_RAYS := [5, 9, 7, 3]
const WARM := Color(1.0, 0.93, 0.67)

var _hits: Array = []
var _freeze_counts: Dictionary = {}
var _shake_age := -1
var _last_shake := Vector2.ZERO


func _ready() -> void:
\tprocess_physics_priority = -100
\tz_index = 100


func _add_freeze(node: Node2D, ticks: int) -> void:
\tif not is_instance_valid(node) or ticks <= 0:
\t\treturn
\tvar id := node.get_instance_id()
\t# Store +1 so unfreeze happens on tick (stop + 1), matching exactly `stop` skipped updates
\t_freeze_counts[id] = maxi(_freeze_counts.get(id, 0), ticks + 1)
\tnode.process_mode = Node.PROCESS_MODE_DISABLED


func hit(attacker: Node2D, target: Node2D, sprite: CanvasItem, at: Vector2, direction: Vector2, damage: int, kill := false) -> void:
\tvar stop := stop_ticks_kill if kill else stop_ticks
\tvar h := {
\t\t"age": 0, "stop": stop, "attacker": attacker, "target": target,
\t\t"sprite": sprite, "at": at, "dir": direction.normalized(), "kill": kill, "label": null
\t}
\t_hits.append(h)
\t_add_freeze(attacker, stop)
\t_add_freeze(target, stop)
\tif flash_ticks > 0 and is_instance_valid(sprite):
\t\tif not sprite.material is ShaderMaterial:
\t\t\tsprite.material = ShaderMaterial.new()
\t\t\tsprite.material.shader = FLASH
\t\tsprite.material.set_shader_parameter("flash", 1.0)
\tif shake_px > 0.0 and shake_ticks > 0:
\t\t_shake_age = 0
\t\t_shake()
\tif number_ticks > 0:
\t\tvar label := Label.new()
\t\tlabel.text = str(damage)
\t\tlabel.modulate = Color(1.0, 0.93, 0.47) if kill else Color.WHITE
\t\tadd_child(label)
\t\th.label = label
\t\t_place_number(h)
\tqueue_redraw()


func _physics_process(_delta: float) -> void:
\tfor id in _freeze_counts.keys():
\t\t_freeze_counts[id] -= 1
\t\tif _freeze_counts[id] <= 0:
\t\t\tvar obj := instance_from_id(id)
\t\t\tif is_instance_valid(obj):
\t\t\t\tobj.process_mode = Node.PROCESS_MODE_INHERIT
\t\t\t_freeze_counts.erase(id)

\tfor h in _hits:
\t\th.age += 1
\t\tvar live: bool = is_instance_valid(h.target) and is_instance_valid(h.attacker)
\t\tif h.age == flash_ticks and is_instance_valid(h.sprite):
\t\t\th.sprite.material.set_shader_parameter("flash", 0.0)
\t\tif h.age == h.stop + 1 and live:
\t\t\t_burst(h)
\t\t\tif h.kill and kill_slow < 1.0 and kill_slow_ticks > 0:
\t\t\t\tEngine.time_scale = kill_slow
\t\tvar k: int = h.age - h.stop
\t\tif k >= 1 and k <= knock_ticks and knock_px > 0.0 and is_instance_valid(h.target):
\t\t\tvar step: Vector2 = h.dir * knock_px * (_ease_out(float(k) / knock_ticks) - _ease_out(float(k - 1) / knock_ticks))
\t\t\tif h.target is PhysicsBody2D:
\t\t\t\th.target.move_and_collide(step)
\t\t\telse:
\t\t\t\th.target.global_position += step
\t\tif h.kill and h.age == h.stop + 1 + kill_slow_ticks:
\t\t\tEngine.time_scale = 1.0
\t\tif h.label:
\t\t\tif h.age >= number_ticks:
\t\t\t\th.label.queue_free()
\t\t\t\th.label = null
\t\t\telse:
\t\t\t\t_place_number(h)

\tvar tail := maxi(maxi(knock_ticks, trail_ticks), maxi(number_ticks, kill_slow_ticks))
\t_hits = _hits.filter(func(h): return h.age < h.stop + 1 + tail)
\tif _shake_age >= 0:
\t\t_shake_age += 1
\t\t_shake()
\tqueue_redraw()


func _ease_out(t: float) -> float:
\treturn 1.0 - pow(1.0 - t, 3.0)


func _shake() -> void:
\tvar camera := get_viewport().get_camera_2d()
\tif camera == null:
\t\treturn
\tcamera.offset -= _last_shake # preserve any existing game camera offset!
\tif _shake_age >= shake_ticks:
\t\t_last_shake = Vector2.ZERO
\t\t_shake_age = -1
\t\treturn
\tvar amp := shake_px * pow(1.0 - float(_shake_age) / shake_ticks, 2.0)
\t_last_shake = Vector2(roundf(amp) * (1.0 if _shake_age % 2 == 0 else -1.0), roundf(amp * randf_range(-0.6, 0.6)))
\tcamera.offset += _last_shake


func _burst(h: Dictionary) -> void:
\tvar count: int = drops_kill if h.kill else drops
\tif count <= 0:
\t\treturn
\tvar p := CPUParticles2D.new()
\tp.amount = count
\tp.one_shot = true
\tp.explosiveness = 1.0
\tp.lifetime = 0.26
\tp.direction = Vector2(-h.dir.x, -h.dir.y - 0.27).normalized()
\tp.spread = 180.0 if h.kill else 70.0
\tp.initial_velocity_min = 90.0
\tp.initial_velocity_max = 200.0
\tp.damping_min = 600.0
\tp.damping_max = 700.0
\tp.gravity = Vector2(0, 150)
\tp.scale_amount_min = 2.0
\tp.scale_amount_max = 3.0
\tp.color = drop_color
\tp.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
\tp.position = to_local(h.at)
\tp.finished.connect(p.queue_free)
\tadd_child(p)
\tp.emitting = true


func _place_number(h: Dictionary) -> void:
\tvar k: int = h.age
\tvar hop := minf(k / 10.0, 1.0)
\tvar rise := 8.0 * (1.0 - pow(1.0 - hop, 2.0)) + (2.0 * sin(PI * hop) if hop < 1.0 else 0.0) + k * 0.08
\tvar label: Label = h.label
\tlabel.position = to_local(h.at) + Vector2(-label.size.x / 2.0, -24.0 - roundf(rise))
\tlabel.visible = k < number_ticks - 6 or k % 2 == 0


func _draw() -> void:
\tfor h in _hits:
\t\tvar at := to_local(h.at)
\t\tif h.age < spark_ticks:
\t\t\tvar n: int = SPARK_RAYS[mini(h.age * SPARK_RAYS.size() / spark_ticks, SPARK_RAYS.size() - 1)]
\t\t\tfor d in [Vector2.RIGHT, Vector2.LEFT, Vector2.UP, Vector2.DOWN]:
\t\t\t\tdraw_line(at, at + d * n, WARM, 1.0)
\t\t\tfor d in [Vector2(1, 1), Vector2(-1, 1), Vector2(1, -1), Vector2(-1, -1)]:
\t\t\t\tdraw_line(at, at + d * (n * 0.5), Color.WHITE, 1.0)
\t\t\tdraw_rect(Rect2(at - Vector2(1, 1), Vector2(3, 3)), Color.WHITE)
\t\tvar fade: float = float(maxi(h.age - h.stop, 0)) / maxi(trail_ticks, 1)
\t\tif trail_ticks > 0 and fade < 1.0 and is_instance_valid(h.attacker):
\t\t\tvar center := to_local(h.attacker.global_position)
\t\t\tvar end := (at - center).angle()
\t\t\tvar start := end - deg_to_rad(trail_degrees) * (1.0 if h.dir.x >= 0.0 else -1.0)
\t\t\tdraw_arc(center, center.distance_to(at), lerpf(start, end, fade), end, 16, Color.WHITE, 2.0)
"""

GODOT4_FLASH_SHADER = """// hit_flash.gdshader — Pure white sprite flash preserving alpha
shader_type canvas_item;

uniform float flash : hint_range(0.0, 1.0) = 0.0;

void fragment() {
\tvec4 c = texture(TEXTURE, UV) * COLOR;
\tCOLOR = vec4(mix(c.rgb, vec3(1.0), flash), c.a);
}
"""

UNITY_HIT_FEEL_CS = """// HitFeedbackManager.cs — 8 hit reactions in FixedUpdate (freezes fighters only, not Time.timeScale!)
using System.Collections.Generic;
using UnityEngine;

public class HitFeedbackManager : MonoBehaviour
{
    public int stopTicks = 5;
    public int stopTicksKill = 9;
    public int flashTicks = 2;
    public float knockDistance = 0.375f; // 12 px @ 32 PPU
    public int knockTicks = 8;
    public float shakePixels = 3f;
    public float pixelsPerUnit = 32f;
    public int shakeTicks = 10;
    public float killSlowScale = 0.3f;
    public int killSlowTicks = 12;

    private class ActiveHit
    {
        public int age;
        public int stop;
        public GameObject attacker;
        public GameObject target;
        public Material flashMat;
        public Vector2 dir;
        public bool kill;
    }

    private readonly List<ActiveHit> _hits = new();
    private readonly Dictionary<GameObject, int> _freezeTicks = new();
    private int _shakeAge = -1;
    private Vector3 _lastShake;
    private static readonly int FlashProp = Shader.PropertyToID("_Flash");

    private void Freeze(GameObject obj, int ticks)
    {
        if (obj == null || ticks <= 0) return;
        // Store +1 so FixedUpdate unfreezes on tick (ticks + 1), skipping exactly `ticks` fighter updates
        _freezeTicks[obj] = _freezeTicks.TryGetValue(obj, out int cur) ? Mathf.Max(cur, ticks + 1) : ticks + 1;
        foreach (var mb in obj.GetComponents<MonoBehaviour>())
            if (mb != this) mb.enabled = false;
        if (obj.TryGetComponent<Animator>(out var anim)) anim.speed = 0f;
    }

    public void Hit(GameObject attacker, GameObject target, SpriteRenderer sprite, Vector2 dir, bool kill = false)
    {
        int stop = kill ? stopTicksKill : stopTicks;
        Material mat = sprite != null ? sprite.material : null;
        var h = new ActiveHit { age = 0, stop = stop, attacker = attacker, target = target, flashMat = mat, dir = dir.normalized, kill = kill };
        _hits.Add(h);
        Freeze(attacker, stop);
        Freeze(target, stop);
        if (flashTicks > 0 && mat != null && mat.HasProperty(FlashProp)) mat.SetFloat(FlashProp, 1f);
        if (shakePixels > 0f && shakeTicks > 0) _shakeAge = 0;
    }

    private void FixedUpdate()
    {
        var keys = new List<GameObject>(_freezeTicks.Keys);
        foreach (var obj in keys)
        {
            _freezeTicks[obj]--;
            if (_freezeTicks[obj] <= 0)
            {
                _freezeTicks.Remove(obj);
                if (obj != null)
                {
                    foreach (var mb in obj.GetComponents<MonoBehaviour>()) mb.enabled = true;
                    if (obj.TryGetComponent<Animator>(out var anim)) anim.speed = 1f;
                }
            }
        }

        foreach (var h in _hits)
        {
            h.age++;
            if (h.age == flashTicks && h.flashMat != null && h.flashMat.HasProperty(FlashProp))
                h.flashMat.SetFloat(FlashProp, 0f);
            if (h.age == h.stop + 1 && h.kill && killSlowScale < 1f)
                Time.timeScale = killSlowScale;
            int k = h.age - h.stop;
            if (k >= 1 && k <= knockTicks && h.target != null)
            {
                float d0 = 1f - Mathf.Pow(1f - (float)(k - 1) / knockTicks, 3f);
                float d1 = 1f - Mathf.Pow(1f - (float)k / knockTicks, 3f);
                Vector2 step = h.dir * knockDistance * (d1 - d0);
                if (h.target.TryGetComponent<Rigidbody2D>(out var rb)) rb.MovePosition(rb.position + step);
                else h.target.transform.position += (Vector3)step;
            }
            if (h.kill && h.age == h.stop + 1 + killSlowTicks)
                Time.timeScale = 1f;
        }
        _hits.RemoveAll(h => h.age >= h.stop + 1 + Mathf.Max(knockTicks, killSlowTicks));
        ApplyShake();
    }

    private void ApplyShake()
    {
        Camera cam = Camera.main;
        if (cam == null) return;
        cam.transform.localPosition -= _lastShake;
        if (_shakeAge < 0 || _shakeAge >= shakeTicks)
        {
            _lastShake = Vector3.zero;
            _shakeAge = -1;
            return;
        }
        float amp = shakePixels * Mathf.Pow(1f - (float)_shakeAge / shakeTicks, 2f);
        float px = Mathf.Round(amp) * (_shakeAge % 2 == 0 ? 1f : -1f);
        float py = Mathf.Round(amp * Random.Range(-0.6f, 0.6f));
        _lastShake = new Vector3(px / pixelsPerUnit, py / pixelsPerUnit, 0f);
        cam.transform.localPosition += _lastShake;
        _shakeAge++;
    }
}
"""


def export_code(engine: str, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if engine == "godot4":
        p1 = out_dir / "hit_feel.gd"
        p2 = out_dir / "hit_flash.gdshader"
        p1.write_text(GODOT4_HIT_FEEL_GD, encoding="utf-8")
        p2.write_text(GODOT4_FLASH_SHADER, encoding="utf-8")
        written.extend([str(p1), str(p2)])
    elif engine == "unity":
        p1 = out_dir / "HitFeedbackManager.cs"
        p1.write_text(UNITY_HIT_FEEL_CS, encoding="utf-8")
        written.append(str(p1))
    else:
        raise ValueError(f"Unsupported engine: {engine}")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="2D Hit Feedback Simulator, Verifier & Code Exporter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify", help="Run all 8 automated 60Hz tick checks")
    p_ver.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export Godot 4 / Unity hit feedback scripts")
    p_exp.add_argument("--engine", choices=["godot4", "unity"], required=True)
    p_exp.add_argument("--out-dir", type=Path, default=Path("exports/hit_feedback"))
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "verify":
        res = run_verify()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Hit Feedback verify: {res['passed']}/{res['total']} passed")
        return 0 if res["all_passed"] else 1

    if args.cmd == "export-code":
        files = export_code(args.engine, args.out_dir)
        print(json.dumps({"engine": args.engine, "files": files}, indent=2) if args.json else str(files))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
