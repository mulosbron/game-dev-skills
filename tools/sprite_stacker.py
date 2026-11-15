#!/usr/bin/env python3
"""
Sprite Stacking CLI:
  1. Slice 4 orthographic views (sheet or separate PNGs) into a ground-first horizontal slice strip.
  2. Render/rotate/bake existing slice strips (`draw_stack`) with exact Nearest sampling, squash, spacing, whole-px snapping, and optional single final outline.
  3. Generate minimal outputs by default (only `slices_strip.png` + `preview.gif`, no 199-file clutter unless `--emit-all`).
  4. Verify dimensions, pixel-for-pixel stacking, circle heading math, and export Godot 4 / Unity / TypeScript code.

Usage:
    python tools/sprite_stacker.py verify --json
    python tools/sprite_stacker.py demo --out exports/sprite_stack_demo --json
    python tools/sprite_stacker.py slice --sheet views.png --out out/ --json
    python tools/sprite_stacker.py render --strip out/slices_strip.png --slices 15 --turn 30 --squash 0.75 --out out/baked.png
    python tools/sprite_stacker.py export-code --engine godot4 --out SpriteStack2D.gd
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")


def _dilate4(m: np.ndarray) -> np.ndarray:
    """4-connected binary dilation."""
    out = m.copy()
    out[1:, :] |= m[:-1, :]
    out[:-1, :] |= m[1:, :]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def _dilate_outside(m: np.ndarray) -> np.ndarray:
    """4-connected dilation treating array borders as True (peels edge outlines cleanly)."""
    p = np.pad(m, 1, constant_values=True)
    return _dilate4(p)[1:-1, 1:-1]


def _run_lr(m: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    R, W = m.shape
    big = np.int32(10**6)
    dfwd = np.full((R, W), big, np.int32)
    prev = np.full(R, -1, np.int32)
    for i in range(W):
        c = m[:, i]
        prev = np.where(c, prev, np.int32(i))
        dfwd[:, i] = np.where(c, i - prev, big)
    dbwd = np.full((R, W), big, np.int32)
    prev = np.full(R, np.int32(W), np.int32)
    for i in range(W - 1, -1, -1):
        c = m[:, i]
        prev = np.where(c, prev, np.int32(i))
        dbwd[:, i] = np.where(c, prev - i, big)
    return dfwd, dbwd


def _run_dist(m: np.ndarray) -> np.ndarray:
    dfwd, dbwd = _run_lr(m)
    return np.minimum(dfwd, dbwd)


def _run_len(m: np.ndarray) -> np.ndarray:
    dfwd, dbwd = _run_lr(m)
    return np.where(m, dfwd + dbwd - 1, 0)


def _get_mask(img: Image.Image, tol: int = 10) -> np.ndarray:
    a = np.asarray(img)
    alpha = a[..., 3]
    if int(alpha.min()) < 200:
        return alpha >= 128
    rgb = a[..., :3].astype(np.int16)
    corners = np.stack([rgb[0, 0], rgb[0, -1], rgb[-1, 0], rgb[-1, -1]])
    cand, counts = np.unique(corners, axis=0, return_counts=True)
    bg = cand[counts.argmax()]
    return np.abs(rgb - bg).max(axis=-1) > tol


def _trim(img: Image.Image, mask: np.ndarray) -> tuple[Image.Image, np.ndarray]:
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        raise ValueError("Empty orthographic view")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    return img.crop((x0, y0, x1, y1)), mask[y0:y1, x0:x1]


def _split_boxes(mask: np.ndarray, min_gap: int = 2) -> list[tuple[int, int, int, int]]:
    """Split orthographic views separated by blank rows/columns."""
    boxes: list[tuple[int, int, int, int]] = []

    def gaps(filled: np.ndarray, k: int) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        run = 0
        for i, f in enumerate(filled):
            if not f:
                run += 1
            else:
                if run >= k:
                    out.append((i - run, i))
                run = 0
        return out

    def rec(x0: int, y0: int, x1: int, y1: int, depth: int = 0) -> None:
        sub = mask[y0:y1, x0:x1]
        if not sub.any():
            return
        ys, xs = np.nonzero(sub)
        yy0, yy1 = y0 + int(ys.min()), y0 + int(ys.max()) + 1
        xx0, xx1 = x0 + int(xs.min()), x0 + int(xs.max()) + 1
        if depth > 64:
            boxes.append((xx0, yy0, xx1, yy1))
            return
        rows = mask[yy0:yy1, xx0:xx1].any(axis=1)
        gs = gaps(rows, min_gap)
        if gs:
            prev = 0
            for a, b in gs:
                rec(xx0, yy0 + prev, xx1, yy0 + a, depth + 1)
                prev = b
            rec(xx0, yy0 + prev, xx1, yy1, depth + 1)
            return
        cols = mask[yy0:yy1, xx0:xx1].any(axis=0)
        gs = gaps(cols, min_gap)
        if gs:
            prev = 0
            for a, b in gs:
                rec(xx0 + prev, yy0, xx0 + a, yy1, depth + 1)
                prev = b
            rec(xx0 + prev, yy0, xx1, yy1, depth + 1)
            return
        boxes.append((xx0, yy0, xx1, yy1))

    rec(0, 0, mask.shape[1], mask.shape[0])
    boxes.sort(key=lambda b: (round((b[1] + b[3]) / 2 / max(1.0, mask.shape[0] / 2.2)), b[0]))
    return boxes


def load_sheet_views(path: Path, warnings: list[str], bg_tol: int = 10) -> list[tuple[Image.Image, np.ndarray]]:
    img = Image.open(path).convert("RGBA")
    mask = _get_mask(img, bg_tol)
    boxes = _split_boxes(mask)
    if len(boxes) < 3:
        raise ValueError(f"Found {len(boxes)} views in sheet; need at least 3 (top/side/front)")
    if len(boxes) > 4:
        warnings.append(f"Found {len(boxes)} components in sheet; keeping largest 4")
        boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)[:4]
        boxes.sort(key=lambda b: (round((b[1] + b[3]) / 2 / max(1.0, mask.shape[0] / 2.2)), b[0]))
    views = [_trim(img.crop(b), mask[b[1]:b[3], b[0]:b[2]]) for b in boxes]
    rest = list(range(len(views)))
    i_top = max(rest, key=lambda i: views[i][0].height / max(1, views[i][0].width))
    rest.remove(i_top)
    i_side = max(rest, key=lambda i: views[i][0].width / max(1, views[i][0].height))
    rest.remove(i_side)
    return [views[i] for i in ([i_top, i_side] + rest)][:4]


def load_individual_views(paths: list[Path], bg_tol: int = 10) -> list[tuple[Image.Image, np.ndarray]]:
    return [_trim(img, _get_mask(img, bg_tol)) for img in (Image.open(p).convert("RGBA") for p in paths)]


def strip_outline_all(
    views: list[tuple[Image.Image, np.ndarray]], mode: str, warnings: list[str]
) -> tuple[list[tuple[Image.Image, np.ndarray]], bool]:
    """Strip outer 1px dark outline consistently across all views if safe (or forced via #RRGGBB)."""
    if mode == "none" or not views:
        return views, False
    if mode == "auto":
        palets = [np.asarray(im)[..., :3].astype(np.int16)[m].reshape(-1, 3) for im, m in views]
        colors, counts = np.unique(np.concatenate(palets), axis=0, return_counts=True)
        lum = colors.astype(int).sum(axis=1)
        cand = colors[(lum < 210) & (counts >= max(8, int(0.005 * sum(len(p) for p in palets))))]
        if len(cand) == 0:
            return views, False
        target = cand[int(np.argmin(cand.astype(int).sum(axis=1)))]
        tol = 6
        darks = []
        ok = True
        for im, m in views:
            rgb = np.asarray(im)[..., :3].astype(np.int16)
            dark = m & (np.abs(rgb - target).max(axis=-1) <= tol)
            darks.append(dark)
            if dark.any():
                thick = np.minimum(_run_len(dark), _run_len(dark.T).T)
                if float((thick[dark] <= 2).mean()) < 0.8:
                    ok = False
        if not ok:
            warnings.append("Outline color overlaps dark interior fills; outline kept (use --outline-strip #RRGGBB to force)")
            return views, False
    else:
        hex_str = mode.lstrip("#")
        target = np.array([int(hex_str[i:i + 2], 16) for i in (0, 2, 4)], np.int16)
        tol = 30
        darks = [m & (np.abs(np.asarray(im)[..., :3].astype(np.int16) - target).max(axis=-1) <= tol) for im, m in views]

    out: list[tuple[Image.Image, np.ndarray]] = []
    any_stripped = False
    for (im, m), dark in zip(views, darks):
        if not dark.any():
            out.append((im, m))
            continue
        mm = m.copy()
        for _ in range(8):
            kill = mm & dark & _dilate_outside(~mm)
            if not kill.any():
                break
            mm &= ~kill
        if int((m & ~mm).sum()) > 0:
            any_stripped = True
        out.append(_trim(im, mm))
    return out, any_stripped


def _quantize_shared_palette(views: list[tuple[Image.Image, np.ndarray]], n_colors: int) -> list[tuple[Image.Image, np.ndarray]]:
    """Map all views onto a single shared palette of n_colors without dithering."""
    if n_colors <= 0:
        return views
    px_raw = np.concatenate([np.asarray(im)[..., :3][m] for im, m in views])
    unique_exact = np.unique(px_raw, axis=0)
    if len(unique_exact) <= n_colors:
        return views
    px = np.unique((px_raw.astype(np.int32) // 6 * 6 + 3).clip(0, 255), axis=0).astype(np.uint8)
    pal_img = Image.fromarray(px.reshape(1, -1, 3), "RGB").quantize(n_colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(pal_img.getpalette()[: n_colors * 3], dtype=np.int32).reshape(-1, 3)
    out: list[tuple[Image.Image, np.ndarray]] = []
    for im, m in views:
        arr = np.asarray(im).copy()
        rgb = arr[..., :3].astype(np.int32)
        idx = ((rgb[..., None, :] - pal[None, None, ...]) ** 2).sum(axis=-1).argmin(axis=-1)
        arr[..., :3] = pal[idx].astype(np.uint8)
        arr[..., 3] = np.where(m, 255, 0)
        out.append((Image.fromarray(arr), m))
    return out


def _fit_view(img: Image.Image, mask: np.ndarray, tw: int, th: int, warnings: list[str], name: str) -> tuple[np.ndarray, np.ndarray]:
    h, w = mask.shape
    if (w, h) == (tw, th):
        return mask, np.asarray(img)[..., :3]
    warnings.append(f"{name} view was {w}x{h}, resized nearest to {tw}x{th}")
    rgba = np.dstack([np.asarray(img)[..., :3], mask.astype(np.uint8) * 255])
    rs = np.asarray(Image.fromarray(rgba).resize((tw, th), Image.NEAREST))
    return rs[..., 3] >= 128, rs[..., :3]


def _match_top_orientation(top_img: Image.Image, top_m: np.ndarray, side_m: np.ndarray) -> str:
    """Detect whether the top view faces 'down' or 'up' by aligning dark cabin/tall features with side profile."""
    tall_cols = side_m.sum(axis=0)
    tall = np.interp(np.linspace(0, len(tall_cols) - 1, top_m.shape[0]), np.arange(len(tall_cols)), tall_cols)
    tall_mask = tall >= 0.8 * tall.max()
    rgb = np.asarray(top_img)[..., :3].astype(int)
    dark = ((rgb.sum(axis=-1) < 240) & top_m).mean(axis=1)
    return "down" if float((dark * tall_mask).sum()) >= float((dark[::-1] * tall_mask).sum()) else "up"


def build_slices_from_views(
    views: list[tuple[Image.Image, np.ndarray]],
    top_faces: str = "auto",
    side_faces: str = "left",
    edge_color: int = 2,
    shade: float = 0.0,
    colors: int = 0,
    outline_strip: str = "auto",
    use_back: bool = True,
) -> tuple[np.ndarray, list[np.ndarray], list[str], bool]:
    """Carve 3D voxel slices (ground slice at index 0) from 3-4 orthographic views."""
    warnings: list[str] = []
    views, stripped = strip_outline_all(views, outline_strip, warnings)
    if colors > 0:
        views = _quantize_shared_palette(views, colors)

    (top_img, top_m), (side_img, side_m), (front_img, front_m) = views[0], views[1], views[2]
    back = views[3] if (use_back and len(views) > 3) else None

    side_m_for_match = side_m[:, ::-1] if side_faces == "left" else side_m
    if top_faces == "auto":
        top_faces = _match_top_orientation(top_img, top_m, side_m_for_match)

    Z, X = top_m.shape
    Y = side_m.shape[0]

    zrows = np.arange(Z) if top_faces == "down" else (Z - 1 - np.arange(Z))
    T_m = top_m[zrows, :]
    T_c = np.asarray(top_img)[..., :3][zrows, :]

    yrows = Y - 1 - np.arange(Y)
    zcols = (Z - 1 - np.arange(side_m.shape[1])) if side_faces == "left" else np.arange(side_m.shape[1])
    S_m = side_m[np.ix_(yrows, zcols)]
    S_c = np.asarray(side_img)[..., :3][np.ix_(yrows, zcols)]
    # Ensure side width matches Z if slight mismatch
    if S_m.shape[1] != Z:
        s_rgba = np.dstack([S_c, S_m.astype(np.uint8) * 255])
        rs = np.asarray(Image.fromarray(s_rgba).resize((Z, Y), Image.NEAREST))
        S_m, S_c = rs[..., 3] >= 128, rs[..., :3]

    F_m, F_c = _fit_view(front_img, front_m, X, Y, warnings, "front")
    F_m = F_m[yrows, :]
    F_c = F_c[yrows, :]

    B_m = None
    if back is not None:
        bm, _ = _fit_view(back[0], back[1], X, Y, warnings, "back")
        B_m = bm[yrows, :]

    solid = np.zeros((Y, Z, X), dtype=bool)
    back_skipped = 0
    for y in range(Y):
        sl = T_m & S_m[y][:, None] & F_m[y][None, :]
        if B_m is not None:
            a = int((F_m[y] & B_m[y]).sum())
            b = int((F_m[y] & B_m[y, ::-1]).sum())
            row = B_m[y] if a <= b else B_m[y, ::-1]
            inter = sl & row[None, :]
            if inter.any():
                sl = inter
            elif sl.any():
                back_skipped += 1
        solid[y] = sl
    if back_skipped:
        warnings.append(f"Front/back views disagreed on {back_skipped} slice height(s); kept front on those layers")

    ring = max(0, edge_color if (stripped or edge_color == 0) else 0)
    slices: list[np.ndarray] = []
    covered = np.zeros((Z, X), dtype=bool)

    # First compute colors per layer from top down so occluded inner overhangs inherit above color when shade>0
    vol_colors = np.zeros((Y, Z, X, 3), dtype=np.uint8)
    for y in range(Y - 1, -1, -1):
        m = solid[y]
        above = covered.copy()
        covered |= m
        if not m.any():
            continue
        dz = _run_dist(m)
        dx = _run_dist(m.T).T
        z_edge = dz <= max(1, ring) if ring > 0 else np.zeros_like(m)
        x_edge = (dx <= max(1, ring)) & ~z_edge if ring > 0 else np.zeros_like(m)

        col = T_c.copy()
        if shade > 0.0 and y < Y - 1:
            # Keep color from layer above where pixel sits deep under upper surface (>2px)
            deep_under = above & (dz > 2) & (dx > 2)
            col[deep_under] = vol_colors[y + 1][deep_under]

        if ring > 0:
            side_row = np.broadcast_to(S_c[y][:, None, :], col.shape)
            front_row = np.broadcast_to(F_c[y][None, :, :], col.shape)
            col[z_edge] = side_row[z_edge]
            col[x_edge] = front_row[x_edge]
            if shade > 0.0:
                is_side_face = above & (z_edge | x_edge)
                factor = max(0.25, 1.0 - shade * (1.0 - y / max(Y - 1, 1)) - shade * 0.4)
                col[is_side_face] = np.clip(col[is_side_face].astype(np.float32) * factor, 0, 255).astype(np.uint8)

        vol_colors[y] = col

    for y in range(Y):
        canvas = np.zeros((Z, X, 4), dtype=np.uint8)
        canvas[..., :3] = vol_colors[y]
        canvas[..., 3] = np.where(solid[y], 255, 0)
        slices.append(canvas)

    return solid, slices, warnings, stripped


def slices_to_strip(slices: list[np.ndarray], gap: int = 0) -> Image.Image:
    """Pack ground-first slices into a horizontal strip (gap=0 for game engines, gap>0 for visual inspection)."""
    if gap <= 0:
        return Image.fromarray(np.concatenate(slices, axis=1))
    Z = slices[0].shape[0]
    spacer = np.zeros((Z, gap, 4), dtype=np.uint8)
    parts = []
    for i, s in enumerate(slices):
        parts.append(s)
        if i < len(slices) - 1:
            parts.append(spacer)
    return Image.fromarray(np.concatenate(parts, axis=1))


def strip_to_slices(strip_img: Image.Image, slice_count: int) -> list[np.ndarray]:
    """Slice a horizontal ground-first strip (count * w x h) back into RGBA numpy arrays."""
    rgba = np.asarray(strip_img.convert("RGBA"))
    h, total_w = rgba.shape[:2]
    if slice_count <= 0 or total_w % slice_count != 0:
        raise ValueError(f"Strip width {total_w} is not cleanly divisible by {slice_count} slices")
    w = total_w // slice_count
    return [rgba[:, i * w : (i + 1) * w, :].copy() for i in range(slice_count)]


def turn_from_velocity(vx: float, vy: float, reverse: bool = False, heading_rad: float | None = None) -> float:
    """For down-facing slice sheets (+y): turn = atan2(vy, vx) - PI/2. When reversing, keep heading instead of flipping."""
    if reverse and heading_rad is not None:
        return heading_rad
    if vx == 0.0 and vy == 0.0:
        return 0.0 if heading_rad is None else heading_rad
    return math.atan2(vy, vx) - math.pi / 2.0


def draw_stack(
    slices: list[np.ndarray],
    turn_deg: float = 0.0,
    squash: float = 0.75,
    spacing: float = 1.0,
    scale: int = 1,
    shadow: bool = False,
    shadow_alpha: int = 70,
    outline_color: tuple[int, int, int] | None = None,
    canvas_wh: tuple[int, int] | None = None,
) -> Image.Image:
    """Render one frame of stacked slices with Nearest rotation, camera squash, and integer lift spacing."""
    n = len(slices)
    imgs = [Image.fromarray(s) for s in slices]
    rot = [im.rotate(-turn_deg, resample=Image.NEAREST, expand=True) if turn_deg % 360 != 0 else im.copy() for im in imgs]
    if squash != 1.0:
        hs = max(1, int(round(rot[0].height * squash)))
        rot = [r.resize((r.width, hs), Image.NEAREST) for r in rot]

    pad = 2 if (canvas_wh is not None or shadow or outline_color is not None) else 0
    sdx, sdy = (2, 2) if shadow else (0, 0)
    max_lift = int(round((n - 1) * spacing)) if n > 1 else 0
    if canvas_wh is None:
        W = rot[0].width + 2 * pad + sdx
        H = rot[0].height + max_lift + 2 * pad + sdy
    else:
        W, H = canvas_wh
    y_bottom = H - pad - sdy
    cx = W // 2

    frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if shadow:
        g = None
        for r in rot:
            arr = np.asarray(r)
            if arr[..., 3].sum() > 0:
                g = arr.copy()
                break
        if g is not None:
            g[..., 0:3] = (12, 12, 16)
            g[..., 3] = (g[..., 3].astype(np.int32) * shadow_alpha // 255).astype(np.uint8)
            gs = Image.fromarray(g)
            frame.alpha_composite(gs, (cx - gs.width // 2 + sdx, y_bottom - gs.height + sdy))

    for z, r in enumerate(rot):
        lift = int(round(z * spacing))
        dx = cx - r.width // 2
        dy = y_bottom - lift - r.height
        frame.alpha_composite(r, (dx, dy))

    if outline_color is not None:
        fa = np.asarray(frame).copy()
        solidm = fa[..., 3] > 0
        ring = _dilate4(solidm) & ~solidm
        fa[ring] = (*outline_color, 255)
        frame = Image.fromarray(fa)

    if scale > 1:
        frame = frame.resize((frame.width * scale, frame.height * scale), Image.NEAREST)
    return frame


def render_turntable_frames(
    slices: list[np.ndarray],
    angle_step: float = 15.0,
    squash: float = 0.75,
    spacing: float = 1.0,
    scale: int = 1,
    shadow: bool = True,
    shadow_alpha: int = 70,
    outline_color: tuple[int, int, int] | None = None,
) -> tuple[list[Image.Image], list[int]]:
    angles = list(range(0, 360, max(1, int(round(angle_step)))))
    imgs = [Image.fromarray(s) for s in slices]
    pre = []
    for ang in angles:
        r0 = imgs[0].rotate(-ang, resample=Image.NEAREST, expand=True)
        hs = max(1, int(round(r0.height * squash))) if squash != 1.0 else r0.height
        pre.append((r0.width, hs))
    pad = 2
    sdx, sdy = (2, 2) if shadow else (0, 0)
    W = max(p[0] for p in pre) + 2 * pad + sdx
    H = max(p[1] for p in pre) + int(round((len(slices) - 1) * spacing)) + 2 * pad + sdy

    frames = [
        draw_stack(
            slices,
            turn_deg=float(ang),
            squash=squash,
            spacing=spacing,
            scale=scale,
            shadow=shadow,
            shadow_alpha=shadow_alpha,
            outline_color=outline_color,
            canvas_wh=(W, H),
        )
        for ang in angles
    ]
    return frames, angles


def save_gif(frames: list[Image.Image], path: Path, fps: float = 12.0, bg: str = "white") -> None:
    ms = max(20, int(round(1000.0 / fps)))
    if bg == "transparent":
        ps = []
        for f in frames:
            alpha = f.getchannel("A")
            p = f.convert("RGB").quantize(colors=255, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
            p.paste(255, mask=alpha.point(lambda a: 255 if a < 128 else 0))
            p.info["transparency"] = 255
            ps.append(p)
        ps[0].save(path, save_all=True, append_images=ps[1:], duration=ms, loop=0, disposal=2, transparency=255, optimize=False)
        return
    ims = []
    for f in frames:
        im = Image.new("RGBA", f.size, (255, 255, 255, 255))
        im.alpha_composite(f)
        ims.append(im.convert("RGB"))
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=ms, loop=0, optimize=False)


def make_demo_car_sheet() -> tuple[Image.Image, int]:
    """Build deterministic voxel sports car (10x15x31) -> 2x2 outlined orthographic sheet + expected voxels."""
    Y, X, Z = 10, 15, 31
    BODY = (45, 92, 224)
    GLASS = (86, 96, 122)
    TIRE = (34, 32, 40)
    STRIPE = (240, 240, 240)
    SPOIL = (32, 54, 152)
    LIGHT = (250, 214, 92)
    TAIL = (204, 62, 52)
    OUT = (24, 22, 30)

    vox = np.zeros((Y, X, Z, 3), np.uint8)
    sol = np.zeros((Y, X, Z), bool)

    def fill(y0: int, y1: int, x0: int, x1: int, z0: int, z1: int, c: tuple[int, int, int]) -> None:
        vox[y0 : y1 + 1, x0 : x1 + 1, z0 : z1 + 1] = c
        sol[y0 : y1 + 1, x0 : x1 + 1, z0 : z1 + 1] = True

    fill(0, 2, 0, 2, 3, 7, TIRE)
    fill(0, 2, 12, 14, 3, 7, TIRE)
    fill(0, 2, 0, 2, 23, 27, TIRE)
    fill(0, 2, 12, 14, 23, 27, TIRE)
    fill(3, 4, 1, 13, 1, 29, BODY)
    fill(5, 5, 1, 13, 2, 29, BODY)
    fill(6, 6, 2, 12, 8, 29, BODY)
    fill(7, 7, 3, 11, 13, 26, BODY)
    fill(8, 8, 4, 10, 16, 22, BODY)
    fill(7, 7, 3, 11, 13, 15, GLASS)
    fill(7, 7, 3, 11, 24, 26, GLASS)
    fill(9, 9, 1, 13, 25, 28, SPOIL)
    fill(4, 4, 2, 4, 1, 1, LIGHT)
    fill(4, 4, 11, 13, 1, 1, LIGHT)
    fill(4, 4, 2, 4, 29, 29, TAIL)
    fill(4, 4, 11, 13, 29, 29, TAIL)

    for z in range(Z):
        for x in range(6, 9):
            ys = np.nonzero(sol[:, x, z])[0]
            if len(ys) and (vox[ys.max(), x, z] == np.array(BODY)).all():
                vox[ys.max(), x, z] = STRIPE

    def proj_top() -> tuple[np.ndarray, np.ndarray]:
        img = np.zeros((Z, X, 3), np.uint8)
        m = np.zeros((Z, X), bool)
        for z in range(Z):
            for x in range(X):
                ys = np.nonzero(sol[:, x, z])[0]
                if len(ys):
                    m[Z - 1 - z, x] = True
                    img[Z - 1 - z, x] = vox[ys.max(), x, z]
        return img, m

    def proj_side() -> tuple[np.ndarray, np.ndarray]:
        img = np.zeros((Y, Z, 3), np.uint8)
        m = np.zeros((Y, Z), bool)
        for y in range(Y):
            for z in range(Z):
                xs = np.nonzero(sol[y, :, z])[0]
                if len(xs):
                    m[Y - 1 - y, z] = True
                    img[Y - 1 - y, z] = vox[y, xs.min(), z]
        return img, m

    def proj_front() -> tuple[np.ndarray, np.ndarray]:
        img = np.zeros((Y, X, 3), np.uint8)
        m = np.zeros((Y, X), bool)
        for y in range(Y):
            for x in range(X):
                zs = np.nonzero(sol[y, x, :])[0]
                if len(zs):
                    m[Y - 1 - y, x] = True
                    img[Y - 1 - y, x] = vox[y, x, zs.min()]
        return img, m

    def proj_back() -> tuple[np.ndarray, np.ndarray]:
        img = np.zeros((Y, X, 3), np.uint8)
        m = np.zeros((Y, X), bool)
        for y in range(Y):
            for x in range(X):
                zs = np.nonzero(sol[y, x, :])[0]
                if len(zs):
                    m[Y - 1 - y, x] = True
                    img[Y - 1 - y, x] = vox[y, x, zs.max()]
        return img, m

    def with_outline(img: np.ndarray, m: np.ndarray, margin: int = 1) -> Image.Image:
        H, W = m.shape
        out = np.zeros((H + 2 * margin, W + 2 * margin, 4), np.uint8)
        sil = np.zeros_like(out[..., 0], bool)
        sil[margin : margin + H, margin : margin + W] = m
        out[..., :3][sil] = img[m]
        out[..., 3][sil] = 255
        ring = _dilate4(sil) & ~sil
        out[..., :3][ring] = OUT
        out[..., 3][ring] = 255
        return Image.fromarray(out)

    top, side, front, back = (with_outline(*p) for p in (proj_top(), proj_side(), proj_front(), proj_back()))
    g = 3
    w_cell = max(im.width for im in (top, side, front, back))
    h_cell = max(im.height for im in (top, side, front, back))
    grid = Image.new("RGBA", (2 * w_cell + g, 2 * h_cell + g), (0, 0, 0, 0))
    grid.alpha_composite(top, (0, 0))
    grid.alpha_composite(side, (w_cell + g, 0))
    grid.alpha_composite(front, (0, h_cell + g))
    grid.alpha_composite(back, (w_cell + g, h_cell + g))
    return grid, int(sol.sum())


def _opaque_bbox(img: Image.Image) -> tuple[int, int]:
    alpha = np.asarray(img)[..., 3] > 0
    ys, xs = np.nonzero(alpha)
    return int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def run_verify(tmp_root: Path) -> dict[str, Any]:
    """Run all 6 automated verification tests for sprite slicing & stacking."""
    checks: dict[str, dict[str, Any]] = {}

    # Synthetic 15-slice reference box (24x43 px) & tapered car (ground 24x43, top 16x22)
    box_slices = []
    car_slices = []
    for z in range(15):
        s_box = np.zeros((43, 24, 4), dtype=np.uint8)
        s_box[:, :, :] = (40 + z * 8, 90 + z * 5, 220, 255)
        box_slices.append(s_box)

        s_car = np.zeros((43, 24, 4), dtype=np.uint8)
        if z < 8:
            s_car[:, :, :] = (45, 92, 224, 255)
        else:
            # Roof/cabin spans y=[4..26], shorter than 43 -> reference 24 x 52 screen size at squash=1!
            s_car[4:27, 3:21, :] = (230, 235, 245, 255)
        car_slices.append(s_car)

    # 1. squash=1, turn=0 exact dimensions & pixel-for-pixel manual paste match
    manual_box = Image.new("RGBA", (24, 43 + 14), (0, 0, 0, 0))
    for z, s in enumerate(box_slices):
        manual_box.alpha_composite(Image.fromarray(s), (0, 14 - z))
    drawn_box = draw_stack(box_slices, turn_deg=0.0, squash=1.0, spacing=1.0, scale=1, shadow=False)
    px_exact = bool(np.array_equal(np.asarray(manual_box), np.asarray(drawn_box)))
    bw, bh = _opaque_bbox(drawn_box)

    drawn_car_s1 = draw_stack(car_slices, turn_deg=0.0, squash=1.0, spacing=1.0, scale=1, shadow=False)
    cw1, ch1 = _opaque_bbox(drawn_car_s1)
    checks["1_squash1_turn0_pixel_exact_and_size"] = {
        "pixel_exact_match": px_exact,
        "box_wh": [bw, bh],
        "tapered_car_wh": [cw1, ch1],
        "ok": (px_exact and bw == 24 and bh == 57 and cw1 == 24),
    }

    # 2. squash=0.75 shorter than squash=1; turn=90 width == slice height (43)
    drawn_car_s075 = draw_stack(car_slices, turn_deg=0.0, squash=0.75, spacing=1.0, scale=1, shadow=False)
    cw75, ch75 = _opaque_bbox(drawn_car_s075)
    drawn_box_90 = draw_stack(box_slices, turn_deg=90.0, squash=0.75, spacing=1.0, scale=1, shadow=False)
    w90, _ = _opaque_bbox(drawn_box_90)
    checks["2_squash_075_and_turn_90"] = {
        "car_squash1_h": ch1,
        "car_squash075_wh": [cw75, ch75],
        "turn90_width": w90,
        "ok": (ch75 < ch1 and w90 == 43),
    }

    # 3. spacing=2 taller than spacing=1; spacing=0 & squash=1 draws flat == slice height with top slice on top
    drawn_sp2 = draw_stack(box_slices, turn_deg=0.0, squash=1.0, spacing=2.0, scale=1, shadow=False)
    _, h_sp2 = _opaque_bbox(drawn_sp2)
    drawn_flat = draw_stack(box_slices, turn_deg=0.0, squash=1.0, spacing=0.0, scale=1, shadow=False)
    flat_w, flat_h = _opaque_bbox(drawn_flat)
    flat_matches_top = bool(np.array_equal(np.asarray(drawn_flat), box_slices[-1]))
    checks["3_spacing_2_and_0_flat"] = {
        "spacing1_h": bh,
        "spacing2_h": h_sp2,
        "spacing0_flat_wh": [flat_w, flat_h],
        "spacing0_matches_top_slice": flat_matches_top,
        "ok": (h_sp2 > bh and flat_h == 43 and flat_matches_top),
    }

    # 4. Circle drive heading: turn = atan2(vy, vx) - pi/2, reverse preserves heading
    t_right = round(math.degrees(turn_from_velocity(1.0, 0.0)), 3)
    t_down = round(math.degrees(turn_from_velocity(0.0, 1.0)), 3)
    t_left = round(math.degrees(turn_from_velocity(-1.0, 0.0)), 3)
    t_up = round(math.degrees(turn_from_velocity(0.0, -1.0)), 3)
    t_rev = round(math.degrees(turn_from_velocity(-1.0, 0.0, reverse=True, heading_rad=math.radians(-90.0))), 3)
    checks["4_circle_heading_atan2"] = {
        "right_deg": t_right,
        "down_deg": t_down,
        "left_deg": t_left,
        "up_deg": t_up,
        "reverse_keeps_heading_deg": t_rev,
        "ok": (t_right == -90.0 and t_down == 0.0 and t_left == 90.0 and t_up == -180.0 and t_rev == -90.0),
    }

    # 5. Four-view pipeline -> visual hull + minimal 2-file output check
    sheet_img, _ = make_demo_car_sheet()
    sheet_path = tmp_root / "_verify_sheet.png"
    out_dir = tmp_root / "_verify_out"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_img.save(sheet_path)
    views = load_sheet_views(sheet_path, [])
    solid, carved_slices, _, stripped = build_slices_from_views(views, edge_color=2, shade=0.25, colors=24)
    out_dir.mkdir(parents=True, exist_ok=True)
    slices_to_strip(carved_slices, gap=0).save(out_dir / "slices_strip.png")
    frames, _ = render_turntable_frames(carved_slices, angle_step=30.0, scale=4, outline_color=(24, 22, 30) if stripped else None)
    save_gif(frames, out_dir / "preview.gif", fps=12.0, bg="white")
    written_files = sorted(p.name for p in out_dir.iterdir())
    checks["5_four_views_carve_and_minimal_out"] = {
        "voxel_count": int(solid.sum()),
        "slices": len(carved_slices),
        "outline_stripped": stripped,
        "minimal_files": written_files,
        "ok": (int(solid.sum()) > 1000 and len(carved_slices) == 10 and stripped and written_files == ["preview.gif", "slices_strip.png"]),
    }

    # 6. Outline drawn once after stack avoids dark interior slice seams
    probe_base = draw_stack(carved_slices, turn_deg=30.0, squash=0.75, scale=1, shadow=False, outline_color=None)
    wh6 = (probe_base.width + 4, probe_base.height + 4)
    no_out = draw_stack(carved_slices, turn_deg=30.0, squash=0.75, scale=1, shadow=False, outline_color=None, canvas_wh=wh6)
    one_out = draw_stack(carved_slices, turn_deg=30.0, squash=0.75, scale=1, shadow=False, outline_color=(24, 22, 30), canvas_wh=wh6)
    arr_no = np.asarray(no_out)[..., :3]
    arr_one = np.asarray(one_out)[..., :3]
    a_no = np.asarray(no_out)[..., 3] > 0
    # Pixels strictly INSIDE original opaque mask must stay completely untouched by final outline
    interior_unchanged = bool(np.array_equal(arr_no[a_no], arr_one[a_no]))
    checks["6_final_outline_preserves_interior"] = {
        "interior_unchanged": interior_unchanged,
        "ok": interior_unchanged,
    }

    # Cleanup internal verify temp dir
    for p in out_dir.iterdir():
        p.unlink()
    out_dir.rmdir()
    sheet_path.unlink()

    all_passed = all(v["ok"] for v in checks.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in checks.values() if v["ok"]), "total": len(checks), "checks": checks}


GODOT4_STACK_GD = """# SpriteStack2D.gd — Stacked slice renderer for Godot 4 (Node2D)
# Sheet must be a single horizontal row of equal slices, ground slice on the left.
# Set project Default Texture Filter to Nearest and keep position rounded to whole pixels.
class_name SpriteStack2D
extends Node2D

@export var sheet: Texture2D
@export var slices := 15
@export var turn := 0.0                      # radians (0 faces +Y down in sheet)
@export_range(0.1, 1.0) var squash := 0.75   # 1.0 straight down, 0.75 low camera
@export var spacing := 1.0                   # screen px per height slice (0 = flat)


func set_heading_from_velocity(vel: Vector2, reversing := false) -> void:
\tif not reversing and vel.length_squared() > 0.01:
\t\tturn = vel.angle() - PI * 0.5


func _process(_delta: float) -> void:
\tqueue_redraw()


func _draw() -> void:
\tif sheet == null or slices <= 0:
\t\treturn
\tvar w := float(sheet.get_width()) / float(slices)
\tvar h := float(sheet.get_height())
\tvar rect := Rect2(-floorf(w * 0.5), -floorf(h * 0.5), w, h)
\tvar spin := Transform2D(turn, Vector2.ZERO)
\tfor z in slices:
\t\tvar lift := Transform2D(Vector2(1.0, 0.0), Vector2(0.0, squash), Vector2(0.0, -roundf(float(z) * spacing)))
\t\tdraw_set_transform_matrix(lift * spin)
\t\tdraw_texture_rect_region(sheet, rect, Rect2(float(z) * w, 0.0, w, h))
"""

UNITY_STACK_CS = """// SpriteStack2D.cs — Child SpriteRenderer stack for Unity (use Point filter on slice sprites)
using UnityEngine;

public class SpriteStack2D : MonoBehaviour
{
    public Sprite[] slices;                  // ground slice at index 0
    [Range(0.1f, 1f)] public float squash = 0.75f;
    public float pixelSize = 1f / 32f;       // 1 screen px in world units
    public float spacingPx = 1f;
    public float turnRad = 0f;
    public int baseSortingOrder = 0;

    private SpriteRenderer[] _renderers;

    private void Awake()
    {
        if (slices == null) return;
        _renderers = new SpriteRenderer[slices.Length];
        for (int z = 0; z < slices.Length; z++)
        {
            var child = new GameObject($"Slice_{z:D2}");
            child.transform.SetParent(transform, false);
            var sr = child.AddComponent<SpriteRenderer>();
            sr.sprite = slices[z];
            sr.sortingOrder = baseSortingOrder + z;
            _renderers[z] = sr;
        }
    }

    public void SetVelocityHeading(Vector2 vel, bool reversing = false)
    {
        if (!reversing && vel.sqrMagnitude > 0.001f)
            turnRad = Mathf.Atan2(vel.y, vel.x) - Mathf.PI * 0.5f;
    }

    private void LateUpdate()
    {
        if (_renderers == null) return;
        float deg = -turnRad * Mathf.Rad2Deg;
        for (int z = 0; z < _renderers.Length; z++)
        {
            var t = _renderers[z].transform;
            t.localPosition = new Vector3(0f, Mathf.Round(z * spacingPx) * pixelSize, 0f);
            t.localScale = new Vector3(1f, squash, 1f);
            t.localRotation = Quaternion.Euler(0f, 0f, deg);
        }
    }
}
"""

TS_STACK_CODE = """// spriteStack.ts — Canvas 2D / Phaser drawStack helper (imageSmoothingEnabled = false)
export function turnFromVelocity(vx: number, vy: number, reversing = false, currentTurn = 0): number {
  if (reversing || (vx === 0 && vy === 0)) return currentTurn;
  return Math.atan2(vy, vx) - Math.PI / 2;
}

export function drawStack(
  ctx: CanvasRenderingContext2D,
  sheet: HTMLImageElement | HTMLCanvasElement,
  count: number,
  x: number,
  y: number,
  turnRad: number,
  squash = 0.75,
  spacing = 1.0
): void {
  const w = sheet.width / count;
  const h = sheet.height;
  const rx = -Math.floor(w / 2);
  const ry = -Math.floor(h / 2);
  const px = Math.round(x);
  const py = Math.round(y);
  ctx.imageSmoothingEnabled = false;
  for (let z = 0; z < count; z++) {
    ctx.save();
    ctx.translate(px, py - Math.round(z * spacing));
    ctx.scale(1, squash);
    ctx.rotate(turnRad);
    ctx.drawImage(sheet, z * w, 0, w, h, rx, ry, w, h);
    ctx.restore();
  }
}
"""


def export_code(engine: str) -> str:
    if engine == "godot4":
        return GODOT4_STACK_GD
    if engine == "unity":
        return UNITY_STACK_CS
    if engine == "typescript":
        return TS_STACK_CODE
    raise ValueError(f"Unsupported engine: {engine}")


def _write_outputs(
    out_dir: Path,
    slices: list[np.ndarray],
    args: argparse.Namespace,
    warnings: list[str],
    stripped: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    # 1. Always write clean ground-first game-ready slice strip (`slices_strip.png`)
    strip_img = slices_to_strip(slices, gap=0)
    strip_path = out_dir / "slices_strip.png"
    strip_img.save(strip_path)

    # 2. Always write rotating GIF preview (`preview.gif`)
    outline_col = (24, 22, 30) if (args.outline == "on" or (args.outline == "auto" and stripped)) else None
    frames, angles = render_turntable_frames(
        slices,
        angle_step=args.angle_step,
        squash=args.squash,
        spacing=args.spacing,
        scale=max(1, args.scale),
        shadow=not args.no_shadow,
        shadow_alpha=args.shadow_alpha,
        outline_color=outline_col,
    )
    gif_path = out_dir / "preview.gif"
    save_gif(frames, gif_path, fps=args.fps, bg=args.bg)

    extra_files: list[str] = []
    if getattr(args, "emit_all", False):
        (out_dir / "slices").mkdir(exist_ok=True)
        (out_dir / "frames").mkdir(exist_ok=True)
        for y, s in enumerate(slices):
            p = out_dir / "slices" / f"slice_{y:02d}.png"
            Image.fromarray(s).save(p)
        for i, f in enumerate(frames):
            f.save(out_dir / "frames" / f"frame_{i:03d}.png")
        preview_strip = slices_to_strip(slices, gap=1)
        if args.scale > 1:
            preview_strip = preview_strip.resize((preview_strip.width * args.scale, preview_strip.height * args.scale), Image.NEAREST)
        preview_strip.save(out_dir / "slices_strip_preview.png")
        cw, ch = frames[0].size
        cols = max(1, min(len(frames), 4096 // cw))
        rows = math.ceil(len(frames) / cols)
        sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.alpha_composite(f, ((i % cols) * cw, (i // cols) * ch))
        sheet.save(out_dir / "turntable.png")
        (out_dir / "meta.json").write_text(
            json.dumps({"slices": len(slices), "slice_wh": [slices[0].shape[1], slices[0].shape[0]], "angles": angles, "warnings": warnings}, indent=2),
            encoding="utf-8",
        )
        extra_files = ["slices/", "frames/", "slices_strip_preview.png", "turntable.png", "meta.json"]

    return {
        "slices": len(slices),
        "slice_wh": [int(slices[0].shape[1]), int(slices[0].shape[0])],
        "slices_strip": str(strip_path),
        "preview_gif": str(gif_path),
        "extra_outputs": extra_files,
        "warnings": warnings,
    }


def _add_render_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--angle-step", type=float, default=15.0)
    p.add_argument("--fps", type=float, default=12.0)
    p.add_argument("--squash", type=float, default=0.75)
    p.add_argument("--spacing", type=float, default=1.0)
    p.add_argument("--scale", type=int, default=6)
    p.add_argument("--outline", choices=["auto", "on", "off"], default="auto")
    p.add_argument("--no-shadow", action="store_true")
    p.add_argument("--shadow-alpha", type=int, default=70)
    p.add_argument("--bg", choices=["white", "transparent"], default="white")
    p.add_argument("--emit-all", action="store_true", help="Also emit per-slice PNGs, frames/, turntable.png & meta.json")
    p.add_argument("--json", action="store_true")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprite Stacking Tool (slice, render, demo, verify, export-code)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_slice = sub.add_parser("slice", help="Slice 4 orthographic views into slice strip + preview GIF (minimal 2-file output by default)")
    src = p_slice.add_mutually_exclusive_group(required=True)
    src.add_argument("--sheet", type=Path)
    src.add_argument("--views", nargs="+", type=Path)
    p_slice.add_argument("-o", "--out", type=Path, default=Path("exports/sprite_stack"))
    p_slice.add_argument("--top-faces", choices=["auto", "down", "up"], default="auto")
    p_slice.add_argument("--side-faces", choices=["left", "right"], default="left")
    p_slice.add_argument("--outline-strip", default="auto")
    p_slice.add_argument("--edge-color", type=int, default=2)
    p_slice.add_argument("--shade", type=float, default=0.0, help="Darken lower side faces (e.g. 0.25)")
    p_slice.add_argument("--colors", type=int, default=0, help="Shared median-cut palette size (e.g. 24; 0 = keep original)")
    p_slice.add_argument("--no-back", action="store_true")
    p_slice.add_argument("--bg-tol", type=int, default=10)
    _add_render_flags(p_slice)

    p_ren = sub.add_parser("render", help="Render static frame or rotating GIF from an existing slices_strip.png")
    p_ren.add_argument("--strip", type=Path, required=True)
    p_ren.add_argument("--slices", type=int, required=True)
    p_ren.add_argument("--turn", type=float, default=None, help="If set, render a single baked PNG at this angle in degrees")
    p_ren.add_argument("-o", "--out", type=Path, default=Path("exports/sprite_stack_render"))
    _add_render_flags(p_ren)

    p_demo = sub.add_parser("demo", help="Generate demo voxel sports car 2x2 sheet, slices_strip.png, and preview.gif")
    p_demo.add_argument("-o", "--out", type=Path, default=Path("exports/sprite_stack_demo"))
    p_demo.add_argument("--save-sheet", action="store_true", help="Also save the input 2x2 views_sheet.png")
    _add_render_flags(p_demo)

    p_ver = sub.add_parser("verify", help="Run all 6 automated dimension/pixel/heading/carve tests")
    p_ver.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export draw_stack code for godot4 / unity / typescript")
    p_exp.add_argument("--engine", choices=["godot4", "unity", "typescript"], required=True)
    p_exp.add_argument("--out", type=Path)
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.cmd == "slice":
        warnings: list[str] = []
        views = load_sheet_views(args.sheet, warnings, args.bg_tol) if args.sheet else load_individual_views(args.views, args.bg_tol)
        _, slices, w2, stripped = build_slices_from_views(
            views,
            top_faces=args.top_faces,
            side_faces=args.side_faces,
            edge_color=args.edge_color,
            shade=args.shade,
            colors=args.colors,
            outline_strip=args.outline_strip,
            use_back=not args.no_back,
        )
        res = _write_outputs(args.out, slices, args, warnings + w2, stripped)
        print(json.dumps(res, indent=2) if args.json else f"Wrote {res['slices_strip']} and {res['preview_gif']}")
        return 0

    if args.cmd == "render":
        slices = strip_to_slices(Image.open(args.strip), args.slices)
        if args.turn is not None:
            out_img = draw_stack(
                slices,
                turn_deg=args.turn,
                squash=args.squash,
                spacing=args.spacing,
                scale=max(1, args.scale),
                shadow=not args.no_shadow,
                shadow_alpha=args.shadow_alpha,
                outline_color=(24, 22, 30) if args.outline == "on" else None,
            )
            args.out.parent.mkdir(parents=True, exist_ok=True)
            out_path = args.out if args.out.suffix.lower() == ".png" else args.out / "baked_stack.png"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_img.save(out_path)
            res = {"baked_png": str(out_path), "size": list(out_img.size)}
        else:
            res = _write_outputs(args.out, slices, args, [], False)
        print(json.dumps(res, indent=2) if args.json else str(res))
        return 0

    if args.cmd == "demo":
        sheet_img, n_vox = make_demo_car_sheet()
        args.out.mkdir(parents=True, exist_ok=True)
        sheet_path = args.out / "demo_views_sheet.png"
        if args.save_sheet:
            sheet_img.save(sheet_path)
        views = [img for img in load_sheet_views(sheet_path, [])] if args.save_sheet else []
        if not views:
            tmp_p = args.out / "_tmp_sheet.png"
            sheet_img.save(tmp_p)
            views = load_sheet_views(tmp_p, [])
            tmp_p.unlink()
        _, slices, warnings, stripped = build_slices_from_views(views, edge_color=2, shade=0.2, colors=24)
        res = _write_outputs(args.out, slices, args, warnings, stripped)
        res["voxels"] = n_vox
        print(json.dumps(res, indent=2) if args.json else f"Demo ready in {args.out}")
        return 0

    if args.cmd == "verify":
        res = run_verify(Path("exports"))
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Sprite Stacker verify: {res['passed']}/{res['total']} passed")
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
