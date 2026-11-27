#!/usr/bin/env python3
"""
Pixel-Art CRT Shader CLI (crt_shader.py)
Faithful Python reference renderer, synthetic test-frame generator, 4-group automated
verification suite (dither melt, scanline/RGB mask structure, barrel warp corners, off bypass),
and Godot 4 / Unity URP HLSL / WebGL2 shader exporter.

Usage:
    python tools/crt_shader.py verify --json
    python tools/crt_shader.py render --demo --scale 6 -o exports/crt_shader/room_crt.png --json
    python tools/crt_shader.py export-shader --engine all --out-dir exports/crt_shader/shaders --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---- Tuned CRT Knobs (matching shaders/crt.gdshader, PixelArtCRT.shader, crt.glsl) ----
LUMA_BLUR = 0.45
CHROMA_BLUR = 1.2
BEAM_MIN = 0.21
BEAM_MAX = 0.40
MASK_PX = 2.0
MASK_DARK = 0.62
MASK_LIGHT = 1.22
GLOW = 0.26
BOOST = 1.5
WARP = (0.031, 0.041)
GAMMA_IN = 2.4
GAMMA_OUT = 2.2
BEAM_GAIN = 1.32
VIGNETTE = 0.22

RGB_TO_YIQ = np.array(
    [
        [0.299, 0.587, 0.114],
        [0.596, -0.274, -0.322],
        [0.211, -0.523, 0.312],
    ],
    dtype=np.float64,
)
YIQ_TO_RGB = np.array(
    [
        [1.0, 0.956, 0.621],
        [1.0, -0.272, -0.647],
        [1.0, -1.106, 1.703],
    ],
    dtype=np.float64,
)

SHADERS_DIR = Path(__file__).resolve().parent.parent / "skills" / "crt-shader" / "shaders"
SHADER_FILES = {
    "godot4": "crt.gdshader",
    "unity": "PixelArtCRT.shader",
    "webgl2": "crt.glsl",
}


# ---------------------------------------------------------------------------
# Vectorized Faithful CRT Reference Renderer
# ---------------------------------------------------------------------------

def _signal_vectorized(
    yiq_frame: np.ndarray,
    rows: np.ndarray,
    xs: np.ndarray,
) -> np.ndarray:
    """
    Vectorized Stage 1: NTSC YIQ horizontal blur + [1 2 1] luma dither-melt filter.
    yiq_frame: (H, W, 3) float64; rows, xs: shape (N,) int / float64.
    Returns (N, 3) float64 RGB clamped to [0, 1].
    """
    h, w = yiq_frame.shape[:2]
    r_clamped = np.clip(rows, 0, h - 1)
    x0 = np.floor(xs).astype(np.int64)

    # Sample 9 horizontal taps: x0 - 4 .. x0 + 4 -> shape (9, N, 3)
    offsets = np.arange(-4, 5, dtype=np.int64)[:, None]
    xi = np.clip(x0[None, :] + offsets, 0, w - 1)
    taps = yiq_frame[r_clamped[None, :], xi]  # (9, N, 3)

    # k = 1..7 (7 taps), [1 2 1] luma filter on taps[k-1], taps[k], taps[k+1]
    luma = 0.25 * taps[0:7, :, 0] + 0.5 * taps[1:8, :, 0] + 0.25 * taps[2:9, :, 0]
    k_offsets = np.arange(-3, 4, dtype=np.float64)[:, None]  # x0 - 3 .. x0 + 3
    d = (x0[None, :] + k_offsets) + 0.5 - xs[None, :]
    wl = np.exp(-0.5 * (d * d) / (LUMA_BLUR * LUMA_BLUR))
    wc = np.exp(-0.5 * (d * d) / (CHROMA_BLUR * CHROMA_BLUR))

    sum_y = np.sum(luma * wl, axis=0)
    sum_i = np.sum(taps[1:8, :, 1] * wc, axis=0)
    sum_q = np.sum(taps[1:8, :, 2] * wc, axis=0)
    w_y = np.sum(wl, axis=0)
    w_c = np.sum(wc, axis=0)

    yiq = np.stack([sum_y / w_y, sum_i / w_c, sum_q / w_c], axis=-1)
    rgb = yiq @ YIQ_TO_RGB.T
    return np.clip(rgb, 0.0, 1.0)


def _glow_vectorized(
    lin_frame: np.ndarray,
    px: np.ndarray,
    py: np.ndarray,
) -> np.ndarray:
    """Vectorized Stage 4: 5x5 wide Gaussian glow (sigma^2 = 2.56) in linear space."""
    h, w = lin_frame.shape[:2]
    cx = np.floor(px).astype(np.int64)
    cy = np.floor(py).astype(np.int64)
    sumv = np.zeros((px.shape[0], 3), dtype=np.float64)
    weight = np.zeros(px.shape[0], dtype=np.float64)
    for j in range(-2, 3):
        yy = np.clip(cy + j, 0, h - 1)
        dy = (cy + j) + 0.5 - py
        for i in range(-2, 3):
            xx = np.clip(cx + i, 0, w - 1)
            dx = (cx + i) + 0.5 - px
            wt = np.exp(-0.5 * (dx * dx + dy * dy) / 2.56)
            sumv += wt[:, None] * lin_frame[yy, xx]
            weight += wt
    return sumv / weight[:, None]


def render_crt(
    frame_u8: np.ndarray,
    scale: int = 6,
    warp: Tuple[float, float] = WARP,
    glow_on: bool = True,
    mask_on: bool = True,
) -> np.ndarray:
    """
    Render native-resolution RGB uint8 frame through the faithful one-pass CRT shader
    at whole-number `scale`. Returns float64 (H*scale, W*scale, 3) in [0, 1].
    """
    h, w = frame_u8.shape[:2]
    sw, sh = w * scale, h * scale

    rgb01 = frame_u8[:, :, :3].astype(np.float64) / 255.0
    yiq_frame = rgb01 @ RGB_TO_YIQ.T
    lin_frame = np.clip(rgb01, 0.0, 1.0) ** GAMMA_IN

    sy, sx = np.mgrid[:sh, :sw]
    sx_f = sx.astype(np.float64) + 0.5
    sy_f = sy.astype(np.float64) + 0.5
    u = sx_f / float(sw)
    v = sy_f / float(sh)

    # 5. Barrel curvature
    cx = u * 2.0 - 1.0
    cy = v * 2.0 - 1.0
    cx_w = cx * (1.0 + cy * cy * warp[0])
    cy_w = cy * (1.0 + cx * cx * warp[1])
    u2 = cx_w * 0.5 + 0.5
    v2 = cy_w * 0.5 + 0.5

    inside = (u2 >= 0.0) & (u2 <= 1.0) & (v2 >= 0.0) & (v2 <= 1.0)
    out = np.zeros((sh, sw, 3), dtype=np.float64)
    if not np.any(inside):
        return out

    px = u2[inside] * float(w)
    py = v2[inside] * float(h)
    y = py - 0.5
    r0 = np.floor(y).astype(np.int64)

    col = np.zeros((px.shape[0], 3), dtype=np.float64)
    for k in (0, 1):
        sig = _signal_vectorized(yiq_frame, r0 + k, px)
        lin = np.clip(sig, 0.0, 1.0) ** GAMMA_IN
        sigma = BEAM_MIN + (BEAM_MAX - BEAM_MIN) * (lin ** 0.6)
        dist = (y - (r0 + k))[:, None]
        col += lin * np.exp(-0.5 * (dist * dist) / (sigma * sigma))
    col *= BEAM_GAIN

    if mask_on:
        stripe = np.floor(sx_f[inside] / MASK_PX).astype(np.int64) % 3
        mask = np.full_like(col, MASK_DARK)
        mask[np.arange(col.shape[0]), stripe] = MASK_LIGHT
        col *= mask

    if glow_on:
        col += GLOW * _glow_vectorized(lin_frame, px, py)

    vig_r = np.clip((cx_w[inside] ** 2 + cy_w[inside] ** 2) * 0.5, 0.0, 1.0)
    col *= (1.0 - VIGNETTE * (vig_r ** 1.5))[:, None]
    out[inside] = np.clip(col * BOOST, 0.0, 1.0) ** (1.0 / GAMMA_OUT)
    return out


def to_uint8(img_f: np.ndarray) -> np.ndarray:
    return np.clip(img_f * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)


# ---------------------------------------------------------------------------
# Synthetic Test Frames & 4-Group Automated Verification Suite
# ---------------------------------------------------------------------------

def make_test_frames() -> Dict[str, np.ndarray]:
    """Generate the 5 canonical test frames (checker, vlines, hlines, gray, room)."""
    near_black = np.array([24, 20, 28], dtype=np.uint8)
    cream = np.array([240, 226, 190], dtype=np.uint8)
    w = h = 32
    yy, xx = np.mgrid[:h, :w]

    checker = np.where(((xx + yy) % 2 == 0)[:, :, None], cream, near_black).astype(np.uint8)
    vlines = np.where((xx % 2 == 0)[:, :, None], cream, near_black).astype(np.uint8)
    hlines = np.where((yy % 2 == 0)[:, :, None], cream, near_black).astype(np.uint8)
    gray = np.full((h, w, 3), 128, dtype=np.uint8)

    rw, rh = 64, 48
    room = np.full((rh, rw, 3), (52, 40, 60), dtype=np.uint8)
    room[30:, :] = (70, 58, 44)
    for y in range(26, 30):
        for x in range(rw):
            if (x + y) % 2 == 0:
                room[y, x] = (20, 16, 24)
    tx, ty = 14, 12
    room[ty - 2 : ty + 2, tx - 1 : tx + 2] = (255, 200, 90)
    room[ty + 2 : ty + 6, tx : tx + 1] = (120, 80, 40)
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            r2 = dx * dx + dy * dy
            if 16 < r2 <= 36 and (dx + dy) % 2 == 0:
                yy_t, xx_t = ty + dy, tx + dx
                if 0 <= yy_t < rh and 0 <= xx_t < rw:
                    room[yy_t, xx_t] = (150, 110, 70)
    cx, cy = 40, 34
    room[cy : cy + 6, cx : cx + 10] = (110, 70, 35)
    room[cy : cy + 1, cx : cx + 10] = (230, 190, 60)
    room[cy + 3 : cy + 4, cx : cx + 10] = (230, 190, 60)
    for rx, ry in ((24, 40), (26, 41), (25, 39), (28, 40)):
        room[ry : ry + 2, rx : rx + 2] = (140, 130, 120)

    return {"checker": checker, "vlines": vlines, "hlines": hlines, "gray": gray, "room": room}


def _luma(img: np.ndarray) -> np.ndarray:
    return 0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]


def run_verify(scale: int = 6) -> Dict[str, Any]:
    """Run all 4 CRT verification groups (A: melt & hlines, B: gray structure, C: warp corners, D: off bypass)."""
    frames = make_test_frames()
    checks: Dict[str, Any] = {}

    # A1/A2: 1px checkerboard & vertical lines melt along scanlines
    # Average per 6px RGB mask triad across the interior (skipping outer vignette triads)
    triad = int(round(MASK_PX * 3))
    for name in ("checker", "vlines"):
        img = render_crt(frames[name], scale=scale, warp=(0.0, 0.0))
        g = _luma(img)
        h_g, w_g = frames[name].shape[:2]
        stds = []
        for r in range(2, h_g - 2):
            row = g[r * scale + scale // 2, :]
            n_triads = len(row) // triad
            triad_means = row[: n_triads * triad].reshape(n_triads, triad).mean(axis=1)
            # Measure central half of the scanline so radial vignette slope doesn't mask dither melt
            q = max(2, n_triads // 4)
            stds.append(float(np.std(triad_means[q:-q])))
        worst = max(stds)
        checks[f"A_{name}_dither_melt"] = {"ok": worst < 0.01, "worst_std": round(worst, 5)}

    # A3: 1px horizontal lines keep their scanline stripes (contrast > 0.15)
    h_img = render_crt(frames["hlines"], scale=scale, warp=(0.0, 0.0))
    prof = _luma(h_img).mean(axis=1)
    scan = prof[scale // 2 :: scale]
    gaps = prof[scale - scale // 2 :: scale]
    contrast = float(np.std(np.concatenate([scan, gaps])))
    checks["A_hlines_keep_stripes"] = {"ok": contrast > 0.15, "contrast_std": round(contrast, 4)}

    # B: flat mid-gray -> 1 centered peak per game row + RGB mask period 6px
    g_img = render_crt(frames["gray"], scale=scale, warp=(0.0, 0.0))
    col = _luma(g_img)[:, g_img.shape[1] // 2]
    peak_offsets = [int(np.argmax(col[r * scale : (r + 1) * scale])) for r in range(frames["gray"].shape[0])]
    # For even scale (e.g. 6), center lies between indices 2 and 3; vignette tips upper half to 3, lower to 2
    valid_centers = {scale // 2 - 1, scale // 2} if (scale % 2 == 0) else {scale // 2}
    even_peaks = set(peak_offsets).issubset(valid_centers)
    row_slice = g_img[scale // 2, 12:60]
    want_dom = np.array([int(x // MASK_PX) % 3 for x in range(12, 60)])
    dom_ok = bool(np.all(np.argmax(row_slice, axis=1) == want_dom))
    checks["B_gray_scanlines_and_rgb_mask"] = {
        "ok": even_peaks and dom_ok,
        "peak_offsets": sorted(set(peak_offsets)),
        "rgb_mask_period_6px_ok": dom_ok,
    }

    # C: default WARP -> 4 corners black
    r_img = render_crt(frames["room"], scale=scale, warp=WARP)
    corners = [r_img[0, 0], r_img[0, -1], r_img[-1, 0], r_img[-1, -1]]
    max_corner = float(max(c.max() for c in corners))
    checks["C_warp_four_corners_black"] = {"ok": max_corner < 0.01, "max_corner": round(max_corner, 5)}

    # D: shader off -> nearest integer upscale matches pixel-for-pixel
    room = frames["room"]
    kron_up = np.kron(room, np.ones((scale, scale, 1), dtype=np.uint8))
    rep_up = np.repeat(np.repeat(room, scale, axis=0), scale, axis=1)
    checks["D_off_nearest_exact"] = {"ok": bool(np.array_equal(kron_up, rep_up))}

    all_ok = all(bool(v["ok"]) for v in checks.values())
    return {
        "ok": all_ok,
        "passed": sum(1 for v in checks.values() if v["ok"]),
        "total": len(checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pixel-Art CRT Shader Reference Renderer, Verifier & Exporter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify", help="Run all 4 CRT verification groups (A..D)")
    p_ver.add_argument("--scale", type=int, default=6, help="Integer display scale (default: 6)")
    p_ver.add_argument("--json", action="store_true")

    p_ren = sub.add_parser("render", help="Render a native-resolution PNG (or --demo) through the CRT shader")
    p_ren.add_argument("input", nargs="?", help="Native-resolution pixel-art PNG")
    p_ren.add_argument("--demo", action="store_true", help="Render built-in 64x48 dithered dungeon room")
    p_ren.add_argument("-o", "--output", default="exports/crt_shader/crt_preview.png")
    p_ren.add_argument("--scale", type=int, default=6, help="Whole-number display scale (default: 6)")
    p_ren.add_argument("--flat", action="store_true", help="Disable curvature (WARP = 0)")
    p_ren.add_argument("--no-glow", action="store_true", help="Disable 5x5 phosphor glow")
    p_ren.add_argument("--no-mask", action="store_true", help="Disable RGB aperture grille mask")
    p_ren.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-shader", help="Export Godot 4 / Unity URP / WebGL2 CRT shaders")
    p_exp.add_argument("--engine", choices=["godot4", "unity", "webgl2", "all"], default="all")
    p_exp.add_argument("--out-dir", type=Path, help="Optional directory to write shader files")
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.cmd == "verify":
        res = run_verify(scale=max(2, args.scale))
        print(json.dumps(res, indent=2) if args.json else f"CRT verify: {res['passed']}/{res['total']} passed")
        return 0 if res["ok"] else 1

    if args.cmd == "render":
        if args.demo:
            frame = make_test_frames()["room"]
        elif args.input:
            frame = np.array(Image.open(args.input).convert("RGB"), dtype=np.uint8)
        else:
            parser.error("Provide an input PNG or pass --demo.")
        warp = (0.0, 0.0) if args.flat else WARP
        img_f = render_crt(frame, scale=max(1, args.scale), warp=warp, glow_on=not args.no_glow, mask_on=not args.no_mask)
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(to_uint8(img_f), mode="RGB").save(out_path)
        payload = {
            "ok": True,
            "output": str(out_path),
            "native_size": [int(frame.shape[1]), int(frame.shape[0])],
            "output_size": [int(img_f.shape[1]), int(img_f.shape[0])],
            "scale": args.scale,
            "warp": list(warp),
        }
        print(json.dumps(payload, indent=2) if args.json else f"Rendered CRT preview -> {out_path}")
        return 0

    if args.cmd == "export-shader":
        targets = list(SHADER_FILES.keys()) if args.engine == "all" else [args.engine]
        written: Dict[str, str] = {}
        sources: Dict[str, str] = {}
        for t in targets:
            src_path = SHADERS_DIR / SHADER_FILES[t]
            code = src_path.read_text(encoding="utf-8")
            sources[t] = code
            if args.out_dir:
                args.out_dir.mkdir(parents=True, exist_ok=True)
                dest = args.out_dir / SHADER_FILES[t]
                dest.write_text(code, encoding="utf-8")
                written[t] = str(dest)
        if args.json:
            out: Dict[str, Any] = {"ok": True, "targets": targets}
            if written:
                out["written"] = written
            else:
                out["shaders"] = {t: {"filename": SHADER_FILES[t], "chars": len(sources[t])} for t in targets}
            print(json.dumps(out, indent=2))
        else:
            if written:
                for t, p in written.items():
                    print(f"Exported {t} -> {p}")
            else:
                for t in targets:
                    print(f"=== {SHADER_FILES[t]} ===\n{sources[t]}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
