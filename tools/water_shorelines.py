#!/usr/bin/env python3
"""
2D Water Shoreline Distance Field Tool (water_shorelines.py)
Bakes per-pixel Euclidean distance fields from 2D land layers, applies smooth
wobble noise, renders animated 6-color shoreline water (depth bands, breathing
foam, incoming wave rings), supports incremental dirty-region & chunked bakes,
runs automated pixel-grid/EDT verification tests, and exports Godot 4 / Unity /
TypeScript code.
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

try:
    from scipy import ndimage as _scipy_ndimage
    HAS_SCIPY = True
except ImportError:
    _scipy_ndimage = None
    HAS_SCIPY = False

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEFAULT_PALETTE: Dict[str, str] = {
    "deep": "#1C4A80",
    "mid": "#226296",
    "shallow": "#348CB0",
    "shoal": "#60BEC4",
    "wave": "#96D6DA",
    "foam": "#ECF6F4",
}


def hex_to_rgba(hex_str: str) -> Tuple[int, int, int, int]:
    s = hex_str.strip().lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
    if len(s) == 8:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    raise ValueError(f"Invalid hex color: {hex_str!r}")


# ---------------------------------------------------------------------------
# Exact 2D Euclidean Distance Transform (Felzenszwalb & Huttenlocher + SciPy)
# ---------------------------------------------------------------------------

def _fh_pass_1d(f: np.ndarray) -> np.ndarray:
    """
    Exact 1D squared distance transform over a 1D float64 array (Felzenszwalb & Huttenlocher).
    """
    n = f.shape[0]
    if n == 0:
        return f.copy()
    v = np.zeros(n, dtype=np.int32)
    z = np.empty(n + 1, dtype=np.float64)
    k = 0
    v[0] = 0
    z[0] = -np.inf
    z[1] = np.inf

    for q in range(1, n):
        fq_qq = float(f[q]) + q * q
        while True:
            p = int(v[k])
            s = (fq_qq - (float(f[p]) + p * p)) / (2.0 * (q - p))
            if s > z[k]:
                break
            k -= 1
        k += 1
        v[k] = q
        z[k] = s
        z[k + 1] = np.inf

    out = np.empty(n, dtype=np.float64)
    k = 0
    for q in range(n):
        while z[k + 1] < q:
            k += 1
        dq = q - int(v[k])
        out[q] = dq * dq + float(f[v[k]])
    return out


def distance_to_land_fh(land_mask: np.ndarray) -> np.ndarray:
    """
    Pure-NumPy Felzenszwalb & Huttenlocher 2D Euclidean distance transform.
    Returns float64 distance in pixels from every pixel to nearest True pixel in land_mask.
    """
    h, w = land_mask.shape
    d = np.where(land_mask, 0.0, 1e20).astype(np.float64)
    for x in range(w):
        d[:, x] = _fh_pass_1d(d[:, x])
    for y in range(h):
        d[y, :] = _fh_pass_1d(d[y, :])
    return np.sqrt(d)


def distance_to_land(land_mask: np.ndarray, force_fh: bool = False) -> np.ndarray:
    """
    Compute exact Euclidean distance in px to nearest land pixel (land_mask == True).
    Uses scipy.ndimage.distance_transform_edt when available unless force_fh=True.
    """
    mask = np.asarray(land_mask, dtype=bool)
    if HAS_SCIPY and not force_fh:
        return _scipy_ndimage.distance_transform_edt(~mask).astype(np.float64)
    return distance_to_land_fh(mask)


# ---------------------------------------------------------------------------
# Smooth Wobble Noise (Global Gaussian + World-Space Deterministic Value Noise)
# ---------------------------------------------------------------------------

def _gaussian_wobble(shape: Tuple[int, int], sigma: float, target_std: float, seed: int) -> np.ndarray:
    """Smooth static wobble from Gaussian-blurred white noise rescaled to target_std."""
    rng = np.random.default_rng(seed)
    white = rng.random(shape, dtype=np.float64)
    if HAS_SCIPY:
        smooth = _scipy_ndimage.gaussian_filter(white, sigma=sigma)
    else:
        # Separable 1D Gaussian kernel fallback
        radius = max(1, int(math.ceil(3.0 * sigma)))
        xs = np.arange(-radius, radius + 1, dtype=np.float64)
        kernel = np.exp(-0.5 * (xs / max(sigma, 1e-6)) ** 2)
        kernel /= kernel.sum()
        pad_y = np.pad(white, ((radius, radius), (0, 0)), mode="reflect")
        tmp = np.apply_along_axis(lambda col: np.convolve(col, kernel, mode="valid"), 0, pad_y)
        pad_x = np.pad(tmp, ((0, 0), (radius, radius)), mode="reflect")
        smooth = np.apply_along_axis(lambda row: np.convolve(row, kernel, mode="valid"), 1, pad_x)

    s_std = float(smooth.std())
    if s_std < 1e-9:
        return np.zeros(shape, dtype=np.float64)
    return (smooth - float(smooth.mean())) / s_std * target_std


def _hash_grid_2d(ix: np.ndarray, iy: np.ndarray, seed: int) -> np.ndarray:
    """Deterministic vectorized float in [-1, 1] at integer lattice points (ix, iy)."""
    x = ix.astype(np.int64) * 374761393 + iy.astype(np.int64) * 668265263 + int(seed) * 1442695041
    x = (x ^ (x >> 13)) * 1274126177
    x = x ^ (x >> 16)
    return ((x & 0xFFFFFF).astype(np.float64) / 8388607.5) - 1.0


def world_space_wobble(
    height: int,
    width: int,
    offset_x: int = 0,
    offset_y: int = 0,
    frequency: float = 0.03,
    amplitude: float = 4.0,
    seed: int = 1,
) -> np.ndarray:
    """
    Deterministic world-space smooth value noise (matches Godot FastNoiseLite concept:
    no fractal, low frequency ~0.03, scaled by amplitude ~4.0 -> ~+-3 px wobble).
    Chunk borders and partial-region rebakes evaluate identically at identical world coords.
    """
    wy = (np.arange(height, dtype=np.float64) + offset_y)[:, None] * frequency
    wx = (np.arange(width, dtype=np.float64) + offset_x)[None, :] * frequency

    x0 = np.floor(wx).astype(np.int64)
    y0 = np.floor(wy).astype(np.int64)
    fx = wx - x0
    fy = wy - y0

    # Quintic smoothstep for C2 continuity
    ux = fx * fx * fx * (fx * (fx * 6.0 - 15.0) + 10.0)
    uy = fy * fy * fy * (fy * (fy * 6.0 - 15.0) + 10.0)

    v00 = _hash_grid_2d(x0, y0, seed)
    v10 = _hash_grid_2d(x0 + 1, y0, seed)
    v01 = _hash_grid_2d(x0, y0 + 1, seed)
    v11 = _hash_grid_2d(x0 + 1, y0 + 1, seed)

    nx0 = v00 + (v10 - v00) * ux
    nx1 = v01 + (v11 - v01) * ux
    return (nx0 + (nx1 - nx0) * uy) * amplitude


# ---------------------------------------------------------------------------
# Baking, Incremental Dirty-Window Update, Demo Island & Contour Preview
# ---------------------------------------------------------------------------

def extract_land_mask(
    land_img: Image.Image,
    mask_mode: str = "alpha",
    key_color: Optional[str] = None,
    key_tolerance: int = 12,
) -> np.ndarray:
    """Extract boolean land mask (True = land, False = water) at art pixel resolution."""
    rgba = np.array(land_img.convert("RGBA"))
    if mask_mode == "alpha":
        return rgba[:, :, 3] > 0
    if mask_mode == "luma":
        rgb = rgba[:, :, :3].astype(np.float32)
        luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        return luma > 127.0
    if mask_mode == "chroma":
        if not key_color:
            raise ValueError("--key-color is required when --mask-mode chroma is used.")
        kr, kg, kb, _ = hex_to_rgba(key_color)
        diff = np.abs(rgba[:, :, :3].astype(np.int32) - np.array([kr, kg, kb], dtype=np.int32)).max(axis=2)
        return (rgba[:, :, 3] > 0) & (diff > key_tolerance)
    raise ValueError(f"Unsupported mask_mode: {mask_mode}")


def bake_distance_map(
    land_mask: np.ndarray,
    max_dist: float = 32.0,
    wobble_mode: str = "gaussian",
    wobble_sigma: float = 8.0,
    wobble_std: float = 2.0,
    world_offset: Tuple[int, int] = (0, 0),
    noise_freq: float = 0.03,
    noise_amp: float = 4.0,
    seed: int = 1,
    force_fh: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Bake 8-bit grayscale distance map [0..255] from land_mask.
    Returns (uint8_map, float_raw_dist).
    """
    dist = distance_to_land(land_mask, force_fh=force_fh)
    h, w = dist.shape

    if wobble_mode == "none":
        wobble = np.zeros((h, w), dtype=np.float64)
    elif wobble_mode == "world":
        wobble = world_space_wobble(
            h, w,
            offset_x=world_offset[0],
            offset_y=world_offset[1],
            frequency=noise_freq,
            amplitude=noise_amp,
            seed=seed,
        )
    elif wobble_mode == "gaussian":
        wobble = _gaussian_wobble((h, w), sigma=wobble_sigma, target_std=wobble_std, seed=seed)
    else:
        raise ValueError(f"Unknown wobble_mode: {wobble_mode}")

    # Keep land pixels at 0 so land interiors never bleed nonzero distance if sampled
    wobbled = np.where(land_mask, 0.0, dist + wobble)
    quantized = np.round(np.clip(wobbled / max_dist, 0.0, 1.0) * 255.0).astype(np.uint8)
    return quantized, dist


def update_distance_region(
    land_mask: np.ndarray,
    existing_map: np.ndarray,
    bbox: Tuple[int, int, int, int],
    max_dist: float = 32.0,
    wobble_mode: str = "world",
    noise_freq: float = 0.03,
    noise_amp: float = 4.0,
    seed: int = 1,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Incremental coast update:
      Recompute distance on a window with 2 * MAX_DIST margin around edit bbox,
      then copy back only the part within MAX_DIST of edit bbox.
    """
    h, w = land_mask.shape
    x0, y0, x1, y1 = bbox
    margin_compute = int(math.ceil(2.0 * max_dist))
    margin_write = int(math.ceil(max_dist))

    cx0 = max(0, x0 - margin_compute)
    cy0 = max(0, y0 - margin_compute)
    cx1 = min(w, x1 + margin_compute)
    cy1 = min(h, y1 + margin_compute)

    wx0 = max(0, x0 - margin_write)
    wy0 = max(0, y0 - margin_write)
    wx1 = min(w, x1 + margin_write)
    wy1 = min(h, y1 + margin_write)

    sub_mask = land_mask[cy0:cy1, cx0:cx1]
    sub_map, _ = bake_distance_map(
        sub_mask,
        max_dist=max_dist,
        wobble_mode=wobble_mode,
        world_offset=(cx0, cy0),
        noise_freq=noise_freq,
        noise_amp=noise_amp,
        seed=seed,
    )

    updated = existing_map.copy()
    ry0, ry1 = wy0 - cy0, wy1 - cy0
    rx0, rx1 = wx0 - cx0, wx1 - cx0
    updated[wy0:wy1, wx0:wx1] = sub_map[ry0:ry1, rx0:rx1]

    info = {
        "edit_bbox": [x0, y0, x1, y1],
        "compute_window": [cx0, cy0, cx1, cy1],
        "writeback_window": [wx0, wy0, wx1, wy1],
        "pixels_updated": int((wx1 - wx0) * (wy1 - wy0)),
    }
    return updated, info


def generate_demo_island(width: int = 360, height: int = 322, tile_size: int = 16, seed: int = 7) -> Image.Image:
    """
    Synthesize a top-down pixel-art sand island + cove + small satellite islets
    with transparent water (alpha == 0) at art resolution.
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:height, :width]
    nx = xx / float(width)
    ny = yy / float(height)

    # Organic dual-lobed island creating a sheltered cove + 2 tiny islets
    cove_main = ((nx - 0.34) / 0.24) ** 2 + ((ny - 0.44) / 0.30) ** 2 < 1.0
    peninsula = ((nx - 0.64) / 0.21) ** 2 + ((ny - 0.35) / 0.21) ** 2 < 1.0
    south_spit = ((nx - 0.56) / 0.16) ** 2 + ((ny - 0.72) / 0.14) ** 2 < 1.0
    islet_a = ((nx - 0.80) / 0.055) ** 2 + ((ny - 0.66) / 0.06) ** 2 < 1.0
    islet_b = ((nx - 0.18) / 0.045) ** 2 + ((ny - 0.76) / 0.05) ** 2 < 1.0

    # Smooth perturbation along coastline quantized to pixel art
    wob = world_space_wobble(height, width, frequency=0.04, amplitude=1.0, seed=seed)
    dist_hint = (
        ((nx - 0.45) / 0.32) ** 2 + ((ny - 0.48) / 0.34) ** 2
    )
    land = cove_main | peninsula | south_spit | islet_a | islet_b
    # Carve a crisp sandy cove notch between the lobes
    cove_carve = ((nx - 0.54) / 0.11) ** 2 + ((ny - 0.53) / 0.13) ** 2 < (0.85 + 0.25 * wob)
    land = (land & ~cove_carve) | islet_a | islet_b
    # Keep a clean water border around edges
    border = tile_size * 2
    land[:border, :] = False
    land[-border:, :] = False
    land[:, :border] = False
    land[:, -border:] = False
    _ = dist_hint

    # Distance inward from coast to shade sand -> grass interior
    inward_d = distance_to_land(~land)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    sand_noise = rng.integers(0, 10, size=(height, width))

    # Wet sand rim (1..3 px), dry sand (3..12 px), grassy inner island (>12 px)
    wet_rim = land & (inward_d <= 3.0)
    dry_sand = land & (inward_d > 3.0) & (inward_d <= 12.0)
    grass_core = land & (inward_d > 12.0)

    rgba[wet_rim] = (204, 174, 118, 255)
    rgba[dry_sand & (sand_noise < 7)] = (232, 206, 148, 255)
    rgba[dry_sand & (sand_noise >= 7)] = (222, 194, 134, 255)
    rgba[grass_core & (sand_noise < 6)] = (118, 174, 84, 255)
    rgba[grass_core & (sand_noise >= 6)] = (104, 160, 74, 255)
    return Image.fromarray(rgba, mode="RGBA")


def render_water_frame(
    dist_map_u8: np.ndarray,
    time_sec: float = 0.0,
    max_dist: float = 32.0,
    shoal_dist: float = 5.0,
    shallow_dist: float = 13.0,
    mid_dist: float = 26.0,
    wave_spacing: float = 11.0,
    wave_speed: float = 4.4,
    wave_thickness: float = 1.6,
    wave_min_dist: float = 4.0,
    wave_max_dist: float = 20.0,
    foam_base: float = 2.2,
    foam_amp: float = 1.1,
    foam_freq: float = 2.5,
    enable_waves: bool = True,
    enable_foam: bool = True,
    flat_water: bool = False,
    palette: Optional[Dict[str, str]] = None,
    land_rgba: Optional[np.ndarray] = None,
) -> Image.Image:
    """
    Evaluate the exact pixel-art water shoreline shader in NumPy at art resolution.
    Optionally composites land_rgba on top of the water.
    """
    pal = {**DEFAULT_PALETTE, **(palette or {})}
    c_deep = np.array(hex_to_rgba(pal["deep"]), dtype=np.uint8)
    c_mid = np.array(hex_to_rgba(pal["mid"]), dtype=np.uint8)
    c_shallow = np.array(hex_to_rgba(pal["shallow"]), dtype=np.uint8)
    c_shoal = np.array(hex_to_rgba(pal["shoal"]), dtype=np.uint8)
    c_wave = np.array(hex_to_rgba(pal["wave"]), dtype=np.uint8)
    c_foam = np.array(hex_to_rgba(pal["foam"]), dtype=np.uint8)

    h, w = dist_map_u8.shape
    out = np.empty((h, w, 4), dtype=np.uint8)
    out[:, :] = c_deep

    if not flat_water:
        d = (dist_map_u8.astype(np.float64) / 255.0) * max_dist
        out[d < mid_dist] = c_mid
        out[d < shallow_dist] = c_shallow
        out[d < shoal_dist] = c_shoal

        if enable_waves:
            phase = np.mod(d + time_sec * wave_speed, wave_spacing)
            wave_mask = (phase < wave_thickness) & (d > wave_min_dist) & (d < wave_max_dist)
            out[wave_mask] = c_wave

        if enable_foam:
            foam_thresh = foam_base + foam_amp * math.sin(time_sec * foam_freq)
            out[d < foam_thresh] = c_foam

    if land_rgba is not None:
        alpha = land_rgba[:, :, 3:4].astype(np.float32) / 255.0
        out[:, :, :3] = np.round(
            out[:, :, :3].astype(np.float32) * (1.0 - alpha) + land_rgba[:, :, :3].astype(np.float32) * alpha
        ).astype(np.uint8)
        out[:, :, 3] = 255

    return Image.fromarray(out, mode="RGBA")


def render_contour_debug(
    dist_map_u8: np.ndarray,
    max_dist: float = 32.0,
    ring_step: float = 5.0,
    land_rgba: Optional[np.ndarray] = None,
) -> Image.Image:
    """Render yellow-to-blue contour rings every `ring_step` px for visual inspection."""
    d = (dist_map_u8.astype(np.float64) / 255.0) * max_dist
    t = np.clip(d / max_dist, 0.0, 1.0)
    # Yellow (near coast) -> Cyan -> Deep Blue
    r = np.round(240 * (1.0 - t) + 28 * t).astype(np.uint8)
    g = np.round(220 * (1.0 - 0.55 * t)).astype(np.uint8)
    b = np.round(60 * (1.0 - t) + 170 * t).astype(np.uint8)
    ring = (np.mod(d, ring_step) < 0.9) & (d > 0.5) & (d < max_dist - 0.5)

    out = np.stack([r, g, b, np.full_like(r, 255)], axis=2)
    out[ring] = (255, 255, 255, 255)
    if land_rgba is not None:
        mask = land_rgba[:, :, 3] > 0
        out[mask] = land_rgba[mask]
    return Image.fromarray(out, mode="RGBA")


# ---------------------------------------------------------------------------
# Automated Verification Suite
# ---------------------------------------------------------------------------

def run_verification_suite(
    render_path: Optional[str] = None,
    custom_palette: Optional[Dict[str, str]] = None,
    mask_path: Optional[str] = None,
    map_path: Optional[str] = None,
    max_dist: float = 32.0,
) -> Dict[str, Any]:
    """
    Execute automated checks from the Water Shoreline specification:
      1. Felzenszwalb-Huttenlocher 2D EDT matches brute-force Euclidean search on every pixel
         + 8-bit clamped [0..32 px] quantization matches.
      2. With wobble/waves/foam off, water at d=4, 12, 25, 27 px is shoal, shallow, mid, deep.
      3. Wave pixels appear strictly in (4, 20) px, move toward the coast at wave_speed,
         and repeat every 2.5 s (11 / 4.4).
      4. Straight-coast foam with wobble off is 1 px at thinnest and 3 px at widest.
      5. Rendered water contains only the 6 water palette colors on the art pixel grid.
      6. Chunked world bakes with MAX_DIST neighbor margin + world wobble match identically across seam.
      7. Optional real --mask / --map alignment and EDT parity check.
    """
    checks: Dict[str, Any] = {}

    # 1. Brute-force vs FH EDT on 24x24 mask
    rng = np.random.default_rng(123)
    small_mask = rng.random((24, 24)) < 0.15
    small_mask[5:9, 10:14] = True
    fh_dist = distance_to_land_fh(small_mask)

    ly, lx = np.where(small_mask)
    yy, xx = np.mgrid[:24, :24]
    bf_dist = np.full((24, 24), np.inf, dtype=np.float64)
    for py, px in zip(ly, lx):
        bf_dist = np.minimum(bf_dist, np.hypot(yy - py, xx - px))

    max_edt_err = float(np.max(np.abs(fh_dist - bf_dist)))
    u8_fh = np.round(np.clip(fh_dist / 32.0, 0.0, 1.0) * 255.0).astype(np.uint8)
    u8_bf = np.round(np.clip(bf_dist / 32.0, 0.0, 1.0) * 255.0).astype(np.uint8)
    checks["edt_matches_bruteforce"] = {
        "ok": max_edt_err < 1e-9 and bool(np.array_equal(u8_fh, u8_bf)),
        "max_pixel_error": max_edt_err,
    }

    # 2. Depth bands at 4, 12, 25, 27 px (straight coast at x=0, no wobble/waves/foam)
    straight = np.zeros((16, 40), dtype=bool)
    straight[:, 0] = True
    u8_straight, _ = bake_distance_map(straight, max_dist=32.0, wobble_mode="none", force_fh=True)
    pal = {**DEFAULT_PALETTE, **(custom_palette or {})}
    band_img = np.array(
        render_water_frame(u8_straight, time_sec=0.0, enable_waves=False, enable_foam=False, palette=pal)
    )
    expected_bands = {
        4: hex_to_rgba(pal["shoal"]),
        12: hex_to_rgba(pal["shallow"]),
        25: hex_to_rgba(pal["mid"]),
        27: hex_to_rgba(pal["deep"]),
    }
    observed_bands = {x: tuple(int(v) for v in band_img[8, x]) for x in (4, 12, 25, 27)}
    checks["depth_bands_4_12_25_27"] = {
        "ok": all(observed_bands[x] == expected_bands[x] for x in (4, 12, 25, 27)),
        "observed": observed_bands,
    }

    # 3. Wave bounds (4 < d < 20), inward motion toward coast, and 2.5 s periodicity
    wave_rgb = hex_to_rgba(pal["wave"])
    w0 = np.array(render_water_frame(u8_straight, time_sec=0.35, enable_waves=True, enable_foam=False, palette=pal))
    w_later = np.array(render_water_frame(u8_straight, time_sec=0.85, enable_waves=True, enable_foam=False, palette=pal))
    w25 = np.array(render_water_frame(u8_straight, time_sec=2.85, enable_waves=True, enable_foam=False, palette=pal))
    wave_xs = np.where((w0[8, :, :3] == wave_rgb[:3]).all(axis=1))[0].tolist()
    wave_xs_later = np.where((w_later[8, :, :3] == wave_rgb[:3]).all(axis=1))[0].tolist()
    waves_in_bounds = len(wave_xs) > 0 and all(4 < x < 20 for x in wave_xs)
    wave_repeats_2_5s = bool(np.array_equal(w0, w25))
    # Over dt = 0.5 s at 4.4 px/s, existing wave rings move inward by ~2.2 px (smaller x)
    # Check min(wave_xs_later) < min(wave_xs) so newly entering outer rings (near x=19) don't skew the mean.
    wave_moves_inward = (
        len(wave_xs) > 0
        and len(wave_xs_later) > 0
        and min(wave_xs_later) < min(wave_xs)
    )
    checks["waves_bounds_and_period"] = {
        "ok": waves_in_bounds and wave_repeats_2_5s and wave_moves_inward,
        "wave_x_positions": wave_xs,
        "wave_x_after_0_5s": wave_xs_later,
        "moves_toward_coast": wave_moves_inward,
        "repeats_at_2_5s": wave_repeats_2_5s,
    }

    # 4. Straight-coast foam width: 1 px min, 3 px max
    foam_rgb = hex_to_rgba(pal["foam"])
    t_min = -math.pi / (2.0 * 2.5)  # sin(t * 2.5) == -1 -> 1.1 px
    t_max = math.pi / (2.0 * 2.5)   # sin(t * 2.5) == +1 -> 3.3 px
    f_min_img = np.array(render_water_frame(u8_straight, time_sec=t_min, enable_waves=False, enable_foam=True, palette=pal))
    f_max_img = np.array(render_water_frame(u8_straight, time_sec=t_max, enable_waves=False, enable_foam=True, palette=pal))
    foam_min_px = int(np.sum((f_min_img[8, 1:, :3] == foam_rgb[:3]).all(axis=1)))
    foam_max_px = int(np.sum((f_max_img[8, 1:, :3] == foam_rgb[:3]).all(axis=1)))
    checks["foam_width_1_to_3_px"] = {
        "ok": foam_min_px == 1 and foam_max_px == 3,
        "min_width_px": foam_min_px,
        "max_width_px": foam_max_px,
    }

    # 5. Six-color pixel-grid check (either on provided --render or synthesized frame)
    target_img = (
        np.array(Image.open(render_path).convert("RGBA"))
        if render_path
        else np.array(render_water_frame(u8_straight, time_sec=0.4, palette=pal))
    )
    allowed = {hex_to_rgba(pal[k])[:3] for k in ("deep", "mid", "shallow", "shoal", "wave", "foam")}
    unique_rgb = {tuple(int(v) for v in px) for px in target_img[:, :, :3].reshape(-1, 3)}
    unexpected = sorted(unique_rgb - allowed)
    checks["six_color_palette_only"] = {
        "ok": len(unexpected) == 0,
        "unique_color_count": len(unique_rgb),
        "unexpected_colors": unexpected[:10],
    }

    # 6. Chunk border seam check (two 64x64 chunks baked with 32 px margin + world wobble)
    full_land = np.zeros((64, 128), dtype=bool)
    full_land[20:42, 48:80] = True  # crosses chunk boundary x=64
    full_map, _ = bake_distance_map(full_land, max_dist=32.0, wobble_mode="world", world_offset=(0, 0), seed=42)

    m = 32
    c0_pad = np.pad(full_land, ((m, m), (m, m)), mode="constant", constant_values=False)
    # Chunk 0: x in [0, 64), padded window x in [-32, 96) -> slice [0 : 64+2m, 0 : 64+2m]
    c0_sub, _ = bake_distance_map(c0_pad[:, : 64 + 2 * m], max_dist=32.0, wobble_mode="world", world_offset=(-m, -m), seed=42)
    c0_crop = c0_sub[m:-m, m:-m]
    # Chunk 1: x in [64, 128), padded window x in [32, 160)
    c1_sub, _ = bake_distance_map(c0_pad[:, 64 : 128 + 2 * m], max_dist=32.0, wobble_mode="world", world_offset=(64 - m, -m), seed=42)
    c1_crop = c1_sub[m:-m, m:-m]

    chunk_diff = int(np.max(np.abs(np.hstack([c0_crop, c1_crop]).astype(np.int32) - full_map.astype(np.int32))))
    checks["chunked_margin_seam_match"] = {
        "ok": chunk_diff == 0,
        "max_diff_vs_full_bake": chunk_diff,
    }

    # 7. Optional real mask / map alignment & range verification
    if mask_path or map_path:
        real_ok = True
        real_info: Dict[str, Any] = {}
        real_mask = None
        if mask_path:
            real_mask = extract_land_mask(Image.open(mask_path), mask_mode="alpha")
            real_info["mask_size"] = [int(real_mask.shape[1]), int(real_mask.shape[0])]
            real_info["land_pixels"] = int(np.sum(real_mask))
            real_info["water_pixels"] = int(np.sum(~real_mask))
            if real_info["water_pixels"] == 0:
                real_ok = False
                real_info["warning"] = "Land mask has zero transparent water pixels (tiles may be opaque)."
        if map_path:
            real_map = np.array(Image.open(map_path).convert("L"))
            real_info["map_size"] = [int(real_map.shape[1]), int(real_map.shape[0])]
            real_info["map_range"] = [int(real_map.min()), int(real_map.max())]
            if real_mask is not None and real_map.shape != real_mask.shape:
                real_ok = False
                real_info["alignment_error"] = (
                    f"Map {real_map.shape[1]}x{real_map.shape[0]} != mask {real_mask.shape[1]}x{real_mask.shape[0]}"
                )
        real_info["ok"] = real_ok
        checks["real_asset_alignment"] = real_info

    all_ok = all(bool(v["ok"]) for v in checks.values())
    return {"ok": all_ok, "checks": checks}


# ---------------------------------------------------------------------------
# Engine Code / Shader Exports
# ---------------------------------------------------------------------------

SNIPPETS: Dict[str, str] = {
    "godot4-baker": """# shore_distance.gd — Runtime Felzenszwalb-Huttenlocher Distance Field Baker (Godot 4.x)
# Usage: $Water.texture = ShoreDistance.bake(land_image)
class_name ShoreDistance
extends RefCounted

const MAX_DIST := 32.0

static func bake(land: Image, world_origin: Vector2i = Vector2i.ZERO, seed: int = 1) -> ImageTexture:
\tvar w := land.get_width()
\tvar h := land.get_height()
\tvar dist := distance(land)
\tvar noise := FastNoiseLite.new()
\tnoise.seed = seed
\tnoise.fractal_type = FastNoiseLite.FRACTAL_NONE
\tnoise.frequency = 0.03
\tvar img := Image.create(w, h, false, Image.FORMAT_L8)
\tfor y in h:
\t\tfor x in w:
\t\t\tvar d := 0.0 if land.get_pixel(x, y).a > 0.0 else dist[y * w + x] + noise.get_noise_2d(x + world_origin.x, y + world_origin.y) * 4.0
\t\t\tvar v := clampf(d / MAX_DIST, 0.0, 1.0)
\t\t\timg.set_pixel(x, y, Color(v, v, v))
\treturn ImageTexture.create_from_image(img)

static func distance(land: Image) -> PackedFloat32Array:
\tvar w := land.get_width()
\tvar h := land.get_height()
\tvar d := PackedFloat32Array()
\td.resize(w * h)
\tfor y in h:
\t\tfor x in w:
\t\t\td[y * w + x] = 0.0 if land.get_pixel(x, y).a > 0.0 else 1e20
\tfor x in w:
\t\t_pass(d, x, w, h)
\tfor y in h:
\t\t_pass(d, y * w, 1, w)
\tfor i in d.size():
\t\td[i] = sqrt(d[i])
\treturn d

static func _pass(d: PackedFloat32Array, start: int, step: int, n: int) -> void:
\tvar f := PackedFloat32Array()
\tf.resize(n)
\tfor i in n:
\t\tf[i] = d[start + i * step]
\tvar v := PackedInt32Array()
\tv.resize(n)
\tvar z := PackedFloat32Array()
\tz.resize(n + 1)
\tvar k := 0
\tz[0] = -INF
\tz[1] = INF
\tfor q in range(1, n):
\t\tvar s := _meet(f, q, v[k])
\t\twhile s <= z[k]:
\t\t\tk -= 1
\t\t\ts = _meet(f, q, v[k])
\t\tk += 1
\t\tv[k] = q
\t\tz[k] = s
\t\tz[k + 1] = INF
\tk = 0
\tfor q in n:
\t\twhile z[k + 1] < q:
\t\t\tk += 1
\t\td[start + q * step] = (q - v[k]) * (q - v[k]) + f[v[k]]

static func _meet(f: PackedFloat32Array, q: int, p: int) -> float:
\treturn ((f[q] + q * q) - (f[p] + p * p)) / (2.0 * (q - p))
""",
    "godot4-shader": """// water_shoreline.gdshader — Put on a Sprite2D drawn under your land TileMapLayer.
// Set Sprite2D texture_filter = Nearest so every band stays locked to the art pixel grid.
shader_type canvas_item;

uniform float max_dist = 32.0; // Must match ShoreDistance.MAX_DIST
uniform vec4 deep : source_color = vec4(0.110, 0.290, 0.502, 1.0);
uniform vec4 mid : source_color = vec4(0.133, 0.384, 0.588, 1.0);
uniform vec4 shallow : source_color = vec4(0.204, 0.549, 0.690, 1.0);
uniform vec4 shoal : source_color = vec4(0.376, 0.745, 0.769, 1.0);
uniform vec4 wave : source_color = vec4(0.588, 0.839, 0.855, 1.0);
uniform vec4 foam : source_color = vec4(0.925, 0.965, 0.957, 1.0);
uniform float shoal_dist = 5.0;
uniform float shallow_dist = 13.0;
uniform float mid_dist = 26.0;
uniform float wave_spacing = 11.0;
uniform float wave_speed = 4.4;
uniform float wave_thickness = 1.6;
uniform float wave_min_dist = 4.0;
uniform float wave_max_dist = 20.0;
uniform float foam_base = 2.2;
uniform float foam_amp = 1.1;
uniform float foam_freq = 2.5;
uniform bool enabled = true;

void fragment() {
\tif (!enabled) {
\t\tCOLOR = deep;
\t} else {
\t\tfloat d = texture(TEXTURE, UV).r * max_dist;
\t\tvec4 c = deep;
\t\tif (d < mid_dist) c = mid;
\t\tif (d < shallow_dist) c = shallow;
\t\tif (d < shoal_dist) c = shoal;
\t\tfloat phase = mod(d + TIME * wave_speed, wave_spacing);
\t\tif (phase < wave_thickness && d > wave_min_dist && d < wave_max_dist) c = wave;
\t\tif (d < foam_base + foam_amp * sin(TIME * foam_freq)) c = foam;
\t\tCOLOR = c;
\t}
}
""",
    "unity-shader": """// WaterShoreline.shader — Unlit 2D Sprite Shader (Set distance texture FilterMode = Point!)
Shader "Custom/WaterShoreline2D"
{
    Properties
    {
        [PerRendererData] _MainTex ("Distance Map (Point)", 2D) = "white" {}
        _MaxDist ("Max Distance (px)", Float) = 32.0
        _Deep ("Deep", Color) = (0.110, 0.290, 0.502, 1)
        _Mid ("Mid", Color) = (0.133, 0.384, 0.588, 1)
        _Shallow ("Shallow", Color) = (0.204, 0.549, 0.690, 1)
        _Shoal ("Shoal", Color) = (0.376, 0.745, 0.769, 1)
        _Wave ("Wave", Color) = (0.588, 0.839, 0.855, 1)
        _Foam ("Foam", Color) = (0.925, 0.965, 0.957, 1)
        _WaveSpacing ("Wave Spacing", Float) = 11.0
        _WaveSpeed ("Wave Speed", Float) = 4.4
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Off ZWrite Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            float _MaxDist, _WaveSpacing, _WaveSpeed;
            fixed4 _Deep, _Mid, _Shallow, _Shoal, _Wave, _Foam;

            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };

            v2f vert(appdata v) {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target {
                float d = tex2D(_MainTex, i.uv).r * _MaxDist;
                fixed4 c = _Deep;
                if (d < 26.0) c = _Mid;
                if (d < 13.0) c = _Shallow;
                if (d < 5.0) c = _Shoal;
                float phase = fmod(d + _Time.y * _WaveSpeed, _WaveSpacing);
                if (phase < 1.6 && d > 4.0 && d < 20.0) c = _Wave;
                if (d < 2.2 + 1.1 * sin(_Time.y * 2.5)) c = _Foam;
                return c;
            }
            ENDCG
        }
    }
}
""",
    "typescript": """// waterShoreline.ts — WebGL2 / Canvas / Phaser pixel-grid shoreline evaluator
export const WATER_PALETTE = {
  deep: "#1C4A80",
  mid: "#226296",
  shallow: "#348CB0",
  shoal: "#60BEC4",
  wave: "#96D6DA",
  foam: "#ECF6F4",
} as const;

export function waterColorAtDistance(d: number, timeSec: number): string {
  let color: string = WATER_PALETTE.deep;
  if (d < 26.0) color = WATER_PALETTE.mid;
  if (d < 13.0) color = WATER_PALETTE.shallow;
  if (d < 5.0) color = WATER_PALETTE.shoal;
  const phase = ((d + timeSec * 4.4) % 11.0 + 11.0) % 11.0;
  if (phase < 1.6 && d > 4.0 && d < 20.0) color = WATER_PALETTE.wave;
  if (d < 2.2 + 1.1 * Math.sin(timeSec * 2.5)) color = WATER_PALETTE.foam;
  return color;
}
""",
    "glsl-shader": """// water_shoreline.frag — Generic OpenGL/WebGL2 fragment shader (Sample u_map with GL_NEAREST!)
uniform sampler2D u_map;      // 8-bit baked distance map (1 texel = 1 art pixel)
uniform float u_max_dist;     // MAX_DIST matching bake (default: 32.0)
uniform float u_time;         // elapsed seconds
uniform bool u_enabled;       // false restores flat deep water

const vec3 DEEP    = vec3(0.110, 0.290, 0.502);
const vec3 MID     = vec3(0.133, 0.384, 0.588);
const vec3 SHALLOW = vec3(0.204, 0.549, 0.690);
const vec3 SHOAL   = vec3(0.376, 0.745, 0.769);
const vec3 WAVE    = vec3(0.588, 0.839, 0.855);
const vec3 FOAM    = vec3(0.925, 0.965, 0.957);

in vec2 v_uv;
out vec4 fragColor;

void main() {
    if (!u_enabled) {
        fragColor = vec4(DEEP, 1.0);
        return;
    }
    float d = texture(u_map, v_uv).r * u_max_dist;
    vec3 c = DEEP;
    if (d < 26.0) c = MID;
    if (d < 13.0) c = SHALLOW;
    if (d < 5.0)  c = SHOAL;
    float phase = mod(d + u_time * 4.4, 11.0);
    if (phase < 1.6 && d > 4.0 && d < 20.0) c = WAVE;
    if (d < 2.2 + 1.1 * sin(u_time * 2.5)) c = FOAM;
    fragColor = vec4(c, 1.0);
}
""",
    "cpp-software": """// water_shoreline_cpu.h — Header-only CPU software renderer for SDL2 / custom 2D engines
#pragma once
#include <cmath>
#include <cstdint>

struct WaterRGB { uint8_t r, g, b; };

struct WaterSettings {
    float max_dist = 32.0f;
    float shoal_dist = 5.0f, shallow_dist = 13.0f, mid_dist = 26.0f;
    float wave_spacing = 11.0f, wave_speed = 4.4f, wave_thickness = 1.6f;
    float wave_min = 4.0f, wave_max = 20.0f;
    float foam_base = 2.2f, foam_amp = 1.1f, foam_freq = 2.5f;
    bool enabled = true;
};

inline WaterRGB water_color_at(uint8_t map8, float time_sec, const WaterSettings& s = {}) {
    constexpr WaterRGB DEEP    = {0x1C, 0x4A, 0x80};
    constexpr WaterRGB MID     = {0x22, 0x62, 0x96};
    constexpr WaterRGB SHALLOW = {0x34, 0x8C, 0xB0};
    constexpr WaterRGB SHOAL   = {0x60, 0xBE, 0xC4};
    constexpr WaterRGB WAVE    = {0x96, 0xD6, 0xDA};
    constexpr WaterRGB FOAM    = {0xEC, 0xF6, 0xF4};
    if (!s.enabled) return DEEP;
    const float d = (static_cast<float>(map8) / 255.0f) * s.max_dist;
    WaterRGB c = DEEP;
    if (d < s.mid_dist)     c = MID;
    if (d < s.shallow_dist) c = SHALLOW;
    if (d < s.shoal_dist)   c = SHOAL;
    float phase = std::fmod(d + time_sec * s.wave_speed, s.wave_spacing);
    if (phase < 0.0f) phase += s.wave_spacing;
    if (phase < s.wave_thickness && d > s.wave_min && d < s.wave_max) c = WAVE;
    if (d < s.foam_base + s.foam_amp * std::sin(time_sec * s.foam_freq)) c = FOAM;
    return c;
}
""",
}


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def _cmd_bake(args: argparse.Namespace) -> int:
    if args.demo:
        land_img = generate_demo_island(tile_size=args.tile_size, seed=args.seed)
    elif args.input:
        land_img = Image.open(args.input)
    else:
        raise ValueError("Provide an input land layer PNG or pass --demo.")

    land_mask = extract_land_mask(
        land_img,
        mask_mode=args.mask_mode,
        key_color=args.key_color,
        key_tolerance=args.key_tolerance,
    )

    scale = (args.tile_size / 16.0) if args.auto_scale else 1.0
    max_dist = args.max_dist * scale
    sigma = args.wobble_sigma * scale
    wobble_std = args.wobble_std * scale

    ox, oy = 0, 0
    if args.world_offset:
        xs, ys = args.world_offset.split(",")
        ox, oy = int(xs.strip()), int(ys.strip())

    wobble_mode = "none" if args.no_wobble else args.wobble_mode
    dist_u8, _ = bake_distance_map(
        land_mask,
        max_dist=max_dist,
        wobble_mode=wobble_mode,
        wobble_sigma=sigma,
        wobble_std=wobble_std,
        world_offset=(ox, oy),
        noise_freq=args.noise_freq / scale,
        noise_amp=args.noise_amp * scale,
        seed=args.seed,
    )

    if args.margin_crop > 0:
        m = args.margin_crop
        dist_u8 = dist_u8[m:-m, m:-m]
        land_img = land_img.crop((m, m, land_img.width - m, land_img.height - m))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(dist_u8, mode="L").save(out_path)

    result: Dict[str, Any] = {
        "ok": True,
        "output_path": str(out_path),
        "size": [int(dist_u8.shape[1]), int(dist_u8.shape[0])],
        "max_dist": max_dist,
        "tile_size": args.tile_size,
        "wobble_mode": wobble_mode,
        "land_pixels": int(np.sum(land_mask)),
        "water_pixels": int(np.sum(~land_mask)),
        "backend": "scipy" if HAS_SCIPY else "felzenszwalb_huttenlocher_numpy",
    }

    if args.save_land:
        lp = Path(args.save_land)
        lp.parent.mkdir(parents=True, exist_ok=True)
        land_img.save(lp)
        result["land_path"] = str(lp)

    land_arr = np.array(land_img.convert("RGBA"))
    if args.preview:
        pp = Path(args.preview)
        pp.parent.mkdir(parents=True, exist_ok=True)
        render_water_frame(
            dist_u8,
            time_sec=args.time,
            max_dist=max_dist,
            shoal_dist=5.0 * scale,
            shallow_dist=13.0 * scale,
            mid_dist=26.0 * scale,
            wave_spacing=11.0 * scale,
            wave_speed=4.4 * scale,
            wave_thickness=1.6 * scale,
            wave_min_dist=4.0 * scale,
            wave_max_dist=20.0 * scale,
            foam_base=2.2 * scale,
            foam_amp=1.1 * scale,
            land_rgba=land_arr,
        ).save(pp)
        result["preview_path"] = str(pp)

    if args.contour_debug:
        cp = Path(args.contour_debug)
        cp.parent.mkdir(parents=True, exist_ok=True)
        render_contour_debug(dist_u8, max_dist=max_dist, ring_step=5.0 * scale, land_rgba=land_arr).save(cp)
        result["contour_debug_path"] = str(cp)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Baked shoreline distance map ({result['size'][0]}x{result['size'][1]}, MAX_DIST={max_dist}) -> {out_path}")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    dist_u8 = np.array(Image.open(args.dist_map).convert("L"))
    land_arr = np.array(Image.open(args.land).convert("RGBA")) if args.land else None
    if land_arr is not None and land_arr.shape[:2] != dist_u8.shape:
        raise ValueError(
            f"Distance map {dist_u8.shape[1]}x{dist_u8.shape[0]} doesn't match land "
            f"{land_arr.shape[1]}x{land_arr.shape[0]} — must share origin and size."
        )
    scale = (args.tile_size / 16.0) if args.auto_scale else 1.0
    max_dist = args.max_dist * scale

    def _make_frame(t: float) -> Image.Image:
        fr = render_water_frame(
            dist_u8,
            time_sec=t,
            max_dist=max_dist,
            shoal_dist=5.0 * scale,
            shallow_dist=13.0 * scale,
            mid_dist=26.0 * scale,
            wave_spacing=11.0 * scale,
            wave_speed=4.4 * scale,
            wave_thickness=1.6 * scale,
            wave_min_dist=4.0 * scale,
            wave_max_dist=20.0 * scale,
            foam_base=2.2 * scale,
            foam_amp=1.1 * scale,
            enable_waves=not args.no_waves,
            enable_foam=not args.no_foam,
            flat_water=args.flat_water,
            land_rgba=land_arr,
        )
        if args.upscale > 1:
            fr = fr.resize((fr.width * args.upscale, fr.height * args.upscale), resample=Image.Resampling.NEAREST)
        return fr

    if args.frames > 1 or args.gif:
        n_frames = max(2, int(args.frames)) if args.frames > 1 else 25
        fps = max(1, int(args.fps))
        frames_img = [_make_frame(args.time + i / float(fps)) for i in range(n_frames)]
        out_path = Path(args.gif if args.gif else args.output)
        if out_path.suffix.lower() != ".gif":
            out_path = out_path.with_suffix(".gif")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frames_img[0].save(
            out_path,
            save_all=True,
            append_images=frames_img[1:],
            duration=max(10, int(round(1000.0 / fps))),
            loop=0,
        )
        res = {
            "ok": True,
            "gif_path": str(out_path),
            "size": [frames_img[0].width, frames_img[0].height],
            "frames": n_frames,
            "fps": fps,
            "duration_sec": round(n_frames / float(fps), 2),
        }
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Rendered {n_frames}-frame animated shoreline GIF ({fps} fps) -> {out_path}")
        return 0

    frame = _make_frame(args.time)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.save(out_path)

    res = {"ok": True, "output_path": str(out_path), "size": [frame.width, frame.height], "time_sec": args.time}
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Rendered shoreline frame (t={args.time}s) -> {out_path}")
    return 0


def _cmd_update_region(args: argparse.Namespace) -> int:
    land_mask = extract_land_mask(Image.open(args.land), mask_mode="alpha")
    existing = np.array(Image.open(args.dist_map).convert("L"))
    x0, y0, x1, y1 = [int(v.strip()) for v in args.bbox.split(",")]
    updated, info = update_distance_region(
        land_mask,
        existing,
        bbox=(x0, y0, x1, y1),
        max_dist=args.max_dist,
        seed=args.seed,
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(updated, mode="L").save(out_path)
    info["ok"] = True
    info["output_path"] = str(out_path)
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        print(f"Updated region {info['writeback_window']} ({info['pixels_updated']} px) -> {out_path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    res = run_verification_suite(
        render_path=args.render,
        mask_path=args.mask,
        map_path=args.map,
        max_dist=args.max_dist,
    )
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


def _cmd_export_code(args: argparse.Namespace) -> int:
    targets = list(SNIPPETS.keys()) if args.target == "all" else [args.target]
    written: Dict[str, str] = {}

    ext_map = {
        "godot4-baker": "shore_distance.gd",
        "godot4-shader": "water_shoreline.gdshader",
        "unity-shader": "WaterShoreline.shader",
        "typescript": "waterShoreline.ts",
        "glsl-shader": "water_shoreline.frag",
        "cpp-software": "water_shoreline_cpu.h",
    }

    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in targets:
            fp = out_dir / ext_map[t]
            fp.write_text(SNIPPETS[t], encoding="utf-8")
            written[t] = str(fp)

    if args.json:
        payload: Dict[str, Any] = {"ok": True, "targets": targets}
        if written:
            payload["written"] = written
        else:
            payload["code"] = {t: SNIPPETS[t] for t in targets}
        print(json.dumps(payload, indent=2))
    else:
        if written:
            for t, p in written.items():
                print(f"Exported {t} -> {p}")
        else:
            for t in targets:
                print(f"=== {t} ===\n{SNIPPETS[t]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="2D Water Shoreline Distance Field pipeline: bake, render, incremental update, verify & export."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # bake
    p_bake = sub.add_parser("bake", help="Bake an 8-bit grayscale distance map from a land layer PNG.")
    p_bake.add_argument("input", nargs="?", help="Land layer RGBA PNG (transparent where water is).")
    p_bake.add_argument("--demo", action="store_true", help="Synthesize a 360x322 pixel-art sand island + cove demo.")
    p_bake.add_argument("-o", "--output", default="exports/water_shorelines/shore_distance.png", help="Output grayscale PNG.")
    p_bake.add_argument("--tile-size", type=int, default=16, help="Base art tile size in px (default: 16).")
    p_bake.add_argument("--auto-scale", action="store_true", help="Scale MAX_DIST, sigma & bands proportionally to tile_size / 16.")
    p_bake.add_argument("--max-dist", type=float, default=32.0, help="MAX_DIST in art px (default: 32.0).")
    p_bake.add_argument("--wobble-mode", choices=["gaussian", "world", "none"], default="gaussian", help="Wobble noise mode.")
    p_bake.add_argument("--wobble-sigma", type=float, default=8.0, help="Gaussian sigma in px (default: 8.0).")
    p_bake.add_argument("--wobble-std", type=float, default=2.0, help="Gaussian wobble std in px (default: 2.0).")
    p_bake.add_argument("--noise-freq", type=float, default=0.03, help="World-space noise frequency (default: 0.03).")
    p_bake.add_argument("--noise-amp", type=float, default=4.0, help="World-space noise amplitude (default: 4.0).")
    p_bake.add_argument("--world-offset", help="World origin 'x,y' for chunked world wobble.")
    p_bake.add_argument("--margin-crop", type=int, default=0, help="Crop N margin pixels from all 4 sides after baking.")
    p_bake.add_argument("--no-wobble", action="store_true", help="Disable wobble (for debug/verification).")
    p_bake.add_argument("--mask-mode", choices=["alpha", "luma", "chroma"], default="alpha", help="How to extract land mask.")
    p_bake.add_argument("--key-color", help="Water hex color to key out when --mask-mode chroma.")
    p_bake.add_argument("--key-tolerance", type=int, default=12, help="Chroma key tolerance (default: 12).")
    p_bake.add_argument("--seed", type=int, default=1, help="Noise/demo seed.")
    p_bake.add_argument("--save-land", help="Optional path to save the input/demo land PNG.")
    p_bake.add_argument("--preview", help="Optional path to render composited water + land preview PNG.")
    p_bake.add_argument("--contour-debug", help="Optional path to render 5 px distance contour rings PNG.")
    p_bake.add_argument("--time", type=float, default=0.0, help="Shader preview timestamp in seconds.")
    p_bake.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_bake.set_defaults(func=_cmd_bake)

    # render
    p_ren = sub.add_parser("render", help="Render water frame from a baked distance map PNG.")
    p_ren.add_argument("dist_map", help="Grayscale distance map PNG.")
    p_ren.add_argument("--land", help="Optional land RGBA PNG to composite on top.")
    p_ren.add_argument("-o", "--output", default="exports/water_shorelines/water_frame.png", help="Output rendered PNG.")
    p_ren.add_argument("--time", type=float, default=0.0, help="Animation time in seconds.")
    p_ren.add_argument("--tile-size", type=int, default=16, help="Base art tile size in px.")
    p_ren.add_argument("--auto-scale", action="store_true", help="Scale distances by tile_size / 16.")
    p_ren.add_argument("--max-dist", type=float, default=32.0, help="MAX_DIST matching the bake (default: 32.0).")
    p_ren.add_argument("--no-waves", action="store_true", help="Disable wave rings.")
    p_ren.add_argument("--no-foam", action="store_true", help="Disable foam line.")
    p_ren.add_argument("--flat-water", action="store_true", help="Render flat deep water (effect-off check).")
    p_ren.add_argument("--upscale", type=int, default=1, help="Nearest-neighbor integer upscale for visual inspection.")
    p_ren.add_argument("--frames", type=int, default=1, help="Number of animation frames (>1 writes looping GIF, e.g. 50 at 20 fps = 2.5s exact loop).")
    p_ren.add_argument("--fps", type=int, default=20, help="Animation FPS when rendering GIF (default: 20).")
    p_ren.add_argument("--gif", help="Explicit output GIF path for animated preview.")
    p_ren.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_ren.set_defaults(func=_cmd_render)

    # update-region
    p_upd = sub.add_parser("update-region", help="Incrementally rebake dirty coastline window (2*MAX_DIST margin).")
    p_upd.add_argument("--land", required=True, help="Updated land RGBA PNG.")
    p_upd.add_argument("--dist-map", required=True, help="Existing grayscale distance map PNG.")
    p_upd.add_argument("--bbox", required=True, help="Edited bounding box 'x0,y0,x1,y1'.")
    p_upd.add_argument("-o", "--output", required=True, help="Output updated grayscale distance map PNG.")
    p_upd.add_argument("--max-dist", type=float, default=32.0, help="MAX_DIST in px (default: 32.0).")
    p_upd.add_argument("--seed", type=int, default=1, help="World noise seed.")
    p_upd.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_upd.set_defaults(func=_cmd_update_region)

    # verify
    p_ver = sub.add_parser("verify", help="Run automated EDT, band, wave, foam, palette, chunk-seam & real-asset checks.")
    p_ver.add_argument("--render", help="Optional rendered water PNG to verify 6-color pixel-grid constraint.")
    p_ver.add_argument("--mask", help="Optional real land RGBA PNG to check transparency & dimensions.")
    p_ver.add_argument("--map", help="Optional real baked distance map PNG to verify alignment with --mask.")
    p_ver.add_argument("--max-dist", type=float, default=32.0, help="MAX_DIST for verification (default: 32.0).")
    p_ver.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_ver.set_defaults(func=_cmd_verify)

    # export-code
    p_exp = sub.add_parser("export-code", help="Export Godot 4 / Unity / TypeScript baker & shader code.")
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
