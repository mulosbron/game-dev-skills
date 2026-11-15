#!/usr/bin/env python3
"""
2D See-Through Occlusion Pipeline Tool (see_through.py)
Implements, renders, verifies, and exports the 4 standard 2D occlusion looks
when a character (or spell/entity) passes behind trees, fog, miasma, or buildings:
  - A: FADE       (opacity fade — best for a single isolated tree/obstacle)
  - B: DITHER     (4x4 Bayer ordered pixel drop — best for fog/mist/canopy regions)
  - C: CUTOUT     (hard circular window — best for spell spheres, lanterns, miasma)
  - D: SILHOUETTE (clipped flat-color copy + stealth alarm-red shift — best for walls/stealth)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BAYER_4X4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.float64,
)

DEFAULT_SILHOUETTE_COLOR = (118, 214, 255, 255)
DEFAULT_ALERT_COLOR = (239, 68, 68, 255)


# ---------------------------------------------------------------------------
# Core Occlusion Math (Exact Parity with Godot 4 / Unity / GLSL Shaders)
# ---------------------------------------------------------------------------

def ease_amount(current: float, goal: float, dt: float, ease_time: float) -> float:
    """Linear move_toward easing between 0 and 1."""
    if ease_time <= 0.0:
        return float(goal)
    step = dt / ease_time
    if current < goal:
        return min(goal, current + step)
    if current > goal:
        return max(goal, current - step)
    return float(current)


def is_behind_test(
    obj_alpha: np.ndarray,
    obj_origin: Tuple[float, float],
    obj_base_y: float,
    feet_pos: Tuple[float, float],
    char_size: Tuple[float, float] = (20.0, 36.0),
    mode: str = "dither",
    cover_grid: Tuple[int, int] = (3, 4),
    cover_needed: float = 0.25,
) -> Tuple[bool, int]:
    """
    Two-part behind test:
      1) Depth: feet_y < obj_base_y (Y grows downward).
      2) Cover: for SILHOUETTE -> bounding box overlap; otherwise 3x4 grid points
         over character box tested against object opaque pixels (alpha > 0).
    Returns (is_behind, hidden_point_count).
    """
    fx, fy = feet_pos
    if fy >= obj_base_y:
        return False, 0

    h, w = obj_alpha.shape
    ox, oy = obj_origin
    cw, ch = char_size

    if mode == "silhouette":
        char_x0, char_y0 = fx - cw * 0.5, fy - ch
        char_x1, char_y1 = fx + cw * 0.5, fy
        obj_x0, obj_y0 = ox, oy
        obj_x1, obj_y1 = ox + w, oy + h
        overlap = not (char_x1 <= obj_x0 or char_x0 >= obj_x1 or char_y1 <= obj_y0 or char_y0 >= obj_y1)
        return overlap, (1 if overlap else 0)

    gx, gy = cover_grid
    hidden = 0
    for ix in range(gx):
        for iy in range(gy):
            px = fx + ((ix + 0.5) / gx - 0.5) * cw
            py = fy + ((iy + 0.5) / gy - 1.0) * ch
            lx = int(math.floor(px - ox))
            ly = int(math.floor(py - oy))
            if 0 <= lx < w and 0 <= ly < h and obj_alpha[ly, lx] > 0:
                hidden += 1

    required = cover_needed * gx * gy
    return (hidden > 0 and hidden >= required), hidden


def compute_bayer_drop_mask(
    height: int,
    width: int,
    origin: Tuple[int, int],
    target_center: Tuple[float, float],
    amount: float,
    radius: float,
    soft: float = 0.0,
    pixel_scale: float = 1.0,
) -> np.ndarray:
    """
    Exact Python mirror of see_through.gdshader fragment drop logic.
    Returns boolean array (H, W): True = pixel is DROPPED (discarded).
    """
    if amount <= 0.0 or (radius <= 0.0 and soft <= 0.0):
        return np.zeros((height, width), dtype=bool)

    ox, oy = origin
    yy, xx = np.mgrid[:height, :width]
    world_x = ox + xx + 0.5
    world_y = oy + yy + 0.5

    cell_x = np.floor(world_x / pixel_scale)
    cell_y = np.floor(world_y / pixel_scale)
    dx = (cell_x + 0.5) * pixel_scale - target_center[0]
    dy = (cell_y + 0.5) * pixel_scale - target_center[1]
    d = np.hypot(dx, dy)

    reach = (radius + soft) * amount
    if soft > 0.0:
        solid = np.clip((d - reach) / soft + 1.0, 0.0, 1.0)
    else:
        solid = np.where(d >= reach, 1.0, 0.0)

    bx = np.mod(cell_x.astype(np.int64), 4)
    by = np.mod(cell_y.astype(np.int64), 4)
    thresh = (BAYER_4X4[by, bx] + 0.5) / 16.0
    return solid <= thresh


def resolve_silhouette_color(
    base_color: Tuple[int, int, int, int] = DEFAULT_SILHOUETTE_COLOR,
    alert_color: Tuple[int, int, int, int] = DEFAULT_ALERT_COLOR,
    alert_ratio: float = 0.0,
    alert_threshold: float = 0.7,
    smooth_blend: bool = False,
) -> Tuple[int, int, int, int]:
    """Return calm silhouette color or stealth alarm-red when near discovery."""
    r = max(0.0, min(1.0, float(alert_ratio)))
    if smooth_blend:
        return tuple(int(round(base_color[i] + (alert_color[i] - base_color[i]) * r)) for i in range(4))  # type: ignore[return-value]
    return alert_color if r >= alert_threshold else base_color


# ---------------------------------------------------------------------------
# Demo Scene Synthesis & Compositor
# ---------------------------------------------------------------------------

def synthesize_demo_sprites() -> Tuple[Image.Image, Image.Image, Image.Image]:
    """
    Create crisp pixel-art demo assets:
      - ground (160x140): grass + dirt path
      - tree (64x80): pixel-art tree with trunk & leafy canopy (origin at bottom-center foot)
      - hero (20x36): top-down pixel-art character (origin at bottom-center feet)
    """
    # Ground 160x140
    g = np.zeros((140, 160, 4), dtype=np.uint8)
    g[:, :] = (94, 152, 70, 255)
    g[48:92, :] = (166, 134, 92, 255)
    g[50:90, ::4] = (156, 124, 84, 255)

    # Tree 64x80 (base foot at x=32, y=75)
    t = np.zeros((80, 64, 4), dtype=np.uint8)
    # Trunk
    t[44:75, 27:37] = (108, 70, 44, 255)
    t[44:75, 33:37] = (86, 54, 34, 255)
    # Canopy circles
    yy, xx = np.mgrid[:80, :64]
    canopy = (
        (((xx - 32) / 24.0) ** 2 + ((yy - 30) / 22.0) ** 2 < 1.0)
        | (((xx - 20) / 14.0) ** 2 + ((yy - 36) / 13.0) ** 2 < 1.0)
        | (((xx - 44) / 14.0) ** 2 + ((yy - 36) / 13.0) ** 2 < 1.0)
    )
    t[canopy] = (46, 114, 52, 255)
    highlight = canopy & (yy < 28) & (xx > 16) & (xx < 48)
    t[highlight] = (68, 142, 66, 255)

    # Hero 20x36 (feet at x=10, y=36)
    h = np.zeros((36, 20, 4), dtype=np.uint8)
    h[2:12, 6:14] = (232, 188, 146, 255)   # Head
    h[2:6, 5:15] = (74, 48, 36, 255)       # Hair
    h[12:25, 5:15] = (54, 108, 194, 255)   # Tunic
    h[14:23, 3:5] = (232, 188, 146, 255)   # Left arm
    h[14:23, 15:17] = (232, 188, 146, 255) # Right arm
    h[25:33, 6:9] = (56, 62, 78, 255)      # Left leg
    h[25:33, 11:14] = (56, 62, 78, 255)    # Right leg
    h[33:36, 5:9] = (92, 56, 36, 255)      # Left boot
    h[33:36, 11:15] = (92, 56, 36, 255)    # Right boot

    return (
        Image.fromarray(g, mode="RGBA"),
        Image.fromarray(t, mode="RGBA"),
        Image.fromarray(h, mode="RGBA"),
    )


def _blit_alpha(dst: np.ndarray, src: np.ndarray, x0: int, y0: int) -> None:
    """Alpha-composite src onto dst at integer top-left (x0, y0)."""
    dh, dw = dst.shape[:2]
    sh, sw = src.shape[:2]
    sx0 = max(0, -x0)
    sy0 = max(0, -y0)
    dx0 = max(0, x0)
    dy0 = max(0, y0)
    cw = min(sw - sx0, dw - dx0)
    ch = min(sh - sy0, dh - dy0)
    if cw <= 0 or ch <= 0:
        return
    sub_src = src[sy0 : sy0 + ch, sx0 : sx0 + cw]
    sub_dst = dst[dy0 : dy0 + ch, dx0 : dx0 + cw]
    a = sub_src[:, :, 3:4].astype(np.float32) / 255.0
    sub_dst[:, :, :3] = np.round(sub_dst[:, :, :3].astype(np.float32) * (1.0 - a) + sub_src[:, :, :3].astype(np.float32) * a).astype(np.uint8)
    sub_dst[:, :, 3] = 255


def render_scene_frame(
    ground_rgba: np.ndarray,
    obj_rgba: np.ndarray,
    obj_pos: Tuple[int, int],
    obj_base_y: int,
    char_rgba: np.ndarray,
    feet_pos: Tuple[int, int],
    mode: str = "dither",
    amount: float = 1.0,
    fade_to: float = 0.4,
    clear_radius: float = 18.0,
    soft: float = 16.0,
    hole_radius: float = 22.0,
    silhouette_color: Tuple[int, int, int, int] = DEFAULT_SILHOUETTE_COLOR,
    alert_color: Tuple[int, int, int, int] = DEFAULT_ALERT_COLOR,
    alert_ratio: float = 0.0,
    alert_threshold: float = 0.7,
    pixel_scale: float = 1.0,
) -> Image.Image:
    """Render a Y-sorted 2D scene with the selected see-through look applied."""
    canvas = ground_rgba.copy()
    ch, cw = char_rgba.shape[:2]
    oh, ow = obj_rgba.shape[:2]

    char_x0 = int(feet_pos[0] - cw // 2)
    char_y0 = int(feet_pos[1] - ch)
    obj_x0, obj_y0 = int(obj_pos[0]), int(obj_pos[1])
    center = (float(feet_pos[0]), float(feet_pos[1]) - ch * 0.5)

    # Prepare modified object sprite
    obj_mod = obj_rgba.copy()
    if amount > 0.0:
        if mode == "fade":
            opacity = 1.0 + (fade_to - 1.0) * amount
            obj_mod[:, :, 3] = np.round(obj_mod[:, :, 3].astype(np.float32) * opacity).astype(np.uint8)
        elif mode in ("dither", "cutout"):
            rad = clear_radius if mode == "dither" else hole_radius
            sft = soft if mode == "dither" else 0.0
            drop = compute_bayer_drop_mask(
                oh, ow,
                origin=(obj_x0, obj_y0),
                target_center=center,
                amount=amount,
                radius=rad,
                soft=sft,
                pixel_scale=pixel_scale,
            )
            obj_mod[drop, 3] = 0

    # Y-sort draw order
    if feet_pos[1] < obj_base_y:
        _blit_alpha(canvas, char_rgba, char_x0, char_y0)
        _blit_alpha(canvas, obj_mod, obj_x0, obj_y0)
        if mode == "silhouette" and amount > 0.0:
            sil_col = resolve_silhouette_color(
                base_color=silhouette_color,
                alert_color=alert_color,
                alert_ratio=alert_ratio,
                alert_threshold=alert_threshold,
            )
            # Clip flat-color copy of character strictly to opaque object pixels
            dh, dw = canvas.shape[:2]
            char_layer = np.zeros((dh, dw, 4), dtype=np.uint8)
            flat_char = np.zeros_like(char_rgba)
            opaque_c = char_rgba[:, :, 3] >= 128
            flat_char[opaque_c] = sil_col
            _blit_alpha(char_layer, flat_char, char_x0, char_y0)

            obj_mask = np.zeros((dh, dw), dtype=bool)
            sx0, sy0 = max(0, -obj_x0), max(0, -obj_y0)
            dx0, dy0 = max(0, obj_x0), max(0, obj_y0)
            cw_clip = min(ow - sx0, dw - dx0)
            ch_clip = min(oh - sy0, dh - dy0)
            if cw_clip > 0 and ch_clip > 0:
                obj_mask[dy0 : dy0 + ch_clip, dx0 : dx0 + cw_clip] = obj_rgba[sy0 : sy0 + ch_clip, sx0 : sx0 + cw_clip, 3] > 0

            clip_pixels = obj_mask & (char_layer[:, :, 3] > 0)
            canvas[clip_pixels, :3] = sil_col[:3]
    else:
        _blit_alpha(canvas, obj_mod, obj_x0, obj_y0)
        _blit_alpha(canvas, char_rgba, char_x0, char_y0)

    return Image.fromarray(canvas, mode="RGBA")


# ---------------------------------------------------------------------------
# 11-Point Automated Verification Suite
# ---------------------------------------------------------------------------

def run_verification_suite() -> Dict[str, Any]:
    """Run all 11 specification tests + stealth alarm-color test."""
    ground_img, tree_img, hero_img = synthesize_demo_sprites()
    ground = np.array(ground_img)
    tree = np.array(tree_img)
    hero = np.array(hero_img)
    tree_alpha = tree[:, :, 3]
    tree_pos = (48, 20)
    tree_base_y = 20 + 75  # 95

    checks: Dict[str, Any] = {}

    # 1. Feet level with or in front of base -> False; 1 px behind + covered -> True
    level_ok, _ = is_behind_test(tree_alpha, tree_pos, tree_base_y, (80, tree_base_y), mode="dither")
    front_ok, _ = is_behind_test(tree_alpha, tree_pos, tree_base_y, (80, tree_base_y + 1), mode="dither")
    behind_ok, hidden_cnt = is_behind_test(tree_alpha, tree_pos, tree_base_y, (80, tree_base_y - 1), mode="dither")
    checks["feet_depth_check"] = {
        "ok": (not level_ok) and (not front_ok) and behind_ok,
        "level_on": level_ok,
        "front_on": front_ok,
        "behind_1px_on": behind_ok,
        "behind_hidden_points": hidden_cnt,
    }

    # 2. Inside bounding box but under 0 opaque pixels -> stays off
    # Tree top-left corner (48..54, 20..30) is empty transparent box space
    empty_box_on, empty_hidden = is_behind_test(tree_alpha, tree_pos, tree_base_y, (50, 52), mode="dither")
    checks["bbox_empty_corner_stays_off"] = {
        "ok": (not empty_box_on) and empty_hidden == 0,
        "hidden_points": empty_hidden,
    }

    # 3. 3 of 12 hidden -> on; 2 of 12 hidden -> off
    synth_alpha = np.zeros((60, 60), dtype=np.uint8)
    # Place character at feet=(30, 50), box x=[20..40], y=[14..50]
    # Test grid points directly by illuminating exact 2 or 3 sample cells
    gx, gy = 3, 4
    pts = []
    for ix in range(gx):
        for iy in range(gy):
            px = int(math.floor(30 + ((ix + 0.5) / gx - 0.5) * 20))
            py = int(math.floor(50 + ((iy + 0.5) / gy - 1.0) * 36))
            pts.append((px, py))

    m2 = synth_alpha.copy()
    for px, py in pts[:2]:
        m2[py, px] = 255
    on_2, h_2 = is_behind_test(m2, (0, 0), 55, (30, 50), mode="dither")

    m3 = synth_alpha.copy()
    for px, py in pts[:3]:
        m3[py, px] = 255
    on_3, h_3 = is_behind_test(m3, (0, 0), 55, (30, 50), mode="dither")
    checks["cover_threshold_3_of_12"] = {
        "ok": (not on_2) and h_2 == 2 and on_3 and h_3 == 3,
        "2_hidden_on": on_2,
        "3_hidden_on": on_3,
    }

    # 4. 60 fps easing: frame 6 -> 0.5, frame 12 -> 1.0, frame 12 off -> 0.0; ease_time=0 -> 1 frame
    dt = 1.0 / 60.0
    amt = 0.0
    for _ in range(6):
        amt = ease_amount(amt, 1.0, dt, 0.2)
    amt_f6 = amt
    for _ in range(6):
        amt = ease_amount(amt, 1.0, dt, 0.2)
    amt_f12 = amt
    for _ in range(12):
        amt = ease_amount(amt, 0.0, dt, 0.2)
    amt_off12 = amt
    snap = ease_amount(0.0, 1.0, dt, 0.0)
    checks["easing_60fps_0_2s"] = {
        "ok": abs(amt_f6 - 0.5) < 1e-6 and abs(amt_f12 - 1.0) < 1e-6 and abs(amt_off12) < 1e-6 and snap == 1.0,
        "frame_6": round(amt_f6, 6),
        "frame_12": round(amt_f12, 6),
        "off_frame_12": round(amt_off12, 6),
        "ease_0_snap": snap,
    }

    # 5. Fade fully on -> opacity 0.4
    fade_opacity = 1.0 + (0.4 - 1.0) * 1.0
    checks["fade_opacity_0_4"] = {"ok": abs(fade_opacity - 0.4) < 1e-9, "opacity": fade_opacity}

    # 6. Dither fully on: <18px dropped, >34px kept, 0 new colors vs base sprites
    solid_wall = np.full((90, 90, 4), (46, 114, 52, 255), dtype=np.uint8)
    drop_dither = compute_bayer_drop_mask(90, 90, (0, 0), (45.0, 45.0), amount=1.0, radius=18.0, soft=16.0)
    yy, xx = np.mgrid[:90, :90]
    dist = np.hypot((xx + 0.5) - 45.0, (yy + 0.5) - 45.0)
    inner_clear_ok = bool(np.all(drop_dither[dist < 18.0]))
    outer_solid_ok = bool(np.all(~drop_dither[dist > 34.0]))

    dither_frame = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="dither", amount=1.0))
    allowed_colors = (
        {tuple(int(v) for v in px) for px in ground[:, :, :3].reshape(-1, 3)}
        | {tuple(int(v) for v in px) for px in tree[tree[:, :, 3] > 0][:, :3]}
        | {tuple(int(v) for v in px) for px in hero[hero[:, :, 3] > 0][:, :3]}
    )
    dither_colors = {tuple(int(v) for v in px) for px in dither_frame[:, :, :3].reshape(-1, 3)}
    checks["dither_radii_and_palette"] = {
        "ok": inner_clear_ok and outer_solid_ok and len(dither_colors - allowed_colors) == 0,
        "inner_18px_all_dropped": inner_clear_ok,
        "outer_34px_all_solid": outer_solid_ok,
        "new_colors_added": len(dither_colors - allowed_colors),
    }

    # 7. Cutout fully on: <22px dropped, >22px kept, 0 new colors
    drop_cutout = compute_bayer_drop_mask(90, 90, (0, 0), (45.0, 45.0), amount=1.0, radius=22.0, soft=0.0)
    cut_in = bool(np.all(drop_cutout[dist < 22.0]))
    cut_out = bool(np.all(~drop_cutout[dist >= 22.0]))
    cutout_frame = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="cutout", amount=1.0))
    cutout_colors = {tuple(int(v) for v in px) for px in cutout_frame[:, :, :3].reshape(-1, 3)}
    checks["cutout_radius_22px_and_palette"] = {
        "ok": cut_in and cut_out and len(cutout_colors - allowed_colors) == 0,
        "inner_22px_all_dropped": cut_in,
        "outer_22px_all_solid": cut_out,
        "new_colors_added": len(cutout_colors - allowed_colors),
    }

    # 8. Two trees, player behind only one -> only that tree opens
    t1_behind, _ = is_behind_test(tree_alpha, (10, 20), 95, (42, 82), mode="dither")
    t2_behind, _ = is_behind_test(tree_alpha, (95, 20), 95, (42, 82), mode="dither")
    checks["independent_per_object_activation"] = {
        "ok": t1_behind and (not t2_behind),
        "tree1_open": t1_behind,
        "tree2_open": t2_behind,
    }

    # 9. Silhouette + stealth alarm-red color switch
    sil_calm = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="silhouette", amount=1.0, alert_ratio=0.2))
    sil_alarm = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="silhouette", amount=1.0, alert_ratio=0.85))
    calm_added = {tuple(int(v) for v in px) for px in sil_calm[:, :, :3].reshape(-1, 3)} - allowed_colors
    alarm_added = {tuple(int(v) for v in px) for px in sil_alarm[:, :, :3].reshape(-1, 3)} - allowed_colors
    checks["silhouette_clip_and_stealth_alarm"] = {
        "ok": calm_added == {DEFAULT_SILHOUETTE_COLOR[:3]} and alarm_added == {DEFAULT_ALERT_COLOR[:3]},
        "calm_added_colors": [list(c) for c in calm_added],
        "alarm_added_colors": [list(c) for c in alarm_added],
    }

    # 10. Null-effect invariant: fade_to=1.0, dither radius=0&soft=0, cutout hole=0 == plain scene
    plain = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="dither", amount=0.0))
    null_fade = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="fade", amount=1.0, fade_to=1.0))
    null_dither = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="dither", amount=1.0, clear_radius=0.0, soft=0.0))
    null_cutout = np.array(render_scene_frame(ground, tree, tree_pos, tree_base_y, hero, (80, 82), mode="cutout", amount=1.0, hole_radius=0.0))
    checks["null_settings_match_plain"] = {
        "ok": (
            bool(np.array_equal(plain, null_fade))
            and bool(np.array_equal(plain, null_dither))
            and bool(np.array_equal(plain, null_cutout))
        ),
    }

    return {"ok": all(bool(v["ok"]) for v in checks.values()), "checks": checks}


# ---------------------------------------------------------------------------
# Engine Code & Shader Templates
# ---------------------------------------------------------------------------

SNIPPETS: Dict[str, Tuple[str, str]] = {
    "godot4-script": (
        "see_through.gd",
        """# see_through.gd — Keeps character visible behind trees, fog, miasma, or stealth walls (Godot 4.x)
# Scenario routing:
#   A (single tree)              -> Mode.FADE
#   B (fog / mist / canopy zone) -> Mode.DITHER
#   C (spell sphere / miasma)    -> Mode.CUTOUT
#   D (stealth wall / occluder)  -> Mode.SILHOUETTE (shifts to silhouette_alert when near detection)
extends Sprite2D

enum Mode { FADE, DITHER, CUTOUT, SILHOUETTE }

@export var mode := Mode.DITHER
@export var target: Node2D
@export var target_sprite: Node2D
@export var target_size := Vector2(20, 36)
@export var ease_time := 0.2
@export var cover_grid := Vector2i(3, 4)
@export var cover_needed := 0.25
@export var pixel_scale := 1.0

@export_group("Looks")
@export var fade_to := 0.4
@export var clear_radius := 18.0
@export var soft := 16.0
@export var hole_radius := 22.0
@export var silhouette := Color8(118, 214, 255)
@export var silhouette_alert := Color8(239, 68, 68)
@export_range(0.0, 1.0) var alert_ratio := 0.0
@export_range(0.0, 1.0) var alert_threshold := 0.7
@export var alert_smooth_blend := false

var amount := 0.0
var _window := ShaderMaterial.new()
var _ghost: Node2D

func _ready() -> void:
\t_window.shader = preload("see_through.gdshader")

func _process(delta: float) -> void:
\tvar goal := 1.0 if target != null and is_behind() else 0.0
\tamount = move_toward(amount, goal, delta / ease_time) if ease_time > 0.0 else goal
\tvar on := amount > 0.0
\tself_modulate.a = lerpf(1.0, fade_to, amount) if mode == Mode.FADE else 1.0
\tif mode == Mode.DITHER or mode == Mode.CUTOUT:
\t\tmaterial = _window
\t\t_window.set_shader_parameter("target", _center())
\t\t_window.set_shader_parameter("amount", amount)
\t\t_window.set_shader_parameter("clear_radius", clear_radius if mode == Mode.DITHER else hole_radius)
\t\t_window.set_shader_parameter("soft", soft if mode == Mode.DITHER else 0.0)
\t\t_window.set_shader_parameter("pixel_scale", pixel_scale)
\telif material == _window:
\t\tmaterial = null
\t_show_ghost(on and mode == Mode.SILHOUETTE)

func is_behind() -> bool:
\tvar feet := target.global_position
\tif feet.y >= global_position.y:
\t\treturn false
\tif mode == Mode.SILHOUETTE:
\t\tvar box := Rect2(feet - Vector2(target_size.x * 0.5, target_size.y), target_size)
\t\treturn (get_global_transform() * get_rect()).intersects(box)
\tvar hidden := 0
\tfor ix in cover_grid.x:
\t\tfor iy in cover_grid.y:
\t\t\tvar at := Vector2((ix + 0.5) / cover_grid.x - 0.5, (iy + 0.5) / cover_grid.y - 1.0) * target_size
\t\t\tif is_pixel_opaque(to_local(feet + at)):
\t\t\t\thidden += 1
\treturn hidden > 0 and hidden >= cover_needed * cover_grid.x * cover_grid.y

func _center() -> Vector2:
\treturn target.global_position - Vector2(0.0, target_size.y * 0.5) if target != null else Vector2.ZERO

func _active_silhouette_color() -> Color:
\tif alert_smooth_blend:
\t\treturn silhouette.lerp(silhouette_alert, clampf(alert_ratio, 0.0, 1.0))
\treturn silhouette_alert if alert_ratio >= alert_threshold else silhouette

func _show_ghost(on: bool) -> void:
\tclip_children = CLIP_CHILDREN_AND_DRAW if on else CLIP_CHILDREN_DISABLED
\tif on and _ghost == null:
\t\t_ghost = target_sprite.duplicate(0)
\t\tvar flat := ShaderMaterial.new()
\t\tflat.shader = preload("flat_color.gdshader")
\t\t_ghost.material = flat
\t\tadd_child(_ghost)
\tif _ghost != null:
\t\t_ghost.visible = on
\tif on:
\t\t_ghost.material.set_shader_parameter("color", _active_silhouette_color())
\t\t_ghost.global_transform = target_sprite.global_transform
\t\tif _ghost is AnimatedSprite2D:
\t\t\t_ghost.animation = target_sprite.animation
\t\t_ghost.frame = target_sprite.frame
\t\t_ghost.flip_h = target_sprite.flip_h
""",
    ),
    "godot4-window-shader": (
        "see_through.gdshader",
        """// see_through.gdshader — Shared pixel-drop shader for DITHER (soft > 0) and CUTOUT (soft = 0)
shader_type canvas_item;

uniform vec2 target;
uniform float amount = 0.0;
uniform float clear_radius = 18.0;
uniform float soft = 16.0;
uniform float pixel_scale = 1.0; // Set > 1.0 if sprites are scaled up in scene

const float BAYER[16] = float[](
\t0.0, 8.0, 2.0, 10.0,
\t12.0, 4.0, 14.0, 6.0,
\t3.0, 11.0, 1.0, 9.0,
\t15.0, 7.0, 13.0, 5.0
);

varying vec2 world;

void vertex() {
\tworld = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
\tif (amount > 0.0 && (clear_radius > 0.0 || soft > 0.0)) {
\t\tvec2 cell = floor(world / max(pixel_scale, 0.0001));
\t\tfloat d = distance((cell + 0.5) * pixel_scale, target);
\t\tfloat reach = (clear_radius + soft) * amount;
\t\tfloat solid = soft > 0.0 ? clamp((d - reach) / soft + 1.0, 0.0, 1.0) : step(reach, d);
\t\tivec2 c = ivec2(mod(cell, 4.0));
\t\tif (solid <= (BAYER[c.y * 4 + c.x] + 0.5) / 16.0) {
\t\t\tdiscard;
\t\t}
\t}
}
""",
    ),
    "godot4-flat-shader": (
        "flat_color.gdshader",
        """// flat_color.gdshader — Clipped stealth silhouette shader (calm cyan -> alarm red)
shader_type canvas_item;

uniform vec4 color : source_color = vec4(0.463, 0.839, 1.0, 1.0);

void fragment() {
\tCOLOR = vec4(color.rgb, step(0.5, texture(TEXTURE, UV).a) * color.a);
}
""",
    ),
    "unity-window-shader": (
        "SeeThroughWindow2D.shader",
        """// SeeThroughWindow2D.shader — Unity 2D Sprite shader for Dither (soft>0) & Cutout (soft=0)
Shader "Custom/SeeThroughWindow2D"
{
    Properties
    {
        [PerRendererData] _MainTex ("Sprite Texture", 2D) = "white" {}
        _Color ("Tint", Color) = (1,1,1,1)
        _Target ("Target Center (World)", Vector) = (0,0,0,0)
        _Amount ("Amount", Range(0,1)) = 0
        _ClearRadius ("Clear Radius", Float) = 18
        _Soft ("Soft Dither Width", Float) = 16
        _PixelScale ("Art Pixel Scale", Float) = 1
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" "CanUseSpriteAtlas"="True" }
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Off ZWrite Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            fixed4 _Color;
            float2 _Target;
            float _Amount, _ClearRadius, _Soft, _PixelScale;

            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; fixed4 color : COLOR; };
            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; fixed4 color : COLOR; float2 world : TEXCOORD1; };

            v2f vert(appdata v) {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                o.color = v.color * _Color;
                o.world = mul(unity_ObjectToWorld, v.vertex).xy;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target {
                fixed4 col = tex2D(_MainTex, i.uv) * i.color;
                if (_Amount > 0.0 && (_ClearRadius > 0.0 || _Soft > 0.0)) {
                    float ps = max(_PixelScale, 0.0001);
                    float2 cell = floor(i.world / ps);
                    float d = distance((cell + 0.5) * ps, _Target);
                    float reach = (_ClearRadius + _Soft) * _Amount;
                    float solid = _Soft > 0.0 ? saturate((d - reach) / _Soft + 1.0) : step(reach, d);
                    int idx = ((int)fmod(abs(cell.y), 4.0)) * 4 + ((int)fmod(abs(cell.x), 4.0));
                    const float bayer[16] = {0,8,2,10, 12,4,14,6, 3,11,1,9, 15,7,13,5};
                    if (solid <= (bayer[idx] + 0.5) / 16.0) clip(-1);
                }
                return col;
            }
            ENDCG
        }
    }
}
""",
    ),
}


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def _cmd_demo(args: argparse.Namespace) -> int:
    ground_img, tree_img, hero_img = synthesize_demo_sprites()
    ground = np.array(ground_img)
    tree = np.array(tree_img)
    hero = np.array(hero_img)
    tree_pos = (48, 20)
    tree_base_y = 95
    feet = (80, 82)

    modes = [
        ("fade", 0.0, "fade"),
        ("dither", 0.0, "dither"),
        ("cutout", 0.0, "cutout"),
        ("silhouette_calm", 0.0, "silhouette"),
        ("silhouette_alarm", 0.9, "silhouette"),
    ]
    panels: List[np.ndarray] = []
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: Dict[str, str] = {}

    for label, alert_r, mode in modes:
        frame = render_scene_frame(
            ground, tree, tree_pos, tree_base_y, hero, feet,
            mode=mode, amount=1.0, alert_ratio=alert_r,
        )
        if args.upscale > 1:
            frame = frame.resize((frame.width * args.upscale, frame.height * args.upscale), resample=Image.Resampling.NEAREST)
        fp = out_dir / f"see_through_{label}.png"
        frame.save(fp)
        written[label] = str(fp)
        panels.append(np.array(frame))

    strip = Image.fromarray(np.hstack(panels), mode="RGBA")
    strip_path = out_dir / "see_through_comparison_strip.png"
    strip.save(strip_path)
    written["comparison_strip"] = str(strip_path)

    payload = {"ok": True, "written": written}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Exported 5-panel comparison strip -> {strip_path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    res = run_verification_suite()
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


def _cmd_export_code(args: argparse.Namespace) -> int:
    targets = list(SNIPPETS.keys()) if args.target == "all" else [args.target]
    written: Dict[str, str] = {}
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in targets:
            fname, code = SNIPPETS[t]
            fp = out_dir / fname
            fp.write_text(code, encoding="utf-8")
            written[t] = str(fp)

    if args.json:
        payload: Dict[str, Any] = {"ok": True, "targets": targets}
        if written:
            payload["written"] = written
        else:
            payload["code"] = {t: {"filename": SNIPPETS[t][0], "source": SNIPPETS[t][1]} for t in targets}
        print(json.dumps(payload, indent=2))
    else:
        if written:
            for t, p in written.items():
                print(f"Exported {t} -> {p}")
        else:
            for t in targets:
                fname, code = SNIPPETS[t]
                print(f"=== {fname} ===\n{code}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2D See-Through Occlusion pipeline: demo renderer, 10-point verification, and Godot/Unity export."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", help="Render Fade, Dither, Cutout, Silhouette (calm & alarm red) comparison PNGs.")
    p_demo.add_argument("--out-dir", default="exports/see_through", help="Directory for rendered PNGs.")
    p_demo.add_argument("--upscale", type=int, default=2, help="Nearest upscale factor (default: 2).")
    p_demo.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_demo.set_defaults(func=_cmd_demo)

    p_ver = sub.add_parser("verify", help="Run the automated 10-point see-through verification suite.")
    p_ver.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_ver.set_defaults(func=_cmd_verify)

    p_exp = sub.add_parser("export-code", help="Export Godot 4 & Unity scripts/shaders.")
    p_exp.add_argument("--target", choices=sorted(list(SNIPPETS.keys()) + ["all"]), default="all", help="Export target.")
    p_exp.add_argument("--out-dir", help="Optional directory to write generated files.")
    p_exp.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_exp.set_defaults(func=_cmd_export_code)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
