#!/usr/bin/env python3
"""
2D Shadowcasting CLI: Bergstrom 8-octant FOV, torch falloff, fog of war,
enemy line of sight, synthetic demo renderer, engine code export, and tests.

Usage:
    python tools/shadowcasting.py verify --json
    python tools/shadowcasting.py demo --out-dir exports/shadowcasting --json
    python tools/shadowcasting.py export-code --engine godot4 --out exports/shadowcasting/Shadowcast.gd
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

sys.stdout.reconfigure(encoding="utf-8")

# 8 octant transform multipliers: (xx, xy, yx, yy)
OCTANTS: list[tuple[int, int, int, int]] = [
    (1, 0, 0, 1),
    (0, 1, 1, 0),
    (0, -1, 1, 0),
    (-1, 0, 0, 1),
    (-1, 0, 0, -1),
    (0, -1, -1, 0),
    (0, 1, -1, 0),
    (1, 0, 0, -1),
]

DEFAULT_AMBIENT = (0.045, 0.05, 0.09)
DEFAULT_TORCH_COLOR = (1.0 * 1.15, 0.80 * 1.15, 0.55 * 1.15)
DEFAULT_FOG_UNSEEN_TINT = (0.30, 0.32, 0.40)


def shadowcast(walls: np.ndarray, origin_x: int, origin_y: int, radius: int) -> np.ndarray:
    """Compute Bergstrom stack-based 8-octant field of view boolean mask."""
    walls_bool = np.asarray(walls, dtype=bool)
    if walls_bool.ndim != 2:
        raise ValueError(f"walls must be 2D, got shape {walls_bool.shape}")
    h, w = walls_bool.shape
    seen = np.zeros((h, w), dtype=bool)
    if radius <= 0 or not (0 <= origin_x < w and 0 <= origin_y < h):
        return seen

    seen[origin_y, origin_x] = True
    r2 = radius * radius

    for xx, xy, yx, yy in OCTANTS:
        stack: list[tuple[int, float, float]] = [(1, 1.0, 0.0)]
        while stack:
            row, start, end = stack.pop()
            if start < end:
                continue
            blocked = False
            new_start = start
            for j in range(row, radius + 1):
                if blocked:
                    break
                dy = -j
                for dx in range(-j, 1):
                    gx = origin_x + dx * xx + dy * xy
                    gy = origin_y + dx * yx + dy * yy
                    left = (dx - 0.5) / (dy + 0.5)
                    right = (dx + 0.5) / (dy - 0.5)
                    if start < right:
                        continue
                    if end > left:
                        break
                    in_bounds = 0 <= gx < w and 0 <= gy < h
                    if in_bounds and (dx * dx + dy * dy) < r2:
                        seen[gy, gx] = True
                    is_wall = (not in_bounds) or bool(walls_bool[gy, gx])
                    if blocked:
                        if is_wall:
                            new_start = right
                        else:
                            blocked = False
                            start = new_start
                    else:
                        if is_wall and j < radius:
                            blocked = True
                            stack.append((j + 1, start, left))
                            new_start = right
    return seen


def radial_mask(shape: tuple[int, int], origin_x: int, origin_y: int, radius: int) -> np.ndarray:
    """Compute plain radial visibility mask without wall occlusion (dx^2 + dy^2 < r^2)."""
    h, w = shape
    seen = np.zeros((h, w), dtype=bool)
    if radius <= 0 or not (0 <= origin_x < w and 0 <= origin_y < h):
        return seen
    yy, xx = np.ogrid[:h, :w]
    return ((xx - origin_x) ** 2 + (yy - origin_y) ** 2) < (radius * radius)


def enemy_line_of_sight(
    walls: np.ndarray,
    enemy_x: int,
    enemy_y: int,
    target_x: int,
    target_y: int,
    radius: int,
) -> bool:
    """Check whether (target_x, target_y) is visible from (enemy_x, enemy_y)."""
    walls_bool = np.asarray(walls, dtype=bool)
    h, w = walls_bool.shape
    if not (0 <= target_x < w and 0 <= target_y < h):
        return False
    dx = target_x - enemy_x
    dy = target_y - enemy_y
    if radius <= 0 or (dx * dx + dy * dy) >= (radius * radius):
        return False
    seen = shadowcast(walls_bool, enemy_x, enemy_y, radius)
    return bool(seen[target_y, target_x])


def upscale_cell_mask(cell_mask: np.ndarray, tile_size: int) -> np.ndarray:
    """Expand a cell-grid boolean mask cleanly to pixel resolution."""
    if tile_size <= 1:
        return np.asarray(cell_mask, dtype=bool)
    return np.repeat(np.repeat(np.asarray(cell_mask, dtype=bool), tile_size, axis=0), tile_size, axis=1)


def dilate_wall_tops(seen_px: np.ndarray, wall_px: np.ndarray, pad_px: int = 5) -> np.ndarray:
    """Include up to `pad_px` of adjacent wall top pixels around visible cells."""
    if pad_px <= 0:
        return seen_px
    struct = np.ones((3, 3), dtype=bool)
    dilated = binary_dilation(seen_px, structure=struct, iterations=pad_px)
    return seen_px | (dilated & wall_px)


def apply_torch_light(
    scene_rgb: np.ndarray,
    walls_grid: np.ndarray,
    origin_cell: tuple[float, float],
    radius_cells: float,
    tile_size: int = 16,
    steps: int = 6,
    power: float = 0.8,
    wall_pad_px: int = 5,
    ambient: tuple[float, float, float] = DEFAULT_AMBIENT,
    torch_color: tuple[float, float, float] = DEFAULT_TORCH_COLOR,
    use_shadowcast: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply stepped torch falloff and shadowcast occlusion to an RGB float [0,1] or uint8 image."""
    img = np.asarray(scene_rgb, dtype=np.float32)
    if img.max() > 1.0 or scene_rgb.dtype == np.uint8:
        img = img / 255.0

    gh, gw = walls_grid.shape
    ph, pw = img.shape[:2]
    cx, cy = int(round(origin_cell[0])), int(round(origin_cell[1]))
    rad_i = max(1, int(math.ceil(radius_cells)))

    if use_shadowcast:
        seen_cells = shadowcast(walls_grid, cx, cy, rad_i)
    else:
        seen_cells = radial_mask((gh, gw), cx, cy, rad_i)

    seen_px = upscale_cell_mask(seen_cells, tile_size)[:ph, :pw]
    wall_px = upscale_cell_mask(walls_grid, tile_size)[:ph, :pw]
    lit_mask = dilate_wall_tops(seen_px, wall_px, pad_px=wall_pad_px) if use_shadowcast else seen_px

    yy, xx = np.mgrid[:ph, :pw]
    ox_px = (origin_cell[0] + 0.5) * tile_size
    oy_px = (origin_cell[1] + 0.5) * tile_size
    radius_px = max(1.0, radius_cells * tile_size)
    dist = np.sqrt((xx - ox_px) ** 2 + (yy - oy_px) ** 2)
    t = np.clip(1.0 - dist / radius_px, 0.0, 1.0) ** power
    if steps > 0:
        light = np.ceil(t * steps) / steps
    else:
        light = t
    light = light * lit_mask.astype(np.float32)

    amb = np.array(ambient, dtype=np.float32).reshape(1, 1, 3)
    torch = np.array(torch_color, dtype=np.float32).reshape(1, 1, 3)
    lit = img * (amb + torch * light[..., None])
    return np.clip(lit, 0.0, 1.0), seen_cells


def update_fog_of_war(
    explored: np.ndarray,
    seen_cells: np.ndarray,
) -> np.ndarray:
    """Monotonically accumulate seen cells into the explored grid."""
    return np.asarray(explored, dtype=bool) | np.asarray(seen_cells, dtype=bool)


def apply_fog_of_war_visual(
    lit_rgb: np.ndarray,
    scene_rgb: np.ndarray,
    seen_cells: np.ndarray,
    explored_cells: np.ndarray,
    walls_grid: np.ndarray,
    tile_size: int = 16,
    wall_pad_px: int = 5,
    unseen_tint: tuple[float, float, float] = DEFAULT_FOG_UNSEEN_TINT,
) -> np.ndarray:
    """Render live sight (lit), explored memory (desaturated gray-blue), and unexplored (black)."""
    lit = np.asarray(lit_rgb, dtype=np.float32)
    base = np.asarray(scene_rgb, dtype=np.float32)
    if base.max() > 1.0 or scene_rgb.dtype == np.uint8:
        base = base / 255.0
    ph, pw = lit.shape[:2]

    wall_px = upscale_cell_mask(walls_grid, tile_size)[:ph, :pw]
    seen_px = dilate_wall_tops(upscale_cell_mask(seen_cells, tile_size)[:ph, :pw], wall_px, pad_px=wall_pad_px)
    exp_px = dilate_wall_tops(upscale_cell_mask(explored_cells, tile_size)[:ph, :pw], wall_px, pad_px=wall_pad_px)

    out = np.zeros_like(lit, dtype=np.float32)
    memory_mask = exp_px & (~seen_px)
    tint = np.array(unseen_tint, dtype=np.float32).reshape(1, 1, 3)
    gray_blue = base.mean(axis=-1, keepdims=True) * tint

    out[seen_px] = lit[seen_px]
    out[memory_mask] = gray_blue[memory_mask]
    return np.clip(out, 0.0, 1.0)


def _build_demo_dungeon(w: int = 20, h: int = 14) -> tuple[np.ndarray, np.ndarray]:
    """Generate a deterministic pixel dungeon with sealed vault, doorway, pillars, and chests."""
    walls = np.zeros((h, w), dtype=bool)
    walls[0, :] = True
    walls[-1, :] = True
    walls[:, 0] = True
    walls[:, -1] = True

    # Partition wall with one doorway at y=6
    walls[:, 10] = True
    walls[6, 10] = False

    # Sealed vault with no door at top-right (cols 14..18, rows 1..5)
    walls[5, 14:19] = True
    walls[1:6, 14] = True

    # Interior pillar
    walls[5:7, 5:7] = True
    walls[9, 13] = True

    tile_size = 16
    ph, pw = h * tile_size, w * tile_size
    img = np.zeros((ph, pw, 3), dtype=np.uint8)

    # Render textured floor & stone walls
    rng = np.random.default_rng(7)
    for cy in range(h):
        for cx in range(w):
            x0, y0 = cx * tile_size, cy * tile_size
            x1, y1 = x0 + tile_size, y0 + tile_size
            if walls[cy, cx]:
                base = np.array([58, 62, 78], dtype=np.int16)
                patch = base + rng.integers(-6, 7, size=(tile_size, tile_size, 1))
                patch[:3, :, :] += 14  # brick top highlight
                patch[-2:, :, :] -= 14  # brick base shadow
                img[y0:y1, x0:x1] = np.clip(patch, 0, 255).astype(np.uint8)
            else:
                checker = 6 if (cx + cy) % 2 == 0 else -4
                base = np.array([104 + checker, 94 + checker, 82 + checker], dtype=np.int16)
                patch = base + rng.integers(-5, 6, size=(tile_size, tile_size, 1))
                img[y0:y1, x0:x1] = np.clip(patch, 0, 255).astype(np.uint8)

    pil = Image.fromarray(img)
    draw = ImageDraw.Draw(pil)
    # Vault chest (unreachable without door!)
    vx, vy = 16 * tile_size + 3, 2 * tile_size + 4
    draw.rectangle([vx, vy, vx + 10, vy + 8], fill=(180, 120, 42), outline=(60, 35, 15))
    draw.rectangle([vx + 3, vy + 3, vx + 7, vy + 5], fill=(245, 210, 90))
    # Hall chest
    hx, hy = 12 * tile_size + 3, 4 * tile_size + 4
    draw.rectangle([hx, hy, hx + 10, hy + 8], fill=(170, 115, 40), outline=(60, 35, 15))
    draw.rectangle([hx + 3, hy + 3, hx + 7, hy + 5], fill=(245, 210, 90))
    # Hero marker at (7, 6)
    px, py = 7 * tile_size + 4, 6 * tile_size + 3
    draw.rectangle([px, py, px + 8, py + 10], fill=(70, 165, 235), outline=(25, 45, 75))
    # Enemy marker at (12, 8)
    ex, ey = 12 * tile_size + 4, 8 * tile_size + 3
    draw.rectangle([ex, ey, ex + 8, ey + 10], fill=(215, 68, 68), outline=(75, 20, 20))

    return np.array(pil, dtype=np.uint8), walls


def render_demo(out_dir: Path) -> dict[str, Any]:
    """Generate side-by-side comparison sheets for plain light vs shadowcast vs fog vs enemy LOS."""
    out_dir.mkdir(parents=True, exist_ok=True)
    scene_u8, walls = _build_demo_dungeon()
    tile_size = 16
    hero = (7, 6)
    radius = 6

    plain_lit, _ = apply_torch_light(
        scene_u8, walls, hero, radius, tile_size=tile_size, use_shadowcast=False
    )
    sc_lit, seen_now = apply_torch_light(
        scene_u8, walls, hero, radius, tile_size=tile_size, use_shadowcast=True
    )

    explored = np.zeros_like(walls, dtype=bool)
    explored = update_fog_of_war(explored, shadowcast(walls, 3, 3, 4))
    explored = update_fog_of_war(explored, seen_now)
    fog_img = apply_fog_of_war_visual(sc_lit, scene_u8, seen_now, explored, walls, tile_size=tile_size)

    los_ok = enemy_line_of_sight(walls, 12, 8, hero[0], hero[1], 10)
    los_blocked = enemy_line_of_sight(walls, 12, 3, hero[0], hero[1], 10)

    def to_pil(arr: np.ndarray) -> Image.Image:
        return Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8))

    p_plain = out_dir / "torch_plain_vs_shadowcast.png"
    p_fog = out_dir / "fog_of_war.png"

    im_plain = to_pil(plain_lit)
    im_sc = to_pil(sc_lit)
    im_fog = to_pil(fog_img)

    w, h = im_plain.size
    sheet1 = Image.new("RGB", (w, h * 2 + 24), (16, 18, 24))
    sheet1.paste(im_plain, (0, 0))
    sheet1.paste(im_sc, (0, h + 24))
    d1 = ImageDraw.Draw(sheet1)
    d1.text((6, 4), "Plain radial torch (bleeds into sealed rooms)", fill=(255, 220, 180))
    d1.text((6, h + 28), "8-octant shadowcast + 5px wall top dilation", fill=(180, 245, 200))
    sheet1.save(p_plain)

    im_fog.save(p_fog)

    return {
        "torch_comparison": str(p_plain),
        "fog_of_war": str(p_fog),
        "vault_chest_seen_shadowcast": bool(seen_now[2, 16]),
        "enemy_at_12_8_sees_hero": los_ok,
        "enemy_at_12_3_sees_hero": los_blocked,
    }


def run_verify() -> dict[str, Any]:
    """Run all 9 verification tests for shadowcasting, fog of war, LOS, and falloff."""
    results: dict[str, dict[str, Any]] = {}

    # 1. Empty 11x11 from (5,5): r=3->25, r=4->45, r=5->69, 90-deg rotation invariant
    empty11 = np.zeros((11, 11), dtype=bool)
    s3 = shadowcast(empty11, 5, 5, 3)
    s4 = shadowcast(empty11, 5, 5, 4)
    s5 = shadowcast(empty11, 5, 5, 5)
    c3, c4, c5 = int(s3.sum()), int(s4.sum()), int(s5.sum())
    rot_ok = bool(np.array_equal(s5, np.rot90(s5)))
    results["1_empty_11x11_counts_and_symmetry"] = {
        "r3": c3,
        "r4": c4,
        "r5": c5,
        "rot90_invariant": rot_ok,
        "ok": (c3 == 25 and c4 == 45 and c5 == 69 and rot_ok),
    }

    # 2. Strict radius (< r^2): r=4 -> (8,5) seen, (9,5) not seen
    r4_8_5 = bool(s4[5, 8])
    r4_9_5 = bool(s4[5, 9])
    results["2_strict_radius_lt_r2"] = {
        "seen_8_5": r4_8_5,
        "seen_9_5": r4_9_5,
        "ok": (r4_8_5 is True and r4_9_5 is False),
    }

    # 3. Single wall at (7,5) with r=6: 106 seen, (7,5) seen, (8,5)/(9,5)/(10,5) blocked
    w_single = np.zeros((11, 11), dtype=bool)
    w_single[5, 7] = True
    s6_wall = shadowcast(w_single, 5, 5, 6)
    cnt_single = int(s6_wall.sum())
    wall_hit = bool(s6_wall[5, 7])
    shadow_8 = bool(s6_wall[5, 8])
    shadow_9 = bool(s6_wall[5, 9])
    shadow_10 = bool(s6_wall[5, 10])
    results["3_single_wall_7_5_r6"] = {
        "seen_count": cnt_single,
        "wall_7_5_seen": wall_hit,
        "behind_8_9_10": [shadow_8, shadow_9, shadow_10],
        "ok": (cnt_single == 106 and wall_hit and not shadow_8 and not shadow_9 and not shadow_10),
    }

    # 4. 7x7 all walls from (3,3) r=3 -> 9 seen
    all_walls = np.ones((7, 7), dtype=bool)
    s_all = shadowcast(all_walls, 3, 3, 3)
    cnt_all = int(s_all.sum())
    results["4_all_walls_7x7_origin_3_3_r3"] = {
        "seen_count": cnt_all,
        "ok": (cnt_all == 9),
    }

    # 5. 6x6 empty from corner (0,0) r=4 -> 15 seen without OOB
    empty6 = np.zeros((6, 6), dtype=bool)
    s_corner = shadowcast(empty6, 0, 0, 4)
    cnt_corner = int(s_corner.sum())
    oob_empty = shadowcast(empty6, -1, 0, 4)
    zero_r = shadowcast(empty6, 0, 0, 0)
    results["5_corner_6x6_bounds_and_guards"] = {
        "seen_count": cnt_corner,
        "oob_origin_count": int(oob_empty.sum()),
        "zero_radius_count": int(zero_r.sum()),
        "ok": (cnt_corner == 15 and int(oob_empty.sum()) == 0 and int(zero_r.sum()) == 0),
    }

    # 6. Closed room -> 0 floor cells inside closed room seen
    vault = np.zeros((11, 11), dtype=bool)
    vault[1:6, 6] = True
    vault[1, 6:10] = True
    vault[5, 6:10] = True
    vault[1:6, 9] = True
    s_vault = shadowcast(vault, 3, 3, 8)
    vault_floor_seen = int(s_vault[2:5, 7:9].sum())
    results["6_closed_room_zero_floor_leak"] = {
        "vault_floor_cells_seen": vault_floor_seen,
        "ok": (vault_floor_seen == 0),
    }

    # 7. Enemy LOS: 11x11 wall col 5, enemy (2,5), player (8,5), r=10 -> False; remove (5,5) -> True
    los_walls = np.zeros((11, 11), dtype=bool)
    los_walls[:, 5] = True
    los_blocked = enemy_line_of_sight(los_walls, 2, 5, 8, 5, 10)
    los_walls[5, 5] = False
    los_clear = enemy_line_of_sight(los_walls, 2, 5, 8, 5, 10)
    results["7_enemy_line_of_sight"] = {
        "blocked_with_wall_col_5": los_blocked,
        "clear_after_opening_5_5": los_clear,
        "ok": (los_blocked is False and los_clear is True),
    }

    # 8. Fog state monotonic + gray-blue / black rendering
    grid_w = np.zeros((5, 5), dtype=bool)
    grid_w[:, 2] = True
    exp0 = np.zeros((5, 5), dtype=bool)
    seen_a = shadowcast(grid_w, 1, 1, 2)
    exp1 = update_fog_of_war(exp0, seen_a)
    seen_b = shadowcast(grid_w, 1, 4, 1)
    exp2 = update_fog_of_war(exp1, seen_b)
    monotonic = bool(np.all(exp1 <= exp2))
    scene_flat = np.full((5 * 8, 5 * 8, 3), 0.8, dtype=np.float32)
    lit_flat, _ = apply_torch_light(scene_flat, grid_w, (1, 4), 1, tile_size=8, wall_pad_px=0)
    fog_vis = apply_fog_of_war_visual(lit_flat, scene_flat, seen_b, exp2, grid_w, tile_size=8, wall_pad_px=0)
    # Cell (0,0) was explored in exp1, unseen in seen_b -> gray-blue tint (B > R)
    mem_px = fog_vis[4, 4]
    # Cell (4,4) never explored -> black (0,0,0)
    unexp_px = fog_vis[4 * 8 + 4, 4 * 8 + 4]
    fog_colors_ok = bool(
        mem_px[2] > mem_px[0] > 0.0 and np.allclose(mem_px, 0.8 * np.array(DEFAULT_FOG_UNSEEN_TINT), atol=1e-4)
        and np.allclose(unexp_px, 0.0, atol=1e-6)
    )
    results["8_fog_of_war_monotonic_and_colors"] = {
        "monotonic": monotonic,
        "memory_rgb": [round(float(x), 4) for x in mem_px],
        "unexplored_rgb": [round(float(x), 4) for x in unexp_px],
        "ok": (monotonic and fog_colors_ok),
    }

    # 9. Feature-off restores plain radial light
    wall_box = np.zeros((9, 9), dtype=bool)
    wall_box[:, 5] = True
    scene9 = np.full((9 * 8, 9 * 8, 3), 0.9, dtype=np.float32)
    lit_sc, _ = apply_torch_light(scene9, wall_box, (2, 4), 5, tile_size=8, use_shadowcast=True)
    lit_plain, _ = apply_torch_light(scene9, wall_box, (2, 4), 5, tile_size=8, use_shadowcast=False)
    # Pixel at cell (6,4) behind wall is only ambient under shadowcast, brighter under plain light
    behind_sc = float(lit_sc[4 * 8 + 4, 6 * 8 + 4].mean())
    behind_plain = float(lit_plain[4 * 8 + 4, 6 * 8 + 4].mean())
    results["9_feature_off_restores_plain_light"] = {
        "behind_wall_shadowcast_mean": round(behind_sc, 4),
        "behind_wall_plain_mean": round(behind_plain, 4),
        "ok": (behind_plain > behind_sc * 2.0),
    }

    all_passed = all(v["ok"] for v in results.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in results.values() if v["ok"]), "total": len(results), "checks": results}


GODOT4_CODE = """# Shadowcast.gd — Bergstrom 8-octant FOV + Line of Sight for Godot 4
# Also applies to 2D platformer cave lighting and stealth cones.
class_name Shadowcast
extends RefCounted

const OCTANTS: Array[Array] = [
\t[1, 0, 0, 1],
\t[0, 1, 1, 0],
\t[0, -1, 1, 0],
\t[-1, 0, 0, 1],
\t[-1, 0, 0, -1],
\t[0, -1, -1, 0],
\t[0, 1, -1, 0],
\t[1, 0, 0, -1],
]


static func compute_fov(walls: PackedByteArray, width: int, height: int, ox: int, oy: int, radius: int) -> PackedByteArray:
\tvar seen := PackedByteArray()
\tseen.resize(width * height)
\tseen.fill(0)
\tif radius <= 0 or ox < 0 or ox >= width or oy < 0 or oy >= height:
\t\treturn seen

\tseen[oy * width + ox] = 1
\tvar r2: int = radius * radius

\tfor m in OCTANTS:
\t\tvar xx: int = m[0]
\t\tvar xy: int = m[1]
\t\tvar yx: int = m[2]
\t\tvar yy: int = m[3]
\t\tvar stack: Array[Array] = [[1, 1.0, 0.0]]
\t\twhile not stack.is_empty():
\t\t\tvar frame: Array = stack.pop_back()
\t\t\tvar row: int = frame[0]
\t\t\tvar start: float = frame[1]
\t\t\tvar end_slope: float = frame[2]
\t\t\tif start < end_slope:
\t\t\t\tcontinue
\t\t\tvar blocked := false
\t\t\tvar new_start := start
\t\t\tfor j in range(row, radius + 1):
\t\t\t\tif blocked:
\t\t\t\t\tbreak
\t\t\t\tvar dy: int = -j
\t\t\t\tfor dx in range(-j, 1):
\t\t\t\t\tvar gx: int = ox + dx * xx + dy * xy
\t\t\t\t\tvar gy: int = oy + dx * yx + dy * yy
\t\t\t\t\tvar left: float = (float(dx) - 0.5) / (float(dy) + 0.5)
\t\t\t\t\tvar right: float = (float(dx) + 0.5) / (float(dy) - 0.5)
\t\t\t\t\tif start < right:
\t\t\t\t\t\tcontinue
\t\t\t\t\tif end_slope > left:
\t\t\t\t\t\tbreak
\t\t\t\t\tvar in_bounds := gx >= 0 and gx < width and gy >= 0 and gy < height
\t\t\t\t\tif in_bounds and (dx * dx + dy * dy) < r2:
\t\t\t\t\t\tseen[gy * width + gx] = 1
\t\t\t\t\tvar is_wall := (not in_bounds) or (walls[gy * width + gx] != 0)
\t\t\t\t\tif blocked:
\t\t\t\t\t\tif is_wall:
\t\t\t\t\t\t\tnew_start = right
\t\t\t\t\t\telse:
\t\t\t\t\t\t\tblocked = false
\t\t\t\t\t\t\tstart = new_start
\t\t\t\t\telif is_wall and j < radius:
\t\t\t\t\t\tblocked = true
\t\t\t\t\t\tstack.append([j + 1, start, left])
\t\t\t\t\t\tnew_start = right
\treturn seen


static func has_line_of_sight(walls: PackedByteArray, width: int, height: int, ex: int, ey: int, tx: int, ty: int, radius: int) -> bool:
\tif tx < 0 or tx >= width or ty < 0 or ty >= height or radius <= 0:
\t\treturn false
\tvar dx := tx - ex
\tvar dy := ty - ey
\tif dx * dx + dy * dy >= radius * radius:
\t\treturn false
\tvar seen := compute_fov(walls, width, height, ex, ey, radius)
\treturn seen[ty * width + tx] != 0
"""

GODOT4_SHADER = """// torch_shadowcast.gdshader — Apply visibility ImageTexture + stepped torch falloff + 5px wall tops
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform sampler2D fov_mask : filter_nearest;
uniform vec2 light_uv = vec2(0.5);
uniform float radius_px = 96.0;
uniform vec2 viewport_px = vec2(320.0, 224.0);
uniform float light_steps = 6.0;
uniform float falloff_power = 0.8;
uniform vec3 ambient_color = vec3(0.045, 0.05, 0.09);
uniform vec3 torch_color = vec3(1.15, 0.92, 0.6325);

void fragment() {
\tvec4 base = texture(screen_tex, SCREEN_UV);
\tfloat vis = texture(fov_mask, SCREEN_UV).r;
\tfloat dist = length((SCREEN_UV - light_uv) * viewport_px);
\tfloat t = pow(clamp(1.0 - dist / max(radius_px, 1.0), 0.0, 1.0), falloff_power);
\tfloat stepped = light_steps > 0.0 ? ceil(t * light_steps) / light_steps : t;
\tvec3 lit = base.rgb * (ambient_color + torch_color * (stepped * vis));
\tCOLOR = vec4(lit, base.a);
}
"""

UNITY_CS_CODE = """// Shadowcast2D.cs — Bergstrom 8-octant FOV, Fog of War, and Enemy Line of Sight
using System.Collections.Generic;
using UnityEngine;

public static class Shadowcast2D
{
    private static readonly int[,] Octants = {
        { 1, 0, 0, 1 }, { 0, 1, 1, 0 }, { 0, -1, 1, 0 }, { -1, 0, 0, 1 },
        { -1, 0, 0, -1 }, { 0, -1, -1, 0 }, { 0, 1, -1, 0 }, { 1, 0, 0, -1 }
    };

    public static bool[,] ComputeFov(bool[,] walls, int ox, int oy, int radius)
    {
        int h = walls.GetLength(0);
        int w = walls.GetLength(1);
        var seen = new bool[h, w];
        if (radius <= 0 || ox < 0 || ox >= w || oy < 0 || oy >= h) return seen;

        seen[oy, ox] = true;
        int r2 = radius * radius;
        var stack = new Stack<(int row, float start, float end)>();

        for (int oct = 0; oct < 8; oct++)
        {
            int xx = Octants[oct, 0], xy = Octants[oct, 1], yx = Octants[oct, 2], yy = Octants[oct, 3];
            stack.Push((1, 1.0f, 0.0f));
            while (stack.Count > 0)
            {
                var (row, start, end) = stack.Pop();
                if (start < end) continue;
                bool blocked = false;
                float newStart = start;
                for (int j = row; j <= radius && !blocked; j++)
                {
                    int dy = -j;
                    for (int dx = -j; dx <= 0; dx++)
                    {
                        int gx = ox + dx * xx + dy * xy;
                        int gy = oy + dx * yx + dy * yy;
                        float left = (dx - 0.5f) / (dy + 0.5f);
                        float right = (dx + 0.5f) / (dy - 0.5f);
                        if (start < right) continue;
                        if (end > left) break;
                        bool inBounds = gx >= 0 && gx < w && gy >= 0 && gy < h;
                        if (inBounds && dx * dx + dy * dy < r2) seen[gy, gx] = true;
                        bool isWall = !inBounds || walls[gy, gx];
                        if (blocked)
                        {
                            if (isWall) newStart = right;
                            else { blocked = false; start = newStart; }
                        }
                        else if (isWall && j < radius)
                        {
                            blocked = true;
                            stack.Push((j + 1, start, left));
                            newStart = right;
                        }
                    }
                }
            }
        }
        return seen;
    }

    public static bool HasLineOfSight(bool[,] walls, int ex, int ey, int tx, int ty, int radius)
    {
        int h = walls.GetLength(0), w = walls.GetLength(1);
        if (tx < 0 || tx >= w || ty < 0 || ty >= h || radius <= 0) return false;
        int dx = tx - ex, dy = ty - ey;
        if (dx * dx + dy * dy >= radius * radius) return false;
        return ComputeFov(walls, ex, ey, radius)[ty, tx];
    }
}
"""

TS_CODE = """// shadowcast.ts — Bergstrom 8-octant FOV, Fog of War, and Line of Sight
const OCTANTS: readonly [number, number, number, number][] = [
  [1, 0, 0, 1], [0, 1, 1, 0], [0, -1, 1, 0], [-1, 0, 0, 1],
  [-1, 0, 0, -1], [0, -1, -1, 0], [0, 1, -1, 0], [1, 0, 0, -1],
];

export function shadowcast(walls: boolean[][], ox: number, oy: number, radius: number): boolean[][] {
  const h = walls.length;
  const w = h > 0 ? walls[0].length : 0;
  const seen = Array.from({ length: h }, () => Array<boolean>(w).fill(false));
  if (radius <= 0 || ox < 0 || ox >= w || oy < 0 || oy >= h) return seen;

  seen[oy][ox] = true;
  const r2 = radius * radius;
  for (const [xx, xy, yx, yy] of OCTANTS) {
    const stack: [number, number, number][] = [[1, 1.0, 0.0]];
    while (stack.length > 0) {
      let [row, start, end] = stack.pop()!;
      if (start < end) continue;
      let blocked = false;
      let newStart = start;
      for (let j = row; j <= radius && !blocked; j++) {
        const dy = -j;
        for (let dx = -j; dx <= 0; dx++) {
          const gx = ox + dx * xx + dy * xy;
          const gy = oy + dx * yx + dy * yy;
          const left = (dx - 0.5) / (dy + 0.5);
          const right = (dx + 0.5) / (dy - 0.5);
          if (start < right) continue;
          if (end > left) break;
          const inBounds = gx >= 0 && gx < w && gy >= 0 && gy < h;
          if (inBounds && dx * dx + dy * dy < r2) seen[gy][gx] = true;
          const isWall = !inBounds || walls[gy][gx];
          if (blocked) {
            if (isWall) newStart = right;
            else { blocked = false; start = newStart; }
          } else if (isWall && j < radius) {
            blocked = true;
            stack.push([j + 1, start, left]);
            newStart = right;
          }
        }
      }
    }
  }
  return seen;
}
"""


def export_code(engine: str) -> str:
    """Return engine-specific shadowcasting template."""
    if engine == "godot4":
        return GODOT4_CODE + "\n" + GODOT4_SHADER
    if engine == "unity":
        return UNITY_CS_CODE
    if engine == "typescript":
        return TS_CODE
    raise ValueError(f"Unsupported engine: {engine}")


def main() -> int:
    parser = argparse.ArgumentParser(description="2D Shadowcasting, Torchlight, Fog of War & LOS CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_verify = sub.add_parser("verify", help="Run automated 9-test verification suite")
    p_verify.add_argument("--json", action="store_true")

    p_demo = sub.add_parser("demo", help="Render comparison demo PNGs")
    p_demo.add_argument("--out-dir", type=Path, default=Path("exports/shadowcasting"))
    p_demo.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export engine code snippet")
    p_exp.add_argument("--engine", choices=["godot4", "unity", "typescript"], required=True)
    p_exp.add_argument("--out", type=Path)
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "verify":
        res = run_verify()
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Shadowcasting verify: {res['passed']}/{res['total']} passed")
        return 0 if res["all_passed"] else 1

    if args.cmd == "demo":
        res = render_demo(args.out_dir)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Rendered shadowcasting demos to {args.out_dir}")
        return 0

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
