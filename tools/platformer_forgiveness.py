#!/usr/bin/env python3
"""
2D / 2.5D Platformer Forgiveness Simulator, Verifier & Engine Code Exporter:
  - Coyote Time (0.1s = 6 ticks @ 60Hz)
  - Jump Buffering (0.1s = 6 ticks @ 60Hz)
  - Corner Correction (4 px whole number; ledge feet-lift + upward ceiling slide)

Usage:
    python tools/platformer_forgiveness.py verify --json
    python tools/platformer_forgiveness.py export-code --engine godot4 --out exports/platformer/player.gd
    python tools/platformer_forgiveness.py export-code --engine unity --out exports/platformer/PlatformerForgivenessController.cs
    python tools/platformer_forgiveness.py export-code --engine godot3d --out exports/platformer/player_25d.gd
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8")

BIG_TICKS = 1000
SKIN = 1e-4


@dataclass(frozen=True)
class Rect:
    """Axis-aligned box defined by top-left (x, y) and size (w, h), +Y down."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def translated(self, dx: float, dy: float) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def overlaps_with_skin(self, other: "Rect", skin: float = SKIN) -> bool:
        """True if penetration depth in both axes meets/exceeds skin (so flush/4.0px edge blocks at 4px)."""
        ox = min(self.right, other.right) - max(self.x, other.x)
        oy = min(self.bottom, other.bottom) - max(self.y, other.y)
        return ox > skin and oy > skin


@dataclass
class ForgivenessConfig:
    tps: int = 60
    run_speed: float = 150.0
    gravity: float = 1100.0
    jump_speed: float = 480.0
    max_fall: float = 560.0
    coyote_time: float = 0.1
    jump_buffer: float = 0.1
    corner_px: int = 4
    box_w: float = 28.0
    box_h: float = 32.0
    variable_jump_cut: float = 0.5


@dataclass
class PlayerSim:
    """Fixed-tick 2D platformer controller implementing exact spec pseudo code."""

    x: float
    y: float
    solids: list[Rect]
    cfg: ForgivenessConfig = field(default_factory=ForgivenessConfig)
    vx: float = 0.0
    vy: float = 0.0
    air_ticks: int = BIG_TICKS
    press_ticks: int = BIG_TICKS
    jumps_executed: int = 0
    bonks: int = 0
    ledge_lifts: int = 0
    ceiling_slides: int = 0

    def body(self, px: float | None = None, py: float | None = None) -> Rect:
        return Rect(self.x if px is None else px, self.y if py is None else py, self.cfg.box_w, self.cfg.box_h)

    def blocked(self, from_x: float, from_y: float, dx: float, dy: float) -> bool:
        """Match Godot `test_move(Transform(from), motion)` / swept box-against-solids check."""
        target = Rect(from_x + dx, from_y + dy, self.cfg.box_w, self.cfg.box_h)
        for s in self.solids:
            # Standard AABB overlap, with >=0 tolerance (1e-6) against movement axis
            # Wait: strict open overlap > 0 allows flush standing at bottom == floor.y when sliding sideways,
            # while edge-flush clearance during vertical ceiling / ledge corner correction uses SKIN on shifted test.
            ox = min(target.right, s.right) - max(target.x, s.x)
            oy = min(target.bottom, s.bottom) - max(target.y, s.y)
            if ox > 1e-6 and oy > 1e-6:
                return True
        return False

    def blocked_corner(self, from_x: float, from_y: float, dx: float, dy: float) -> bool:
        """Corner clearance test with zero-penetration guard (`>= 0`, matching test_move safe_margin)."""
        target = Rect(from_x + dx, from_y + dy, self.cfg.box_w, self.cfg.box_h)
        for s in self.solids:
            ox = min(target.right, s.right) - max(target.x, s.x)
            oy = min(target.bottom, s.bottom) - max(target.y, s.y)
            if ox >= -1e-6 and oy >= -1e-6:
                return True
        return False

    def on_ground(self) -> bool:
        return self.blocked(self.x, self.y, 0.0, 0.05)

    def clear_input_state(self) -> None:
        """Call on death, respawn, or menu/pause close so old presses cannot fire."""
        self.press_ticks = BIG_TICKS

    def respawn(self, rx: float, ry: float) -> None:
        self.x, self.y = rx, ry
        self.vx, self.vy = 0.0, 0.0
        self.air_ticks = BIG_TICKS
        self.clear_input_state()

    def _correct_corners(self, dt: float) -> None:
        if self.on_ground() or self.cfg.corner_px <= 0:
            return
        # 1. Sideways into ledge feet clip: lift onto ledge
        side_dx = self.vx * dt
        if side_dx != 0.0 and self.blocked(self.x, self.y, side_dx, 0.0):
            for px in range(1, self.cfg.corner_px + 1):
                lift_dy = -float(px)
                if not self.blocked_corner(self.x, self.y, 0.0, lift_dy) and not self.blocked_corner(
                    self.x, self.y + lift_dy, side_dx, 0.0
                ):
                    self.y += lift_dy
                    self.ledge_lifts += 1
                    break

        # 2. Upward into ceiling corner clip: slide sideways around corner
        rise_dy = self.vy * dt
        if rise_dy < 0.0 and self.blocked(self.x, self.y, 0.0, rise_dy):
            if self.vx > 0.0:
                ways = [1.0]
            elif self.vx < 0.0:
                ways = [-1.0]
            else:
                ways = [-1.0, 1.0]
            for px in range(1, self.cfg.corner_px + 1):
                for way in ways:
                    shift_dx = way * float(px)
                    if not self.blocked_corner(self.x, self.y, shift_dx, 0.0) and not self.blocked_corner(
                        self.x + shift_dx, self.y, 0.0, rise_dy
                    ):
                        self.x += shift_dx
                        self.ceiling_slides += 1
                        return

    def _move_and_slide(self, dt: float) -> None:
        # Resolve X axis
        dx = self.vx * dt
        if dx != 0.0:
            nx = self.x + dx
            cand = Rect(nx, self.y, self.cfg.box_w, self.cfg.box_h)
            for s in self.solids:
                ox = min(cand.right, s.right) - max(cand.x, s.x)
                oy = min(cand.bottom, s.bottom) - max(cand.y, s.y)
                if ox > 1e-6 and oy > 1e-6:
                    if dx > 0.0:
                        nx = min(nx, s.x - self.cfg.box_w)
                    else:
                        nx = max(nx, s.right)
                    cand = Rect(nx, self.y, self.cfg.box_w, self.cfg.box_h)
                    self.vx = 0.0
            self.x = nx

        # Resolve Y axis
        dy = self.vy * dt
        if dy != 0.0:
            ny = self.y + dy
            cand = Rect(self.x, ny, self.cfg.box_w, self.cfg.box_h)
            for s in self.solids:
                ox = min(cand.right, s.right) - max(cand.x, s.x)
                oy = min(cand.bottom, s.bottom) - max(cand.y, s.y)
                if ox > 1e-6 and oy > 1e-6:
                    if dy > 0.0:
                        ny = min(ny, s.y - self.cfg.box_h)
                        self.vy = 0.0
                    else:
                        ny = max(ny, s.bottom)
                        self.vy = 0.0
                        self.bonks += 1
                    cand = Rect(self.x, ny, self.cfg.box_w, self.cfg.box_h)
            self.y = ny

    def step(self, move_dir: float = 0.0, jump_just_pressed: bool = False, jump_just_released: bool = False) -> bool:
        """Advance one fixed physics tick. Returns True if a jump fired on this tick."""
        c = self.cfg
        dt = 1.0 / c.tps
        grounded = self.on_ground()

        self.air_ticks = 0 if grounded else self.air_ticks + 1
        self.press_ticks = 0 if jump_just_pressed else self.press_ticks + 1

        coyote_max = round(c.coyote_time * c.tps)
        buffer_max = round(c.jump_buffer * c.tps)
        can_jump = self.air_ticks <= coyote_max
        wants_jump = self.press_ticks <= buffer_max

        jumped = False
        if can_jump and wants_jump:
            self.vy = -c.jump_speed
            self.air_ticks = BIG_TICKS
            self.press_ticks = BIG_TICKS
            self.jumps_executed += 1
            jumped = True
        elif not grounded:
            self.vy = min(self.vy + c.gravity * dt, c.max_fall)

        if jump_just_released and self.vy < 0.0:
            self.vy *= c.variable_jump_cut

        self.vx = move_dir * c.run_speed
        self._correct_corners(dt)
        self._move_and_slide(dt)
        return jumped


def _run_coyote_probe(press_after_ticks: int, coyote_time: float = 0.1) -> bool:
    """Run off ledge at x=100 (solid x=[0,100], y=200); press jump N ticks after leaving."""
    cfg = ForgivenessConfig(coyote_time=coyote_time, jump_buffer=0.1, corner_px=4)
    floor = Rect(0.0, 200.0, 100.0, 32.0)
    # Place player standing cleanly on edge, then run right until first air tick
    sim = PlayerSim(x=98.0, y=200.0 - cfg.box_h, solids=[floor], cfg=cfg)
    assert sim.on_ground()

    left_ground_ticks = 0
    for _ in range(30):
        grounded_before = sim.on_ground()
        # Next tick after leaving ground: when on_ground() becomes False, air_ticks becomes 1!
        # Wait: check spec wording: "'6 ticks after leaving' is the tick on which air_ticks becomes 6"
        should_press = not grounded_before and (sim.air_ticks + 1 == press_after_ticks)
        jumped = sim.step(move_dir=1.0, jump_just_pressed=should_press)
        if should_press:
            return jumped
        if sim.air_ticks > 0:
            left_ground_ticks = sim.air_ticks
    raise RuntimeError(f"Never reached air_ticks={press_after_ticks} (last={left_ground_ticks})")


def _run_buffer_probe(press_before_ticks: int, jump_buffer: float = 0.1) -> bool:
    """Fall cleanly onto floor; press jump `press_before_ticks` ticks before the first grounded tick."""
    cfg = ForgivenessConfig(coyote_time=0.1, jump_buffer=jump_buffer, corner_px=4)
    floor = Rect(0.0, 200.0, 200.0, 32.0)
    # First simulate dry fall from y=40 to discover exact landing tick index!
    probe = PlayerSim(x=60.0, y=40.0, solids=[floor], cfg=cfg)
    landing_tick = None
    for t in range(1, 120):
        if probe.on_ground():
            landing_tick = t
            break
        probe.step()
    assert landing_tick is not None and landing_tick > press_before_ticks

    press_tick = landing_tick - press_before_ticks
    sim = PlayerSim(x=60.0, y=40.0, solids=[floor], cfg=cfg)
    for t in range(1, landing_tick + 2):
        jumped = sim.step(jump_just_pressed=(t == press_tick))
        if t == landing_tick:
            return jumped
    return False


def _run_ledge_probe(overlap_px: float, corner_px: int = 4) -> dict[str, Any]:
    """Place player moving sideways in air into a ledge whose top is `overlap_px` above feet."""
    cfg = ForgivenessConfig(corner_px=corner_px)
    ledge = Rect(100.0, 200.0, 64.0, 32.0)
    # Feet at ledge.y + overlap_px -> body.y = 200 + overlap_px - 32
    sim = PlayerSim(x=100.0 - cfg.box_w - 1.0, y=200.0 + overlap_px - cfg.box_h, solids=[ledge], cfg=cfg)
    sim.vy = 10.0  # slightly falling in air
    for _ in range(10):
        sim.step(move_dir=1.0)
    landed_on_ledge = sim.body().right > ledge.x and sim.y <= 200.0 - cfg.box_h + 0.5 and sim.on_ground()
    return {
        "overlap_px": overlap_px,
        "landed_on_ledge": landed_on_ledge,
        "ledge_lifts": sim.ledge_lifts,
        "final_y": round(sim.y, 3),
    }


def _run_ceiling_probe(overlap_px: float, move_dir: float = 0.0, corner_px: int = 4) -> dict[str, Any]:
    """Jump upward with head overlapping left end of ceiling block at x=100 by `overlap_px`."""
    cfg = ForgivenessConfig(corner_px=corner_px)
    ceiling = Rect(100.0, 100.0, 64.0, 32.0)
    floor = Rect(0.0, 200.0, 200.0, 32.0)
    # Right edge of player overlaps ceiling left edge (100.0) by `overlap_px`
    start_x = 100.0 - cfg.box_w + overlap_px
    # Place head just under ceiling bottom (132.0) + 4 px so upward jump tests ceiling on tick 1-2
    sim = PlayerSim(x=start_x, y=135.0, solids=[ceiling, floor], cfg=cfg)
    sim.vy = -cfg.jump_speed
    sim.air_ticks = BIG_TICKS
    for _ in range(5):
        sim.step(move_dir=move_dir)
    kept_rising = sim.bonks == 0 and sim.y < 132.0 - cfg.box_h + 2.0
    return {
        "overlap_px": overlap_px,
        "move_dir": move_dir,
        "kept_rising": kept_rising,
        "bonks": sim.bonks,
        "ceiling_slides": sim.ceiling_slides,
        "final_x": round(sim.x, 3),
        "final_y": round(sim.y, 3),
    }


def run_verify() -> dict[str, Any]:
    """Run all 6 required verification suites + boundary & pitfall guards."""
    checks: dict[str, dict[str, Any]] = {}

    # 1. Coyote time: 6 ticks jumps, 7 ticks does not
    c6 = _run_coyote_probe(6)
    c7 = _run_coyote_probe(7)
    checks["1_coyote_time_6_vs_7_ticks"] = {
        "tick_6_jumped": c6,
        "tick_7_jumped": c7,
        "ok": (c6 is True and c7 is False),
    }

    # 2. Jump buffering: 6 ticks before landing fires on landing, 7 ticks does not
    b6 = _run_buffer_probe(6)
    b7 = _run_buffer_probe(7)
    checks["2_jump_buffer_6_vs_7_ticks"] = {
        "ticks_before_6_jumped": b6,
        "ticks_before_7_jumped": b7,
        "ok": (b6 is True and b7 is False),
    }

    # 3. No double jump 3 ticks after jumping + spawn-in-air guard + pause/respawn clear
    floor = Rect(0.0, 200.0, 200.0, 32.0)
    cfg = ForgivenessConfig()
    sim_dj = PlayerSim(x=50.0, y=200.0 - cfg.box_h, solids=[floor], cfg=cfg)
    j1 = sim_dj.step(jump_just_pressed=True)
    sim_dj.step()
    sim_dj.step()
    j2 = sim_dj.step(jump_just_pressed=True)  # 3 ticks later
    sim_air_spawn = PlayerSim(x=50.0, y=80.0, solids=[floor], cfg=cfg)
    air_spawn_jump = sim_air_spawn.step(jump_just_pressed=True)
    sim_air_spawn.step(jump_just_pressed=True)
    sim_air_spawn.clear_input_state()
    cleared_press_ticks = sim_air_spawn.press_ticks
    checks["3_no_double_jump_and_guards"] = {
        "initial_jump": j1,
        "second_press_at_3_ticks": j2,
        "air_spawn_jump": air_spawn_jump,
        "cleared_press_ticks": cleared_press_ticks,
        "ok": (j1 is True and j2 is False and air_spawn_jump is False and cleared_press_ticks == BIG_TICKS),
    }

    # 4. Ledge corner correction: 3 px and 3.99 px land on ledge; 4.0 px and 5.0 px do not
    l3 = _run_ledge_probe(3.0)
    l399 = _run_ledge_probe(3.99)
    l4 = _run_ledge_probe(4.0)
    l5 = _run_ledge_probe(5.0)
    checks["4_ledge_corner_correction"] = {
        "3px": l3,
        "3_99px": l399,
        "4px": l4,
        "5px": l5,
        "ok": (l3["landed_on_ledge"] and l399["landed_on_ledge"] and not l4["landed_on_ledge"] and not l5["landed_on_ledge"]),
    }

    # 5. Ceiling corner correction: 3 px neutral slides past & rises; 4px/5px bonks; moving INTO block bonks
    ce3 = _run_ceiling_probe(3.0, move_dir=0.0)
    ce399 = _run_ceiling_probe(3.99, move_dir=0.0)
    ce4 = _run_ceiling_probe(4.0, move_dir=0.0)
    ce5 = _run_ceiling_probe(5.0, move_dir=0.0)
    ce3_into = _run_ceiling_probe(3.0, move_dir=1.0)
    checks["5_ceiling_corner_correction"] = {
        "3px_neutral": ce3,
        "3_99px_neutral": ce399,
        "4px_neutral": ce4,
        "5px_neutral": ce5,
        "3px_moving_into_block": ce3_into,
        "ok": (
            ce3["kept_rising"]
            and ce399["kept_rising"]
            and not ce4["kept_rising"]
            and not ce5["kept_rising"]
            and not ce3_into["kept_rising"]
        ),
    }

    # 6. All three settings at 0 -> strict tick-0 ground jump still works, all forgiveness off
    c0 = _run_coyote_probe(1, coyote_time=0.0)
    b0 = _run_buffer_probe(1, jump_buffer=0.0)
    l0 = _run_ledge_probe(1.0, corner_px=0)
    ce0 = _run_ceiling_probe(1.0, move_dir=0.0, corner_px=0)
    cfg0 = ForgivenessConfig(coyote_time=0.0, jump_buffer=0.0, corner_px=0)
    sim0 = PlayerSim(x=50.0, y=200.0 - cfg0.box_h, solids=[floor], cfg=cfg0)
    ground_jump_ok = sim0.step(jump_just_pressed=True)
    checks["6_zero_settings_restore_vanilla"] = {
        "coyote_1tick_at_0": c0,
        "buffer_1tick_at_0": b0,
        "ledge_1px_at_0": l0["landed_on_ledge"],
        "ceiling_1px_at_0": ce0["kept_rising"],
        "ground_tick0_jump": ground_jump_ok,
        "ok": (not c0 and not b0 and not l0["landed_on_ledge"] and not ce0["kept_rising"] and ground_jump_ok),
    }

    all_passed = all(v["ok"] for v in checks.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in checks.values() if v["ok"]), "total": len(checks), "checks": checks}


GODOT4_PLAYER_GD = """# player.gd — Godot 4 CharacterBody2D with Coyote Time, Jump Buffering & Dual Corner Correction
extends CharacterBody2D

@export var run_speed := 150.0     # px/s
@export var gravity := 1100.0      # px/s^2
@export var jump_speed := 480.0    # px/s
@export var max_fall := 560.0      # px/s
@export_range(0.0, 1.0) var variable_jump_cut := 0.5

@export_group("Forgiveness")
@export var coyote_time := 0.1     # s after leaving ground (0 = off; 0.1s = 6 ticks @ 60Hz)
@export var jump_buffer := 0.1     # s jump press kept before landing (0 = off)
@export var corner_px := 4         # px whole number (0 = off; 1/8 to 1/2 tile size)

const BIG_TICKS := 1000
var _air_ticks := BIG_TICKS        # spawned in air cannot jump
var _press_ticks := BIG_TICKS


func clear_jump_buffer() -> void:
\t# Call on death, respawn, and pause/menu close so queued presses do not misfire.
\t_press_ticks = BIG_TICKS


func _physics_process(delta: float) -> void:
\t_air_ticks = 0 if is_on_floor() else _air_ticks + 1
\t_press_ticks = 0 if Input.is_action_just_pressed("ui_accept") else _press_ticks + 1

\tvar tps := Engine.physics_ticks_per_second
\tvar can_jump := _air_ticks <= roundi(coyote_time * tps)
\tvar wants_jump := _press_ticks <= roundi(jump_buffer * tps)
\tif can_jump and wants_jump:
\t\tvelocity.y = -jump_speed
\t\t_air_ticks = BIG_TICKS     # close coyote window to prevent double jump
\t\t_press_ticks = BIG_TICKS   # consume buffered press
\telif not is_on_floor():
\t\tvelocity.y = minf(velocity.y + gravity * delta, max_fall)

\tif Input.is_action_just_released("ui_accept") and velocity.y < 0.0:
\t\tvelocity.y *= variable_jump_cut

\tvelocity.x = Input.get_axis("ui_left", "ui_right") * run_speed
\t_correct_corners(delta)
\tmove_and_slide()


func _correct_corners(delta: float) -> void:
\tif is_on_floor() or corner_px <= 0:
\t\treturn
\t# Ledge: lift feet onto corner when clipped horizontally in the air
\tvar side := Vector2(velocity.x * delta, 0.0)
\tif side.x != 0.0 and test_move(global_transform, side):
\t\tfor px in range(1, corner_px + 1):
\t\t\tvar lift := Vector2(0.0, -px)
\t\t\tif not test_move(global_transform, lift) and not test_move(global_transform.translated(lift), side):
\t\t\t\tglobal_position += lift
\t\t\t\tbreak
\t# Ceiling: slide around corner only along movement direction (or either if x==0)
\tvar rise := Vector2(0.0, velocity.y * delta)
\tif rise.y < 0.0 and test_move(global_transform, rise):
\t\tvar ways := [signf(velocity.x)] if velocity.x != 0.0 else [-1.0, 1.0]
\t\tfor px in range(1, corner_px + 1):
\t\t\tfor way in ways:
\t\t\t\tvar shift := Vector2(way * px, 0.0)
\t\t\t\tif not test_move(global_transform, shift) and not test_move(global_transform.translated(shift), rise):
\t\t\t\t\tglobal_position += shift
\t\t\t\t\treturn
"""

UNITY_PLAYER_CS = """// PlatformerForgivenessController.cs — Unity 2D FixedUpdate ticks + Update input latch + BoxCast corner correction
using UnityEngine;

[RequireComponent(typeof(Rigidbody2D), typeof(BoxCollider2D))]
public class PlatformerForgivenessController : MonoBehaviour
{
    [Header("Movement")]
    public float runSpeed = 4.6875f;     // e.g. 150 px/s @ 32 PPU
    public float gravity = 34.375f;
    public float jumpSpeed = 15.0f;
    public float maxFall = 17.5f;
    public LayerMask groundMask;

    [Header("Forgiveness")]
    public float coyoteTime = 0.1f;      // 0 = off (6 ticks @ 60Hz FixedUpdate)
    public float jumpBuffer = 0.1f;      // 0 = off
    public int cornerPx = 4;             // 0 = off
    public float pixelsPerUnit = 32f;    // set 1 if world units == pixels

    private const int BigTicks = 1000;
    private Rigidbody2D _rb;
    private BoxCollider2D _box;
    private int _airTicks = BigTicks;
    private int _pressTicks = BigTicks;
    private bool _jumpPressedLatch;
    private float _moveInput;
    private readonly RaycastHit2D[] _hits = new RaycastHit2D[4];

    private void Awake()
    {
        _rb = GetComponent<Rigidbody2D>();
        _box = GetComponent<BoxCollider2D>();
    }

    public void ClearJumpBuffer()
    {
        _jumpPressedLatch = false;
        _pressTicks = BigTicks;
    }

    private void Update()
    {
        // Latch per-frame GetButtonDown so FixedUpdate never drops a press!
        if (Input.GetButtonDown("Jump"))
            _jumpPressedLatch = true;
        _moveInput = Input.GetAxisRaw("Horizontal");
    }

    private bool Blocked(Vector2 fromPos, Vector2 motion)
    {
        float dist = motion.magnitude;
        if (dist <= 1e-6f) return false;
        Vector2 saved = _rb.position;
        _rb.position = fromPos;
        int count = _box.Cast(motion / dist, _hits, dist, true);
        _rb.position = saved;
        return count > 0;
    }

    private bool OnGround() => Blocked(_rb.position, Vector2.down * (1f / pixelsPerUnit));

    private void FixedUpdate()
    {
        float dt = Time.fixedDeltaTime;
        int tps = Mathf.RoundToInt(1f / dt);
        bool grounded = OnGround();

        _airTicks = grounded ? 0 : _airTicks + 1;
        _pressTicks = _jumpPressedLatch ? 0 : _pressTicks + 1;
        _jumpPressedLatch = false;

        Vector2 vel = _rb.linearVelocity;
        bool canJump = _airTicks <= Mathf.RoundToInt(coyoteTime * tps);
        bool wantsJump = _pressTicks <= Mathf.RoundToInt(jumpBuffer * tps);

        if (canJump && wantsJump)
        {
            vel.y = jumpSpeed;
            _airTicks = BigTicks;
            _pressTicks = BigTicks;
        }
        else if (!grounded)
        {
            vel.y = Mathf.Max(vel.y - gravity * dt, -maxFall);
        }

        vel.x = _moveInput * runSpeed;
        CorrectCorners(ref vel, dt);
        _rb.linearVelocity = vel;
    }

    private void CorrectCorners(ref Vector2 vel, float dt)
    {
        if (OnGround() || cornerPx <= 0) return;
        float unitPx = 1f / pixelsPerUnit;
        Vector2 pos = _rb.position;

        Vector2 side = new Vector2(vel.x * dt, 0f);
        if (Mathf.Abs(side.x) > 1e-5f && Blocked(pos, side))
        {
            for (int px = 1; px <= cornerPx; px++)
            {
                Vector2 lift = new Vector2(0f, px * unitPx);
                if (!Blocked(pos, lift) && !Blocked(pos + lift, side))
                {
                    _rb.position += lift;
                    pos = _rb.position;
                    break;
                }
            }
        }

        Vector2 rise = new Vector2(0f, vel.y * dt);
        if (rise.y > 0f && Blocked(pos, rise))
        {
            float[] ways = vel.x != 0f ? new[] { Mathf.Sign(vel.x) } : new[] { -1f, 1f };
            for (int px = 1; px <= cornerPx; px++)
            {
                foreach (float way in ways)
                {
                    Vector2 shift = new Vector2(way * px * unitPx, 0f);
                    if (!Blocked(pos, shift) && !Blocked(pos + shift, rise))
                    {
                        _rb.position += shift;
                        return;
                    }
                }
            }
        }
    }
}
"""

GODOT_25D_GD = """# player_25d.gd — 2.5D Platformer (Godot 4 CharacterBody3D, Z locked)
# Same fixed-tick windows (_air_ticks, _press_ticks) + 3D test_move() corner correction!
extends CharacterBody3D

@export var run_speed := 6.0
@export var gravity := 28.0
@export var jump_speed := 12.0
@export var max_fall := 18.0
@export var coyote_time := 0.1
@export var jump_buffer := 0.1
@export var corner_units := 0.125 # e.g. 1/8 unit (equivalent to 4px on 32px tile)
@export var corner_steps := 4

const BIG_TICKS := 1000
var _air_ticks := BIG_TICKS
var _press_ticks := BIG_TICKS


func _physics_process(delta: float) -> void:
\t_air_ticks = 0 if is_on_floor() else _air_ticks + 1
\t_press_ticks = 0 if Input.is_action_just_pressed("ui_accept") else _press_ticks + 1

\tvar tps := Engine.physics_ticks_per_second
\tif _air_ticks <= roundi(coyote_time * tps) and _press_ticks <= roundi(jump_buffer * tps):
\t\tvelocity.y = jump_speed
\t\t_air_ticks = BIG_TICKS
\t\t_press_ticks = BIG_TICKS
\telif not is_on_floor():
\t\tvelocity.y = maxf(velocity.y - gravity * delta, -max_fall)

\tvelocity.x = Input.get_axis("ui_left", "ui_right") * run_speed
\tvelocity.z = 0.0
\t_correct_corners_3d(delta)
\tmove_and_slide()
\tglobal_position.z = 0.0


func _correct_corners_3d(delta: float) -> void:
\tif is_on_floor() or corner_steps <= 0 or corner_units <= 0.0:
\t\treturn
\tvar step := corner_units / float(corner_steps)
\tvar side := Vector3(velocity.x * delta, 0.0, 0.0)
\tif side.x != 0.0 and test_move(global_transform, side):
\t\tfor i in range(1, corner_steps + 1):
\t\t\tvar lift := Vector3(0.0, float(i) * step, 0.0)
\t\t\tif not test_move(global_transform, lift) and not test_move(global_transform.translated(lift), side):
\t\t\t\tglobal_position += lift
\t\t\t\tbreak
\tvar rise := Vector3(0.0, velocity.y * delta, 0.0)
\tif rise.y > 0.0 and test_move(global_transform, rise):
\t\tvar ways := [signf(velocity.x)] if velocity.x != 0.0 else [-1.0, 1.0]
\t\tfor i in range(1, corner_steps + 1):
\t\t\tfor way in ways:
\t\t\t\tvar shift := Vector3(way * float(i) * step, 0.0, 0.0)
\t\t\t\tif not test_move(global_transform, shift) and not test_move(global_transform.translated(shift), rise):
\t\t\t\t\tglobal_position += shift
\t\t\t\t\treturn
"""


def export_code(engine: str) -> str:
    if engine == "godot4":
        return GODOT4_PLAYER_GD
    if engine == "unity":
        return UNITY_PLAYER_CS
    if engine == "godot3d":
        return GODOT_25D_GD
    raise ValueError(f"Unsupported engine: {engine}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Platformer Forgiveness (Coyote + Buffer + Corner) CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser("verify", help="Run all 6 automated 60Hz tick verification checks")
    p_verify.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export tested Godot 4 / Unity / 2.5D templates")
    p_exp.add_argument("--engine", choices=["godot4", "unity", "godot3d"], required=True)
    p_exp.add_argument("--out", type=Path)
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "verify":
        res = run_verify()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Platformer Forgiveness verify: {res['passed']}/{res['total']} passed")
        return 0 if res["all_passed"] else 1

    if args.cmd == "export-code":
        code = export_code(args.engine)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(code, encoding="utf-8")
        if args.json:
            print(json.dumps({"engine": args.engine, "out": str(args.out) if args.out else None, "chars": len(code)}, indent=2))
        elif not args.out:
            print(code)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
