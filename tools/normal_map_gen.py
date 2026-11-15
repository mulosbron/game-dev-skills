#!/usr/bin/env python3
"""
Pixel Art Normal Map & Cavity Light Mask Generator (normal_map_gen.py)
Powered by the Moonfell Pixel Art Lighter v3.6.0 Cluster-Faceted Algorithm (MIT License)
+ Classic Smooth Distance-Transform Pillow Mode.

Key Pixel-Art Specific Features (Faceted Mode - Default):
1. Connected Color Cluster Segmentation: Flat pixel color islands share a unified facet normal
   (zero blurry Sobel gradients inside flat pixel colors).
2. 8-Direction & 4-Elevation Normal Quantization: Discrete 45-degree compass angles and
   stepped elevations (0.24, 0.48, 0.72, 0.90) for crisp pixel-art normal maps.
3. Outline Merging (--merge-outlines): Dark 1px outlines inherit adjacent interior facet normals
   instead of creating dark trenches around sprites.
4. Facet Splitting (--facets): Splits large single-color clusters into directional sub-facets.
5. 1-2px Orphan Island De-speckling: Removes single-pixel normal noise.
6. Cavity Light Mask Generation (--mask): Outputs a companion '_m.png' light mask with cavity occlusion.
7. Linear-sRGB Point Light Preview (--preview): Generates an animated GIF with physical inverse-square falloff.
"""

import sys
import json
import math
import argparse
from collections import deque
from pathlib import Path
from typing import Tuple
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
    "character":    {"strength": 65,  "facets": 15, "floor": 30, "ceiling": 255, "cavity": 20, "edge_width": 3},
    "object":       {"strength": 100, "facets": 35, "floor": 20, "ceiling": 255, "cavity": 35, "edge_width": 3},
    "architecture": {"strength": 100, "facets": 20, "floor": 30, "ceiling": 255, "cavity": 25, "edge_width": 1},
    "terrain":      {"strength": 110, "facets": 50, "floor": 35, "ceiling": 255, "cavity": 20, "edge_width": 3},
}


def _unit3(vx: float, vy: float, vz: float):
    length = math.hypot(vx, vy, vz) or 1.0
    return vx / length, vy / length, vz / length


def _quantize_normal(vx: float, vy: float, vz: float, preset: str, scale: float):
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


def _segment_and_distance(arr: np.ndarray):
    """
    Computes foreground mask, Rec.709 luminance, connected RGB color clusters,
    and Manhattan boundary distance field exactly as in Pixel Art Lighter v3.6.0.
    """
    h, w, _ = arr.shape
    n_total = w * h
    flat_rgba = arr.reshape(-1, 4)

    fg = flat_rgba[:, 3] > 0
    lum = (0.2126 * flat_rgba[:, 0] + 0.7152 * flat_rgba[:, 1] + 0.0722 * flat_rgba[:, 2]) / 255.0

    if not np.any(fg):
        return fg, lum, [], np.full(n_total, -1, dtype=np.int32), np.zeros(n_total, dtype=np.float32), 0.0, 1.0

    lo = float(np.min(lum[fg]))
    hi = float(np.max(lum[fg]))

    def adjacent(idx: int):
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

    # 1. Connected color clusters (identical RGB)
    labels = np.full(n_total, -1, dtype=np.int32)
    clusters = []
    r_ch = flat_rgba[:, 0]
    g_ch = flat_rgba[:, 1]
    b_ch = flat_rgba[:, 2]

    for i in range(n_total):
        if fg[i] and labels[i] < 0:
            cid = len(clusters)
            labels[i] = cid
            q = deque([i])
            pixels = []
            ri, gi, bi = r_ch[i], g_ch[i], b_ch[i]
            while q:
                p = q.popleft()
                pixels.append(p)
                for nb in adjacent(p):
                    if fg[nb] and labels[nb] < 0 and r_ch[nb] == ri and g_ch[nb] == gi and b_ch[nb] == bi:
                        labels[nb] = cid
                        q.append(nb)
            clusters.append({"pixels": pixels, "value": float(lum[i])})

    # 2. Manhattan BFS boundary distance field
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

    return fg, lum, clusters, labels, distance, lo, hi


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
) -> Path:
    """
    Generates a crisp, cluster-faceted pixel-art normal map using the Moonfell Pixel Art Lighter v3.6.0 algorithm.
    """
    preset = preset if preset in PRESET_DEFAULTS else "character"
    defaults = PRESET_DEFAULTS[preset]
    strength_val = shape_strength if shape_strength is not None else defaults["strength"]
    facets_val = facets if facets is not None else defaults["facets"]
    edge_w = edge_width if edge_width is not None else defaults["edge_width"]

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img, dtype=np.uint8)
    h, w, _ = arr.shape
    n_total = w * h
    flat_rgba = arr.reshape(-1, 4)

    fg, lum, clusters, labels, distance, lo, hi = _segment_and_distance(arr)
    if not np.any(fg):
        print(f"Warning: {image_path} has no opaque pixels.")
        return None

    def adjacent(idx: int):
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

    scale = strength_val / 100.0
    field = np.zeros(n_total, dtype=np.float32)
    max_dist_cap = 8.0 if preset == "character" else 16.0
    convex_mult = 0.0 if preset == "architecture" else (0.12 if preset == "terrain" else 0.65)
    lum_mult = 3.5 if preset == "architecture" else (4.0 if preset == "terrain" else (1.2 if preset == "character" else 2.1))

    for i in range(n_total):
        if fg[i]:
            convex = math.sqrt(min(float(distance[i]), max_dist_cap)) * convex_mult
            field[i] = convex + normalized(i) * lum_mult

    # Edge-width smoothing passes over height field
    for _ in range(edge_w):
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

    dirs = np.zeros((n_total, 3), dtype=np.float32)
    dirs[:, 2] = 1.0

    def at_field(idx: int, fallback: float) -> float:
        return float(field[idx]) if (0 <= idx < n_total and fg[idx]) else fallback

    for i in range(n_total):
        if fg[i]:
            x = i % w
            y = i // w
            fi = float(field[i])
            dx = (at_field(i + 1, fi) if x < w - 1 else fi) - (at_field(i - 1, fi) if x > 0 else fi)
            dy = (at_field(i + w, fi) if y < h - 1 else fi) - (at_field(i - w, fi) if y > 0 else fi)
            dirs[i] = _unit3(-dx * scale, dy * scale, 1.0)

    # Cluster averaging & Facet Splitting
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

        groups = {}
        split = facets_val > 0 and len(cluster["pixels"]) >= round(180 - facets_val * 1.1)
        if split:
            for p in cluster["pixels"]:
                dx, dy = float(dirs[p, 0]), float(dirs[p, 1])
                tilt = math.hypot(dx, dy)
                key = round(math.atan2(dy, dx) / (math.pi / 2.0)) if tilt > 0.35 else 9
                groups.setdefault(key, []).append(p)

        min_group_len = max(16, len(cluster["pixels"]) * 0.16)
        supported = [g for g in groups.values() if len(g) >= min_group_len]
        allow = False
        if len(supported) >= 2:
            means = []
            for g in supported:
                gx = sum(float(dirs[p, 0]) for p in g)
                gy = sum(float(dirs[p, 1]) for p in g)
                gz = sum(float(dirs[p, 2]) for p in g)
                means.append(_unit3(gx, gy, gz))
            threshold = 0.8 - facets_val * 0.001
            for i_m in range(len(means)):
                for j_m in range(i_m):
                    dot = means[i_m][0] * means[j_m][0] + means[i_m][1] * means[j_m][1] + means[i_m][2] * means[j_m][2]
                    if dot < threshold:
                        allow = True

        base = _quantize_normal(avg_x, avg_y, avg_z, preset, scale)
        for p in cluster["pixels"]:
            dirs[p] = base

        if allow:
            for g in supported:
                gx, gy, gz = 0.0, 0.0, 0.0
                for p in g:
                    x = p % w
                    y = p // w
                    fp = float(field[p])
                    dx = (at_field(p + 1, fp) if x < w - 1 else fp) - (at_field(p - 1, fp) if x > 0 else fp)
                    dy = (at_field(p + w, fp) if y < h - 1 else fp) - (at_field(p - w, fp) if y > 0 else fp)
                    vx, vy, vz = _unit3(-dx * scale, dy * scale, 1.0)
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

    # Orphan 1-2px normal island de-speckling
    seen = np.zeros(n_total, dtype=bool)
    for i in range(n_total):
        if fg[i] and not seen[i]:
            group = []
            q = deque([i])
            seen[i] = True
            ix, iy = float(dirs[i, 0]), float(dirs[i, 1])
            while q:
                p = q.popleft()
                group.append(p)
                for nb in adjacent(p):
                    if fg[nb] and not seen[nb]:
                        if abs(float(dirs[nb, 0]) - ix) < 0.001 and abs(float(dirs[nb, 1]) - iy) < 0.001:
                            seen[nb] = True
                            q.append(nb)
            if len(group) <= 2:
                group_set = set(group)
                neighbors = [nb for p in group for nb in adjacent(p) if fg[nb] and nb not in group_set]
                if neighbors:
                    nb0 = neighbors[0]
                    for p in group:
                        dirs[p] = dirs[nb0]

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
    print(f"Generated faceted normal map ({preset}): {output_path} ({w}x{h})")
    return output_path


def generate_light_mask(
    image_path: Path,
    output_path: Path = None,
    preset: str = "object",
    strength: float = None,
    floor: float = None,
    ceiling: float = 255.0,
    cavity: float = None,
) -> Path:
    """
    Generates a cavity-aware Light Mask ('_m.png') using the Moonfell Pixel Art Lighter v3.6.0 algorithm.
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

    fg, lum, clusters, labels, _, lo, hi = _segment_and_distance(arr)
    lum_range = hi - lo

    def adjacent(idx: int):
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


def _edt_2d(mask: np.ndarray) -> np.ndarray:
    if HAS_SCIPY:
        return distance_transform_edt(mask).astype(np.float32)
    # Fallback Manhattan-like approximation only if scipy missing
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
    # Pad by 1 transparent pixel so sprites touching canvas borders keep their bevel
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
    ny = -gy if invert_y else gy  # image rows go down, so +gy faces up in OpenGL/Godot
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
    n[..., 1] = -n[..., 1]  # to screen space, Y down
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
    Verify outline normal map & stepped lighting invariants:
      1. Round sprite middle row: leftmost inside R < 100, rightmost R > 156; top+1 G > 156.
      2. Pixels > 5 px outside sprite equal (128, 128, 255) within 1.
      3. Flat normal stepped falloff (steps=6, radius=70, height=26):
         10 px -> 5/6, 35 px -> 2/6, >=70 px -> 0.
      4. Light left of round sprite -> left half brighter than right half.
      5. Steps=0 gives smooth light; flat normals give uniform flat lighting.
    """
    # Synthesize 48x48 round sprite (circle r=14 centered at 24,24)
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

    # Pixels > 5 px outside circle
    dist_out = np.hypot(xx - 23.5, yy - 23.5) - 14.0
    far_outside = dist_out > 5.0
    neutral_diff = int(np.max(np.abs(norm_arr[far_outside].astype(np.int32) - np.array([128, 128, 255], dtype=np.int32))))

    # Stepped light check on flat normal (128, 128, 255)
    flat_n = np.full((1, 80, 3), (128, 128, 255), dtype=np.uint8)
    albedo = np.ones((1, 80, 3), dtype=np.float32)
    gx, gy = np.meshgrid(np.arange(80, dtype=np.float32), np.array([0.0], dtype=np.float32))
    _, lit_stepped = step_light_eval((gx, gy), albedo, flat_n, light_xy=(0.0, 0.0), steps=6)
    _, lit_smooth = step_light_eval((gx, gy), albedo, flat_n, light_xy=(0.0, 0.0), steps=0)

    s10 = float(lit_stepped[0, 10])
    s35 = float(lit_stepped[0, 35])
    s70 = float(lit_stepped[0, 70])

    # Light left of round sprite (x=4, y=24) -> left half brighter than right half
    gx48, gy48 = np.meshgrid(np.arange(48, dtype=np.float32), np.arange(48, dtype=np.float32))
    albedo48 = sprite_arr[:, :, :3].astype(np.float32) / 255.0
    lit_round, _ = step_light_eval((gx48, gy48), albedo48, norm_arr, light_xy=(4.0, 23.5), steps=6)
    left_half_mean = float(lit_round[circle & (xx < 23)].mean())
    right_half_mean = float(lit_round[circle & (xx > 24)].mean())

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
) -> Path:
    """
    Unified entry point. Supports:
      - 'faceted': Moonfell Pixel Art Lighter v3.6.0 cluster-faceted (default)
      - 'outline': Quarter-circle bevel from 1px-padded outline + luminance detail
      - 'boxy': Low-bevel crate/box preset (bevel=1.5, top=3.6) preventing pillow look
      - 'floor-tile': Seamless 3x3 dark-gap threshold normal map for floor tiles
      - 'smooth': Classic continuous distance-transform Sobel
    """
    if mode == "outline":
        return generate_outline_normal_map(
            image_path=image_path,
            output_path=output_path,
            bevel=bevel,
            top=top,
            detail=detail,
            blur=blur,
            invert_y=invert_y,
        )
    if mode == "boxy":
        b = 1.5 if bevel == 5.0 else bevel
        t = 12.0 * b / 5.0 if top == 12.0 else top
        return generate_outline_normal_map(
            image_path=image_path,
            output_path=output_path,
            bevel=b,
            top=t,
            detail=detail,
            blur=blur,
            invert_y=invert_y,
        )
    if mode == "floor-tile":
        b = 3.0 if bevel == 5.0 else bevel
        t = 2.5 if top == 12.0 else top
        d = 1.0 if detail == 1.5 else detail
        return generate_floor_tile_normal_map(
            image_path=image_path,
            output_path=output_path,
            bevel=b,
            top=t,
            detail=d,
            blur=blur,
            gap_percentile=gap_percentile,
            invert_y=invert_y,
        )
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
        )

    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    alpha = arr[:, :, 3] / 255.0
    mask = alpha > 0.1
    if not np.any(mask):
        print(f"Warning: {image_path} has no opaque pixels.")
        return None

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
    return output_path


def _srgb_to_linear(arr: np.ndarray) -> np.ndarray:
    c = arr / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.maximum(0.0, c)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * (c ** (1.0 / 2.4)) - 0.055)
    return np.clip( np.round(s * 255.0), 0, 255 ).astype(np.uint8)


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
):
    """
    Renders an animated GIF showing a 3D point light orbiting the sprite.
    When steps > 0 (e.g. steps=6), renders quantized pixel-art stepped light bands.
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

    frames = []
    for i in range(num_frames):
        angle = (2.0 * math.pi * i) / num_frames
        lx = cx + math.cos(angle) * orbit_rx
        ly = cy + math.sin(angle) * orbit_ry

        dx = lx - xx
        dy = yy - ly
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
    parser = argparse.ArgumentParser(description="Pixel Art Normal Map & Light Mask Generator (Faceted + Outline Bevel + Floor Tile + Stepped Shader)")
    parser.add_argument("image", nargs="?", help="Input 2D PNG sprite or floor tile image")
    parser.add_argument("-o", "--output", help="Output normal map PNG path (default: <input>_n.png)")
    parser.add_argument(
        "--mode",
        choices=["faceted", "outline", "boxy", "floor-tile", "smooth"],
        default="faceted",
        help="Generation mode: 'faceted' (Moonfell cluster-faceted), 'outline' (quarter-circle 1px-padded bevel), 'boxy' (1.5px crate bevel), 'floor-tile' (3x3 dark-gap normal map), or 'smooth'",
    )
    parser.add_argument("--preset", choices=["character", "object", "architecture", "terrain"], default="character", help="Subject preset for faceted mode (default: character)")
    parser.add_argument("-s", "--strength", type=float, default=1.5, help="Bump height strength for faceted/smooth modes (default: 1.5)")
    parser.add_argument("--facets", type=float, default=None, help="Facet splitting 0-100 (default: preset value)")
    parser.add_argument("--edge-width", type=int, default=None, help="Edge width passes 0-5 (default: preset value)")
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
    parser.add_argument("--verify", action="store_true", help="Run automated verification suite for outline normals & stepped lighting")
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

    out_path = Path(args.output) if args.output else None
    norm_path = generate_normal_map(
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
    )

    mask_path = None
    if args.mask or (args.preview and args.mode == "faceted"):
        mask_path = generate_light_mask(in_path, preset=args.preset)

    gif_path = None
    if args.preview and norm_path:
        gif_path = norm_path.parent / f"{in_path.stem}_lighting_preview.gif"
        render_lighting_preview(in_path, norm_path, gif_path, mask_path=mask_path, steps=args.steps)

    if args.json:
        print(json.dumps({
            "ok": True,
            "mode": args.mode,
            "normal_map": str(norm_path) if norm_path else None,
            "light_mask": str(mask_path) if mask_path else None,
            "preview_gif": str(gif_path) if gif_path else None,
        }, indent=2))


if __name__ == "__main__":
    main()
