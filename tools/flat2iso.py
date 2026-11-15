#!/usr/bin/env python3
"""
Flat2Iso Studio CLI (tools/flat2iso.py)
Headless, AI-friendly 2:1 isometric (dimetric) pixel art converter.
Ports the exact zero-anti-aliasing algorithms from `skills/flat2iso/assets/flat2iso.html`:
  1. Column Shift (Lotovik / Incursio Flat2Iso) with _stripN.png animation support
  2. 3-Face / 5-Face Box Builder (Front + Side + Top -> 2:1 isometric + 4-dir sheets)
  3. Logical Pixel Scale Auto-Detection & Parity Validation
  4. Local Offline Interactive HTML Studio Server (`serve`)

Usage:
  python tools/flat2iso.py inspect sprite.png --json
  python tools/flat2iso.py shift sprite.png --steps 2 --direction right --scale auto --json
  python tools/flat2iso.py shift --demo --outline -o exports/flat2iso/demo_shift.png
  python tools/flat2iso.py box --front f.png --side s.png --top t.png --sheet --sheet-mode strip4 --json
  python tools/flat2iso.py box --demo --rot all --sheet --seams --json
  python tools/flat2iso.py serve --port 8765
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import math
import os
import re
import socketserver
import sys
import webbrowser
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HTML_ASSET = WORKSPACE_ROOT / "skills" / "flat2iso" / "assets" / "flat2iso.html"
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "flat2iso"

LIGHT_PRESETS = {
    "std": (1.0, 0.82, 0.62),
    "rev": (1.0, 0.62, 0.82),
    "none": (1.0, 1.0, 1.0),
}


# ---------------------------------------------------------------------------
# Pixel Buffer Helpers (RGBA uint8 arrays, shape (H, W, 4))
# ---------------------------------------------------------------------------

def new_pix(w: int, h: int) -> np.ndarray:
    return np.zeros((max(1, int(h)), max(1, int(w)), 4), dtype=np.uint8)


def load_rgba(path: Path) -> np.ndarray:
    with Image.open(path) as img:
        return np.array(img.convert("RGBA"), dtype=np.uint8)


def save_rgba(pix: np.ndarray, path: Path, export_scale: int = 1) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(pix, mode="RGBA")
    if export_scale > 1:
        img = img.resize(
            (img.width * export_scale, img.height * export_scale),
            resample=Image.Resampling.NEAREST,
        )
    img.save(path, format="PNG")
    return img.width, img.height


def downscale_pixel_art(src: np.ndarray, scale: int) -> np.ndarray:
    if scale <= 1:
        return src.copy()
    h, w = src.shape[:2]
    out_w = w // scale
    out_h = h // scale
    if out_w < 1 or out_h < 1:
        raise ValueError(f"Scale {scale} is larger than image dimensions {w}x{h}")
    off = scale // 2
    ys = np.arange(out_h) * scale + off
    xs = np.arange(out_w) * scale + off
    return src[np.ix_(ys, xs)].copy()


def detect_scale(pix: np.ndarray) -> int:
    """Detect uniform integer upscaling factor via run-length GCD."""
    h, w = pix.shape[:2]
    g = 0

    for y in range(h):
        row = pix[y]
        changes = np.flatnonzero(np.any(row[1:] != row[:-1], axis=1))
        bounds = np.concatenate(([-1], changes, [w - 1]))
        runs = np.diff(bounds)
        for r in np.unique(runs):
            g = math.gcd(g, int(r))
            if g == 1:
                return 1

    for x in range(w):
        col = pix[:, x]
        changes = np.flatnonzero(np.any(col[1:] != col[:-1], axis=1))
        bounds = np.concatenate(([-1], changes, [h - 1]))
        runs = np.diff(bounds)
        for r in np.unique(runs):
            g = math.gcd(g, int(r))
            if g == 1:
                return 1

    return max(1, min(64, g or 1))


def resolve_scale(src: np.ndarray, scale_arg: str | int) -> tuple[np.ndarray, int]:
    if isinstance(scale_arg, str) and scale_arg.lower() == "auto":
        s = detect_scale(src)
    else:
        s = max(1, int(scale_arg))
    return downscale_pixel_art(src, s), s


def trim_pix(pix: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(pix[:, :, 3] > 0)
    if len(xs) == 0:
        return new_pix(1, 1)
    return pix[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()


def add_outline(pix: np.ndarray, color: tuple[int, int, int, int]) -> np.ndarray:
    h, w = pix.shape[:2]
    out = new_pix(w + 2, h + 2)
    out[1:h + 1, 1:w + 1] = pix
    alpha_mask = out[:, :, 3] > 0
    neighbor = np.zeros_like(alpha_mask)
    neighbor[:, 1:] |= alpha_mask[:, :-1]
    neighbor[:, :-1] |= alpha_mask[:, 1:]
    neighbor[1:, :] |= alpha_mask[:-1, :]
    neighbor[:-1, :] |= alpha_mask[1:, :]
    border = (~alpha_mask) & neighbor
    out[border] = np.array(color, dtype=np.uint8)
    return out


def mirror_x(pix: np.ndarray) -> np.ndarray:
    return pix[:, ::-1].copy()


def rot90_cw(pix: np.ndarray, times: int) -> np.ndarray:
    k = times % 4
    if k == 0:
        return pix.copy()
    return np.rot90(pix, k=-k).copy()


def parse_hex_color(hex_str: str) -> tuple[int, int, int, int]:
    h = hex_str.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"Expected #RRGGBB hex color, got: {hex_str!r}")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def darkest_color(pix: np.ndarray) -> tuple[int, int, int] | None:
    flat = pix.reshape(-1, 4)
    opaque = flat[flat[:, 3] >= 128]
    if len(opaque) == 0:
        return None
    lum = opaque[:, 0] * 0.299 + opaque[:, 1] * 0.587 + opaque[:, 2] * 0.114
    best = opaque[int(np.argmin(lum))]
    return (int(best[0]), int(best[1]), int(best[2]))


def shade_rgb(c: np.ndarray, factor: float) -> np.ndarray:
    # Match JS Math.round(v * f) = floor(v * f + 0.5) for non-negative values
    r = min(255, int(math.floor(int(c[0]) * factor + 0.5)))
    g = min(255, int(math.floor(int(c[1]) * factor + 0.5)))
    b = min(255, int(math.floor(int(c[2]) * factor + 0.5)))
    return np.array([r, g, b, int(c[3])], dtype=np.uint8)


def lit_pixel(c: np.ndarray, factor: float, keep_rgb: tuple[int, int, int] | None) -> np.ndarray:
    if keep_rgb is not None and (int(c[0]), int(c[1]), int(c[2])) == keep_rgb:
        return c
    return shade_rgb(c, factor)


# ---------------------------------------------------------------------------
# Core Algorithms (1:1 parity with flat2iso.html)
# ---------------------------------------------------------------------------

def column_shift(
    pix: np.ndarray,
    steps: int = 2,
    direction: str = "right",
    center: int | None = None,
    invert: bool = False,
) -> np.ndarray:
    h, w = pix.shape[:2]
    steps = max(1, int(steps))
    if center is None:
        center = w // 2

    def sh(x: int) -> int:
        if direction == "right":
            return x // steps
        if direction == "left":
            return (w - 1 - x) // steps
        if x >= center:
            return (x - center) // steps
        return (center - 1 - x) // steps

    shifts = [sh(x) for x in range(w)]
    max_shift = max(shifts) if shifts else 0
    out = new_pix(w, h + max_shift)
    for x, s in enumerate(shifts):
        dy = s if invert else (max_shift - s)
        out[dy:dy + h, x] = pix[:, x]
    return trim_pix(out)


def build_box(
    left: np.ndarray,
    right: np.ndarray,
    top: np.ndarray,
    *,
    l_top: float = 1.0,
    l_left: float = 0.82,
    l_right: float = 0.62,
    keep_outline: bool = True,
    outline: bool = False,
    outline_color: tuple[int, int, int, int] = (26, 19, 38, 255),
    seams: bool = False,
    seam_dark: float = 0.7,
) -> np.ndarray:
    H, W = left.shape[:2]
    D = right.shape[1]
    extra = math.ceil((W + D) / 2) + 3
    ox = W
    oy = H + extra
    out = new_pix(W + D, H + extra)

    outline_l = darkest_color(left) if keep_outline else None
    outline_r = darkest_color(right) if keep_outline else None
    outline_t = darkest_color(top) if keep_outline else None

    def put(x: int, y: int, rgba: np.ndarray) -> None:
        if 0 <= x < out.shape[1] and 0 <= y < out.shape[0]:
            out[y, x] = rgba

    # Left face
    for u in range(W):
        shift = (W - 1 - u) // 2
        for v in range(H):
            c = left[v, u]
            if c[3] == 0:
                continue
            put(ox + (u - W), oy + (v - H) - shift, lit_pixel(c, l_left, outline_l))

    # Right face
    for u in range(D):
        shift = u // 2
        for v in range(H):
            c = right[v, u]
            if c[3] == 0:
                continue
            put(ox + u, oy + (v - H) - shift, lit_pixel(c, l_right, outline_r))

    # Top face: inverse-mapped 2:1 diamond matching staircase edges pixel-for-pixel
    p_l = (-W) // 2
    p_r = (D - 1) // 2
    for sx in range(-W, D):
        p = sx // 2
        j = sx - 2 * p
        t_min = p if p >= 0 else (-1 - p)
        t_max = min(p - 2 * p_l - 1, 2 * p_r - p)
        for t in range(t_min, t_max + 1):
            if sx < 0:
                X = t - p - j
                Z = t + p + 1
            else:
                X = t - p
                Z = t + p + j
            X = max(0, min(W - 1, X))
            Z = max(0, min(D - 1, Z))
            c = top[D - 1 - Z, W - 1 - X]
            if c[3] == 0:
                continue
            put(ox + sx, oy + (-H - 1 - t), lit_pixel(c, l_top, outline_t))

    # Depth-aware seam darkening
    if seams:
        def darken(x: int, y: int) -> None:
            if 0 <= x < out.shape[1] and 0 <= y < out.shape[0] and out[y, x, 3] > 0:
                out[y, x] = shade_rgb(out[y, x], seam_dark)

        for v in range(H):
            darken(ox - 1, oy + (v - H))
        for u in range(W):
            darken(ox + (u - W), oy - H - 1 - ((W - 1 - u) // 2))
        for u in range(D):
            darken(ox + u, oy - H - 1 - (u // 2))

    res = trim_pix(out)
    if outline:
        res = add_outline(res, outline_color)
    return res


def faces_for_rotation(faces: dict[str, np.ndarray | None], rot: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    front = faces["front"]
    side = faces["side"]
    top = faces["top"]
    assert front is not None and side is not None and top is not None
    back = faces["back"] if faces.get("back") is not None else mirror_x(front)
    left_s = faces["left"] if faces.get("left") is not None else mirror_x(side)
    r = rot % 4
    if r == 1:
        return left_s, front, rot90_cw(top, 3)
    if r == 2:
        return back, left_s, rot90_cw(top, 2)
    if r == 3:
        return side, back, rot90_cw(top, 1)
    return front, side, top


def validate_box_faces(faces: dict[str, np.ndarray | None]) -> list[str]:
    errs: list[str] = []
    front, side, top = faces.get("front"), faces.get("side"), faces.get("top")
    if front is None or side is None or top is None:
        return ["front, side, and top faces are required."]
    fh, fw = front.shape[:2]
    sh, sw = side.shape[:2]
    th, tw = top.shape[:2]
    if fw != tw:
        errs.append(f"front width ({fw}) != top width ({tw})")
    if sw != th:
        errs.append(f"side width ({sw}) != top height ({th})")
    if fh != sh:
        errs.append(f"front height ({fh}) != side height ({sh})")
    back = faces.get("back")
    if back is not None and back.shape[:2] != (fh, fw):
        errs.append(f"back size ({back.shape[1]}x{back.shape[0]}) != front size ({fw}x{fh})")
    left_s = faces.get("left")
    if left_s is not None and left_s.shape[:2] != (sh, sw):
        errs.append(f"left size ({left_s.shape[1]}x{left_s.shape[0]}) != side size ({sw}x{sh})")
    return errs


# ---------------------------------------------------------------------------
# Demo Sprites (identical to flat2iso.html)
# ---------------------------------------------------------------------------

def demo_front() -> np.ndarray:
    P = {
        "o": (42, 30, 54, 255),
        "w1": (182, 120, 70, 255),
        "w2": (156, 98, 56, 255),
        "w3": (122, 74, 42, 255),
        "m": (220, 206, 170, 255),
        "k": (240, 200, 80, 255),
    }
    p = new_pix(16, 14)
    for y in range(14):
        for x in range(16):
            c = P["w3"] if (y % 4 == 0) else (P["w2"] if ((x + (y // 4) * 3) % 7 == 0) else P["w1"])
            if x == 0 or y == 0 or x == 15 or y == 13:
                c = P["o"]
            p[y, x] = c
    for x in range(4, 12):
        p[4, x] = P["o"]
        p[10, x] = P["o"]
    for y in range(4, 11):
        p[y, 4] = P["o"]
        p[y, 11] = P["o"]
    for y in range(5, 10):
        for x in range(5, 11):
            p[y, x] = P["m"]
    p[7, 9] = P["k"]
    p[8, 9] = P["o"]
    return p


def demo_side() -> np.ndarray:
    P = {
        "o": (42, 30, 54, 255),
        "w1": (182, 120, 70, 255),
        "w2": (156, 98, 56, 255),
        "w3": (122, 74, 42, 255),
    }
    p = new_pix(10, 14)
    for y in range(14):
        for x in range(10):
            c = P["w3"] if (y % 4 == 0) else (P["w2"] if ((x + y) % 5 == 0) else P["w1"])
            if x == 0 or y == 0 or x == 9 or y == 13:
                c = P["o"]
            p[y, x] = c
    return p


def demo_top() -> np.ndarray:
    P = {
        "o": (42, 30, 54, 255),
        "w1": (182, 120, 70, 255),
        "w2": (156, 98, 56, 255),
        "w3": (122, 74, 42, 255),
    }
    p = new_pix(16, 10)
    for y in range(10):
        for x in range(16):
            c = P["w3"] if (x % 4 == 0) else (P["w2"] if ((x + y) % 6 == 0) else P["w1"])
            if x == 0 or y == 0 or x == 15 or y == 9:
                c = P["o"]
            p[y, x] = c
    return p


# ---------------------------------------------------------------------------
# Strip & Sheet Helpers (GameMaker / Godot Friendly)
# ---------------------------------------------------------------------------

def detect_strip_frames(path: Path) -> int | None:
    m = re.search(r"_strip(\d+)$", path.stem, re.IGNORECASE)
    return int(m.group(1)) if m else None


def pack_uniform_strip(frames: list[np.ndarray]) -> tuple[np.ndarray, int, int]:
    cell_w = max(f.shape[1] for f in frames)
    cell_h = max(f.shape[0] for f in frames)
    sheet = new_pix(cell_w * len(frames), cell_h)
    for idx, frame in enumerate(frames):
        fh, fw = frame.shape[:2]
        # Bottom-center anchor inside each uniform frame cell
        x0 = idx * cell_w + (cell_w - fw) // 2
        y0 = cell_h - fh
        sheet[y0:y0 + fh, x0:x0 + fw] = frame
    return sheet, cell_w, cell_h


def pack_compact_sheet(views: list[np.ndarray], gap: int = 2) -> np.ndarray:
    sheet_h = max(v.shape[0] for v in views)
    sheet_w = sum(v.shape[1] for v in views) + gap * (len(views) - 1)
    sheet = new_pix(sheet_w, sheet_h)
    x = 0
    for v in views:
        vh, vw = v.shape[:2]
        sheet[sheet_h - vh:sheet_h, x:x + vw] = v
        x += vw + gap
    return sheet


def parity_info(width: int, steps: int) -> tuple[bool, str]:
    even_w = (width % 2) == 0
    even_s = (steps % 2) == 0
    if even_w == even_s:
        return True, f"Parity OK: width {width} ({'even' if even_w else 'odd'}), steps {steps} ({'even' if even_s else 'odd'})."
    return False, (
        f"Parity mismatch: width {width} ({'even' if even_w else 'odd'}) vs steps {steps} "
        f"({'even' if even_s else 'odd'}). Even width + even steps or odd width + odd steps gives cleaner edges."
    )


def emit_result(payload: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if not payload.get("ok", True):
        print(f"ERROR: {payload.get('error')}", file=sys.stderr)
        return
    for w in payload.get("warnings", []):
        print(f"WARN: {w}", file=sys.stderr)
    for out in payload.get("outputs", []):
        print(f"Saved: {out['path']} ({out['width']}x{out['height']})")
    if payload.get("summary"):
        print(payload["summary"])


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_inspect(args: argparse.Namespace) -> int:
    in_path = Path(args.input).resolve()
    if not in_path.exists():
        emit_result({"ok": False, "command": "inspect", "error": f"File not found: {in_path}"}, args.json)
        return 1
    raw = load_rgba(in_path)
    detected = detect_scale(raw)
    native = downscale_pixel_art(raw, detected)
    trimmed = trim_pix(native)
    ok_par, par_note = parity_info(native.shape[1], args.steps)
    strip_n = detect_strip_frames(in_path)
    payload = {
        "ok": True,
        "command": "inspect",
        "path": str(in_path),
        "raw_width": int(raw.shape[1]),
        "raw_height": int(raw.shape[0]),
        "detected_scale": detected,
        "native_width": int(native.shape[1]),
        "native_height": int(native.shape[0]),
        "trimmed_width": int(trimmed.shape[1]),
        "trimmed_height": int(trimmed.shape[0]),
        "strip_frames_hint": strip_n,
        "steps": args.steps,
        "parity_compatible": ok_par,
        "parity_note": par_note,
        "summary": (
            f"{in_path.name}: raw {raw.shape[1]}x{raw.shape[0]}, detected scale {detected}x -> "
            f"native {native.shape[1]}x{native.shape[0]} (trimmed {trimmed.shape[1]}x{trimmed.shape[0]}). {par_note}"
        ),
    }
    emit_result(payload, args.json)
    return 0


def cmd_shift(args: argparse.Namespace) -> int:
    if args.demo:
        src_name = "demo_crate"
        raw = demo_front()
        used_scale = 1
        src = raw
        frames_count = args.frames or 1
    else:
        if not args.input:
            emit_result({"ok": False, "command": "shift", "error": "Provide <input> image or --demo."}, args.json)
            return 1
        in_path = Path(args.input).resolve()
        if not in_path.exists():
            emit_result({"ok": False, "command": "shift", "error": f"File not found: {in_path}"}, args.json)
            return 1
        src_name = in_path.stem
        raw = load_rgba(in_path)
        src, used_scale = resolve_scale(raw, args.scale)
        frames_count = args.frames if args.frames is not None else (detect_strip_frames(in_path) or 1)

    if frames_count > 1:
        if src.shape[1] % frames_count != 0:
            emit_result({
                "ok": False,
                "command": "shift",
                "error": f"Native width {src.shape[1]} is not divisible by {frames_count} frames.",
            }, args.json)
            return 1
        frame_w = src.shape[1] // frames_count
        frames = [src[:, i * frame_w:(i + 1) * frame_w] for i in range(frames_count)]
    else:
        frames = [src]

    outline_rgba = parse_hex_color(args.outline_color)
    shifted_frames: list[np.ndarray] = []
    for frame in frames:
        res = column_shift(
            frame,
            steps=args.steps,
            direction=args.direction,
            center=args.center,
            invert=args.invert,
        )
        if args.outline:
            res = add_outline(res, outline_rgba)
        shifted_frames.append(res)

    if len(shifted_frames) > 1:
        out_pix, cell_w, cell_h = pack_uniform_strip(shifted_frames)
        default_name = f"{re.sub(r'_strip\\d+$', '', src_name)}_iso_{args.direction}_s{args.steps}_strip{len(shifted_frames)}.png"
    else:
        out_pix = shifted_frames[0]
        cell_w, cell_h = out_pix.shape[1], out_pix.shape[0]
        default_name = f"{src_name}_iso_{args.direction}_s{args.steps}.png"

    out_path = Path(args.output).resolve() if args.output else (DEFAULT_EXPORT_DIR / default_name)
    out_w, out_h = save_rgba(out_pix, out_path, export_scale=args.export_scale)

    frame_native_w = frames[0].shape[1]
    ok_par, par_note = parity_info(frame_native_w, args.steps)
    warnings = [] if ok_par else [par_note]

    payload = {
        "ok": True,
        "command": "shift",
        "input": {
            "source": "demo" if args.demo else str(Path(args.input).resolve()),
            "detected_or_used_scale": used_scale,
            "native_width": int(src.shape[1]),
            "native_height": int(src.shape[0]),
            "frames": len(shifted_frames),
            "frame_native_width": int(frame_native_w),
        },
        "params": {
            "steps": args.steps,
            "direction": args.direction,
            "center": args.center if args.center is not None else frame_native_w // 2,
            "invert": args.invert,
            "outline": args.outline,
            "export_scale": args.export_scale,
        },
        "parity_compatible": ok_par,
        "parity_note": par_note,
        "warnings": warnings,
        "outputs": [
            {
                "path": str(out_path),
                "width": out_w,
                "height": out_h,
                "native_width": int(out_pix.shape[1]),
                "native_height": int(out_pix.shape[0]),
                "cell_width": int(cell_w * args.export_scale),
                "cell_height": int(cell_h * args.export_scale),
                "frames": len(shifted_frames),
            }
        ],
    }
    emit_result(payload, args.json)
    return 0


def cmd_box(args: argparse.Namespace) -> int:
    faces: dict[str, np.ndarray | None] = {
        "front": None,
        "side": None,
        "top": None,
        "back": None,
        "left": None,
    }
    used_scale = 1
    stem = "demo_box"

    if args.demo:
        faces["front"] = demo_front()
        faces["side"] = demo_side()
        faces["top"] = demo_top()
    else:
        req = {"front": args.front, "side": args.side, "top": args.top}
        missing = [k for k, v in req.items() if not v]
        if missing:
            emit_result({
                "ok": False,
                "command": "box",
                "error": f"Missing required face(s): {', '.join(missing)}. Pass --front, --side, --top or use --demo.",
            }, args.json)
            return 1

        raw_faces: dict[str, np.ndarray] = {}
        for k in ("front", "side", "top", "back", "left"):
            val = getattr(args, k)
            if val:
                p = Path(val).resolve()
                if not p.exists():
                    emit_result({"ok": False, "command": "box", "error": f"{k} file not found: {p}"}, args.json)
                    return 1
                raw_faces[k] = load_rgba(p)
        stem = Path(args.front).stem

        if isinstance(args.scale, str) and args.scale.lower() == "auto":
            used_scale = detect_scale(raw_faces["front"])
        else:
            used_scale = max(1, int(args.scale))

        for k, raw in raw_faces.items():
            faces[k] = downscale_pixel_art(raw, used_scale)

    errs = validate_box_faces(faces)
    if errs:
        emit_result({"ok": False, "command": "box", "error": " ; ".join(errs)}, args.json)
        return 1

    if args.light == "custom":
        l_top, l_left, l_right = args.l_top, args.l_left, args.l_right
    else:
        l_top, l_left, l_right = LIGHT_PRESETS[args.light]

    outline_rgba = parse_hex_color(args.outline_color)
    views = []
    for r in range(4):
        lf, rf, tf = faces_for_rotation(faces, r)
        views.append(
            build_box(
                lf,
                rf,
                tf,
                l_top=l_top,
                l_left=l_left,
                l_right=l_right,
                keep_outline=args.keep_outline,
                outline=args.outline,
                outline_color=outline_rgba,
                seams=args.seams,
                seam_dark=args.seam_dark,
            )
        )

    out_dir = Path(args.out_dir).resolve() if args.out_dir else DEFAULT_EXPORT_DIR
    outputs: list[dict[str, Any]] = []

    if args.sheet_only:
        args.sheet = True

    rot_indices = [] if args.sheet_only else ([0, 1, 2, 3] if args.rot == "all" else [int(args.rot)])
    for r in rot_indices:
        v = views[r]
        if args.output and len(rot_indices) == 1 and not args.sheet:
            out_path = Path(args.output).resolve()
        else:
            out_path = out_dir / f"{stem}_iso_rot{r}.png"
        w, h = save_rgba(v, out_path, export_scale=args.export_scale)
        outputs.append({
            "kind": "rotation",
            "rotation": r,
            "degrees": r * 90,
            "path": str(out_path),
            "width": w,
            "height": h,
            "native_width": int(v.shape[1]),
            "native_height": int(v.shape[0]),
        })

    if args.sheet:
        if args.sheet_mode == "strip4":
            sheet_pix, cw, ch = pack_uniform_strip(views)
            default_sheet = out_dir / f"{stem}_iso_4dir_strip4.png"
        else:
            sheet_pix = pack_compact_sheet(views, gap=2)
            cw, ch = None, None
            default_sheet = out_dir / f"{stem}_iso_4dir_sheet.png"
        sheet_path = Path(args.output).resolve() if (args.output and args.sheet_only) else default_sheet
        sw, sh = save_rgba(sheet_pix, sheet_path, export_scale=args.export_scale)
        sheet_meta: dict[str, Any] = {
            "kind": f"sheet_{args.sheet_mode}",
            "frames": 4,
            "path": str(sheet_path),
            "width": sw,
            "height": sh,
            "native_width": int(sheet_pix.shape[1]),
            "native_height": int(sheet_pix.shape[0]),
        }
        if cw is not None and ch is not None:
            sheet_meta["cell_width"] = int(cw * args.export_scale)
            sheet_meta["cell_height"] = int(ch * args.export_scale)
        outputs.append(sheet_meta)

    f_front, f_side, f_top = faces["front"], faces["side"], faces["top"]
    assert f_front is not None and f_side is not None and f_top is not None
    payload = {
        "ok": True,
        "command": "box",
        "dimensions": {
            "W": int(f_front.shape[1]),
            "D": int(f_side.shape[1]),
            "H": int(f_front.shape[0]),
            "scale_used": used_scale,
            "export_scale": args.export_scale,
        },
        "lighting": {
            "preset": args.light,
            "top": l_top,
            "left": l_left,
            "right": l_right,
            "keep_outline": args.keep_outline,
            "seams": args.seams,
            "seam_dark": args.seam_dark,
            "outline": args.outline,
        },
        "warnings": [],
        "outputs": outputs,
    }
    emit_result(payload, args.json)
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    if not HTML_ASSET.exists():
        print(f"ERROR: HTML studio not found at {HTML_ASSET}", file=sys.stderr)
        return 1
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HTML_ASSET.parent))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/{HTML_ASSET.name}"
        print(f"Serving Flat2Iso Studio at {url} (Ctrl+C to stop)")
        if not args.no_open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
    return 0


# ---------------------------------------------------------------------------
# Argument Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Flat2Iso Studio CLI — Headless 2:1 isometric pixel art converter & HTML studio launcher."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # inspect
    p_ins = sub.add_parser("inspect", help="Detect logical pixel scale and 2:1 parity compatibility")
    p_ins.add_argument("input", help="Path to PNG/image file")
    p_ins.add_argument("--steps", type=int, default=2, help="Target step width for parity check (default: 2)")
    p_ins.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")

    # shift
    p_sh = sub.add_parser("shift", help="Column-shift a flat orthographic sprite (or _stripN.png) to isometric")
    p_sh.add_argument("input", nargs="?", help="Path to flat orthographic image (omit when using --demo)")
    p_sh.add_argument("--demo", action="store_true", help="Use the built-in 16x14 wooden crate demo sprite")
    p_sh.add_argument("--steps", type=int, default=2, choices=[1, 2, 3, 4], help="Columns per 1px vertical step (2 = 2:1 dimetric)")
    p_sh.add_argument("--direction", default="right", choices=["right", "left", "split"], help="Shift direction")
    p_sh.add_argument("--center", type=int, default=None, help="0-based split column index (for --direction split)")
    p_sh.add_argument("--invert", action="store_true", help="Slope downward instead of upward")
    p_sh.add_argument("--scale", default="1", help="Input pixel scale to downscale by ('auto' or integer, default: 1)")
    p_sh.add_argument("--export-scale", type=int, default=1, help="Integer nearest-neighbor export upscale (default: 1)")
    p_sh.add_argument("--outline", action="store_true", help="Add 1px silhouette outline around output")
    p_sh.add_argument("--outline-color", default="#1a1326", help="Silhouette outline hex color (default: #1a1326)")
    p_sh.add_argument("--frames", type=int, default=None, help="Explicit horizontal frame count (auto-detected for *_stripN.png)")
    p_sh.add_argument("-o", "--output", help="Output PNG path")
    p_sh.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")

    # box
    p_bx = sub.add_parser("box", help="Project Front + Side + Top orthographic faces into a 2:1 isometric box")
    p_bx.add_argument("--demo", action="store_true", help="Use built-in 16x14x10 wooden crate demo faces")
    p_bx.add_argument("--front", help="Front face image (W x H)")
    p_bx.add_argument("--side", help="Right side face image (D x H)")
    p_bx.add_argument("--top", help="Top face image (W x D; bottom edge = front, right edge = right side)")
    p_bx.add_argument("--back", help="Optional back face image (W x H; defaults to mirrored front)")
    p_bx.add_argument("--left", help="Optional left side face image (D x H; defaults to mirrored side)")
    p_bx.add_argument("--rot", default="0", choices=["0", "1", "2", "3", "all"], help="Rotation index 0..3 (90 deg steps) or 'all'")
    p_bx.add_argument("--sheet", action="store_true", help="Export 4-direction sprite sheet alongside rotation(s)")
    p_bx.add_argument("--sheet-mode", default="strip4", choices=["strip4", "compact"], help="strip4 = uniform-cell _strip4.png (GameMaker/Godot), compact = 2px gap")
    p_bx.add_argument("--sheet-only", action="store_true", help="When combined with -o and --sheet, write sheet to -o")
    p_bx.add_argument("--light", default="std", choices=["std", "rev", "none", "custom"], help="3-face lighting preset")
    p_bx.add_argument("--l-top", type=float, default=1.0, help="Custom top light multiplier")
    p_bx.add_argument("--l-left", type=float, default=0.82, help="Custom left light multiplier")
    p_bx.add_argument("--l-right", type=float, default=0.62, help="Custom right light multiplier")
    p_bx.add_argument("--keep-outline", action=argparse.BooleanOptionalAction, default=True, help="Protect darkest color per face from lighting")
    p_bx.add_argument("--outline", action="store_true", help="Add 1px silhouette outline around box")
    p_bx.add_argument("--outline-color", default="#1a1326", help="Silhouette outline hex color")
    p_bx.add_argument("--seams", action="store_true", help="Darken face junction seams (depth-aware)")
    p_bx.add_argument("--seam-dark", type=float, default=0.7, help="Seam darkening multiplier (default: 0.7)")
    p_bx.add_argument("--scale", default="1", help="Input pixel scale ('auto' or integer, default: 1)")
    p_bx.add_argument("--export-scale", type=int, default=1, help="Integer nearest-neighbor export upscale (default: 1)")
    p_bx.add_argument("-o", "--output", help="Output PNG path (for single rotation or --sheet-only)")
    p_bx.add_argument("--out-dir", help="Output directory when exporting multiple files")
    p_bx.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")

    # serve
    p_sv = sub.add_parser("serve", help="Launch the offline Flat2Iso Studio HTML UI locally")
    p_sv.add_argument("--port", type=int, default=8765, help="Local port (default: 8765)")
    p_sv.add_argument("--no-open", action="store_true", help="Do not auto-open browser")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "inspect":
        return cmd_inspect(args)
    if args.cmd == "shift":
        return cmd_shift(args)
    if args.cmd == "box":
        return cmd_box(args)
    if args.cmd == "serve":
        return cmd_serve(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
