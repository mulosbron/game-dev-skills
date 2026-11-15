#!/usr/bin/env python3
"""
8-Mode 2D Camera Follow Simulator, Verifier & Code Exporter (128x128 @ 60Hz baseline).

Modes:
  1. locked       - Exact lock on target
  2. smooth       - Exponential damping (rate 2.6/s; rate<=0 snaps)
  3. dead_zone    - Inner safe box (+/-22x, +/-18y in 128x128 view)
  4. rooms        - 128x128 room grid + 0.55s (33-tick) smoothstep transition, tick-1 snap
  5. look_ahead   - Directional 32px velocity lead (rate 3.4/s)
  6. points       - POI smoothstep pull (60->24px, pull 0.6, rate 3.5/s)
  7. aim          - Cursor aim share (0.45 share, rate 8/s)
  8. two_targets  - Midpoint + dynamic zoom (pad 104, clamp [128, 240], move 4.5, zoom 3.5)

Usage:
    python tools/camera_follow_2d.py verify --json
    python tools/camera_follow_2d.py export-code --engine godot4 --out-dir exports/camera_follow_2d
    python tools/camera_follow_2d.py export-code --engine unity --out-dir exports/camera_follow_2d
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

DT_60HZ = 1.0 / 60.0


def exp_alpha(rate: float, dt: float) -> float:
    """Frame-rate independent exponential smoothing factor; rate <= 0 snaps immediately (1.0)."""
    if rate <= 0.0:
        return 1.0
    return 1.0 - math.exp(-rate * dt)


def smoothstep01(t: float) -> float:
    """Cubic Hermite smoothstep clamped to [0, 1]."""
    u = max(0.0, min(1.0, t))
    return u * u * (3.0 - 2.0 * u)


@dataclass
class CameraConfig:
    view_w: float = 128.0
    view_h: float = 128.0
    smooth_rate: float = 2.6
    dead_zone_half_x: float = 22.0
    dead_zone_half_y: float = 18.0
    room_w: float = 128.0
    room_h: float = 128.0
    room_transition_s: float = 0.55
    look_ahead_dist: float = 32.0
    look_ahead_rate: float = 3.4
    poi_outer_radius: float = 60.0
    poi_inner_radius: float = 24.0
    poi_pull: float = 0.6
    poi_rate: float = 3.5
    aim_share: float = 0.45
    aim_rate: float = 8.0
    two_pad: float = 104.0
    two_min_span: float = 128.0
    two_max_span: float = 240.0
    two_move_rate: float = 4.5
    two_zoom_rate: float = 3.5


@dataclass
class CameraState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    span: float = 128.0
    initialized: bool = False
    # look_ahead offset memory
    lead_x: float = 0.0
    lead_y: float = 0.0
    # rooms transition state
    room_ix: int = 0
    room_iy: int = 0
    room_from_x: float = 0.0
    room_from_y: float = 0.0
    room_to_x: float = 0.0
    room_to_y: float = 0.0
    room_elapsed: float = 0.55
    # aim/poi smoothed offset
    offset_x: float = 0.0
    offset_y: float = 0.0
    # diagnostics
    history: list[tuple[float, float, float]] = field(default_factory=list)


class CameraFollow2DSim:
    """Deterministic tick simulator for all 8 2D camera follow modes."""

    def __init__(self, mode: str, cfg: CameraConfig | None = None) -> None:
        self.mode = mode
        self.cfg = cfg or CameraConfig()
        self.state = CameraState(span=self.cfg.view_w)

    def _room_center(self, tx: float, ty: float) -> tuple[int, int, float, float]:
        ix = math.floor(tx / self.cfg.room_w)
        iy = math.floor(ty / self.cfg.room_h)
        return ix, iy, (ix + 0.5) * self.cfg.room_w, (iy + 0.5) * self.cfg.room_h

    def step(
        self,
        tx: float,
        ty: float,
        dt: float = DT_60HZ,
        facing_x: float = 0.0,
        facing_y: float = 0.0,
        pois: list[tuple[float, float]] | None = None,
        aim_dx: float = 0.0,
        aim_dy: float = 0.0,
        tx2: float | None = None,
        ty2: float | None = None,
    ) -> tuple[float, float, float]:
        c = self.cfg
        s = self.state

        if not s.initialized:
            s.initialized = True
            if self.mode == "rooms":
                ix, iy, cx, cy = self._room_center(tx, ty)
                s.room_ix, s.room_iy = ix, iy
                s.room_from_x, s.room_from_y = cx, cy
                s.room_to_x, s.room_to_y = cx, cy
                s.room_elapsed = c.room_transition_s
                s.x, s.y = cx, cy
            elif self.mode == "two_targets" and tx2 is not None and ty2 is not None:
                s.x = 0.5 * (tx + tx2)
                s.y = 0.5 * (ty + ty2)
                sep = max(abs(tx - tx2), abs(ty - ty2))
                s.span = max(c.two_min_span, min(c.two_max_span, sep + c.two_pad))
                s.zoom = c.view_w / s.span
            else:
                s.x, s.y = tx, ty
            s.history.append((s.x, s.y, s.zoom))
            return s.x, s.y, s.zoom

        if self.mode == "locked":
            s.x, s.y = tx, ty

        elif self.mode == "smooth":
            a = exp_alpha(c.smooth_rate, dt)
            s.x += (tx - s.x) * a
            s.y += (ty - s.y) * a

        elif self.mode == "dead_zone":
            if c.dead_zone_half_x <= 0.0 and c.dead_zone_half_y <= 0.0:
                s.x, s.y = tx, ty
            else:
                dx = tx - s.x
                dy = ty - s.y
                if dx > c.dead_zone_half_x:
                    s.x = tx - c.dead_zone_half_x
                elif dx < -c.dead_zone_half_x:
                    s.x = tx + c.dead_zone_half_x
                if dy > c.dead_zone_half_y:
                    s.y = ty - c.dead_zone_half_y
                elif dy < -c.dead_zone_half_y:
                    s.y = ty + c.dead_zone_half_y

        elif self.mode == "rooms":
            ix, iy, cx, cy = self._room_center(tx, ty)
            if ix != s.room_ix or iy != s.room_iy:
                s.room_ix, s.room_iy = ix, iy
                s.room_from_x, s.room_from_y = s.x, s.y
                s.room_to_x, s.room_to_y = cx, cy
                s.room_elapsed = 0.0
            if c.room_transition_s <= 0.0 or s.room_elapsed >= c.room_transition_s:
                s.x, s.y = s.room_to_x, s.room_to_y
            else:
                s.room_elapsed = min(c.room_transition_s, s.room_elapsed + dt)
                w = smoothstep01(s.room_elapsed / c.room_transition_s)
                s.x = s.room_from_x + (s.room_to_x - s.room_from_x) * w
                s.y = s.room_from_y + (s.room_to_y - s.room_from_y) * w

        elif self.mode == "look_ahead":
            if c.look_ahead_dist <= 0.0:
                s.lead_x = 0.0
                s.lead_y = 0.0
            else:
                a = exp_alpha(c.look_ahead_rate, dt)
                goal_lx = facing_x * c.look_ahead_dist
                goal_ly = facing_y * c.look_ahead_dist
                s.lead_x += (goal_lx - s.lead_x) * a
                s.lead_y += (goal_ly - s.lead_y) * a
            s.x = tx + s.lead_x
            s.y = ty + s.lead_y

        elif self.mode == "points":
            goal_ox, goal_oy = 0.0, 0.0
            if c.poi_pull > 0.0 and pois:
                best_w = 0.0
                best_dx, best_dy = 0.0, 0.0
                span = max(1e-6, c.poi_outer_radius - c.poi_inner_radius)
                for px, py in pois:
                    dx, dy = px - tx, py - ty
                    dist = math.hypot(dx, dy)
                    if dist < c.poi_outer_radius:
                        w = smoothstep01((c.poi_outer_radius - dist) / span)
                        if w > best_w:
                            best_w = w
                            best_dx, best_dy = dx, dy
                goal_ox = best_dx * c.poi_pull * best_w
                goal_oy = best_dy * c.poi_pull * best_w
            a = exp_alpha(c.poi_rate, dt)
            s.offset_x += (goal_ox - s.offset_x) * a
            s.offset_y += (goal_oy - s.offset_y) * a
            s.x = tx + s.offset_x
            s.y = ty + s.offset_y

        elif self.mode == "aim":
            if c.aim_share <= 0.0:
                s.offset_x, s.offset_y = 0.0, 0.0
            else:
                a = exp_alpha(c.aim_rate, dt)
                s.offset_x += (aim_dx * c.aim_share - s.offset_x) * a
                s.offset_y += (aim_dy * c.aim_share - s.offset_y) * a
            s.x = tx + s.offset_x
            s.y = ty + s.offset_y

        elif self.mode == "two_targets":
            p2x = tx if tx2 is None else tx2
            p2y = ty if ty2 is None else ty2
            mid_x = 0.5 * (tx + p2x)
            mid_y = 0.5 * (ty + p2y)
            am = exp_alpha(c.two_move_rate, dt)
            az = exp_alpha(c.two_zoom_rate, dt)
            s.x += (mid_x - s.x) * am
            s.y += (mid_y - s.y) * am
            sep = max(abs(tx - p2x), abs(ty - p2y))
            target_span = max(c.two_min_span, min(c.two_max_span, sep + c.two_pad))
            s.span += (target_span - s.span) * az
            s.zoom = c.view_w / s.span

        else:
            raise ValueError(f"Unknown mode: {self.mode}")

        s.history.append((s.x, s.y, s.zoom))
        return s.x, s.y, s.zoom


def run_verify() -> dict[str, Any]:
    """Verify all 8 camera modes + edge guards (rate=0 snap, zero-distance fallback)."""
    checks: dict[str, dict[str, Any]] = {}

    # 1. locked
    sim_lock = CameraFollow2DSim("locked")
    pos_lock = [sim_lock.step(float(i * 7), float(i * 3))[:2] for i in range(5)]
    checks["1_locked"] = {
        "final": pos_lock[-1],
        "ok": all(pos_lock[i] == (float(i * 7), float(i * 3)) for i in range(5)),
    }

    # 2. smooth (rate 2.6/s + rate=0 snap)
    sim_sm = CameraFollow2DSim("smooth")
    sim_sm.step(0.0, 0.0)
    for _ in range(60):
        sx, _, _ = sim_sm.step(100.0, 0.0)
    expected_1s = 100.0 * (1.0 - math.exp(-2.6))
    sim_snap = CameraFollow2DSim("smooth", CameraConfig(smooth_rate=0.0))
    sim_snap.step(0.0, 0.0)
    snap_x, _, _ = sim_snap.step(88.0, 0.0)
    checks["2_smooth_and_rate0_snap"] = {
        "after_1s_x": round(sx, 3),
        "expected_1s_x": round(expected_1s, 3),
        "rate0_snap_x": snap_x,
        "ok": (abs(sx - expected_1s) < 0.05 and snap_x == 88.0),
    }

    # 3. dead_zone (+/-22 x, +/-18 y, Godot drag margins 22/64 & 18/64, 0->locked)
    sim_dz = CameraFollow2DSim("dead_zone")
    sim_dz.step(0.0, 0.0)
    inside_pos = sim_dz.step(20.0, -15.0)[:2]
    outside_pos = sim_dz.step(30.0, -25.0)[:2]
    godot_margin_h = 22.0 / (128.0 * 0.5)
    godot_margin_v = 18.0 / (128.0 * 0.5)
    sim_dz0 = CameraFollow2DSim("dead_zone", CameraConfig(dead_zone_half_x=0.0, dead_zone_half_y=0.0))
    sim_dz0.step(0.0, 0.0)
    dz0_pos = sim_dz0.step(5.0, 7.0)[:2]
    checks["3_dead_zone"] = {
        "inside_stays": inside_pos,
        "outside_clamps_to": outside_pos,
        "godot_drag_margins": [round(godot_margin_h, 5), round(godot_margin_v, 5)],
        "zero_fallback_locked": dz0_pos,
        "ok": (
            inside_pos == (0.0, 0.0)
            and outside_pos == (8.0, -7.0)
            and abs(godot_margin_h - 0.34375) < 1e-6
            and abs(godot_margin_v - 0.28125) < 1e-6
            and dz0_pos == (5.0, 7.0)
        ),
    }

    # 4. rooms (128x128 rooms, tick-1 snap, 0.55s = 33 ticks smoothstep)
    sim_rm = CameraFollow2DSim("rooms")
    init_rm = sim_rm.step(10.0, 20.0)[:2]  # room 0 -> (64, 64)
    # Cross into room (1, 0) -> center (192, 64)
    mid_rm = None
    for tick in range(1, 34):
        rx, ry, _ = sim_rm.step(130.0, 20.0)
        if tick == 16:
            mid_rm = (rx, ry)
    checks["4_rooms_tick1_snap_and_33tick_smoothstep"] = {
        "tick1_snap": init_rm,
        "tick16_mid_x": round(mid_rm[0], 3) if mid_rm else None,
        "tick33_arrived": (round(rx, 4), round(ry, 4)),
        "ok": (init_rm == (64.0, 64.0) and abs(rx - 192.0) < 1e-4 and abs(ry - 64.0) < 1e-4 and 64.0 < mid_rm[0] < 192.0),
    }

    # 5. look_ahead (32px lead, rate 3.4/s -> 30.9px after 1s walk, ~1.0px after 1s rest; dist=0->locked)
    sim_la = CameraFollow2DSim("look_ahead")
    sim_la.step(0.0, 0.0, facing_x=0.0)
    for i in range(1, 61):
        px = i * 1.0
        cx, _, _ = sim_la.step(px, 0.0, facing_x=1.0)
    lead_after_1s_walk = cx - 60.0
    for _ in range(60):
        cx_rest, _, _ = sim_la.step(60.0, 0.0, facing_x=0.0)
    lead_after_1s_rest = cx_rest - 60.0
    sim_la0 = CameraFollow2DSim("look_ahead", CameraConfig(look_ahead_dist=0.0))
    sim_la0.step(0.0, 0.0)
    la0_x, _, _ = sim_la0.step(12.0, 0.0, facing_x=1.0)
    checks["5_look_ahead"] = {
        "walk_1s_lead_px": round(lead_after_1s_walk, 2),
        "rest_1s_lead_px": round(lead_after_1s_rest, 2),
        "dist0_locked_x": la0_x,
        "ok": (abs(lead_after_1s_walk - 30.93) < 0.2 and abs(lead_after_1s_rest - 1.03) < 0.2 and la0_x == 12.0),
    }

    # 6. points (POI group, smoothstep 60->24px, pull 0.6, rate 3.5/s -> 0px@60, 14.0px@40, 14.4px@24)
    def steady_poi_offset(dist: float) -> float:
        sim_p = CameraFollow2DSim("points")
        sim_p.step(0.0, 0.0, pois=[(dist, 0.0)])
        for _ in range(300):
            x, _, _ = sim_p.step(0.0, 0.0, pois=[(dist, 0.0)])
        return x

    off_60 = steady_poi_offset(60.0)
    off_40 = steady_poi_offset(40.0)
    off_24 = steady_poi_offset(24.0)
    sim_p0 = CameraFollow2DSim("points", CameraConfig(poi_pull=0.0))
    sim_p0.step(0.0, 0.0, pois=[(24.0, 0.0)])
    p0_x, _, _ = sim_p0.step(10.0, 0.0, pois=[(34.0, 0.0)])
    checks["6_points_poi"] = {
        "offset_at_60px": round(off_60, 3),
        "offset_at_40px": round(off_40, 2),
        "offset_at_24px": round(off_24, 2),
        "pull0_locked_x": p0_x,
        "ok": (abs(off_60) < 1e-4 and abs(off_40 - 14.0) < 0.15 and abs(off_24 - 14.4) < 0.15 and p0_x == 10.0),
    }

    # 7. aim (share 0.45, rate 8/s -> 27px @ 60px steady, 44.2px @ 100px after 0.5s, 45px steady; share=0->locked)
    sim_a60 = CameraFollow2DSim("aim")
    sim_a60.step(0.0, 0.0, aim_dx=60.0)
    for _ in range(240):
        a60_x, _, _ = sim_a60.step(0.0, 0.0, aim_dx=60.0)

    sim_a100 = CameraFollow2DSim("aim")
    sim_a100.step(0.0, 0.0, aim_dx=0.0)
    for _ in range(30):  # 0.5s @ 60Hz
        a100_half, _, _ = sim_a100.step(0.0, 0.0, aim_dx=100.0)
    for _ in range(240):
        a100_steady, _, _ = sim_a100.step(0.0, 0.0, aim_dx=100.0)
    sim_a0 = CameraFollow2DSim("aim", CameraConfig(aim_share=0.0))
    sim_a0.step(0.0, 0.0, aim_dx=100.0)
    a0_x, _, _ = sim_a0.step(5.0, 0.0, aim_dx=100.0)
    checks["7_aim"] = {
        "steady_60px": round(a60_x, 2),
        "after_0_5s_100px": round(a100_half, 2),
        "steady_100px": round(a100_steady, 2),
        "share0_locked_x": a0_x,
        "ok": (
            abs(a60_x - 27.0) < 0.05
            and abs(a100_half - 44.2) < 0.15
            and abs(a100_steady - 45.0) < 0.05
            and a0_x == 5.0
        ),
    }

    # 8. two_targets (pad 104, clamp [128, 240], move 4.5, zoom 3.5 -> 204/0.627 @ 100px, 240/0.533 @ 200px)
    sim_t100 = CameraFollow2DSim("two_targets")
    sim_t100.step(-50.0, 0.0, tx2=50.0, ty2=0.0)
    for _ in range(240):
        mx100, _, z100 = sim_t100.step(-50.0, 0.0, tx2=50.0, ty2=0.0)
    span100 = sim_t100.state.span

    sim_t200 = CameraFollow2DSim("two_targets")
    sim_t200.step(-100.0, 0.0, tx2=100.0, ty2=0.0)
    for _ in range(240):
        mx200, _, z200 = sim_t200.step(-100.0, 0.0, tx2=100.0, ty2=0.0)
    span200 = sim_t200.state.span

    checks["8_two_targets"] = {
        "at_100px": {"span": round(span100, 1), "zoom": round(z100, 3), "mid_x": round(mx100, 3)},
        "at_200px": {"span": round(span200, 1), "zoom": round(z200, 3), "mid_x": round(mx200, 3)},
        "ok": (
            abs(span100 - 204.0) < 0.2
            and abs(z100 - 0.627) < 0.002
            and abs(span200 - 240.0) < 0.2
            and abs(z200 - 0.533) < 0.002
        ),
    }

    all_passed = all(v["ok"] for v in checks.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in checks.values() if v["ok"]), "total": len(checks), "checks": checks}


GODOT4_CAMERA2D_GD = """# CameraFollow2D.gd — 8-mode 2D Camera2D controller (Godot 4)
# Attach directly to Camera2D. Set process_physics_priority > player (e.g. 300)
# or call snap_or_step() right after player move_and_slide() so there is zero 1-frame lag.
class_name CameraFollow2D
extends Camera2D

enum Mode { LOCKED, SMOOTH, DEAD_ZONE, ROOMS, LOOK_AHEAD, POINTS, AIM, TWO_TARGETS }

@export var mode: Mode = Mode.SMOOTH
@export var target_path: NodePath
@export var second_target_path: NodePath
@export var view_size := Vector2(128.0, 128.0)

@export_group("Smooth & Dead Zone")
@export var smooth_rate: float = 2.6 # 0 = instant snap
@export var dead_zone_half_px := Vector2(22.0, 18.0) # 128x128 -> drag_left/right=0.34375, top/bottom=0.28125

@export_group("Rooms")
@export var room_size := Vector2(128.0, 128.0)
@export var room_transition_sec: float = 0.55 # ~33 frames @ 60Hz

@export_group("Look Ahead & Aim")
@export var look_ahead_dist: float = 32.0 # 0 -> locked
@export var look_ahead_rate: float = 3.4
@export var aim_share: float = 0.45 # 0 -> locked
@export var aim_rate: float = 8.0

@export_group("Points of Interest")
@export var poi_group: StringName = &"camera_poi"
@export var poi_outer_px: float = 60.0
@export var poi_inner_px: float = 24.0
@export var poi_pull: float = 0.6
@export var poi_rate: float = 3.5

@export_group("Two Targets")
@export var two_pad_px: float = 104.0
@export var two_min_span_px: float = 128.0
@export var two_max_span_px: float = 240.0
@export var two_move_rate: float = 4.5
@export var two_zoom_rate: float = 3.5

var _initialized := false
var _lead := Vector2.ZERO
var _offset := Vector2.ZERO
var _room_idx := Vector2i.ZERO
var _room_from := Vector2.ZERO
var _room_to := Vector2.ZERO
var _room_t: float = 1.0
var _span: float = 128.0


func _ready() -> void:
\tprocess_physics_priority = 300
\t_span = view_size.x
\t_sync_drag_margins()


func _sync_drag_margins() -> void:
\tdrag_horizontal_enabled = (mode == Mode.DEAD_ZONE) and (dead_zone_half_px.x > 0.0)
\tdrag_vertical_enabled = (mode == Mode.DEAD_ZONE) and (dead_zone_half_px.y > 0.0)
\tvar half_view := view_size * 0.5
\tif half_view.x > 0.0:
\t\tvar mx := clampf(dead_zone_half_px.x / half_view.x, 0.0, 1.0)
\t\tdrag_left_margin = mx
\t\tdrag_right_margin = mx
\tif half_view.y > 0.0:
\t\tvar my := clampf(dead_zone_half_px.y / half_view.y, 0.0, 1.0)
\t\tdrag_top_margin = my
\t\tdrag_bottom_margin = my


func _exp_alpha(rate: float, delta: float) -> float:
\treturn 1.0 if rate <= 0.0 else (1.0 - exp(-rate * delta))


func _smoothstep01(t: float) -> float:
\tvar u := clampf(t, 0.0, 1.0)
\treturn u * u * (3.0 - 2.0 * u)


func _physics_process(delta: float) -> void:
\tvar target := get_node_or_null(target_path) as Node2D
\tif target == null:
\t\treturn
\tvar p := target.global_position
\tif not _initialized:
\t\t_initialized = true
\t\tif mode == Mode.ROOMS:
\t\t\t_room_idx = Vector2i(floori(p.x / room_size.x), floori(p.y / room_size.y))
\t\t\t_room_to = (Vector2(_room_idx) + Vector2(0.5, 0.5)) * room_size
\t\t\t_room_from = _room_to
\t\t\t_room_t = 1.0
\t\t\tglobal_position = _room_to
\t\telse:
\t\t\tglobal_position = p
\t\treturn

\tmatch mode:
\t\tMode.LOCKED:
\t\t\tglobal_position = p
\t\tMode.SMOOTH:
\t\t\tglobal_position = global_position.lerp(p, _exp_alpha(smooth_rate, delta))
\t\tMode.DEAD_ZONE:
\t\t\tif dead_zone_half_px == Vector2.ZERO:
\t\t\t\tglobal_position = p
\t\t\telse:
\t\t\t\tvar d := p - global_position
\t\t\t\tif d.x > dead_zone_half_px.x: global_position.x = p.x - dead_zone_half_px.x
\t\t\t\telif d.x < -dead_zone_half_px.x: global_position.x = p.x + dead_zone_half_px.x
\t\t\t\tif d.y > dead_zone_half_px.y: global_position.y = p.y - dead_zone_half_px.y
\t\t\t\telif d.y < -dead_zone_half_px.y: global_position.y = p.y + dead_zone_half_px.y
\t\tMode.ROOMS:
\t\t\tvar idx := Vector2i(floori(p.x / room_size.x), floori(p.y / room_size.y))
\t\t\tif idx != _room_idx:
\t\t\t\t_room_idx = idx
\t\t\t\t_room_from = global_position
\t\t\t\t_room_to = (Vector2(idx) + Vector2(0.5, 0.5)) * room_size
\t\t\t\t_room_t = 0.0
\t\t\tif room_transition_sec <= 0.0 or _room_t >= 1.0:
\t\t\t\tglobal_position = _room_to
\t\t\telse:
\t\t\t\t_room_t = minf(1.0, _room_t + delta / room_transition_sec)
\t\t\t\tglobal_position = _room_from.lerp(_room_to, _smoothstep01(_room_t))
\t\tMode.LOOK_AHEAD:
\t\t\tvar facing := Vector2.ZERO
\t\t\tif target is CharacterBody2D and target.velocity.length_squared() > 1.0:
\t\t\t\tfacing = target.velocity.normalized()
\t\t\tvar goal := Vector2.ZERO if look_ahead_dist <= 0.0 else facing * look_ahead_dist
\t\t\t_lead = _lead.lerp(goal, _exp_alpha(look_ahead_rate, delta))
\t\t\tglobal_position = p + _lead
\t\tMode.POINTS:
\t\t\tvar goal_o := Vector2.ZERO
\t\t\tif poi_pull > 0.0:
\t\t\t\tvar best_w := 0.0
\t\t\t\tfor node in get_tree().get_nodes_in_group(poi_group):
\t\t\t\t\tif node is Node2D:
\t\t\t\t\t\tvar delta_p: Vector2 = node.global_position - p
\t\t\t\t\t\tvar dist := delta_p.length()
\t\t\t\t\t\tif dist < poi_outer_px:
\t\t\t\t\t\t\tvar w := _smoothstep01((poi_outer_px - dist) / maxf(0.001, poi_outer_px - poi_inner_px))
\t\t\t\t\t\t\tif w > best_w:
\t\t\t\t\t\t\t\tbest_w = w
\t\t\t\t\t\t\t\tgoal_o = delta_p * poi_pull * w
\t\t\t_offset = _offset.lerp(goal_o, _exp_alpha(poi_rate, delta))
\t\t\tglobal_position = p + _offset
\t\tMode.AIM:
\t\t\tvar aim_delta := Vector2.ZERO if aim_share <= 0.0 else (get_global_mouse_position() - p) * aim_share
\t\t\t_offset = _offset.lerp(aim_delta, _exp_alpha(aim_rate, delta))
\t\t\tglobal_position = p + _offset
\t\tMode.TWO_TARGETS:
\t\t\tvar second := get_node_or_null(second_target_path) as Node2D
\t\t\tvar p2 := p if second == null else second.global_position
\t\t\tvar mid := (p + p2) * 0.5
\t\t\tglobal_position = global_position.lerp(mid, _exp_alpha(two_move_rate, delta))
\t\t\tvar sep := maxf(absf(p.x - p2.x), absf(p.y - p2.y))
\t\t\tvar target_span := clampf(sep + two_pad_px, two_min_span_px, two_max_span_px)
\t\t\t_span = lerpf(_span, target_span, _exp_alpha(two_zoom_rate, delta))
\t\t\tvar z := view_size.x / _span
\t\t\tzoom = Vector2(z, z)
"""

UNITY_ROOM_FOCUS_CS = """// RoomFocus.cs — Cinemachine 3 grid-room snapper & smoothstep focus proxy (128x128 @ 0.55s)
using UnityEngine;

public class RoomFocus : MonoBehaviour
{
    public Transform player;
    public Vector2 roomSize = new Vector2(128f, 128f);
    public float transitionDuration = 0.55f;

    private bool _initialized;
    private Vector2Int _roomIdx;
    private Vector3 _fromPos;
    private Vector3 _toPos;
    private float _elapsed;

    private void LateUpdate()
    {
        if (player == null) return;
        int ix = Mathf.FloorToInt(player.position.x / roomSize.x);
        int iy = Mathf.FloorToInt(player.position.y / roomSize.y);
        Vector2Int idx = new Vector2Int(ix, iy);
        Vector3 center = new Vector3((ix + 0.5f) * roomSize.x, (iy + 0.5f) * roomSize.y, transform.position.z);

        if (!_initialized)
        {
            _initialized = true;
            _roomIdx = idx;
            _fromPos = center;
            _toPos = center;
            _elapsed = transitionDuration;
            transform.position = center;
            return;
        }

        if (idx != _roomIdx)
        {
            _roomIdx = idx;
            _fromPos = transform.position;
            _toPos = center;
            _elapsed = 0f;
        }

        if (transitionDuration <= 0f || _elapsed >= transitionDuration)
        {
            transform.position = _toPos;
            return;
        }

        _elapsed = Mathf.Min(transitionDuration, _elapsed + Time.deltaTime);
        float t = Mathf.SmoothStep(0f, 1f, _elapsed / transitionDuration);
        transform.position = Vector3.Lerp(_fromPos, _toPos, t);
    }
}
"""

UNITY_CAMERA_POI_CS = """// CameraPoi.cs — Point of Interest marker read by PoiFocus in Unity
using UnityEngine;

public class CameraPoi : MonoBehaviour
{
    public float outerRadius = 60f;
    public float innerRadius = 24f;
    [Range(0f, 1f)] public float pullStrength = 0.6f;
}
"""

UNITY_POI_FOCUS_CS = """// PoiFocus.cs — Pulls Cinemachine TrackingTarget toward active CameraPoi points
// Convert rate to Cinemachine Damping via: Damping = 4.605f / rate (e.g. rate 3.5 -> 1.316)
using UnityEngine;

public class PoiFocus : MonoBehaviour
{
    public Transform player;
    public CameraPoi[] pois;
    public float rate = 3.5f;

    private Vector3 _offset;

    private void LateUpdate()
    {
        if (player == null) return;
        Vector3 goal = Vector3.zero;
        float bestWeight = 0f;

        if (pois != null)
        {
            foreach (var poi in pois)
            {
                if (poi == null || poi.pullStrength <= 0f) continue;
                Vector3 delta = poi.transform.position - player.position;
                delta.z = 0f;
                float dist = delta.magnitude;
                if (dist < poi.outerRadius)
                {
                    float u = Mathf.Clamp01((poi.outerRadius - dist) / Mathf.Max(0.001f, poi.outerRadius - poi.innerRadius));
                    float w = u * u * (3f - 2f * u);
                    if (w > bestWeight)
                    {
                        bestWeight = w;
                        goal = delta * (poi.pullStrength * w);
                    }
                }
            }
        }

        float alpha = rate <= 0f ? 1f : 1f - Mathf.Exp(-rate * Time.deltaTime);
        _offset = Vector3.Lerp(_offset, goal, alpha);
        transform.position = player.position + _offset;
    }
}
"""

UNITY_AIM_FOCUS_CS = """// AimFocus.cs — Blends player and world mouse cursor (share 0.45, rate 8/s -> Cinemachine Damping 4.605/8 = 0.576)
using UnityEngine;

public class AimFocus : MonoBehaviour
{
    public Transform player;
    public Camera worldCamera;
    [Range(0f, 1f)] public float share = 0.45f;
    public float rate = 8.0f;

    private Vector3 _offset;

    private void LateUpdate()
    {
        if (player == null || worldCamera == null) return;
        Vector3 goal = Vector3.zero;
        if (share > 0f)
        {
            Vector3 mouseWorld = worldCamera.ScreenToWorldPoint(Input.mousePosition);
            mouseWorld.z = player.position.z;
            goal = (mouseWorld - player.position) * share;
        }
        float alpha = rate <= 0f ? 1f : 1f - Mathf.Exp(-rate * Time.deltaTime);
        _offset = Vector3.Lerp(_offset, goal, alpha);
        transform.position = player.position + _offset;
    }
}
"""


def export_engine_files(engine: str, out_dir: Path) -> list[str]:
    """Write engine-specific scripts into out_dir and return created file paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if engine == "godot4":
        p = out_dir / "CameraFollow2D.gd"
        p.write_text(GODOT4_CAMERA2D_GD, encoding="utf-8")
        written.append(str(p))
    elif engine == "unity":
        files = {
            "RoomFocus.cs": UNITY_ROOM_FOCUS_CS,
            "CameraPoi.cs": UNITY_CAMERA_POI_CS,
            "PoiFocus.cs": UNITY_POI_FOCUS_CS,
            "AimFocus.cs": UNITY_AIM_FOCUS_CS,
        }
        for name, src in files.items():
            p = out_dir / name
            p.write_text(src, encoding="utf-8")
            written.append(str(p))
    else:
        raise ValueError(f"Unsupported engine: {engine}")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="8-Mode 2D Camera Follow Simulator & Exporter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser("verify", help="Verify all 8 camera modes at 60Hz")
    p_verify.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export Godot 4 / Unity Cinemachine 3 scripts")
    p_exp.add_argument("--engine", choices=["godot4", "unity"], required=True)
    p_exp.add_argument("--out-dir", type=Path, default=Path("exports/camera_follow_2d"))
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "verify":
        res = run_verify()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Camera Follow 2D verify: {res['passed']}/{res['total']} passed")
        return 0 if res["all_passed"] else 1

    if args.cmd == "export-code":
        paths = export_engine_files(args.engine, args.out_dir)
        if args.json:
            print(json.dumps({"engine": args.engine, "files": paths}, indent=2))
        else:
            print("Exported:", ", ".join(paths))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
