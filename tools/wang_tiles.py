#!/usr/bin/env python3
"""
Edge Wang Tiles Pipeline Tool (wang_tiles.py)
Generates, places, verifies, and exports 16-tile (2-color edge-matched) Wang tilesets
to break repeating grid patterns across 2D game terrains.

Features:
  - cut:     Cut a 4x4 (16-tile) index-ordered Wang atlas from one seamless texture
             using plainest-region spot scoring + Efros & Freeman minimum-error boundary cuts.
  - map:     Generate deterministic finite, looping, or stateless chunked Wang tile maps
             with neighbor-invariant verification, PNG previews, and orange/blue edge overlays.
  - verify:  Audit an existing 4x4 Wang atlas for pixel-level edge continuity across all
             64 horizontal and 64 vertical valid joins, plus edge-variance warnings.
  - snippet: Print drop-in integration code for Godot 4, Unity, TypeScript/Phaser, or Python.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

COLOR_ZERO_RGB = (249, 115, 22, 255)  # Orange = edge color 0
COLOR_ONE_RGB = (59, 130, 246, 255)   # Blue   = edge color 1


# ---------------------------------------------------------------------------
# Core Wang Tile Math & Stateless Chunk Hashing
# ---------------------------------------------------------------------------

def wang_index(top: int, right: int, bottom: int, left: int) -> int:
    """Return canonical 0..15 Wang index: top + 2*right + 4*bottom + 8*left."""
    return (top & 1) + 2 * (right & 1) + 4 * (bottom & 1) + 8 * (left & 1)


def decode_wang_index(index: int) -> Tuple[int, int, int, int]:
    """Decode 0..15 Wang index into (top, right, bottom, left) edge colors."""
    return (
        index & 1,
        (index >> 1) & 1,
        (index >> 2) & 1,
        (index >> 3) & 1,
    )


def atlas_coords(index: int) -> Tuple[int, int]:
    """Return (col, row) in a 4x4 index-ordered atlas."""
    return index % 4, index // 4


def _splitmix64(x: int) -> int:
    """64-bit SplitMix finalizer for deterministic stateless edge hashing."""
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return (x ^ (x >> 31)) & 0xFFFFFFFFFFFFFFFF


def hash_edge_bit(world_seed: int, edge_x: int, edge_y: int, axis: int) -> int:
    """
    Deterministic 0/1 edge color from (world_seed, edge_x, edge_y, axis).
    axis=0 -> horizontal edge (top of cell (edge_y, edge_x))
    axis=1 -> vertical edge   (left of cell (edge_y, edge_x))
    Adjacent chunks agree on shared boundary edges without sharing state.
    """
    h = _splitmix64(world_seed & 0xFFFFFFFFFFFFFFFF)
    h = _splitmix64(h ^ ((edge_x * 0xD6E8FEB86659FD93) & 0xFFFFFFFFFFFFFFFF))
    h = _splitmix64(h ^ ((edge_y * 0xA5A3564E27F8862D) & 0xFFFFFFFFFFFFFFFF))
    h = _splitmix64(h ^ ((axis & 1) * 0x9E3779B97F4A7C15))
    return (h >> 63) & 1


def generate_wang_grid(
    rows: int,
    cols: int,
    seed: int = 42,
    mode: str = "finite",
    chunk_x: int = 0,
    chunk_y: int = 0,
) -> Tuple[List[List[int]], List[List[int]], List[List[int]]]:
    """
    Generate a rows x cols Wang tile index grid and its underlying edge arrays.
    Returns (grid, h_edges, v_edges).
    """
    if rows <= 0 or cols <= 0:
        raise ValueError("rows and cols must be positive integers.")

    if mode == "chunked":
        ox = chunk_x * cols
        oy = chunk_y * rows
        h_edges = [
            [hash_edge_bit(seed, ox + c, oy + r, 0) for c in range(cols)]
            for r in range(rows + 1)
        ]
        v_edges = [
            [hash_edge_bit(seed, ox + c, oy + r, 1) for c in range(cols + 1)]
            for r in range(rows)
        ]
    elif mode == "looping":
        rng = np.random.default_rng(seed)
        h_edges = rng.integers(0, 2, size=(rows, cols), dtype=np.int32).tolist()
        v_edges = rng.integers(0, 2, size=(rows, cols), dtype=np.int32).tolist()
    elif mode == "finite":
        rng = np.random.default_rng(seed)
        h_edges = rng.integers(0, 2, size=(rows + 1, cols), dtype=np.int32).tolist()
        v_edges = rng.integers(0, 2, size=(rows, cols + 1), dtype=np.int32).tolist()
    else:
        raise ValueError(f"Unsupported mode: {mode}. Choose finite, looping, or chunked.")

    grid: List[List[int]] = []
    for r in range(rows):
        row_vals: List[int] = []
        r_next = (r + 1) % rows if mode == "looping" else r + 1
        for c in range(cols):
            c_next = (c + 1) % cols if mode == "looping" else c + 1
            top = h_edges[r][c]
            bottom = h_edges[r_next][c]
            left = v_edges[r][c]
            right = v_edges[r][c_next]
            row_vals.append(wang_index(top, right, bottom, left))
        grid.append(row_vals)

    return grid, h_edges, v_edges


def verify_wang_grid(grid: Sequence[Sequence[int]], looping: bool = False) -> Dict[str, Any]:
    """
    Assert that every neighboring pair of cells shares matching edge colors
    and every index is in 0..15.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    mismatches: List[Dict[str, Any]] = []
    invalid_indices: List[Dict[str, Any]] = []

    for r in range(rows):
        if len(grid[r]) != cols:
            raise ValueError(f"Non-rectangular grid at row {r}.")
        for c in range(cols):
            idx = int(grid[r][c])
            if not (0 <= idx <= 15):
                invalid_indices.append({"row": r, "col": c, "index": idx})
                continue
            t, ri, b, le = decode_wang_index(idx)
            if c + 1 < cols or looping:
                nc = (c + 1) % cols
                nidx = int(grid[r][nc])
                if 0 <= nidx <= 15:
                    _, _, _, n_left = decode_wang_index(nidx)
                    if ri != n_left:
                        mismatches.append({
                            "type": "horizontal",
                            "cell": [r, c],
                            "neighbor": [r, nc],
                            "cell_right": ri,
                            "neighbor_left": n_left,
                        })
            if r + 1 < rows or looping:
                nr = (r + 1) % rows
                nidx = int(grid[nr][c])
                if 0 <= nidx <= 15:
                    n_top, _, _, _ = decode_wang_index(nidx)
                    if b != n_top:
                        mismatches.append({
                            "type": "vertical",
                            "cell": [r, c],
                            "neighbor": [nr, c],
                            "cell_bottom": b,
                            "neighbor_top": n_top,
                        })

    return {
        "rows": rows,
        "cols": cols,
        "looping": looping,
        "invariant_ok": len(mismatches) == 0 and len(invalid_indices) == 0,
        "mismatch_count": len(mismatches),
        "invalid_index_count": len(invalid_indices),
        "mismatches": mismatches[:20],
        "invalid_indices": invalid_indices[:20],
    }


# ---------------------------------------------------------------------------
# Procedural Demo Texture & Seamless Texture Sampling
# ---------------------------------------------------------------------------

def generate_demo_meadow(width: int = 280, height: int = 298, seed: int = 7) -> Image.Image:
    """
    Synthesize a seamless pixel-art meadow (280x298 by default) containing:
      - Light grass base with subtle pixel-art grass tufts
      - A darker grass patch (larger than 32px)
      - Scattered small rocks and yellow/white flowers
    Ideal for testing plainest-region edge spot selection vs busy regions.
    """
    rng = np.random.default_rng(seed)
    arr = np.zeros((height, width, 4), dtype=np.uint8)

    base_tones = [
        (106, 168, 79, 255),
        (116, 178, 86, 255),
        (98, 158, 72, 255),
        (124, 186, 92, 255),
    ]
    noise = rng.integers(0, 100, size=(height, width))
    arr[:, :] = base_tones[0]
    arr[noise > 55] = base_tones[1]
    arr[noise < 25] = base_tones[2]
    arr[noise > 88] = base_tones[3]

    # Subtle 2px grass blades (kept uniform enough for plain areas)
    for _ in range(int(width * height * 0.015)):
        x = int(rng.integers(0, width))
        y = int(rng.integers(0, height))
        arr[y % height, x % width] = (86, 145, 63, 255)
        arr[(y - 1) % height, x % width] = (132, 194, 98, 255)

    # Large dark grass patch in upper-left quadrant (intentionally > 32px)
    yy, xx = np.ogrid[:height, :width]
    patch_mask = (((xx - 68) / 42.0) ** 2 + ((yy - 70) / 34.0) ** 2) < 1.0
    patch_noise = rng.integers(0, 10, size=(height, width))
    arr[patch_mask & (patch_noise < 7)] = (74, 128, 56, 255)
    arr[patch_mask & (patch_noise >= 7)] = (66, 116, 50, 255)

    # Scatter yellow & white flowers in lower-right & middle-left regions (busy spots)
    flower_centers = []
    for _ in range(42):
        fx = int(rng.integers(width // 2, width))
        fy = int(rng.integers(height // 3, height))
        flower_centers.append((fx, fy, rng.random() < 0.6))
    for _ in range(14):
        fx = int(rng.integers(0, width // 2))
        fy = int(rng.integers(height // 2, height))
        flower_centers.append((fx, fy, rng.random() < 0.5))

    for fx, fy, is_yellow in flower_centers:
        petal = (250, 214, 67, 255) if is_yellow else (244, 246, 238, 255)
        center = (212, 122, 38, 255) if is_yellow else (238, 198, 62, 255)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            arr[(fy + dy) % height, (fx + dx) % width] = petal
        arr[fy % height, fx % width] = center

    # Scatter a few small gray rocks in busy zone
    for _ in range(8):
        rx = int(rng.integers(width // 2, width))
        ry = int(rng.integers(0, height // 2))
        for dy in range(-1, 2):
            for dx in range(-2, 2):
                if abs(dx) + abs(dy) <= 2:
                    col = (146, 152, 144, 255) if dy <= 0 else (108, 114, 108, 255)
                    arr[(ry + dy) % height, (rx + dx) % width] = col

    return Image.fromarray(arr, mode="RGBA")


def sample_wrap(arr: np.ndarray, x0: int, y0: int, w: int, h: int) -> np.ndarray:
    """Sample a (h, w, C) patch with wrap-around modulo texture dimensions."""
    tex_h, tex_w = arr.shape[:2]
    ys = (np.arange(y0, y0 + h) % tex_h)[:, None]
    xs = (np.arange(x0, x0 + w) % tex_w)[None, :]
    return arr[ys, xs]


# ---------------------------------------------------------------------------
# Plainest-Region Auto-Spot Scoring & Minimum Error Boundary Cut (Image Quilting)
# ---------------------------------------------------------------------------

def _compute_busyness_map(tex_rgb: np.ndarray) -> np.ndarray:
    """
    Score each pixel's visual 'loudness' (gradient + outlier deviation from local mean).
    Lower scores indicate calm, even base terrain without flowers, rocks, or dark clumps.
    """
    rgb = tex_rgb.astype(np.float32)
    h, w = rgb.shape[:2]

    # Periodic finite differences
    gx = np.abs(np.roll(rgb, -1, axis=1) - rgb).sum(axis=2)
    gy = np.abs(np.roll(rgb, -1, axis=0) - rgb).sum(axis=2)
    grad = gx + gy

    # Global/local outlier penalty (bright petals, dark rocks stand out from median grass)
    med = np.median(rgb, axis=(0, 1))
    outlier = np.linalg.norm(rgb - med[None, None, :], axis=2)

    # Combine gradient and amplified outlier spike
    return grad + 1.5 * (outlier ** 1.3)


def _box_sum_wrap(field: np.ndarray, box_h: int, box_w: int) -> np.ndarray:
    """Exact wrap-around box sum over (box_h, box_w) using 2D integral image."""
    h, w = field.shape
    padded = np.tile(field, (2, 2))
    cs = np.pad(padded, ((1, 0), (1, 0)), mode="constant").cumsum(axis=0).cumsum(axis=1)
    y0 = np.arange(h)[:, None]
    x0 = np.arange(w)[None, :]
    return cs[y0 + box_h, x0 + box_w] - cs[y0, x0 + box_w] - cs[y0 + box_h, x0] + cs[y0, x0]


def select_plain_edge_spots(
    tex_rgb: np.ndarray,
    tile_size: int,
    edge_width: int,
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    Automatically pick 2 horizontal edge spots [(hx0, hy0), (hx1, hy1)] and
    2 vertical edge spots [(vx0, vy0), (vx1, vy1)] from the plainest regions
    of the seamless texture, separated so colors 0 and 1 remain distinct.
    """
    h, w = tex_rgb.shape[:2]
    busy = _compute_busyness_map(tex_rgb)

    # H-spot spans rows [hy - edge_width, hy + edge_width) and cols [hx, hx + tile_size)
    h_scores = _box_sum_wrap(busy, 2 * edge_width, tile_size)
    # V-spot spans rows [vy, vy + tile_size) and cols [vx - edge_width, vx + edge_width)
    v_scores = _box_sum_wrap(busy, tile_size, 2 * edge_width)

    min_sep = max(tile_size, min(w, h) // 4)

    def _toroidal_dist2(x1: int, y1: int, x2: int, y2: int) -> float:
        dx = min(abs(x1 - x2), w - abs(x1 - x2))
        dy = min(abs(y1 - y2), h - abs(y1 - y2))
        return float(dx * dx + dy * dy)

    def _pick_pair(score_grid: np.ndarray, y_shift: int, x_shift: int, avoid: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        flat_order = np.argsort(score_grid, axis=None)
        chosen: List[Tuple[int, int]] = []
        # Subsample step keeps candidate scan fast even on 2K textures
        stride = max(1, len(flat_order) // 12000)
        for threshold_sep in (min_sep, tile_size // 2, 4):
            chosen.clear()
            for flat_idx in flat_order[::stride]:
                top_y, left_x = divmod(int(flat_idx), w)
                cand = ((left_x + x_shift) % w, (top_y + y_shift) % h)
                if all(_toroidal_dist2(cand[0], cand[1], p[0], p[1]) >= threshold_sep ** 2 for p in chosen + avoid):
                    chosen.append(cand)
                    if len(chosen) == 2:
                        return chosen
        # Ultimate fallback
        while len(chosen) < 2:
            chosen.append(((len(chosen) * tile_size) % w, (len(chosen) * tile_size) % h))
        return chosen

    h_spots = _pick_pair(h_scores, y_shift=edge_width, x_shift=0, avoid=[])
    v_spots = _pick_pair(v_scores, y_shift=0, x_shift=edge_width, avoid=h_spots)
    return h_spots, v_spots


def select_middle_spots(
    tex_rgb: np.ndarray,
    tile_size: int,
    seed: int = 42,
    avoid_loud: bool = True,
) -> List[Tuple[int, int]]:
    """Pick 16 well-spread middle patch origins (x, y), favoring calm base material."""
    h, w = tex_rgb.shape[:2]
    rng = np.random.default_rng(seed)
    busy = _compute_busyness_map(tex_rgb)
    tile_scores = _box_sum_wrap(busy, tile_size, tile_size)

    # Pick the calmest candidate per stratified cell when avoid_loud=True so rocks/flowers don't repeat every 16 cells
    cutoff = np.percentile(tile_scores, 40 if avoid_loud else 100)
    spots: List[Tuple[int, int]] = []
    cell_w = max(1.0, w / 4.0)
    cell_h = max(1.0, h / 4.0)

    for idx in range(16):
        gx, gy = idx % 4, idx // 4
        x_start = int(gx * cell_w)
        y_start = int(gy * cell_h)
        best_cand: Optional[Tuple[int, int]] = None
        best_score = float("inf")
        n_samples = 48 if avoid_loud else 16
        for _ in range(n_samples):
            cx = (x_start + int(rng.integers(0, max(1, int(cell_w))))) % w
            cy = (y_start + int(rng.integers(0, max(1, int(cell_h))))) % h
            sc = float(tile_scores[cy, cx])
            if sc < best_score:
                best_score = sc
                best_cand = (cx, cy)
            if not avoid_loud and sc <= cutoff:
                break
        spots.append(best_cand if best_cand is not None else (x_start % w, y_start % h))

    return spots


def _min_error_cut_1d(strip_band: np.ndarray, middle_band: np.ndarray, max_depths: np.ndarray) -> np.ndarray:
    """
    Efros & Freeman 1D minimum-error boundary cut along width N.
    strip_band, middle_band: shape (E, N, 3) float32 where index 0 is the outer tile border.
    max_depths: shape (N,) int array with 1 <= max_depths[c] <= E-1.
    Returns cut_depth[c] in [1 .. max_depths[c]] such that rows [0 .. cut_depth[c]-1]
    come from strip_band and deeper rows come from middle_band.
    """
    e_max, width, _ = strip_band.shape
    diff2 = np.sum((strip_band - middle_band) ** 2, axis=2)  # (E, N)

    dp = np.full((e_max, width), np.inf, dtype=np.float64)
    back = np.zeros((e_max, width), dtype=np.int32)

    # Start at column 1 (column 0 and width-1 are tile corner columns)
    c0 = 1
    d0 = int(max_depths[c0])
    dp[1 : d0 + 1, c0] = diff2[1 : d0 + 1, c0]

    for c in range(2, width - 1):
        d_prev = int(max_depths[c - 1])
        d_curr = int(max_depths[c])
        for r in range(1, d_curr + 1):
            r_lo = max(1, r - 1)
            r_hi = min(d_prev, r + 1)
            prev_slice = dp[r_lo : r_hi + 1, c - 1]
            best_rel = int(np.argmin(prev_slice))
            best_prev_r = r_lo + best_rel
            dp[r, c] = diff2[r, c] + dp[best_prev_r, c - 1]
            back[r, c] = best_prev_r

    c_end = width - 2
    d_end = int(max_depths[c_end])
    cut = np.ones(width, dtype=np.int32)
    curr_r = 1 + int(np.argmin(dp[1 : d_end + 1, c_end]))
    for c in range(c_end, 0, -1):
        cut[c] = curr_r
        curr_r = int(back[curr_r, c])

    return cut


def build_wang_tile(
    tex_rgba: np.ndarray,
    tile_size: int,
    edge_width: int,
    h_spots: Sequence[Tuple[int, int]],
    v_spots: Sequence[Tuple[int, int]],
    middle_spot: Tuple[int, int],
    top: int,
    right: int,
    bottom: int,
    left: int,
    corner_mode: str = "h-priority",
) -> np.ndarray:
    """
    Build one T x T Wang tile from 4 edge strips and 1 middle patch using
    minimum-error boundary cuts inside each edge's diagonal triangle.
    """
    T = tile_size
    E = min(edge_width, T // 2)
    if E < 2:
        E = 2

    hx_t, hy_t = h_spots[top]
    hx_b, hy_b = h_spots[bottom]
    vx_l, vy_l = v_spots[left]
    vx_r, vy_r = v_spots[right]
    mx, my = middle_spot

    middle = sample_wrap(tex_rgba, mx, my, T, T)
    top_strip = sample_wrap(tex_rgba, hx_t, hy_t, T, E)
    bot_strip = sample_wrap(tex_rgba, hx_b, hy_b - E, T, E)
    left_strip = sample_wrap(tex_rgba, vx_l, vy_l, E, T)
    right_strip = sample_wrap(tex_rgba, vx_r - E, vy_r, E, T)

    out = middle.copy()
    m_rgb = middle[:, :, :3].astype(np.float32)

    # Max depth inside each edge's diagonal triangle at column/row i in [1..T-2]
    idx = np.arange(T)
    max_d = np.minimum(np.minimum(idx, T - 1 - idx), E - 1)
    max_d = np.maximum(max_d, 1)

    # 1. Top cut (rows 0..E-1 from top_strip)
    top_cut = _min_error_cut_1d(top_strip[:, :, :3].astype(np.float32), m_rgb[:E, :, :], max_d)
    for c in range(1, T - 1):
        out[: top_cut[c], c] = top_strip[: top_cut[c], c]

    # 2. Bottom cut (flip vertically so row 0 of band is tile's bottom border T-1)
    bot_band = bot_strip[::-1, :, :3].astype(np.float32)
    bot_mid = m_rgb[T - E : T, :, :][::-1, :, :]
    bot_cut = _min_error_cut_1d(bot_band, bot_mid, max_d)
    for c in range(1, T - 1):
        d = int(bot_cut[c])
        out[T - d : T, c] = bot_strip[E - d : E, c]

    # 3. Left cut (transpose so cols become rows in DP)
    left_band = np.transpose(left_strip[:, :, :3], (1, 0, 2)).astype(np.float32)
    left_mid = np.transpose(m_rgb[:, :E, :], (1, 0, 2))
    left_cut = _min_error_cut_1d(left_band, left_mid, max_d)
    for r in range(1, T - 1):
        out[r, : left_cut[r]] = left_strip[r, : left_cut[r]]

    # 4. Right cut (transpose + reverse column direction)
    right_band = np.transpose(right_strip[:, ::-1, :3], (1, 0, 2)).astype(np.float32)
    right_mid = np.transpose(m_rgb[:, T - E : T, :][:, ::-1, :], (1, 0, 2))
    right_cut = _min_error_cut_1d(right_band, right_mid, max_d)
    for r in range(1, T - 1):
        d = int(right_cut[r])
        out[r, T - d : T] = right_strip[r, E - d : E]

    # 5. Diagonal corners (0,0), (0,T-1), (T-1,0), (T-1,T-1)
    if corner_mode == "blend":
        out[0, 0] = ((top_strip[0, 0].astype(np.int32) + left_strip[0, 0].astype(np.int32)) // 2).astype(np.uint8)
        out[0, T - 1] = ((top_strip[0, T - 1].astype(np.int32) + right_strip[0, E - 1].astype(np.int32)) // 2).astype(np.uint8)
        out[T - 1, 0] = ((bot_strip[E - 1, 0].astype(np.int32) + left_strip[T - 1, 0].astype(np.int32)) // 2).astype(np.uint8)
        out[T - 1, T - 1] = ((bot_strip[E - 1, T - 1].astype(np.int32) + right_strip[T - 1, E - 1].astype(np.int32)) // 2).astype(np.uint8)
    else:
        # h-priority: horizontal strips own the 4 corner pixels, keeping top/bottom seams 100% exact
        out[0, 0] = top_strip[0, 0]
        out[0, T - 1] = top_strip[0, T - 1]
        out[T - 1, 0] = bot_strip[E - 1, 0]
        out[T - 1, T - 1] = bot_strip[E - 1, T - 1]

    return out


def cut_wang_atlas(
    tex_img: Image.Image,
    tile_size: int = 32,
    edge_width: Optional[int] = None,
    seed: int = 42,
    h_spots: Optional[List[Tuple[int, int]]] = None,
    v_spots: Optional[List[Tuple[int, int]]] = None,
    avoid_loud_middles: bool = True,
    corner_mode: str = "h-priority",
) -> Tuple[Image.Image, Dict[str, Any]]:
    """Cut a 4x4 index-ordered Wang atlas from a seamless texture."""
    rgba = tex_img.convert("RGBA")
    tex_arr = np.array(rgba)
    tex_rgb = tex_arr[:, :, :3]
    if edge_width is None:
        edge_width = max(4, tile_size // 4)

    auto_h, auto_v = select_plain_edge_spots(tex_rgb, tile_size, edge_width)
    chosen_h = h_spots if h_spots is not None else auto_h
    chosen_v = v_spots if v_spots is not None else auto_v
    m_spots = select_middle_spots(tex_rgb, tile_size, seed=seed, avoid_loud=avoid_loud_middles)

    atlas = np.zeros((4 * tile_size, 4 * tile_size, 4), dtype=np.uint8)
    for idx in range(16):
        t, r, b, l = decode_wang_index(idx)
        tile = build_wang_tile(
            tex_arr,
            tile_size=tile_size,
            edge_width=edge_width,
            h_spots=chosen_h,
            v_spots=chosen_v,
            middle_spot=m_spots[idx],
            top=t,
            right=r,
            bottom=b,
            left=l,
            corner_mode=corner_mode,
        )
        col, row = atlas_coords(idx)
        atlas[row * tile_size : (row + 1) * tile_size, col * tile_size : (col + 1) * tile_size] = tile

    atlas_img = Image.fromarray(atlas, mode="RGBA")
    info = {
        "tile_size": tile_size,
        "edge_width": edge_width,
        "atlas_size": [4 * tile_size, 4 * tile_size],
        "source_size": [rgba.width, rgba.height],
        "h_spots": [list(p) for p in chosen_h],
        "v_spots": [list(p) for p in chosen_v],
        "middle_spots": [list(p) for p in m_spots],
        "corner_mode": corner_mode,
    }
    return atlas_img, info


# ---------------------------------------------------------------------------
# Atlas Verification & Rendering Overlays
# ---------------------------------------------------------------------------

def verify_wang_atlas(atlas_img: Image.Image, tile_size: Optional[int] = None) -> Dict[str, Any]:
    """
    Audit a 4x4 index-ordered Wang atlas:
      - Confirms 4x4 square tile geometry
      - Measures seam MAE across all 64 valid H joins and 64 valid V joins
      - Compares against mismatched joins to confirm edge matching
      - Checks edge pixel variance for potential repeating grid artifacts
    """
    rgba = atlas_img.convert("RGBA")
    arr = np.array(rgba)
    h_px, w_px = arr.shape[:2]

    if tile_size is None:
        if w_px != h_px or w_px % 4 != 0:
            raise ValueError(f"Atlas {w_px}x{h_px} is not a 4x4 square grid; pass --tile-size.")
        tile_size = w_px // 4

    expected = 4 * tile_size
    if w_px != expected or h_px != expected:
        return {
            "ok": False,
            "error": f"Expected {expected}x{expected} for tile_size={tile_size}, got {w_px}x{h_px}.",
        }

    tiles: List[np.ndarray] = []
    for idx in range(16):
        col, row = atlas_coords(idx)
        tiles.append(arr[row * tile_size : (row + 1) * tile_size, col * tile_size : (col + 1) * tile_size, :3].astype(np.float32))

    # Measure border continuity along inner pixels [1:-1] (and full [:] for H)
    matched_v_err: List[float] = []
    mismatched_v_err: List[float] = []
    matched_h_err: List[float] = []
    mismatched_h_err: List[float] = []

    for i in range(16):
        _, r_i, b_i, _ = decode_wang_index(i)
        for j in range(16):
            t_j, _, _, l_j = decode_wang_index(j)
            # Vertical seam: tile i on left, tile j on right
            v_diff = float(np.mean(np.abs(tiles[i][1:-1, -1] - tiles[j][1:-1, 0])))
            if r_i == l_j:
                matched_v_err.append(v_diff)
            else:
                mismatched_v_err.append(v_diff)
            # Horizontal seam: tile i on top, tile j on bottom
            h_diff = float(np.mean(np.abs(tiles[i][-1, 1:-1] - tiles[j][0, 1:-1])))
            if b_i == t_j:
                matched_h_err.append(h_diff)
            else:
                mismatched_h_err.append(h_diff)

    # Check per-channel spatial border std deviation to warn on overly noisy/floral edges
    edge_stds: List[float] = []
    for idx in range(16):
        t = tiles[idx]
        edge_stds.extend([
            float(np.mean(np.std(t[0, :], axis=0))),
            float(np.mean(np.std(t[-1, :], axis=0))),
            float(np.mean(np.std(t[:, 0], axis=0))),
            float(np.mean(np.std(t[:, -1], axis=0))),
        ])

    return {
        "ok": True,
        "tile_size": tile_size,
        "atlas_size": [w_px, h_px],
        "matched_h_seam_mae": round(float(np.mean(matched_h_err)), 3),
        "matched_v_seam_mae": round(float(np.mean(matched_v_err)), 3),
        "mismatched_h_seam_mae": round(float(np.mean(mismatched_h_err)), 3),
        "mismatched_v_seam_mae": round(float(np.mean(mismatched_v_err)), 3),
        "edge_channel_std_mean": round(float(np.mean(edge_stds)), 3),
        "edge_channel_std_max": round(float(np.max(edge_stds)), 3),
    }


def _draw_tile_edge_bars(canvas: np.ndarray, y0: int, x0: int, tile_size: int, idx: int, bar_thickness: int = 2) -> None:
    """Draw orange (0) / blue (1) edge bars on the 4 edges of one tile."""
    t, r, b, l = decode_wang_index(idx)
    c_t = COLOR_ONE_RGB if t else COLOR_ZERO_RGB
    c_r = COLOR_ONE_RGB if r else COLOR_ZERO_RGB
    c_b = COLOR_ONE_RGB if b else COLOR_ZERO_RGB
    c_l = COLOR_ONE_RGB if l else COLOR_ZERO_RGB

    m = max(3, tile_size // 5)
    bt = min(bar_thickness, max(1, tile_size // 8))
    canvas[y0 : y0 + bt, x0 + m : x0 + tile_size - m] = c_t
    canvas[y0 + tile_size - bt : y0 + tile_size, x0 + m : x0 + tile_size - m] = c_b
    canvas[y0 + m : y0 + tile_size - m, x0 : x0 + bt] = c_l
    canvas[y0 + m : y0 + tile_size - m, x0 + tile_size - bt : x0 + tile_size] = c_r


def render_debug_atlas(atlas_img: Image.Image, tile_size: int) -> Image.Image:
    """Return a copy of the 4x4 atlas annotated with orange (0) / blue (1) edge bars and indices."""
    arr = np.array(atlas_img.convert("RGBA"))
    for idx in range(16):
        col, row = atlas_coords(idx)
        _draw_tile_edge_bars(arr, row * tile_size, col * tile_size, tile_size, idx)
    out = Image.fromarray(arr, mode="RGBA")
    draw = ImageDraw.Draw(out)
    for idx in range(16):
        col, row = atlas_coords(idx)
        x0, y0 = col * tile_size, row * tile_size
        draw.text((x0 + 4, y0 + 4), str(idx), fill=(255, 255, 255, 230))
    return out


def render_map_image(
    atlas_img: Image.Image,
    grid: Sequence[Sequence[int]],
    tile_size: int,
    debug_overlay: bool = False,
) -> Image.Image:
    """Render a Wang tile index grid into a single RGBA image."""
    atlas_arr = np.array(atlas_img.convert("RGBA"))
    rows = len(grid)
    cols = len(grid[0]) if rows > 0 else 0
    canvas = np.zeros((rows * tile_size, cols * tile_size, 4), dtype=np.uint8)

    for r in range(rows):
        for c in range(cols):
            idx = int(grid[r][c])
            acol, arow = atlas_coords(idx)
            tile = atlas_arr[
                arow * tile_size : (arow + 1) * tile_size,
                acol * tile_size : (acol + 1) * tile_size,
            ]
            y0, x0 = r * tile_size, c * tile_size
            canvas[y0 : y0 + tile_size, x0 : x0 + tile_size] = tile
            if debug_overlay:
                _draw_tile_edge_bars(canvas, y0, x0, tile_size, idx)

    return Image.fromarray(canvas, mode="RGBA")


# ---------------------------------------------------------------------------
# Engine Integration Snippets
# ---------------------------------------------------------------------------

SNIPPETS: Dict[str, str] = {
    "godot4": """# Godot 4.x TileMapLayer — Edge Wang Tiles (Stateless Chunk Hash + Finite Mode)
extends Node2D

@export var ground_layer: TileMapLayer
@export var source_id: int = 0
@export var world_seed: int = 42

static func _mix64(x: int) -> int:
\tx = (x + 0x9E3779B97F4A7C15)
\tx = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9
\tx = (x ^ (x >> 27)) * 0x94D049BB133111EB
\treturn x ^ (x >> 31)

func edge_color(edge_x: int, edge_y: int, axis: int) -> int:
\tvar h: int = _mix64(world_seed)
\th = _mix64(h ^ (edge_x * 0xD6E8FEB86659FD93))
\th = _mix64(h ^ (edge_y * 0xA5A3564E27F8862D))
\th = _mix64(h ^ (axis * 0x9E3779B97F4A7C15))
\treturn (h >> 63) & 1

func wang_tile_at(col: int, row: int) -> int:
\tvar top := edge_color(col, row, 0)
\tvar bottom := edge_color(col, row + 1, 0)
\tvar left := edge_color(col, row, 1)
\tvar right := edge_color(col + 1, row, 1)
\treturn top + 2 * right + 4 * bottom + 8 * left

func paint_rect(start_col: int, start_row: int, cols: int, rows: int) -> void:
\tfor row in range(start_row, start_row + rows):
\t\tfor col in range(start_col, start_col + cols):
\t\t\tvar tile := wang_tile_at(col, row)
\t\t\tground_layer.set_cell(Vector2i(col, row), source_id, Vector2i(tile % 4, tile / 4))
""",
    "unity": """// Unity Tilemap — Edge Wang Tiles (Note: Unity Y points up -> row maps to -row)
using UnityEngine;
using UnityEngine.Tilemaps;

public class WangTileGround : MonoBehaviour
{
    public Tilemap tilemap;
    public TileBase[] wangTiles; // 16 tiles in index order: top + 2*right + 4*bottom + 8*left
    public ulong worldSeed = 42UL;

    private static ulong Mix64(ulong x)
    {
        x += 0x9E3779B97F4A7C15UL;
        x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9UL;
        x = (x ^ (x >> 27)) * 0x94D049BB133111EBUL;
        return x ^ (x >> 31);
    }

    private int EdgeColor(int edgeX, int edgeY, int axis)
    {
        ulong h = Mix64(worldSeed);
        h = Mix64(h ^ (unchecked((ulong)(long)edgeX) * 0xD6E8FEB86659FD93UL));
        h = Mix64(h ^ (unchecked((ulong)(long)edgeY) * 0xA5A3564E27F8862DUL));
        h = Mix64(h ^ ((ulong)axis * 0x9E3779B97F4A7C15UL));
        return (int)((h >> 63) & 1UL);
    }

    public int WangTileAt(int row, int col)
    {
        int top = EdgeColor(col, row, 0);
        int bottom = EdgeColor(col, row + 1, 0);
        int left = EdgeColor(col, row, 1);
        int right = EdgeColor(col + 1, row, 1);
        return top + 2 * right + 4 * bottom + 8 * left;
    }

    public void PaintChunk(int startRow, int startCol, int rows, int cols)
    {
        for (int r = startRow; r < startRow + rows; r++)
        {
            for (int c = startCol; c < startCol + cols; c++)
            {
                int tile = WangTileAt(r, c);
                tilemap.SetTile(new Vector3Int(c, -r, 0), wangTiles[tile]);
            }
        }
    }
}
""",
    "typescript": """// TypeScript / Phaser / Web 2D — Edge Wang Tiles (Stateless BigInt SplitMix64 Hash)
const MASK64 = 0xFFFFFFFFFFFFFFFFn;

function mix64(x: bigint): bigint {
  x = (x + 0x9E3779B97F4A7C15n) & MASK64;
  x = ((x ^ (x >> 30n)) * 0xBF58476D1CE4E5B9n) & MASK64;
  x = ((x ^ (x >> 27n)) * 0x94D049BB133111EBn) & MASK64;
  return (x ^ (x >> 31n)) & MASK64;
}

export function edgeColor(seed: number, edgeX: number, edgeY: number, axis: 0 | 1): 0 | 1 {
  let h = mix64(BigInt(seed) & MASK64);
  h = mix64(h ^ ((BigInt.asUintN(64, BigInt(edgeX)) * 0xD6E8FEB86659FD93n) & MASK64));
  h = mix64(h ^ ((BigInt.asUintN(64, BigInt(edgeY)) * 0xA5A3564E27F8862Dn) & MASK64));
  h = mix64(h ^ ((BigInt(axis) * 0x9E3779B97F4A7C15n) & MASK64));
  return Number((h >> 63n) & 1n) as 0 | 1;
}

export function wangTileAt(seed: number, row: number, col: number): number {
  const top = edgeColor(seed, col, row, 0);
  const bottom = edgeColor(seed, col, row + 1, 0);
  const left = edgeColor(seed, col, row, 1);
  const right = edgeColor(seed, col + 1, row, 1);
  return top + 2 * right + 4 * bottom + 8 * left; // 0..15; col = idx % 4, row = Math.floor(idx / 4)
}
""",
    "python": """# Python — Finite, Looping, and Chunked Edge Wang Tiles
def wang_index(top: int, right: int, bottom: int, left: int) -> int:
    return top + 2 * right + 4 * bottom + 8 * left

def mix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    return (x ^ (x >> 31)) & 0xFFFFFFFFFFFFFFFF

def edge_color(seed: int, edge_x: int, edge_y: int, axis: int) -> int:
    h = mix64(seed)
    h = mix64(h ^ ((edge_x * 0xD6E8FEB86659FD93) & 0xFFFFFFFFFFFFFFFF))
    h = mix64(h ^ ((edge_y * 0xA5A3564E27F8862D) & 0xFFFFFFFFFFFFFFFF))
    h = mix64(h ^ ((axis * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF))
    return (h >> 63) & 1

def wang_tile_at(seed: int, row: int, col: int) -> int:
    return wang_index(
        top=edge_color(seed, col, row, 0),
        right=edge_color(seed, col + 1, row, 1),
        bottom=edge_color(seed, col, row + 1, 0),
        left=edge_color(seed, col, row, 1),
    )
""",
    "love2d": """-- LÖVE (Love2D) — Edge Wang Tiles (4x4 index-ordered atlas, Y points down)
local function wangTile(hEdges, vEdges, r, c)
    local top    = hEdges[r][c]
    local bottom = hEdges[r + 1][c]
    local left   = vEdges[r][c]
    local right  = vEdges[r][c + 1]
    return top + 2 * right + 4 * bottom + 8 * left
end

local function drawWangCell(atlas, quads, hEdges, vEdges, r, c, tileSize)
    local idx = wangTile(hEdges, vEdges, r, c)
    -- Prebuild quads[0..15] with col = idx % 4, row = math.floor(idx / 4)
    love.graphics.draw(atlas, quads[idx], (c - 1) * tileSize, (r - 1) * tileSize)
end
""",
}


# ---------------------------------------------------------------------------
# CLI Argument Parsing
# ---------------------------------------------------------------------------

def _parse_spots(spec: str) -> List[Tuple[int, int]]:
    parts = [p.strip() for p in spec.split(";") if p.strip()]
    if len(parts) != 2:
        raise ValueError(f"Expected exactly 2 semicolon-separated x,y coordinates, got: {spec!r}")
    out: List[Tuple[int, int]] = []
    for p in parts:
        xs, ys = p.split(",")
        out.append((int(xs.strip()), int(ys.strip())))
    return out


def _cmd_cut(args: argparse.Namespace) -> int:
    if args.demo:
        tex_img = generate_demo_meadow(seed=args.seed)
    elif args.input:
        tex_img = Image.open(args.input)
    else:
        raise ValueError("Provide an input texture path or pass --demo.")

    h_spots = _parse_spots(args.h_spots) if args.h_spots else None
    v_spots = _parse_spots(args.v_spots) if args.v_spots else None

    atlas_img, info = cut_wang_atlas(
        tex_img,
        tile_size=args.tile_size,
        edge_width=args.edge_width,
        seed=args.seed,
        h_spots=h_spots,
        v_spots=v_spots,
        avoid_loud_middles=not args.allow_loud_middles,
        corner_mode=args.corner_mode,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    atlas_img.save(out_path)
    info["atlas_path"] = str(out_path)

    if args.save_source:
        src_path = Path(args.save_source)
        src_path.parent.mkdir(parents=True, exist_ok=True)
        tex_img.save(src_path)
        info["source_path"] = str(src_path)

    if args.debug_atlas:
        dbg_path = Path(args.debug_atlas)
        dbg_path.parent.mkdir(parents=True, exist_ok=True)
        render_debug_atlas(atlas_img, args.tile_size).save(dbg_path)
        info["debug_atlas_path"] = str(dbg_path)

    if args.preview_map:
        c_str, r_str = args.preview_map.lower().split("x")
        p_cols, p_rows = int(c_str), int(r_str)
        grid, _, _ = generate_wang_grid(p_rows, p_cols, seed=args.seed, mode="chunked")
        map_check = verify_wang_grid(grid, looping=False)
        info["preview_map_check"] = {
            "rows": p_rows,
            "cols": p_cols,
            "invariant_ok": map_check["invariant_ok"],
        }
        prev_path = Path(args.preview_out) if args.preview_out else out_path.with_name(f"{out_path.stem}_preview_{p_cols}x{p_rows}.png")
        prev_path.parent.mkdir(parents=True, exist_ok=True)
        render_map_image(atlas_img, grid, args.tile_size, debug_overlay=False).save(prev_path)
        info["preview_map_path"] = str(prev_path)

        if args.debug_map:
            dmap_path = Path(args.debug_map)
            dmap_path.parent.mkdir(parents=True, exist_ok=True)
            render_map_image(atlas_img, grid, args.tile_size, debug_overlay=True).save(dmap_path)
            info["debug_map_path"] = str(dmap_path)

    info["seam_verification"] = verify_wang_atlas(atlas_img, tile_size=args.tile_size)

    if args.json:
        print(json.dumps(info, indent=2))
    else:
        sv = info["seam_verification"]
        print(f"Saved 4x4 Wang atlas ({info['atlas_size'][0]}x{info['atlas_size'][1]}) -> {out_path}")
        print(f"H spots: {info['h_spots']} | V spots: {info['v_spots']}")
        print(
            f"Seam MAE (matched vs mismatched): "
            f"H={sv['matched_h_seam_mae']} vs {sv['mismatched_h_seam_mae']}, "
            f"V={sv['matched_v_seam_mae']} vs {sv['mismatched_v_seam_mae']}"
        )
    return 0


def _cmd_map(args: argparse.Namespace) -> int:
    grid, _, _ = generate_wang_grid(
        rows=args.rows,
        cols=args.cols,
        seed=args.seed,
        mode=args.mode,
        chunk_x=args.chunk_x,
        chunk_y=args.chunk_y,
    )
    check = verify_wang_grid(grid, looping=(args.mode == "looping"))
    payload: Dict[str, Any] = {
        "mode": args.mode,
        "seed": args.seed,
        "rows": args.rows,
        "cols": args.cols,
        "chunk": [args.chunk_x, args.chunk_y] if args.mode == "chunked" else None,
        "verification": check,
    }

    if args.atlas:
        atlas_img = Image.open(args.atlas)
        tile_size = args.tile_size or (atlas_img.width // 4)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        render_map_image(atlas_img, grid, tile_size, debug_overlay=False).save(out_path)
        payload["render_path"] = str(out_path)
        if args.debug_overlay:
            dbg_path = Path(args.debug_overlay)
            dbg_path.parent.mkdir(parents=True, exist_ok=True)
            render_map_image(atlas_img, grid, tile_size, debug_overlay=True).save(dbg_path)
            payload["debug_overlay_path"] = str(dbg_path)

    if args.grid_out:
        gpath = Path(args.grid_out)
        gpath.parent.mkdir(parents=True, exist_ok=True)
        gpath.write_text(json.dumps({"mode": args.mode, "seed": args.seed, "tile_indices": grid}, indent=2), encoding="utf-8")
        payload["grid_path"] = str(gpath)

    if args.include_grid or (not args.atlas and not args.grid_out):
        payload["tile_indices"] = grid

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Generated {args.rows}x{args.cols} {args.mode} Wang map (seed={args.seed}) | invariant_ok={check['invariant_ok']}")
        if "render_path" in payload:
            print(f"Rendered preview -> {payload['render_path']}")
    return 0 if check["invariant_ok"] else 1


def run_selftest() -> Dict[str, Any]:
    """
    Self-test finite, looping, and chunked Wang edge placement invariants:
      1. Finite 24x24 grid neighbor agreement + seed determinism.
      2. Looping 20x20 grid toroidal wrap-around neighbor agreement.
      3. Two adjacent 16x16 chunks (chunk (0,0) and (1,0), plus (0,1)) agree on every shared border edge.
      4. All 16 tile indices (0..15) decode/encode cleanly and map to 4x4 atlas coordinates.
    """
    g1, _, _ = generate_wang_grid(24, 24, seed=42, mode="finite")
    g1_rep, _, _ = generate_wang_grid(24, 24, seed=42, mode="finite")
    finite_res = verify_wang_grid(g1, looping=False)
    deterministic_ok = (g1 == g1_rep)

    g_loop, _, _ = generate_wang_grid(20, 20, seed=7, mode="looping")
    loop_res = verify_wang_grid(g_loop, looping=True)

    c00, _, _ = generate_wang_grid(16, 16, seed=99, mode="chunked", chunk_x=0, chunk_y=0)
    c10, _, _ = generate_wang_grid(16, 16, seed=99, mode="chunked", chunk_x=1, chunk_y=0)
    c01, _, _ = generate_wang_grid(16, 16, seed=99, mode="chunked", chunk_x=0, chunk_y=1)
    h_stitch = [c00[r] + c10[r] for r in range(16)]
    v_stitch = c00 + c01
    chunk_h_res = verify_wang_grid(h_stitch, looping=False)
    chunk_v_res = verify_wang_grid(v_stitch, looping=False)

    codec_ok = all(
        wang_index(*decode_wang_index(i)) == i and atlas_coords(i) == (i % 4, i // 4)
        for i in range(16)
    )

    checks = {
        "finite_24x24_invariant": {"ok": finite_res["invariant_ok"], "mismatch_count": finite_res["mismatch_count"]},
        "seed_determinism": {"ok": deterministic_ok},
        "looping_20x20_wrap_invariant": {"ok": loop_res["invariant_ok"], "mismatch_count": loop_res["mismatch_count"]},
        "chunked_horizontal_seam": {"ok": chunk_h_res["invariant_ok"], "mismatch_count": chunk_h_res["mismatch_count"]},
        "chunked_vertical_seam": {"ok": chunk_v_res["invariant_ok"], "mismatch_count": chunk_v_res["mismatch_count"]},
        "index_codec_and_4x4_coords": {"ok": codec_ok},
    }
    return {"ok": all(bool(v["ok"]) for v in checks.values()), "checks": checks}


def _cmd_verify(args: argparse.Namespace) -> int:
    result: Dict[str, Any] = {}
    ok = True

    if args.selftest:
        st = run_selftest()
        result["selftest"] = st
        ok = ok and bool(st["ok"])

    if args.atlas:
        atlas_img = Image.open(args.atlas)
        atlas_res = verify_wang_atlas(atlas_img, tile_size=args.tile_size)
        result["atlas"] = atlas_res
        ok = ok and bool(atlas_res.get("ok"))

    if args.map:
        raw = json.loads(Path(args.map).read_text(encoding="utf-8"))
        grid = raw["tile_indices"] if isinstance(raw, dict) and "tile_indices" in raw else raw
        map_res = verify_wang_grid(grid, looping=args.looping)
        result["map"] = map_res
        ok = ok and bool(map_res.get("invariant_ok"))

    if not result:
        raise ValueError("Provide --selftest, --atlas, and/or --map to verify.")

    result["ok"] = ok
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result, indent=2))
    return 0 if ok else 1


def _cmd_snippet(args: argparse.Namespace) -> int:
    code = SNIPPETS[args.engine]
    if args.json:
        print(json.dumps({"engine": args.engine, "code": code}, indent=2))
    else:
        print(code)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Edge Wang Tiles pipeline: cut 16-tile atlases, generate/verify maps, and export engine snippets."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # cut
    p_cut = sub.add_parser("cut", help="Cut a 4x4 Wang atlas from a seamless terrain texture.")
    p_cut.add_argument("input", nargs="?", help="Path to seamless input texture PNG.")
    p_cut.add_argument("--demo", action="store_true", help="Synthesize a 280x298 pixel-art meadow texture to demo.")
    p_cut.add_argument("-o", "--output", default="exports/wang_tiles/wang_atlas.png", help="Output 4x4 atlas PNG path.")
    p_cut.add_argument("--tile-size", type=int, default=32, help="Tile width/height in pixels (default: 32).")
    p_cut.add_argument("--edge-width", type=int, default=None, help="Edge strip overlap width (default: tile_size // 4).")
    p_cut.add_argument("--seed", type=int, default=42, help="Seed for middle sampling and preview map.")
    p_cut.add_argument("--h-spots", help="Optional explicit H edge spots 'x0,y0;x1,y1'.")
    p_cut.add_argument("--v-spots", help="Optional explicit V edge spots 'x0,y0;x1,y1'.")
    p_cut.add_argument("--allow-loud-middles", action="store_true", help="Allow noisy/flower middles instead of filtering to calm base.")
    p_cut.add_argument("--corner-mode", choices=["h-priority", "blend"], default="h-priority", help="Corner pixel strategy.")
    p_cut.add_argument("--save-source", help="Optional path to save the input/demo source texture.")
    p_cut.add_argument("--debug-atlas", help="Optional path to save atlas with orange/blue edge bars & indices.")
    p_cut.add_argument("--preview-map", help="Render a COLSxROWS zoom-out check map, e.g. '20x20'.")
    p_cut.add_argument("--preview-out", help="Output path for preview map PNG.")
    p_cut.add_argument("--debug-map", help="Optional path to save preview map with orange/blue edge bars.")
    p_cut.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_cut.set_defaults(func=_cmd_cut)

    # map
    p_map = sub.add_parser("map", help="Generate and verify a deterministic Wang tile grid/preview.")
    p_map.add_argument("--rows", type=int, default=20, help="Number of map rows (default: 20).")
    p_map.add_argument("--cols", type=int, default=20, help="Number of map columns (default: 20).")
    p_map.add_argument("--seed", type=int, default=42, help="World seed.")
    p_map.add_argument("--mode", choices=["finite", "looping", "chunked"], default="chunked", help="Edge generation mode.")
    p_map.add_argument("--chunk-x", type=int, default=0, help="Chunk X coordinate (chunked mode).")
    p_map.add_argument("--chunk-y", type=int, default=0, help="Chunk Y coordinate (chunked mode).")
    p_map.add_argument("--atlas", help="Optional 4x4 Wang atlas PNG to render the map preview.")
    p_map.add_argument("--tile-size", type=int, default=None, help="Tile size (auto-detected from atlas width / 4).")
    p_map.add_argument("-o", "--output", default="exports/wang_tiles/wang_map_preview.png", help="Rendered map PNG path.")
    p_map.add_argument("--debug-overlay", help="Optional path to save map with orange/blue edge bars.")
    p_map.add_argument("--grid-out", help="Optional path to write tile_indices JSON.")
    p_map.add_argument("--include-grid", action="store_true", help="Include 2D tile_indices in stdout JSON.")
    p_map.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_map.set_defaults(func=_cmd_map)

    # verify
    p_ver = sub.add_parser("verify", help="Verify a 4x4 Wang atlas, generated tile_indices map, and/or math self-test.")
    p_ver.add_argument("--selftest", action="store_true", help="Run built-in finite/looping/chunked/determinism self-test.")
    p_ver.add_argument("--atlas", help="Path to 4x4 Wang atlas PNG.")
    p_ver.add_argument("--tile-size", type=int, default=None, help="Expected tile size in pixels.")
    p_ver.add_argument("--map", help="Path to JSON file containing tile_indices.")
    p_ver.add_argument("--looping", action="store_true", help="Check toroidal wrap-around edges on map.")
    p_ver.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_ver.set_defaults(func=_cmd_verify)

    # snippet
    p_snip = sub.add_parser("snippet", help="Print drop-in Wang tile placement + chunk hash code.")
    p_snip.add_argument("--engine", choices=sorted(SNIPPETS.keys()), required=True, help="Target engine/language.")
    p_snip.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_snip.set_defaults(func=_cmd_snippet)

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
