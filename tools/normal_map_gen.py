#!/usr/bin/env python3
"""
Pixel Art Normal Map, Cavity Light Mask & De-Lighting Generator (normal_map_gen.py)
Powered by the @xprite/lighter + Moonfell Pixel Art Lighter Cluster-Faceted Algorithm (MIT License)
+ Quarter-Circle Outline Bevel, 3x3 Seamless Floor-Tile, and Smooth Distance-Transform Modes.

Key Pixel-Art Specific Features (Faceted Mode - Default):
1. Perceptual CIELAB & Exact-RGB Connected Clustering (--region-mode perceptual|exact-rgb):
   Groups flat and softly anti-aliased pixel color islands into unified facets without
   breaking on subtle gradients or bleeding across sharp contrast/alpha edges.
2. Automatic Painted-Light Direction Estimation (--painted-light-angle / auto):
   Fits contour normals against chroma-grouped luminance with 4-fold spatial holdout and
   component consistency checks to detect baked-in light direction and confidence.
3. Painted-Light-Aware Normal Tilting (--painted-light-influence):
   Reduces height-field luminance artifacts and tilts normals cleanly using local relative
   luminance toward the painted light angle.
4. Sprite-Scale-Adaptive Height Ramp & Facet Splitting (--facets):
   Small sprites keep a concave sqrt(distance) bevel ramp; larger sprites transition to a
   linear ramp with footprint-scaled facet thresholds and 8-direction x 4-elevation quantization.
5. Architecture Straight-Edge Alignment:
   Keeps straight exterior walls continuous across brick color variations in architecture preset.
6. Outline Merging (--merge-outlines) & Cluster-Scoped 1-2px Orphan De-speckling:
   Dark 1px outlines inherit adjacent interior facet normals instead of creating dark trenches.
7. Painted-Light Removal / De-Lighting (--delight):
   Divides out baked-in directional lighting in linear sRGB to produce flat-lit albedo
   ('<stem>_delit.png') and cleaner dynamic relighting previews.
8. Cavity Light Mask Generation (--mask):
   Outputs a companion '_m.png' light mask with cavity occlusion.
9. Linear-sRGB Point Light Preview (--preview):
   Generates an animated GIF with physical inverse-square falloff and optional cel steps.
"""

import sys
import json
import math
import argparse
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image

try:
    from scipy.ndimage import distance_transform_edt, gaussian_filter, sobel
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

GODOT4_STEPPED_SHADER = """// pixel_art_stepped_light.gdshader — Stepped 2D normal-mapped lighting (Godot 4.x)
// Attach to every Sprite2D / TileMapLayer the PointLight2D touches (use CanvasTexture with Normal Map + Nearest).
shader_type canvas_item;

uniform float radius = 70.0;   // Light reach in pixels
uniform int bands = 6;         // 0 = smooth light, 6 = crisp pixel-art light bands
uniform float falloff_power = 1.2;

void light() {
\tvec3 to_light = LIGHT_POSITION - LIGHT_VERTEX;
\tfloat falloff = pow(clamp(1.0 - length(to_light.xy) / radius, 0.0, 1.0), falloff_power);
\tfloat lit = falloff * max(dot(NORMAL, normalize(to_light)), 0.0);
\tif (bands > 0) {
\t\tlit = ceil(lit * float(bands)) / float(bands);
\t}
\tLIGHT = vec4(COLOR.rgb * LIGHT_COLOR.rgb * LIGHT_ENERGY * lit, LIGHT_COLOR.a);
}
"""

UNITY_URP_GUIDANCE = """// Unity URP 2D — Outline Normal Map & Stepped Lighting Notes
// 1. Add generated <sprite>_n.png as Secondary Texture named _NormalMap in Sprite Editor (FilterMode = Point, sRGB = Off).
// 2. If light from above lights the bottom edge, re-run with --invert-y (DirectX -Y green channel).
// 3. In custom Sprite-Lit-Default Shader Graph / HLSL fragment, compute:
//    falloff = pow(saturate(1.0 - length(toLight.xy) / _Radius), 1.2);
//    lit = falloff * max(dot(worldNormal, normalize(toLight)), 0.0);
//    if (_Steps > 0) lit = ceil(lit * _Steps) / _Steps;
"""

PRESET_DEFAULTS = {
    "character":    {"strength": 65,  "facets": 15, "floor": 30, "ceiling": 255, "cavity": 20, "edge_width": 2},
    "object":       {"strength": 100, "facets": 35, "floor": 20, "ceiling": 255, "cavity": 35, "edge_width": 3},
    "architecture": {"strength": 100, "facets": 20, "floor": 30, "ceiling": 255, "cavity": 25, "edge_width": 1},
    "terrain":      {"strength": 110, "facets": 50, "floor": 35, "ceiling": 255, "cavity": 20, "edge_width": 3},
}

HEIGHT_PROFILES = {
    "architecture": {"silhouette": 0.0,  "cap": 16.0, "luminance": 3.5},
    "character":    {"silhouette": 0.65, "cap": 8.0,  "luminance": 1.2},
    "object":       {"silhouette": 0.65, "cap": 16.0, "luminance": 2.1},
    "terrain":      {"silhouette": 0.12, "cap": 16.0, "luminance": 4.0},
}

# Precomputed sRGB byte -> linear float lookup table
_SRGB_LINEAR_LUT = np.array(
    [
        (v / 255.0) / 12.92 if (v / 255.0) <= 0.04045 else (((v / 255.0) + 0.055) / 1.055) ** 2.4
        for v in range(256)
    ],
    dtype=np.float64,
)

# CIELAB constants (D65)
_D65 = (0.95047, 1.0, 1.08883)
_LAB_EPSILON = 216.0 / 24389.0
_LAB_KAPPA = 24389.0 / 27.0

# Perceptual clustering thresholds (@xprite/lighter)
_REGION_DELTA_E_SQ = 10.0 * 10.0
_EDGE_DELTA_E_SQ = 6.0 * 6.0
_EDGE_ALPHA_STEP = 48

# Painted light estimation & normal tilt constants (@xprite/lighter)
_PAINTED_LIGHT_TILT_GAIN = 3.0
_ESTIMATE_FADE_LOW = 0.2
_ESTIMATE_FADE_HIGH = 0.45
_DELIGHT_ELEVATION_DEG = 45.0
_DELIGHT_AMBIENT = 0.15


def _lab_pivot(val: float) -> float:
    return math.cbrt(val) if val > _LAB_EPSILON else (_LAB_KAPPA * val + 16.0) / 116.0


def _rgb_to_lab(r: int, g: int, b: int) -> Tuple[float, float, float]:
    lr = float(_SRGB_LINEAR_LUT[r])
    lg = float(_SRGB_LINEAR_LUT[g])
    lb = float(_SRGB_LINEAR_LUT[b])
    x = _lab_pivot((lr * 0.4124564 + lg * 0.3575761 + lb * 0.1804375) / _D65[0])
    y = _lab_pivot((lr * 0.2126729 + lg * 0.7151522 + lb * 0.0721750) / _D65[1])
    z = _lab_pivot((lr * 0.0193339 + lg * 0.1191920 + lb * 0.9503041) / _D65[2])
    return (116.0 * y - 16.0, 500.0 * (x - y), 200.0 * (y - z))


def _unit3(vx: float, vy: float, vz: float) -> Tuple[float, float, float]:
    length = math.hypot(vx, vy, vz) or 1.0
    return vx / length, vy / length, vz / length


def _quantize_normal(vx: float, vy: float, vz: float, preset: str, scale: float) -> Tuple[float, float, float]:
    vx, vy, vz = _unit3(vx, vy, vz)
    tilt = math.hypot(vx, vy)
    if tilt < 0.12:
        return 0.0, 0.0, 1.0
    angle = round(math.atan2(vy, vx) / (math.pi / 4.0)) * (math.pi / 4.0)
    if preset == "architecture":
        elevation = min(0.9, 0.6 * scale)
    elif tilt < 0.3:
        elevation = 0.24
    elif tilt < 0.6:
        elevation = 0.48
    elif tilt < 0.85:
        elevation = 0.72
    else:
        elevation = 0.90
    nx = math.cos(angle) * elevation
    ny = math.sin(angle) * elevation
    nz = math.sqrt(max(0.0, 1.0 - elevation * elevation))
    return nx, ny, nz


def _segment_and_distance(arr: np.ndarray, region_mode: str = "perceptual"):
    """
    Computes foreground mask, Rec.709 luminance, connected color clusters
    (perceptual CIELAB Delta-E or exact RGB), foreground area, and Manhattan
    boundary distance field (ported from @xprite/lighter).
    """
    h, w, _ = arr.shape
    n_total = w * h
    flat_rgba = arr.reshape(-1, 4)

    fg = flat_rgba[:, 3] > 0
    lum = (
        0.2126 * flat_rgba[:, 0].astype(np.float32)
        + 0.7152 * flat_rgba[:, 1].astype(np.float32)
        + 0.0722 * flat_rgba[:, 2].astype(np.float32)
    ) / 255.0

    fg_area = int(np.count_nonzero(fg))
    if fg_area == 0:
        return fg, lum, [], np.full(n_total, -1, dtype=np.int32), np.zeros(n_total, dtype=np.float32), 0.0, 1.0, 0

    lo = float(np.min(lum[fg]))
    hi = float(np.max(lum[fg]))

    def adjacent(idx: int) -> List[int]:
        x = idx % w
        y = idx // w
        out = []
        if x > 0:
            out.append(idx - 1)
        if x < w - 1:
            out.append(idx + 1)
        if y > 0:
            out.append(idx - w)
        if y < h - 1:
            out.append(idx + w)
        return out

    labels = np.full(n_total, -1, dtype=np.int32)
    clusters = []
    r_ch = flat_rgba[:, 0]
    g_ch = flat_rgba[:, 1]
    b_ch = flat_rgba[:, 2]
    a_ch = flat_rgba[:, 3]

    perceptual = region_mode == "perceptual"
    if perceptual:
        lab_cache: Dict[int, Tuple[float, float, float]] = {}

        def get_lab(rgb_key: int) -> Tuple[float, float, float]:
            val = lab_cache.get(rgb_key)
            if val is not None:
                return val
            val = _rgb_to_lab((rgb_key >> 16) & 255, (rgb_key >> 8) & 255, rgb_key & 255)
            if len(lab_cache) >= 4096:
                lab_cache.clear()
            lab_cache[rgb_key] = val
            return val

        def lab_dist_sq(c1: int, c2: int) -> float:
            if c1 == c2:
                return 0.0
            a1 = get_lab(c1)
            a2 = get_lab(c2)
            dl = a1[0] - a2[0]
            da = a1[1] - a2[1]
            db = a1[2] - a2[2]
            return dl * dl + da * da + db * db

        rgb_keys = (
            (r_ch.astype(np.int32) << 16)
            | (g_ch.astype(np.int32) << 8)
            | b_ch.astype(np.int32)
        )

    for i in range(n_total):
        if fg[i] and labels[i] < 0:
            cid = len(clusters)
            labels[i] = cid
            q = deque([i])
            pixels = []
            lum_sum = 0.0
            if perceptual:
                seed_rgb = int(rgb_keys[i])
                while q:
                    p = q.popleft()
                    pixels.append(p)
                    lum_sum += float(lum[p])
                    p_rgb = int(rgb_keys[p])
                    p_a = int(a_ch[p])
                    for nb in adjacent(p):
                        if fg[nb] and labels[nb] < 0:
                            if abs(p_a - int(a_ch[nb])) >= _EDGE_ALPHA_STEP:
                                continue
                            nb_rgb = int(rgb_keys[nb])
                            if (
                                lab_dist_sq(p_rgb, nb_rgb) <= _EDGE_DELTA_E_SQ
                                and lab_dist_sq(seed_rgb, nb_rgb) <= _REGION_DELTA_E_SQ
                            ):
                                labels[nb] = cid
                                q.append(nb)
                clusters.append({"pixels": pixels, "value": lum_sum / len(pixels)})
            else:
                ri, gi, bi = int(r_ch[i]), int(g_ch[i]), int(b_ch[i])
                while q:
                    p = q.popleft()
                    pixels.append(p)
                    for nb in adjacent(p):
                        if (
                            fg[nb]
                            and labels[nb] < 0
                            and int(r_ch[nb]) == ri
                            and int(g_ch[nb]) == gi
                            and int(b_ch[nb]) == bi
                        ):
                            labels[nb] = cid
                            q.append(nb)
                clusters.append({"pixels": pixels, "value": float(lum[i])})

    # Manhattan BFS boundary distance field
    distance = np.full(n_total, float(n_total), dtype=np.float32)
    q = deque()
    for i in range(n_total):
        if fg[i]:
            x = i % w
            y = i // w
            if x == 0 or x == w - 1 or y == 0 or y == h - 1 or any(not fg[nb] for nb in adjacent(i)):
                distance[i] = 1.0
                q.append(i)

    while q:
        p = q.popleft()
        dp = distance[p] + 1.0
        for nb in adjacent(p):
            if fg[nb] and distance[nb] > dp:
                distance[nb] = dp
                q.append(nb)

    return fg, lum, clusters, labels, distance, lo, hi, fg_area


def _angular_distance_deg(a: float, b: float) -> float:
    return abs(((a - b + 540.0) % 360.0) - 180.0)


def _fit_light_direction(samples: list) -> Optional[dict]:
    """Fit image-plane light azimuth (0=right, 90=up) against contour normal samples."""
    min_fit_pixels = 40
    fit_eps = 1e-9
    angle_step = 5
    angle_count = 360 // angle_step
    elevations = (25.0, 45.0, 65.0)
    rad_per_deg = math.pi / 180.0

    if len(samples) < min_fit_pixels:
        return None

    by_group: Dict[int, list] = {}
    for s in samples:
        by_group.setdefault(s[5], []).append(s)

    groups = []
    observed_variance = 0.0
    for grp in by_group.values():
        cnt = len(grp)
        mean_l = sum(s[3] for s in grp) / cnt
        residuals = [s[3] - mean_l for s in grp]
        weight = 1.0 / math.sqrt(cnt)
        observed_variance += weight * sum(r * r for r in residuals)
        groups.append((grp, residuals, weight))

    if observed_variance <= fit_eps:
        return None

    scores = [-1.0] * angle_count
    winner = 0
    for slot in range(angle_count):
        ang = slot * angle_step * rad_per_deg
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)
        best_slot = -1.0
        for elev in elevations:
            h_rad = elev * rad_per_deg
            cos_h = math.cos(h_rad)
            lx = cos_a * cos_h
            ly = sin_a * cos_h
            lz = math.sin(h_rad)
            pred_var = 0.0
            cov = 0.0
            for grp, residuals, weight in groups:
                s_pred = 0.0
                s_sq = 0.0
                s_cross = 0.0
                for idx_s, sample in enumerate(grp):
                    pred = sample[0] * lx + sample[1] * ly + sample[2] * lz
                    if pred > 0.0:
                        s_pred += pred
                        s_sq += pred * pred
                        s_cross += pred * residuals[idx_s]
                pred_var += weight * (s_sq - (s_pred * s_pred) / len(grp))
                cov += weight * s_cross
            if pred_var > fit_eps:
                sc = cov / math.sqrt(pred_var * observed_variance)
                if sc > best_slot:
                    best_slot = sc
        scores[slot] = best_slot
        if scores[slot] > scores[winner]:
            winner = slot

    return {
        "angle": float(winner * angle_step),
        "fit": float(scores[winner]),
        "opposite_margin": float(scores[winner] - scores[(winner + angle_count // 2) % angle_count]),
    }


def estimate_painted_light(
    arr: np.ndarray,
    shading_arr: Optional[np.ndarray] = None,
) -> Optional[dict]:
    """
    Estimate painted-in directional light azimuth (degrees, 0=right, 90=up) and
    correlation fit in [0, 1] from contour shading (ported from @xprite/lighter).
    Returns {"angle": float, "fit": float} or None if no reliable light signal exists.
    """
    h, w, _ = arr.shape
    count = w * h
    if count > 1_048_576:
        return None
    if shading_arr is not None and (shading_arr.shape[0] != h or shading_arr.shape[1] != w):
        return None

    solid_alpha = 128
    contour_depth = 4.0
    distance_cap = contour_depth + 3.0
    min_slope = 0.15
    min_component_pixels = 24
    min_fit_pixels = 40
    min_group_pixels = 8
    chroma_steps = 16
    chroma_buckets = chroma_steps + 1
    tone_steps = 32
    min_tone_pixels = 2
    min_tones = 3
    min_contrast = 0.025
    min_fit = 0.3
    min_opposite_margin = 0.12
    min_component_fit = 0.25
    max_holdout_drift = 45.0
    max_component_drift = 75.0
    holdout_count = 4
    min_tile_size = 4
    tiles_per_sprite = 5
    block_row_step = 7
    max_samples = 8192

    flat = arr.reshape(-1, 4)
    mask = flat[:, 3] >= solid_alpha
    area = int(np.count_nonzero(mask))
    if area < min_fit_pixels:
        return None

    ys_fg, xs_fg = np.where(arr[:, :, 3] >= solid_alpha)
    left = int(xs_fg.min())
    top = int(ys_fg.min())

    def index_at(x: int, y: int) -> int:
        return y * w + x if (0 <= x < w and 0 <= y < h) else -1

    distance = np.zeros(count, dtype=np.float32)
    labels = np.full(count, -1, dtype=np.int32)
    component_sizes: List[int] = []
    cardinals = ((-1, 0), (1, 0), (0, -1), (0, 1))

    for i in range(count):
        if not mask[i]:
            continue
        x = i % w
        y = i // w
        is_edge = False
        for dx, dy in cardinals:
            nb = index_at(x + dx, y + dy)
            if nb < 0 or not mask[nb]:
                is_edge = True
                break
        distance[i] = 1.0 if is_edge else distance_cap
        if labels[i] >= 0:
            continue
        cid = len(component_sizes)
        labels[i] = cid
        q = deque([i])
        comp_len = 0
        while q:
            p = q.popleft()
            comp_len += 1
            px = p % w
            py = p // w
            for dx, dy in cardinals:
                nb = index_at(px + dx, py + dy)
                if nb >= 0 and mask[nb] and labels[nb] < 0:
                    labels[nb] = cid
                    q.append(nb)
        component_sizes.append(comp_len)

    # Two bounded chamfer passes
    chamfer = ((-1, 0, 1.0), (0, -1, 1.0), (-1, -1, math.sqrt(2.0)), (1, -1, math.sqrt(2.0)))
    for sign in (1, -1):
        rng = range(count) if sign == 1 else range(count - 1, -1, -1)
        for i in rng:
            if not mask[i] or distance[i] == 1.0:
                continue
            x = i % w
            y = i // w
            di = float(distance[i])
            for dx, dy, cost in chamfer:
                nb = index_at(x + dx * sign, y + dy * sign)
                if nb >= 0 and mask[nb]:
                    cand = float(distance[nb]) + cost
                    if cand < di:
                        di = cand
            distance[i] = di

    # Smooth distance field
    smooth = np.zeros(count, dtype=np.float32)
    for i in range(count):
        if not mask[i]:
            continue
        s = float(distance[i]) * 2.0
        wt = 2.0
        x = i % w
        y = i // w
        for dx, dy in cardinals:
            nb = index_at(x + dx, y + dy)
            if nb >= 0 and mask[nb]:
                s += float(distance[nb])
                wt += 1.0
        smooth[i] = s / wt

    tile_size = max(min_tile_size, int(math.sqrt(area) // tiles_per_sprite))
    flat_shading = shading_arr.reshape(-1, 4) if shading_arr is not None else None

    # Sample tuple: (nx, ny, nz, luminance, component, group, block)
    samples = []
    for i in range(count):
        if not mask[i] or distance[i] > contour_depth:
            continue
        comp = int(labels[i])
        if component_sizes[comp] < min_component_pixels:
            continue
        x = i % w
        y = i // w
        l_idx = index_at(x - 1, y)
        r_idx = index_at(x + 1, y)
        d_idx = index_at(x, y + 1)
        u_idx = index_at(x, y - 1)
        nx = ((float(smooth[l_idx]) if l_idx >= 0 else 0.0) - (float(smooth[r_idx]) if r_idx >= 0 else 0.0)) * 0.5
        ny = ((float(smooth[d_idx]) if d_idx >= 0 else 0.0) - (float(smooth[u_idx]) if u_idx >= 0 else 0.0)) * 0.5
        length = math.hypot(nx, ny, 1.0)
        if math.hypot(nx, ny) / length < min_slope:
            continue

        r_v, g_v, b_v = int(flat[i, 0]), int(flat[i, 1]), int(flat[i, 2])
        if flat_shading is not None:
            sa = float(flat_shading[i, 3]) / 255.0
            sl = (0.2126 * flat_shading[i, 0] + 0.7152 * flat_shading[i, 1] + 0.0722 * flat_shading[i, 2]) / 255.0
            luminance = 0.5 + sa * (sl - 0.5)
            group = comp
        else:
            if max(r_v, g_v, b_v) < 20:
                continue
            rgb_sum = float(r_v + g_v + b_v)
            red_b = round((r_v / rgb_sum) * chroma_steps)
            green_b = round((g_v / rgb_sum) * chroma_steps)
            group = (comp * chroma_buckets + red_b) * chroma_buckets + green_b
            luminance = (0.2126 * r_v + 0.7152 * g_v + 0.0722 * b_v) / 255.0

        block = (((y - top) // tile_size) * block_row_step + ((x - left) // tile_size)) % holdout_count
        samples.append((nx / length, ny / length, 1.0 / length, luminance, comp, group, block))

    if len(samples) > max_samples:
        total_s = len(samples)
        bounded = [samples[(k * total_s) // max_samples] for k in range(max_samples)]
    else:
        bounded = samples

    by_group: Dict[int, list] = {}
    for s in bounded:
        by_group.setdefault(s[5], []).append(s)

    supported = []
    contrast = 0.0
    for grp in by_group.values():
        if len(grp) < min_group_pixels:
            continue
        tones = [0] * (tone_steps + 1)
        for s in grp:
            tones[min(tone_steps, max(0, round(s[3] * tone_steps)))] += 1
        if sum(1 for t in tones if t >= min_tone_pixels) < min_tones:
            continue
        mean_l = sum(s[3] for s in grp) / len(grp)
        for s in grp:
            diff = s[3] - mean_l
            contrast += diff * diff
            supported.append(s)

    if len(supported) < min_fit_pixels or contrast < len(supported) * (min_contrast ** 2):
        return None

    candidate = _fit_light_direction(supported)
    if (
        candidate is None
        or candidate["fit"] < min_fit
        or candidate["opposite_margin"] < min_opposite_margin
    ):
        return None

    # 4-fold spatial holdout consistency check
    for blk in range(holdout_count):
        fold_fit = _fit_light_direction([s for s in supported if s[6] != blk])
        if fold_fit is None or _angular_distance_deg(fold_fit["angle"], candidate["angle"]) > max_holdout_drift:
            return None

    # Per-component consistency check
    by_comp: Dict[int, list] = {}
    for s in supported:
        by_comp.setdefault(s[4], []).append(s)
    for comp_samples in by_comp.values():
        c_fit = _fit_light_direction(comp_samples)
        if (
            c_fit is not None
            and c_fit["fit"] >= min_component_fit
            and _angular_distance_deg(c_fit["angle"], candidate["angle"]) > max_component_drift
        ):
            return None

    return {"angle": candidate["angle"], "fit": round(candidate["fit"], 4)}


def _painted_light_signal(
    w: int,
    h: int,
    fg: np.ndarray,
    fg_area: int,
    lum: np.ndarray,
    shading_arr: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Signed luminance relative to surrounding foreground (ported from @xprite/lighter)."""
    radius = min(12, max(2, round(math.sqrt(max(1, fg_area)) / 4.0)))
    if shading_arr is not None:
        flat_s = shading_arr.reshape(-1, 4).astype(np.float32)
        sa = flat_s[:, 3] / 255.0
        sl = (0.2126 * flat_s[:, 0] + 0.7152 * flat_s[:, 1] + 0.0722 * flat_s[:, 2]) / 255.0
        brightness = (0.5 + sa * (sl - 0.5)).reshape(h, w)
    else:
        brightness = lum.reshape(h, w).astype(np.float32)

    fg2d = fg.reshape(h, w).astype(np.float32)
    masked_b = brightness * fg2d

    # Fast 2D separable sliding-window box sum via cumulative sums
    pad = radius
    b_pad = np.pad(masked_b, ((0, 0), (pad, pad)), mode="constant")
    f_pad = np.pad(fg2d, ((0, 0), (pad, pad)), mode="constant")
    cs_b = np.pad(np.cumsum(b_pad, axis=1), ((0, 0), (1, 0)), mode="constant")
    cs_f = np.pad(np.cumsum(f_pad, axis=1), ((0, 0), (1, 0)), mode="constant")
    win = 2 * pad + 1
    row_sums = cs_b[:, win:] - cs_b[:, :-win]
    row_cnts = cs_f[:, win:] - cs_f[:, :-win]

    rs_pad = np.pad(row_sums, ((pad, pad), (0, 0)), mode="constant")
    rc_pad = np.pad(row_cnts, ((pad, pad), (0, 0)), mode="constant")
    cs_rs = np.pad(np.cumsum(rs_pad, axis=0), ((1, 0), (0, 0)), mode="constant")
    cs_rc = np.pad(np.cumsum(rc_pad, axis=0), ((1, 0), (0, 0)), mode="constant")
    box_sums = cs_rs[win:, :] - cs_rs[:-win, :]
    box_cnts = cs_rc[win:, :] - cs_rc[:-win, :]

    signal = np.zeros((h, w), dtype=np.float32)
    valid = (fg2d > 0.5) & (box_cnts > 0.5)
    signal[valid] = brightness[valid] - (box_sums[valid] / box_cnts[valid])
    return signal.reshape(-1)


def _align_straight_architecture_edges(
    dirs: np.ndarray,
    fg: np.ndarray,
    w: int,
    h: int,
    sprite_scale: float,
    strength: float,
) -> None:
    """Keep straight exterior architectural edges continuous across brick color changes."""
    depth = max(1, round(sprite_scale * 2.0))
    min_length = max(12, depth * 4)
    n_total = w * h
    dist = np.full(n_total, depth, dtype=np.int32)
    edge_x = np.zeros(n_total, dtype=np.int32)
    edge_y = np.zeros(n_total, dtype=np.int32)

    for horizontal in (True, False):
        line_count, line_length = (h, w) if horizontal else (w, h)
        line_stride, pixel_stride = (w, 1) if horizontal else (1, w)
        for side in (-1, 1):
            for line in range(line_count):
                start = line * line_stride
                outside = (line + side < 0) or (line + side >= line_count)
                run_start = 0
                for offset in range(line_length + 1):
                    pixel = start + offset * pixel_stride
                    if (
                        offset < line_length
                        and fg[pixel]
                        and (outside or not fg[pixel + side * line_stride])
                    ):
                        continue
                    if offset - run_start >= min_length:
                        for along in range(run_start, offset):
                            for step in range(depth):
                                inside = line - step * side
                                p = inside * line_stride + along * pixel_stride
                                if inside < 0 or inside >= line_count or not fg[p]:
                                    break
                                if step > dist[p]:
                                    continue
                                if step < dist[p]:
                                    dist[p] = step
                                    edge_x[p] = 0
                                    edge_y[p] = 0
                                if horizontal:
                                    edge_y[p] -= side
                                else:
                                    edge_x[p] += side
                    run_start = offset + 1

    for p in range(n_total):
        ex = int(edge_x[p])
        ey = int(edge_y[p])
        length = math.hypot(ex, ey)
        if length == 0.0:
            continue
        tilt = min(0.95, 0.35 * strength * (1.0 - dist[p] / depth))
        dirs[p, 0] = (ex * tilt) / length
        dirs[p, 1] = (ey * tilt) / length
        dirs[p, 2] = math.sqrt(max(0.0, 1.0 - tilt * tilt))


def generate_faceted_normal_map(
    image_path: Path,
    output_path: Path = None,
    preset: str = "character",
    shape_strength: float = None,
    normal_strength: float = 100.0,
    facets: float = None,
    edge_width: int = None,
    merge_outlines: bool = True,
    invert_y: bool = False,
    region_mode: str = "perceptual",
    painted_light_angle: Optional[float] = None,
    painted_light_influence: float = 60.0,
    shading_path: Optional[Path] = None,
    return_meta: bool = False,
):
    """
    Generates a crisp, cluster-faceted pixel-art normal map using the upgraded
    @xprite/lighter + Moonfell Pixel Art Lighter algorithm (Lab-aware clustering,
    sprite-scale-adaptive height ramp & faceting, painted-light estimation & tilting,
    and architecture straight-edge alignment).
    """
    preset = preset if preset in PRESET_DEFAULTS else "character"
    defaults = PRESET_DEFAULTS[preset]
    profile = HEIGHT_PROFILES[preset]
    strength_val = shape_strength if shape_strength is not None else defaults["strength"]
    facets_val = facets if facets is not None else defaults["facets"]
    edge_w = edge_width if edge_width is not None else defaults["edge_width"]

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape
    n_total = w * h
    flat_rgba = arr.reshape(-1, 4)

    shading_arr = None
    if shading_path is not None and Path(shading_path).exists():
        s_img = Image.open(shading_path).convert("RGBA")
        if s_img.size != (w, h):
            raise ValueError(f"Shading image dimensions {s_img.size} must match sprite {(w, h)}")
        shading_arr = np.array(s_img, dtype=np.uint8)

    fg, lum, clusters, labels, distance, lo, hi, fg_area = _segment_and_distance(arr, region_mode=region_mode)
    if fg_area == 0:
        print(f"Warning: {image_path} has no opaque pixels.")
        return (None, {}) if return_meta else None

    def adjacent(idx: int) -> List[int]:
        x = idx % w
        y = idx // w
        out = []
        if x > 0:
            out.append(idx - 1)
        if x < w - 1:
            out.append(idx + 1)
        if y > 0:
            out.append(idx - w)
        if y < h - 1:
            out.append(idx + w)
        return out

    lum_range = hi - lo

    def normalized(idx: int) -> float:
        return (float(lum[idx]) - lo) / lum_range if lum_range > 1e-5 else 0.75

    # Resolve painted light angle & influence
    influence = max(0.0, min(100.0, float(painted_light_influence))) / 100.0
    estimate = None
    angle_deg = 135.0
    if influence > 0.0:
        if painted_light_angle is not None:
            angle_deg = float(painted_light_angle) % 360.0
        else:
            estimate = estimate_painted_light(arr, shading_arr)
            if estimate is not None:
                angle_deg = estimate["angle"]
                fade = min(1.0, max(0.0, (estimate["fit"] - _ESTIMATE_FADE_LOW) / (_ESTIMATE_FADE_HIGH - _ESTIMATE_FADE_LOW)))
                influence *= fade
            else:
                influence = 0.0

    # Detect thin dark outline clusters
    thin = np.zeros(n_total, dtype=bool)
    if merge_outlines:
        for cluster in clusters:
            if cluster["value"] > lo + lum_range * 0.24:
                continue
            interior = 0
            for p in cluster["pixels"]:
                nbs = adjacent(p)
                if len(nbs) == 4 and all(labels[nb] == labels[p] for nb in nbs):
                    interior += 1
            if interior / len(cluster["pixels"]) < 0.15:
                for p in cluster["pixels"]:
                    thin[p] = True

    sprite_scale = min(2.0, math.sqrt(fg_area) / 64.0)
    bevel_pow = min(1.0, max(0.5, 0.5 + (sprite_scale - 0.5) * 0.5))
    scale = strength_val / 100.0
    cap = profile["cap"]
    sil_mult = profile["silhouette"] * math.sqrt(cap)
    lum_mult = profile["luminance"] * (1.0 - influence)

    field = np.zeros(n_total, dtype=np.float32)
    for i in range(n_total):
        if fg[i]:
            convex = ((min(float(distance[i]), cap) / cap) ** bevel_pow) * sil_mult
            field[i] = convex + normalized(i) * lum_mult

    # Edge-width smoothing passes over height field
    for _ in range(max(0, int(edge_w))):
        blurred = np.zeros(n_total, dtype=np.float32)
        for i in range(n_total):
            if fg[i]:
                s = field[i] * 2.0
                cnt = 2
                for nb in adjacent(i):
                    if fg[nb]:
                        s += field[nb]
                        cnt += 1
                blurred[i] = s / cnt
        field = blurred

    light_sig = _painted_light_signal(w, h, fg, fg_area, lum, shading_arr) if influence > 0.0 else None
    angle_rad = math.radians(angle_deg)
    light_x = math.cos(angle_rad) * influence * _PAINTED_LIGHT_TILT_GAIN
    light_y = math.sin(angle_rad) * influence * _PAINTED_LIGHT_TILT_GAIN

    def at_field(idx: int, fallback: float) -> float:
        return float(field[idx]) if (0 <= idx < n_total and fg[idx]) else fallback

    def normal_at(pixel: int) -> Tuple[float, float, float]:
        x = pixel % w
        y = pixel // w
        fi = float(field[pixel])
        dx = (at_field(pixel + 1, fi) if x < w - 1 else fi) - (at_field(pixel - 1, fi) if x > 0 else fi)
        dy = (at_field(pixel + w, fi) if y < h - 1 else fi) - (at_field(pixel - w, fi) if y > 0 else fi)
        if influence <= 0.0:
            return _unit3(-dx * scale, dy * scale, 1.0)
        tilt = float(light_sig[pixel])
        return _unit3(-dx * scale + light_x * tilt, dy * scale + light_y * tilt, 1.0)

    dirs = np.zeros((n_total, 3), dtype=np.float32)
    dirs[:, 2] = 1.0
    for i in range(n_total):
        if fg[i]:
            dirs[i] = normal_at(i)

    # Sprite-scale-adaptive Cluster Averaging & Facet Splitting (@xprite/lighter)
    facet_strength = facets_val / 100.0
    min_facet_area = max(8, round((180.0 - facets_val * 1.1) * sprite_scale))
    facet_support_factor = 1.5 - facet_strength * 0.75
    facet_dot_limit = 0.7 + facet_strength * 0.1

    for cluster in clusters:
        sx, sy, sz = 0.0, 0.0, 0.0
        for p in cluster["pixels"]:
            if preset == "architecture" and math.hypot(float(dirs[p, 0]), float(dirs[p, 1])) < 0.06:
                continue
            sx += float(dirs[p, 0])
            sy += float(dirs[p, 1])
            sz += float(dirs[p, 2])
        if sz == 0.0:
            sx, sy, sz = 0.0, 0.0, 1.0
        avg_x, avg_y, avg_z = _unit3(sx, sy, sz)

        groups: Dict[int, List[int]] = {}
        split = facets_val > 0 and len(cluster["pixels"]) >= min_facet_area
        if split:
            for p in cluster["pixels"]:
                dx, dy = float(dirs[p, 0]), float(dirs[p, 1])
                tilt = math.hypot(dx, dy)
                key = (round(math.atan2(dy, dx) / (math.pi / 2.0)) + 4) % 4 if tilt > 0.35 else 9
                groups.setdefault(key, []).append(p)

        min_support = max(2, math.ceil(math.sqrt(len(cluster["pixels"])) * facet_support_factor))
        supported = [g for g in groups.values() if len(g) >= min_support]
        allow = False
        if len(supported) >= 2:
            means = []
            for g in supported:
                gx = sum(float(dirs[p, 0]) for p in g)
                gy = sum(float(dirs[p, 1]) for p in g)
                gz = sum(float(dirs[p, 2]) for p in g)
                means.append(_unit3(gx, gy, gz))
            for i_m in range(len(means)):
                for j_m in range(i_m):
                    dot = means[i_m][0] * means[j_m][0] + means[i_m][1] * means[j_m][1] + means[i_m][2] * means[j_m][2]
                    if dot < facet_dot_limit:
                        allow = True

        base = _quantize_normal(avg_x, avg_y, avg_z, preset, scale)
        for p in cluster["pixels"]:
            dirs[p] = base

        if allow:
            for g in supported:
                gx, gy, gz = 0.0, 0.0, 0.0
                for p in g:
                    vx, vy, vz = normal_at(p)
                    gx += vx
                    gy += vy
                    gz += vz
                gv = _quantize_normal(gx, gy, gz, preset, scale)
                for p in g:
                    dirs[p] = gv

    # Outline merging: propagate non-thin interior normals into thin outline clusters
    if merge_outlines:
        assigned = np.zeros(n_total, dtype=bool)
        q = deque()
        for i in range(n_total):
            if fg[i] and not thin[i]:
                assigned[i] = True
                q.append(i)
        while q:
            p = q.popleft()
            for nb in adjacent(p):
                if fg[nb] and not assigned[nb]:
                    assigned[nb] = True
                    dirs[nb] = dirs[p]
                    q.append(nb)

    # Cluster-scoped orphan 1-2px normal island de-speckling
    seen = np.zeros(n_total, dtype=bool)
    for i in range(n_total):
        if fg[i] and not seen[i]:
            group = []
            q = deque([i])
            seen[i] = True
            ix, iy = float(dirs[i, 0]), float(dirs[i, 1])
            li = int(labels[i])
            while q:
                p = q.popleft()
                group.append(p)
                for nb in adjacent(p):
                    if labels[nb] == li and not seen[nb]:
                        if abs(float(dirs[nb, 0]) - ix) < 0.001 and abs(float(dirs[nb, 1]) - iy) < 0.001:
                            seen[nb] = True
                            q.append(nb)
            if len(group) <= 2:
                group_set = set(group)
                neighbors = [nb for p in group for nb in adjacent(p) if labels[nb] == li and nb not in group_set]
                if neighbors:
                    nb0 = neighbors[0]
                    for p in group:
                        dirs[p] = dirs[nb0]

    # Architecture straight exterior edge alignment
    if preset == "architecture" and scale > 0.0:
        _align_straight_architecture_edges(dirs, fg, w, h, sprite_scale, scale)

    normal_gain = normal_strength / 100.0
    out_rgba = np.zeros((n_total, 4), dtype=np.uint8)
    for i in range(n_total):
        if fg[i]:
            ny_dir = -float(dirs[i, 1]) if invert_y else float(dirs[i, 1])
            nx, ny, nz = _unit3(float(dirs[i, 0]) * normal_gain, ny_dir * normal_gain, float(dirs[i, 2]))
        else:
            nx, ny, nz = 0.0, 0.0, 1.0
        out_rgba[i, 0] = int(round((nx + 1.0) * 127.5))
        out_rgba[i, 1] = int(round((ny + 1.0) * 127.5))
        out_rgba[i, 2] = int(round((nz + 1.0) * 127.5))
        out_rgba[i, 3] = flat_rgba[i, 3]

    normal_img = Image.fromarray(out_rgba.reshape((h, w, 4)), mode="RGBA")
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}_n.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normal_img.save(output_path)

    meta = {
        "region_mode": region_mode,
        "painted_light_estimate": estimate,
        "painted_light_angle_used": round(angle_deg, 2) if influence > 0.0 else None,
        "painted_light_influence_used": round(influence * 100.0, 1),
    }
    print(f"Generated faceted normal map ({preset}, {region_mode}): {output_path} ({w}x{h})")
    return (output_path, meta) if return_meta else output_path


def generate_light_mask(
    image_path: Path,
    output_path: Path = None,
    preset: str = "object",
    strength: float = None,
    floor: float = None,
    ceiling: float = 255.0,
    cavity: float = None,
    region_mode: str = "exact-rgb",
) -> Path:
    """
    Generates a cavity-aware Light Mask ('_m.png') using the @xprite/lighter / Moonfell algorithm.
    """
    preset = preset if preset in PRESET_DEFAULTS else "object"
    defaults = PRESET_DEFAULTS[preset]
    strength_val = (strength if strength is not None else defaults["strength"]) / 100.0
    floor_val = (floor if floor is not None else defaults["floor"]) / 255.0
    ceil_val = ceiling / 255.0
    cavity_val = (cavity if cavity is not None else defaults["cavity"]) / 100.0

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape
    n_total = w * h
    flat_rgba = arr.reshape(-1, 4)

    fg, lum, clusters, labels, _, lo, hi, _ = _segment_and_distance(arr, region_mode=region_mode)
    lum_range = hi - lo

    def adjacent(idx: int) -> List[int]:
        x = idx % w
        y = idx // w
        out = []
        if x > 0:
            out.append(idx - 1)
        if x < w - 1:
            out.append(idx + 1)
        if y > 0:
            out.append(idx - w)
        if y < h - 1:
            out.append(idx + w)
        return out

    out_rgba = np.zeros((n_total, 4), dtype=np.uint8)
    for cluster in clusters:
        val = cluster["value"]
        t = (val - lo) / lum_range if lum_range > 1e-5 else 0.75
        receive = floor_val + (1.0 - floor_val) * (t ** 1.15)
        if cavity_val > 0 and t < 0.35:
            surrounded = 0
            for p in cluster["pixels"]:
                higher = 0
                total = 0
                for nb in adjacent(p):
                    if fg[nb] and labels[nb] != labels[p]:
                        total += 1
                        if lum[nb] > val + lum_range * 0.15:
                            higher += 1
                if total > 0 and (higher / total) > 0.5:
                    surrounded += 1
            receive *= 1.0 - cavity_val * min(1.0, surrounded / max(1.0, math.sqrt(len(cluster["pixels"]))))
        receive = 1.0 - strength_val + strength_val * receive
        v = int(round(255.0 * max(0.0, min(ceil_val, receive))))
        for p in cluster["pixels"]:
            out_rgba[p, 0] = v
            out_rgba[p, 1] = v
            out_rgba[p, 2] = v
            out_rgba[p, 3] = flat_rgba[p, 3]

    mask_img = Image.fromarray(out_rgba.reshape((h, w, 4)), mode="RGBA")
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}_m.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask_img.save(output_path)
    print(f"Generated cavity light mask: {output_path} ({w}x{h})")
    return output_path


def _painted_light_gain_map(
    nx: np.ndarray,
    ny: np.ndarray,
    nz: np.ndarray,
    delight_angle: float,
    delight_influence: float = 100.0,
    invert_y: bool = False,
) -> np.ndarray:
    """
    Per-pixel linear gain dividing out directional light painted at `delight_angle`
    (+Y up azimuth, 45 deg elevation, ambient=0.15 + Lambert).
    """
    strength = max(0.0, min(100.0, float(delight_influence))) / 100.0
    if strength <= 0.0:
        return np.ones_like(nx, dtype=np.float32)
    az = math.radians(float(delight_angle))
    el = math.radians(_DELIGHT_ELEVATION_DEG)
    y_sign = -1.0 if invert_y else 1.0
    lx = math.cos(az) * math.cos(el)
    ly = math.sin(az) * math.cos(el) * y_sign
    lz = math.sin(el)
    facing = np.maximum(0.0, nx * lx + ny * ly + nz * lz)
    gain = 1.0 + strength * (1.0 / (_DELIGHT_AMBIENT + (1.0 - _DELIGHT_AMBIENT) * facing) - 1.0)
    return gain.astype(np.float32)


def remove_painted_light(
    sprite_path: Path,
    normal_path: Path,
    output_path: Path = None,
    angle: Optional[float] = None,
    influence: float = 100.0,
    invert_y: bool = False,
) -> Tuple[Optional[Path], Optional[float]]:
    """
    Divide out a baked-in directional light from an albedo sprite using its normal map,
    writing a flat-lit albedo PNG ('<stem>_delit.png') for dynamic 2D relighting.
    """
    sprite_img = Image.open(sprite_path).convert("RGBA")
    normal_img = Image.open(normal_path).convert("RGBA")
    if sprite_img.size != normal_img.size:
        raise ValueError(f"Normal map dimensions {normal_img.size} must match sprite {sprite_img.size}")

    s_arr = np.array(sprite_img, dtype=np.uint8)
    n_arr = np.array(normal_img, dtype=np.float32)

    if angle is None:
        est = estimate_painted_light(s_arr)
        if est is None:
            print("Warning: could not auto-estimate painted light direction for de-lighting; skipping.")
            return None, None
        angle = est["angle"]

    albedo_lin = _srgb_to_linear(s_arr[:, :, :3].astype(np.float32))
    alpha = s_arr[:, :, 3]
    fg = alpha > 0

    nx = (n_arr[:, :, 0] / 255.0) * 2.0 - 1.0
    ny = (n_arr[:, :, 1] / 255.0) * 2.0 - 1.0
    nz = (n_arr[:, :, 2] / 255.0) * 2.0 - 1.0
    n_len = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    nx, ny, nz = nx / n_len, ny / n_len, nz / n_len

    gain = _painted_light_gain_map(nx, ny, nz, angle, influence, invert_y=invert_y)
    out_rgb = np.zeros_like(s_arr[:, :, :3], dtype=np.uint8)
    for c in range(3):
        out_rgb[:, :, c] = _linear_to_srgb(albedo_lin[:, :, c] * gain)
    out_rgb[~fg] = 0

    delit_img = Image.fromarray(np.dstack([out_rgb, alpha]), mode="RGBA")
    if output_path is None:
        output_path = sprite_path.parent / f"{sprite_path.stem}_delit.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    delit_img.save(output_path)
    print(f"Saved de-lit flat albedo (angle={angle:.1f} deg, influence={influence:.0f}%): {output_path}")
    return output_path, float(angle)


def _edt_2d(mask: np.ndarray) -> np.ndarray:
    if HAS_SCIPY:
        return distance_transform_edt(mask).astype(np.float32)
    return mask.astype(np.float32)


def _gauss_2d(arr: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0.0:
        return arr.astype(np.float32)
    if HAS_SCIPY:
        return gaussian_filter(arr, sigma).astype(np.float32)
    return arr.astype(np.float32)


def outline_height(
    sprite: Image.Image,
    bevel: float = 5.0,
    top: float = 12.0,
    detail: float = 1.5,
) -> np.ndarray:
    """
    Height per pixel from the sprite's outline: a quarter-circle rounded bevel up from the
    1px-padded transparent edge, flat on top, plus centered luminance relief for surface detail.
    """
    a = np.asarray(sprite.convert("RGBA"), dtype=np.float32)
    inside = a[..., 3] > 127.0
    if not np.any(inside):
        return np.zeros(inside.shape, dtype=np.float32)
    d = _edt_2d(np.pad(inside, 1))[1:-1, 1:-1]
    r = np.clip(d / max(float(bevel), 1e-4), 0.0, 1.0)
    h = float(top) * np.sqrt(np.maximum(0.0, 1.0 - (1.0 - r) ** 2))
    lum = (a[..., :3] @ np.array([0.299, 0.587, 0.114], dtype=np.float32)) / 255.0
    h = h + float(detail) * (lum - float(lum[inside].mean()))
    return np.where(inside, h, 0.0).astype(np.float32)


def outline_normal_map_from_height(
    height: np.ndarray,
    blur: float = 0.7,
    invert_y: bool = False,
) -> Image.Image:
    """
    Normals from the slope of the heightmap: X -> red, up -> green (unless invert_y), Z -> blue.
    Flat/outside pixels evaluate to neutral (128, 128, 255).
    """
    gy, gx = np.gradient(_gauss_2d(height, blur))
    ny = -gy if invert_y else gy
    n = np.stack([-gx, ny, np.ones_like(gx)], axis=-1)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    rgb = np.clip(np.round((n * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def generate_outline_normal_map(
    image_path: Path,
    output_path: Path = None,
    bevel: float = 5.0,
    top: float = 12.0,
    detail: float = 1.5,
    blur: float = 0.7,
    invert_y: bool = False,
) -> Path:
    """Generate a sprite normal map from its silhouette outline + luminance detail."""
    sprite = Image.open(image_path).convert("RGBA")
    h = outline_height(sprite, bevel=bevel, top=top, detail=detail)
    norm_img = outline_normal_map_from_height(h, blur=blur, invert_y=invert_y)
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}_n.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    norm_img.save(output_path)
    return output_path


def generate_floor_tile_normal_map(
    image_path: Path,
    output_path: Path = None,
    bevel: float = 3.0,
    top: float = 2.5,
    detail: float = 1.0,
    blur: float = 0.7,
    gap_percentile: float = 30.0,
    invert_y: bool = False,
) -> Path:
    """
    Generate a seamless normal map for a tileable floor tile (no transparent edges)
    by tiling 3x3, thresholding dark mortar/stone gaps into alpha, running outline_height,
    and cropping back to the center tile.
    """
    tile = Image.open(image_path).convert("RGBA")
    w, h = tile.size
    floor = Image.new("RGBA", (w * 3, h * 3))
    for ty in range(3):
        for tx in range(3):
            floor.paste(tile, (tx * w, ty * h))
    gray = np.asarray(floor.convert("L"), dtype=np.float32)
    stones = _gauss_2d(gray, 0.8) > np.percentile(gray, gap_percentile)
    floor.putalpha(Image.fromarray((stones.astype(np.uint8) * 255), mode="L"))
    height = outline_height(floor, bevel=bevel, top=top, detail=detail)
    floor_norm = outline_normal_map_from_height(height, blur=blur, invert_y=invert_y)
    center_norm = floor_norm.crop((w, h, 2 * w, 2 * h))
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}_n.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    center_norm.save(output_path)
    return output_path


def step_light_eval(
    pos_xy: Tuple[np.ndarray, np.ndarray],
    albedo_rgb01: np.ndarray,
    normal_rgb: np.ndarray,
    light_xy: Tuple[float, float],
    light_height: float = 26.0,
    radius: float = 70.0,
    steps: int = 6,
    energy: float = 1.6,
    light_color: Tuple[float, float, float] = (1.0, 0.8, 0.56),
    ambient: Tuple[float, float, float] = (0.24, 0.25, 0.33),
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Exact Python mirror of the Godot stepped light() shader.
    Returns (lit_rgb_uint8, lit_scalar_float).
    """
    n = normal_rgb[..., :3].astype(np.float32) / 255.0 * 2.0 - 1.0
    n[..., 1] = -n[..., 1]
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)

    xx, yy = pos_xy
    dx = light_xy[0] - xx
    dy = light_xy[1] - yy
    dz = np.full_like(dx, float(light_height), dtype=np.float32)
    dist_xy = np.hypot(dx, dy)
    dist_3d = np.maximum(np.sqrt(dx * dx + dy * dy + dz * dz), 1e-6)

    falloff = np.clip(1.0 - dist_xy / max(float(radius), 1e-4), 0.0, 1.0) ** 1.2
    ndotl = np.maximum(0.0, (n[..., 0] * dx + n[..., 1] * dy + n[..., 2] * dz) / dist_3d)
    lit = falloff * ndotl
    if steps > 0:
        lit = np.ceil(lit * float(steps)) / float(steps)

    amb = np.array(ambient, dtype=np.float32)[None, None, :]
    lcol = np.array(light_color, dtype=np.float32)[None, None, :]
    out01 = np.clip(albedo_rgb01 * (amb + lcol * float(energy) * lit[..., None]), 0.0, 1.0)
    return np.round(out01 * 255.0).astype(np.uint8), lit


def run_outline_verification() -> dict:
    """
    Verify outline normal map, stepped lighting, and @xprite/lighter invariants:
      1. Round sprite middle row: leftmost inside R < 100, rightmost R > 156; top+1 G > 156.
      2. Pixels > 5 px outside sprite equal (128, 128, 255) within 1.
      3. Flat normal stepped falloff (steps=6, radius=70, height=26): 10->5/6, 35->2/6, >=70->0.
      4. Light left of round sprite -> left half brighter than right half.
      5. Steps=0 gives smooth light vs stepped.
      6. Perceptual CIELAB clustering groups close colors, stops at contrast/alpha/transparent edges.
      7. Painted light estimation detects top-left shading on a 24x24 shaded disc with fit >= 0.45.
      8. Delighting lifts shadow-facing side more than lit-facing side and is symmetric (0 vs 180 deg).
    """
    yy, xx = np.mgrid[:48, :48]
    circle = ((xx - 23.5) ** 2 + (yy - 23.5) ** 2) <= 14.0 ** 2
    sprite_arr = np.zeros((48, 48, 4), dtype=np.uint8)
    sprite_arr[circle] = (180, 120, 80, 255)
    sprite_img = Image.fromarray(sprite_arr, mode="RGBA")

    h = outline_height(sprite_img, bevel=5.0, top=12.0, detail=1.5)
    norm_arr = np.asarray(outline_normal_map_from_height(h, blur=0.7), dtype=np.uint8)

    mid_xs = np.where(circle[24, :])[0]
    left_r = int(norm_arr[24, mid_xs[0], 0])
    right_r = int(norm_arr[24, mid_xs[-1], 0])
    top_ys = np.where(circle[:, 24])[0]
    top_plus1_g = int(norm_arr[top_ys[0] + 1, 24, 1])

    dist_out = np.hypot(xx - 23.5, yy - 23.5) - 14.0
    far_outside = dist_out > 5.0
    neutral_diff = int(np.max(np.abs(norm_arr[far_outside].astype(np.int32) - np.array([128, 128, 255], dtype=np.int32))))

    flat_n = np.full((1, 80, 3), (128, 128, 255), dtype=np.uint8)
    albedo = np.ones((1, 80, 3), dtype=np.float32)
    gx, gy = np.meshgrid(np.arange(80, dtype=np.float32), np.array([0.0], dtype=np.float32))
    _, lit_stepped = step_light_eval((gx, gy), albedo, flat_n, light_xy=(0.0, 0.0), steps=6)
    _, lit_smooth = step_light_eval((gx, gy), albedo, flat_n, light_xy=(0.0, 0.0), steps=0)

    s10 = float(lit_stepped[0, 10])
    s35 = float(lit_stepped[0, 35])
    s70 = float(lit_stepped[0, 70])

    gx48, gy48 = np.meshgrid(np.arange(48, dtype=np.float32), np.arange(48, dtype=np.float32))
    albedo48 = sprite_arr[:, :, :3].astype(np.float32) / 255.0
    lit_round, _ = step_light_eval((gx48, gy48), albedo48, norm_arr, light_xy=(4.0, 23.5), steps=6)
    left_half_mean = float(lit_round[circle & (xx < 23)].mean())
    right_half_mean = float(lit_round[circle & (xx > 24)].mean())

    # 6. Perceptual CIELAB clustering check (matches @xprite/lighter unit test)
    seg_arr = np.array(
        [[[96, 96, 96, 255], [100, 100, 100, 255], [116, 116, 116, 255], [116, 116, 116, 180], [116, 116, 116, 0], [116, 116, 116, 180]]],
        dtype=np.uint8,
    )
    _, _, _, p_labels, _, _, _, _ = _segment_and_distance(seg_arr, region_mode="perceptual")
    _, _, _, e_labels, _, _, _, _ = _segment_and_distance(seg_arr, region_mode="exact-rgb")
    perceptual_ok = (p_labels.tolist() == [0, 0, 1, 2, -1, 3]) and (e_labels.tolist() == [0, 1, 2, 2, -1, 3])

    # 7. Painted light estimation on 24x24 top-left-lit disc
    disc_size = 24
    disc_arr = np.zeros((disc_size, disc_size, 4), dtype=np.uint8)
    for y_d in range(disc_size):
        for x_d in range(disc_size):
            dx_d = x_d - disc_size / 2.0 + 0.5
            dy_d = y_d - disc_size / 2.0 + 0.5
            if dx_d * dx_d + dy_d * dy_d < (disc_size / 2.0 - 1.0) ** 2:
                shade = round(70 + 140 * max(0.0, (-dx_d - dy_d) / disc_size + 0.5))
                disc_arr[y_d, x_d] = (shade, round(shade * 0.8), round(shade * 0.6), 255)
    light_est = estimate_painted_light(disc_arr)
    est_ok = light_est is not None and light_est["fit"] >= 0.45 and _angular_distance_deg(light_est["angle"], 135.0) <= 25.0

    # 8. Delight gain check (left-facing vs right-facing normal under 180 deg painted light)
    nx_t = np.array([[-0.71, 0.71]], dtype=np.float32)
    ny_t = np.array([[0.0, 0.0]], dtype=np.float32)
    nz_t = np.array([[0.704, 0.704]], dtype=np.float32)
    g180 = _painted_light_gain_map(nx_t, ny_t, nz_t, 180.0, 100.0)
    g0 = _painted_light_gain_map(nx_t, ny_t, nz_t, 0.0, 100.0)
    delight_ok = bool(
        g180[0, 1] > g180[0, 0] >= 1.0
        and abs(float(g180[0, 0]) - float(g0[0, 1])) < 1e-5
        and abs(float(g180[0, 1]) - float(g0[0, 0])) < 1e-5
    )

    checks = {
        "round_sprite_normal_directions": {
            "ok": left_r < 100 and right_r > 156 and top_plus1_g > 156,
            "left_r": left_r,
            "right_r": right_r,
            "top_plus1_g": top_plus1_g,
        },
        "outside_5px_neutral_128_128_255": {
            "ok": neutral_diff <= 1,
            "max_diff": neutral_diff,
        },
        "stepped_falloff_10_35_70px": {
            "ok": abs(s10 - 5.0 / 6.0) < 1e-5 and abs(s35 - 2.0 / 6.0) < 1e-5 and abs(s70) < 1e-5,
            "step_at_10px": round(s10, 4),
            "step_at_35px": round(s35, 4),
            "step_at_70px": round(s70, 4),
        },
        "left_lit_brighter_than_right": {
            "ok": left_half_mean > right_half_mean,
            "left_mean": round(left_half_mean, 2),
            "right_mean": round(right_half_mean, 2),
        },
        "steps_0_smooth_vs_stepped": {
            "ok": float(np.max(np.abs(lit_smooth - lit_stepped))) > 0.01,
        },
        "perceptual_cielab_clustering": {
            "ok": perceptual_ok,
            "perceptual_labels": p_labels.tolist(),
            "exact_rgb_labels": e_labels.tolist(),
        },
        "painted_light_estimation_disc": {
            "ok": est_ok,
            "estimate": light_est,
        },
        "delight_gain_asymmetry_and_mirror": {
            "ok": delight_ok,
            "gain_180": [round(float(g180[0, 0]), 3), round(float(g180[0, 1]), 3)],
        },
    }
    return {"ok": all(bool(v["ok"]) for v in checks.values()), "checks": checks}


def generate_normal_map(
    image_path: Path,
    output_path: Path = None,
    strength: float = 1.5,
    smoothness: float = 0.5,
    pillow_weight: float = 0.65,
    invert_y: bool = False,
    mode: str = "faceted",
    preset: str = "character",
    facets: float = None,
    edge_width: int = None,
    merge_outlines: bool = True,
    bevel: float = 5.0,
    top: float = 12.0,
    detail: float = 1.5,
    blur: float = 0.7,
    gap_percentile: float = 30.0,
    region_mode: str = "perceptual",
    painted_light_angle: Optional[float] = None,
    painted_light_influence: float = 60.0,
    shading_path: Optional[Path] = None,
    return_meta: bool = False,
):
    """
    Unified entry point. Supports:
      - 'faceted': @xprite/lighter + Moonfell cluster-faceted with Lab clustering & painted-light estimation (default)
      - 'outline': Quarter-circle bevel from 1px-padded outline + luminance detail
      - 'boxy': Low-bevel crate/box preset (bevel=1.5, top=3.6) preventing pillow look
      - 'floor-tile': Seamless 3x3 dark-gap threshold normal map for floor tiles
      - 'smooth': Classic continuous distance-transform Sobel
    """
    if mode == "outline":
        p = generate_outline_normal_map(
            image_path=image_path,
            output_path=output_path,
            bevel=bevel,
            top=top,
            detail=detail,
            blur=blur,
            invert_y=invert_y,
        )
        return (p, {}) if return_meta else p
    if mode == "boxy":
        b = 1.5 if bevel == 5.0 else bevel
        t = 12.0 * b / 5.0 if top == 12.0 else top
        p = generate_outline_normal_map(
            image_path=image_path,
            output_path=output_path,
            bevel=b,
            top=t,
            detail=detail,
            blur=blur,
            invert_y=invert_y,
        )
        return (p, {}) if return_meta else p
    if mode == "floor-tile":
        b = 3.0 if bevel == 5.0 else bevel
        t = 2.5 if top == 12.0 else top
        d = 1.0 if detail == 1.5 else detail
        p = generate_floor_tile_normal_map(
            image_path=image_path,
            output_path=output_path,
            bevel=b,
            top=t,
            detail=d,
            blur=blur,
            gap_percentile=gap_percentile,
            invert_y=invert_y,
        )
        return (p, {}) if return_meta else p
    if mode == "faceted":
        shape_str = strength * 50.0 if strength != 1.5 else None
        return generate_faceted_normal_map(
            image_path=image_path,
            output_path=output_path,
            preset=preset,
            shape_strength=shape_str,
            facets=facets,
            edge_width=edge_width,
            merge_outlines=merge_outlines,
            invert_y=invert_y,
            region_mode=region_mode,
            painted_light_angle=painted_light_angle,
            painted_light_influence=painted_light_influence,
            shading_path=shading_path,
            return_meta=return_meta,
        )

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    alpha = arr[:, :, 3] / 255.0
    mask = alpha > 0.1
    if not np.any(mask):
        print(f"Warning: {image_path} has no opaque pixels.")
        return (None, {}) if return_meta else None

    lum = (arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722) / 255.0
    if HAS_SCIPY:
        dist = distance_transform_edt(mask)
        max_dist = np.max(dist)
        if max_dist > 0:
            dist = dist / max_dist
    else:
        dist = mask.astype(np.float32)

    height_map = ((dist * pillow_weight) + (lum * (1.0 - pillow_weight))) * mask
    if HAS_SCIPY:
        dx = sobel(height_map, axis=1) * strength
        dy = sobel(height_map, axis=0) * strength
    else:
        dx = np.gradient(height_map, axis=1) * strength * 4.0
        dy = np.gradient(height_map, axis=0) * strength * 4.0

    if invert_y:
        dy = -dy

    dz = np.ones_like(dx)
    length = np.maximum(np.sqrt(dx * dx + dy * dy + dz * dz), 1e-6)
    nx, ny, nz = -dx / length, -dy / length, dz / length

    r = ((nx * 0.5 + 0.5) * 255.0).clip(0, 255)
    g = ((ny * 0.5 + 0.5) * 255.0).clip(0, 255)
    b = ((nz * 0.5 + 0.5) * 255.0).clip(0, 255)
    r[~mask], g[~mask], b[~mask] = 128, 128, 255

    normal_arr = np.stack([r, g, b, arr[:, :, 3]], axis=-1).astype(np.uint8)
    normal_img = Image.fromarray(normal_arr, mode="RGBA")
    if output_path is None:
        output_path = image_path.parent / f"{image_path.stem}_n.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normal_img.save(output_path)
    print(f"Generated smooth normal map: {output_path} ({normal_img.width}x{normal_img.height})")
    return (output_path, {}) if return_meta else output_path


def _srgb_to_linear(arr: np.ndarray) -> np.ndarray:
    c = arr / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.maximum(0.0, c)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1.0 / 2.4)) - 0.055)
    return np.clip(np.round(s * 255.0), 0, 255).astype(np.uint8)


def render_lighting_preview(
    sprite_path: Path,
    normal_path: Path,
    output_gif: Path,
    mask_path: Path = None,
    num_frames: int = 20,
    light_color=(255, 220, 150),
    power: float = 2.6,
    ambient: float = 0.22,
    steps: int = 0,
    delight_angle: Optional[float] = None,
    delight_influence: float = 100.0,
    invert_y: bool = False,
):
    """
    Renders an animated GIF showing a 3D point light orbiting the sprite.
    When steps > 0 (e.g. steps=6), renders quantized pixel-art stepped light bands.
    When delight_angle is provided, divides out painted-in lighting before relighting.
    """
    sprite_img = Image.open(sprite_path).convert("RGBA")
    normal_img = Image.open(normal_path).convert("RGBA")
    w, h = sprite_img.size

    s_arr = np.array(sprite_img, dtype=np.float32)
    n_arr = np.array(normal_img, dtype=np.float32)

    albedo_lin = _srgb_to_linear(s_arr[:, :, :3])
    alpha = s_arr[:, :, 3].astype(np.uint8)
    fg = alpha > 0

    nx = (n_arr[:, :, 0] / 255.0) * 2.0 - 1.0
    ny = (n_arr[:, :, 1] / 255.0) * 2.0 - 1.0
    nz = (n_arr[:, :, 2] / 255.0) * 2.0 - 1.0
    n_len = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    nx, ny, nz = nx / n_len, ny / n_len, nz / n_len

    if delight_angle is not None:
        gain = _painted_light_gain_map(nx, ny, nz, delight_angle, delight_influence, invert_y=invert_y)
        albedo_lin = albedo_lin * gain[:, :, None]

    if mask_path and mask_path.exists():
        m_arr = np.array(Image.open(mask_path).convert("RGBA"), dtype=np.float32)
        mask_val = (0.2126 * m_arr[:, :, 0] + 0.7152 * m_arr[:, :, 1] + 0.0722 * m_arr[:, :, 2]) / 255.0
    else:
        mask_val = np.ones((h, w), dtype=np.float32)

    light_lin = _srgb_to_linear(np.array(light_color, dtype=np.float32))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * 0.5, h * 0.5
    orbit_rx = max(16.0, w * 0.42)
    orbit_ry = max(16.0, h * 0.42)
    z_height = max(18.0, min(w, h) * 0.35)
    falloff_radius = max(48.0, max(w, h) * 0.9)
    y_sign = -1.0 if invert_y else 1.0

    frames = []
    for i in range(num_frames):
        angle = (2.0 * math.pi * i) / num_frames
        lx = cx + math.cos(angle) * orbit_rx
        ly = cy + math.sin(angle) * orbit_ry

        dx = lx - xx
        dy = (yy - ly) * y_sign
        d = np.maximum(1e-6, np.sqrt(dx * dx + dy * dy + z_height * z_height))
        diffuse = np.maximum(0.0, (nx * dx + ny * dy + nz * z_height) / d)
        atten = 1.0 / (1.0 + (d / falloff_radius) ** 2)
        lit_factor = diffuse * atten * mask_val
        if steps > 0:
            lit_factor = np.ceil(lit_factor * float(steps)) / float(steps)
        direct = power * lit_factor

        lit_rgb = np.zeros((h, w, 3), dtype=np.uint8)
        for c in range(3):
            lit_rgb[:, :, c] = _linear_to_srgb(albedo_lin[:, :, c] * (ambient + direct * light_lin[c]))
        lit_rgb[~fg] = 0

        frame_rgba = np.dstack([lit_rgb, alpha])
        frames.append(Image.fromarray(frame_rgba, mode="RGBA"))

    output_gif.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output_gif, save_all=True, append_images=frames[1:], duration=65, loop=0, disposal=2)
    print(f"Saved linear-sRGB lighting preview GIF (steps={steps}): {output_gif}")


def main():
    parser = argparse.ArgumentParser(
        description="Pixel Art Normal Map, Cavity Mask & De-Lighting Generator (@xprite/lighter Faceted + Outline Bevel + Floor Tile + Stepped Shader)"
    )
    parser.add_argument("image", nargs="?", help="Input 2D PNG sprite or floor tile image")
    parser.add_argument("-o", "--output", help="Output normal map PNG path (default: <input>_n.png)")
    parser.add_argument(
        "--mode",
        choices=["faceted", "outline", "boxy", "floor-tile", "smooth"],
        default="faceted",
        help="Generation mode: 'faceted' (@xprite/lighter Lab-clustered faceted), 'outline' (quarter-circle 1px-padded bevel), 'boxy' (1.5px crate bevel), 'floor-tile' (3x3 dark-gap normal map), or 'smooth'",
    )
    parser.add_argument("--preset", choices=["character", "object", "architecture", "terrain"], default="character", help="Subject preset for faceted mode (default: character)")
    parser.add_argument("--region-mode", choices=["perceptual", "exact-rgb"], default="perceptual", help="Cluster segmentation mode for faceted normals: 'perceptual' (CIELAB Delta-E, default) or 'exact-rgb'")
    parser.add_argument("--painted-light-angle", type=float, default=None, help="Manual painted-light azimuth in degrees (0=right, 90=up). Omit to auto-estimate.")
    parser.add_argument("--painted-light-influence", type=float, default=60.0, help="Painted-light handling influence 0-100 (default: 60; 0 disables)")
    parser.add_argument("--shading", help="Optional separate shading map PNG (same dimensions as sprite) for painted-light estimation & tilting")
    parser.add_argument("--estimate-light", action="store_true", help="Only estimate painted-in light direction and confidence, then exit")
    parser.add_argument("--delight", action="store_true", help="Export de-lit flat albedo (<input>_delit.png) and apply de-lighting to --preview GIF")
    parser.add_argument("--delight-influence", type=float, default=100.0, help="De-lighting strength 0-100 when --delight is set (default: 100)")
    parser.add_argument("-s", "--strength", type=float, default=1.5, help="Bump height strength for faceted/smooth modes (default: 1.5)")
    parser.add_argument("--facets", type=float, default=None, help="Facet splitting 0-100 (default: preset value)")
    parser.add_argument("--edge-width", type=int, default=None, help="Smoothing passes 0-6 (default: preset value)")
    parser.add_argument("--no-merge-outlines", action="store_true", help="Disable merging dark pixel outlines into adjacent facets")
    parser.add_argument("-p", "--pillow", type=float, default=0.65, help="Pillow volume weight [0.0 to 1.0] for smooth mode")
    parser.add_argument("--bevel", type=float, default=5.0, help="Bevel width in px for outline/floor-tile modes (default: 5.0; 1.5 for boxy, 3.0 for floor-tile)")
    parser.add_argument("--top", type=float, default=12.0, help="Top plateau height in px for outline/floor-tile modes (default: 12.0; 2.5 for floor-tile)")
    parser.add_argument("--detail", type=float, default=1.5, help="Luminance surface detail weight (default: 1.5; 1.0 for floor-tile)")
    parser.add_argument("--blur", type=float, default=0.7, help="Gaussian height blur sigma before gradient (default: 0.7)")
    parser.add_argument("--gap-percentile", type=float, default=30.0, help="Darkest percentile treated as mortar/gaps in floor-tile mode (default: 30.0)")
    parser.add_argument("--steps", type=int, default=0, help="Quantized lighting bands for --preview GIF (e.g., 6 for crisp pixel-art cel steps)")
    parser.add_argument("--invert-y", action="store_true", help="Invert Y/Green normal channel (DirectX)")
    parser.add_argument("--mask", action="store_true", help="Also generate cavity Light Mask (<input>_m.png)")
    parser.add_argument("--preview", action="store_true", help="Also render an animated lighting preview GIF")
    parser.add_argument("--export-shader", choices=["godot4", "unity"], help="Print Godot 4 stepped canvas_item light() shader or Unity URP guidance")
    parser.add_argument("--verify", action="store_true", help="Run automated verification suite for outline normals, stepped lighting & @xprite/lighter")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()

    if args.verify:
        res = run_outline_verification()
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["ok"] else 1)

    if args.export_shader:
        src = GODOT4_STEPPED_SHADER if args.export_shader == "godot4" else UNITY_URP_GUIDANCE
        if args.json:
            print(json.dumps({"ok": True, "engine": args.export_shader, "source": src}, indent=2))
        else:
            print(src)
        sys.exit(0)

    if not args.image:
        parser.error("the following arguments are required: image (unless --verify or --export-shader is used)")

    in_path = Path(args.image)
    if not in_path.exists():
        print(f"Error: {in_path} does not exist.")
        sys.exit(1)

    shading_path = Path(args.shading) if args.shading else None
    if args.estimate_light:
        arr = np.array(Image.open(in_path).convert("RGBA"), dtype=np.uint8)
        s_arr = np.array(Image.open(shading_path).convert("RGBA"), dtype=np.uint8) if shading_path and shading_path.exists() else None
        est = estimate_painted_light(arr, s_arr)
        if args.json:
            print(json.dumps({"ok": True, "image": str(in_path), "painted_light_estimate": est}, indent=2))
        else:
            if est:
                print(f"Estimated painted light: angle={est['angle']:.1f} deg, fit={est['fit']:.4f}")
            else:
                print("No reliable painted directional light detected.")
        sys.exit(0)

    out_path = Path(args.output) if args.output else None
    norm_path, meta = generate_normal_map(
        in_path,
        out_path,
        strength=args.strength,
        pillow_weight=args.pillow,
        invert_y=args.invert_y,
        mode=args.mode,
        preset=args.preset,
        facets=args.facets,
        edge_width=args.edge_width,
        merge_outlines=not args.no_merge_outlines,
        bevel=args.bevel,
        top=args.top,
        detail=args.detail,
        blur=args.blur,
        gap_percentile=args.gap_percentile,
        region_mode=args.region_mode,
        painted_light_angle=args.painted_light_angle,
        painted_light_influence=args.painted_light_influence,
        shading_path=shading_path,
        return_meta=True,
    )

    mask_path = None
    if args.mask or (args.preview and args.mode == "faceted"):
        mask_path = generate_light_mask(in_path, preset=args.preset)

    delit_path = None
    delight_angle_used = None
    if args.delight and norm_path:
        angle_hint = args.painted_light_angle
        if angle_hint is None and meta.get("painted_light_estimate"):
            angle_hint = meta["painted_light_estimate"]["angle"]
        delit_path, delight_angle_used = remove_painted_light(
            in_path,
            norm_path,
            angle=angle_hint,
            influence=args.delight_influence,
            invert_y=args.invert_y,
        )

    gif_path = None
    if args.preview and norm_path:
        gif_path = norm_path.parent / f"{in_path.stem}_lighting_preview.gif"
        render_lighting_preview(
            in_path,
            norm_path,
            gif_path,
            mask_path=mask_path,
            steps=args.steps,
            delight_angle=delight_angle_used if args.delight else None,
            delight_influence=args.delight_influence,
            invert_y=args.invert_y,
        )

    if args.json:
        print(json.dumps({
            "ok": True,
            "mode": args.mode,
            "normal_map": str(norm_path) if norm_path else None,
            "light_mask": str(mask_path) if mask_path else None,
            "delit_albedo": str(delit_path) if delit_path else None,
            "preview_gif": str(gif_path) if gif_path else None,
            "painted_light_estimate": meta.get("painted_light_estimate"),
            "painted_light_angle_used": meta.get("painted_light_angle_used"),
            "painted_light_influence_used": meta.get("painted_light_influence_used"),
        }, indent=2))


if __name__ == "__main__":
    main()
