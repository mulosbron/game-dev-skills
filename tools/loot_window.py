#!/usr/bin/env python3
"""
Pixel Art Loot Window CLI: 9-slice tileable frame, code-drawn rarity slots (Common..Legendary),
staggered reveal timeline (chest shake -> lid open -> window fade+slide -> per-item landing FX),
screen-blended elliptical glow + 7 light shafts, demo PNG/GIF renderer, Godot 4 / Unity export & verify.

Usage:
    python tools/loot_window.py verify --json
    python tools/loot_window.py demo --out exports/loot_window --scale 4 --json
    python tools/loot_window.py export-code --engine godot4 --out-dir exports/loot_window
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")

WINDOW_W = 222
WINDOW_H = 172
PATCH_B = 16
COLS = 5
ROWS = 3
SLOT_SIZE = 34
SLOT_GAP = 3
GRID_ORIGIN = (20, 22)
TITLE_PLATE_SIZE = (64, 18)
TITLE_TOP_OFFSET = -7
BUTTON_SIZE = (80, 20)
BUTTON_Y = 136
CHEST_SIZE = (48, 40)

RARITIES: dict[str, dict[str, Any]] = {
    "common": {"border": "#5e6878", "light": "#8b96a6", "fill": "#26212e", "sparkles": 0, "ring_px": 0},
    "uncommon": {"border": "#3a7d3a", "light": "#6cbf4a", "fill": "#1c2a22", "sparkles": 4, "ring_px": 0},
    "rare": {"border": "#2f6fc4", "light": "#64b3f0", "fill": "#1b2440", "sparkles": 6, "ring_px": 3},
    "epic": {"border": "#6d3aa8", "light": "#a974e0", "fill": "#261c3a", "sparkles": 8, "ring_px": 5},
    "legendary": {"border": "#d9a440", "light": "#f2d16b", "fill": "#33261a", "sparkles": 14, "ring_px": 0},
}

# Tiny 3x5 pixel digits 0-9 for bottom-right stack counts
DIGITS_3X5: dict[str, tuple[str, ...]] = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    s = h.lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb[:3])


def smoothstep01(t: float) -> float:
    u = max(0.0, min(1.0, t))
    return u * u * (3.0 - 2.0 * u)


def slot_position(index: int) -> tuple[int, int]:
    """Return top-left (x, y) in art pixels for slot index 0..14 inside 222x172 window."""
    if not (0 <= index < COLS * ROWS):
        raise ValueError(f"Slot index {index} out of range 0..{COLS * ROWS - 1}")
    col = index % COLS
    row = index // COLS
    step = SLOT_SIZE + SLOT_GAP
    return GRID_ORIGIN[0] + col * step, GRID_ORIGIN[1] + row * step


def make_synthetic_frame_96() -> Image.Image:
    """Create a deterministic 96x96 ornate wooden frame with brass corners and 16px tiled edges."""
    img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    px = img.load()
    wood_dark = (58, 36, 26, 255)
    wood_mid = (102, 66, 44, 255)
    wood_hi = (138, 92, 58, 255)
    brass_dark = (146, 102, 34, 255)
    brass_mid = (212, 162, 62, 255)
    brass_hi = (244, 214, 114, 255)
    inner_bg = (28, 22, 34, 255)
    outline = (22, 16, 24, 255)

    for y in range(96):
        for x in range(96):
            in_top = y < 16
            in_bot = y >= 80
            in_left = x < 16
            in_right = x >= 80
            if not (in_top or in_bot or in_left or in_right):
                px[x, y] = inner_bg
                continue
            if x in (0, 95) or y in (0, 95) or (x in (15, 80) and 15 <= y <= 80) or (y in (15, 80) and 15 <= x <= 80):
                px[x, y] = outline
            elif (in_top or in_bot) and (in_left or in_right):
                # Corner brass bracket
                px[x, y] = brass_hi if (x in (2, 82) or y in (2, 82)) else (brass_dark if (x in (14, 94) or y in (14, 94)) else brass_mid)
                if (x in (5, 90)) and (y in (5, 90)):
                    px[x, y] = wood_dark  # corner rivet
            else:
                # Repeating 16px wood planks + brass rivets along middle edge segment
                t = (x - 16) % 16 if (in_top or in_bot) else (y - 16) % 16
                c = wood_hi if (y in (2, 82) or x in (2, 82)) else (wood_dark if (y in (14, 93) or x in (14, 93)) else wood_mid)
                if t == 8 and ((y in (7, 8, 87, 88)) or (x in (7, 8, 87, 88))):
                    c = brass_mid
                px[x, y] = c
    return img


def nine_slice(src: Image.Image, w: int, h: int, b: int = PATCH_B) -> Image.Image:
    """Cut src into 3x3 pieces `b` px from each edge; keep corners exact and repeat/tile edges & center."""
    src_rgba = src.convert("RGBA")
    sw, sh = src_rgba.size
    if w < 2 * b or h < 2 * b or sw <= 2 * b or sh <= 2 * b:
        raise ValueError(f"Invalid dimensions for 9-slice border {b}: src=({sw},{sh}), out=({w},{h})")
    src_cols = [(0, b), (b, sw - b), (sw - b, sw)]
    src_rows = [(0, b), (b, sh - b), (sh - b, sh)]
    out_cols = [(0, b), (b, w - b), (w - b, w)]
    out_rows = [(0, b), (b, h - b), (h - b, h)]
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for (sy0, sy1), (y0, y1) in zip(src_rows, out_rows):
        for (sx0, sx1), (x0, x1) in zip(src_cols, out_cols):
            piece = src_rgba.crop((sx0, sy0, sx1, sy1))
            pw, ph = piece.size
            for y in range(y0, y1, ph):
                for x in range(x0, x1, pw):
                    part = piece.crop((0, 0, min(pw, x1 - x), min(ph, y1 - y)))
                    out.alpha_composite(part, (x, y))
    return out


def draw_slot(rarity: str, flash_white: bool = False) -> Image.Image:
    """Draw a 34x34 inventory slot with exact rarity border/light/fill and bevel lines."""
    if flash_white:
        return Image.new("RGBA", (SLOT_SIZE, SLOT_SIZE), (255, 255, 255, 255))
    r = RARITIES[rarity]
    border = hex_to_rgb(r["border"]) + (255,)
    light = hex_to_rgb(r["light"]) + (255,)
    fill = hex_to_rgb(r["fill"]) + (255,)
    inner_dark = (max(0, fill[0] - 12), max(0, fill[1] - 12), max(0, fill[2] - 12), 255)
    inner_lite = (min(255, fill[0] + 22), min(255, fill[1] + 22), min(255, fill[2] + 22), 255)

    im = Image.new("RGBA", (SLOT_SIZE, SLOT_SIZE), border)
    px = im.load()
    for y in range(1, SLOT_SIZE - 1):
        for x in range(1, SLOT_SIZE - 1):
            if x == 1 or y == 1:
                px[x, y] = inner_dark
            elif x == SLOT_SIZE - 2 or y == SLOT_SIZE - 2:
                px[x, y] = inner_lite
            else:
                px[x, y] = fill
    if rarity != "common":
        for dy in range(2):
            for dx in range(2):
                px[2 + dx, 2 + dy] = light
    return im


def draw_stack_count(img: Image.Image, count: int) -> None:
    """Draw 3x5 pixel digits with 1px dark outline at bottom-right of a 34x34 slot."""
    if count <= 1:
        return
    s = str(count)
    total_w = len(s) * 4 - 1
    ox = SLOT_SIZE - 2 - total_w - 1
    oy = SLOT_SIZE - 2 - 5 - 1
    px = img.load()
    coords = []
    for ci, ch in enumerate(s):
        glyph = DIGITS_3X5.get(ch, DIGITS_3X5["0"])
        for gy in range(5):
            for gx in range(3):
                if glyph[gy][gx] == "1":
                    coords.append((ox + ci * 4 + gx, oy + gy))
    for x, y in coords:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if 0 <= x + dx < SLOT_SIZE and 0 <= y + dy < SLOT_SIZE:
                    px[x + dx, y + dy] = (18, 14, 24, 255)
    for x, y in coords:
        if 0 <= x < SLOT_SIZE and 0 <= y < SLOT_SIZE:
            px[x, y] = (255, 255, 255, 255)


def glow_shape(tau: float, t: float) -> tuple[float, float, float]:
    """Return (reach, strength, shafts) tau seconds after glow start, t = clock seconds."""
    breathe = math.sin(2.0 * math.pi * t / 2.6)
    calm = (0.6 * (1.0 + 0.06 * breathe), 0.5 * (1.0 + 0.12 * breathe), 0.35)
    peak = (0.95, 0.9, 0.85)
    if tau <= 0.0:
        return 0.0, 0.0, 0.0
    if tau < 0.18:
        e = 1.0 - (1.0 - tau / 0.18) ** 3
        return (peak[0] * e, peak[1] * e, peak[2] * e)
    e = smoothstep01((tau - 0.18) / 0.62)
    return (
        peak[0] + (calm[0] - peak[0]) * e,
        peak[1] + (calm[1] - peak[1]) * e,
        peak[2] + (calm[2] - peak[2]) * e,
    )


def add_glow(floor_rgb: np.ndarray, tau: float, t: float, win_rect: tuple[int, int, int, int]) -> np.ndarray:
    """Apply elliptical round warm glow (255, 178, 84) + 7 rotating light shafts using screen blend."""
    floor = np.asarray(floor_rgb, dtype=np.float32)
    if tau <= 0.0:
        return floor
    h, w = floor.shape[:2]
    wx, wy, ww, wh = win_rect
    cx, cy = wx + ww * 0.5, wy + wh * 0.5
    yy, xx = np.mgrid[:h, :w]
    rx, ry = ww * 0.5, wh * 0.5
    nx, ny = (xx - cx) / max(1.0, rx), (yy - cy) / max(1.0, ry)
    r = np.sqrt(nx * nx + ny * ny)
    a = np.arctan2(ny, nx)

    reach, k, ks = glow_shape(tau, t)
    d = np.maximum(r - 0.55, 0.0)
    glow = np.exp(-d * d / max(1e-6, 2.0 * reach * reach))
    wide = np.exp(-d * d / max(1e-6, 2.0 * (1.45 * reach) ** 2))
    shafts = (0.5 + 0.5 * np.cos(7.0 * (a - 0.18 * t))) ** 3
    light = glow[..., None] * np.array([255.0, 178.0, 84.0], np.float32) * (0.5 * k) + (wide * shafts)[
        ..., None
    ] * np.array([255.0, 218.0, 140.0], np.float32) * (0.32 * ks)
    out = floor + np.minimum(light, 255.0) * (1.0 - floor / 255.0)
    return np.clip(out, 0.0, 255.0)


@dataclass
class LootItem:
    name: str
    rarity: str
    count: int = 1
    material: str = "metal"


def simulate_reveal_at_time(
    items: list[LootItem],
    t_sec: float,
    reveal_enabled: bool = True,
    fps: int = 60,
) -> dict[str, Any]:
    """Evaluate exact state of chest, window, glow, and all 15 slots at timestamp `t_sec`."""
    # Timeline in seconds:
    # 0.00 -> 0.60 chest shake (1px -> 3px)
    # 0.76 -> 1.09 lid 8 frames @ 24fps, 4px hop
    # 1.00 -> 1.22 window alpha 0..1, y_offset 6..0
    # 1.10 glow start (0.1s after window)
    # 1.38 + 0.15 * n land(item n, slot n)
    if not reveal_enabled:
        return {
            "window_alpha": 1.0,
            "window_y_offset": 0,
            "chest_shake_x": 0,
            "lid_frame": 7,
            "slots": [
                {
                    "index": i,
                    "occupied": i < len(items),
                    "rarity": items[i].rarity if i < len(items) else "common",
                    "border": RARITIES[items[i].rarity]["border"] if i < len(items) else RARITIES["common"]["border"],
                    "sparkles_spawned": 0,
                    "white_flash": False,
                }
                for i in range(COLS * ROWS)
            ],
        }

    shake_px = 0
    if 0.0 <= t_sec < 0.60:
        u = t_sec / 0.60
        amp = 1.0 + 2.0 * u
        shake_px = int(round(amp)) * (1 if int(t_sec * fps) % 2 == 0 else -1)

    lid_frame = 0 if t_sec < 0.76 else min(7, int((t_sec - 0.76) * 24.0))

    if t_sec < 1.00:
        win_alpha, win_dy = 0.0, 6
    elif t_sec < 1.22:
        u = smoothstep01((t_sec - 1.00) / 0.22)
        win_alpha, win_dy = u, int(round(6.0 * (1.0 - u)))
    else:
        win_alpha, win_dy = 1.0, 0

    frame_idx = int(round(t_sec * fps))
    slots_out = []
    for i in range(COLS * ROWS):
        has_item = i < len(items)
        land_t = 1.38 + 0.15 * i
        land_frame = int(round(land_t * fps))
        landed = has_item and (frame_idx >= land_frame)
        eff_rarity = items[i].rarity if landed else "common"
        white_flash = landed and (items[i].rarity == "legendary") and (0 <= (frame_idx - land_frame) < 2)
        sparkles = RARITIES[eff_rarity]["sparkles"] if landed else 0
        slots_out.append(
            {
                "index": i,
                "occupied": landed,
                "rarity": eff_rarity,
                "border": RARITIES[eff_rarity]["border"],
                "sparkles_spawned": sparkles,
                "ring_px": RARITIES[eff_rarity]["ring_px"] if landed else 0,
                "white_flash": white_flash,
                "land_time": round(land_t, 4) if has_item else None,
            }
        )

    return {
        "t": round(t_sec, 4),
        "window_alpha": round(win_alpha, 4),
        "window_y_offset": win_dy,
        "chest_shake_px": shake_px,
        "lid_frame": lid_frame,
        "glow_tau": max(0.0, t_sec - 1.10),
        "slots": slots_out,
    }


def _draw_demo_icon(rarity: str, seed: int) -> Image.Image:
    """Create a crisp 32x32 bordered RPG icon centered with >=1px margin."""
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    col = hex_to_rgb(RARITIES[rarity]["light"]) + (255,)
    dark = (22, 16, 24, 255)
    kind = seed % 3
    if kind == 0:  # diagonal sword corner to corner (1px margin)
        for k in range(3, 28):
            for w in (-2, -1, 0, 1, 2):
                x, y = k, 31 - k
                if 1 <= x < 31 and 1 <= y + w < 31:
                    d.point((x, y + w), fill=dark if abs(w) == 2 else col)
        d.rectangle([5, 22, 10, 27], fill=(212, 162, 62, 255), outline=dark)
    elif kind == 1:  # shield / helmet
        d.rounded_rectangle([5, 4, 26, 27], radius=6, fill=col, outline=dark, width=2)
        d.rectangle([10, 11, 21, 16], fill=dark)
    else:  # gem / ring
        d.polygon([(16, 3), (28, 15), (16, 28), (4, 15)], fill=col, outline=dark)
    return im


def render_demo(out_dir: Path, scale: int = 4) -> dict[str, Any]:
    """Render static 4x integer-scaled loot window showcase + glow preview PNG."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_96 = make_synthetic_frame_96()
    win_img = nine_slice(frame_96, WINDOW_W, WINDOW_H, b=PATCH_B)

    sample_items = [
        LootItem("Iron Dagger", "common", 1),
        LootItem("Health Vial", "common", 5),
        LootItem("Ranger Boots", "uncommon", 1),
        LootItem("Knight Helm", "rare", 1),
        LootItem("Arcane Ring", "epic", 1),
        LootItem("Flameblade", "legendary", 1),
        LootItem("Gold Coins", "common", 42),
        LootItem("Mana Potion", "uncommon", 3),
        LootItem("Tower Shield", "rare", 1),
        LootItem("Void Crown", "epic", 1),
        LootItem("Oak Arrow", "common", 16),
        LootItem("Ruby Core", "rare", 2),
    ]

    for idx in range(COLS * ROWS):
        sx, sy = slot_position(idx)
        if idx < len(sample_items):
            it = sample_items[idx]
            sl = draw_slot(it.rarity, flash_white=False)
            icon = _draw_demo_icon(it.rarity, idx)
            sl.alpha_composite(icon, (1, 1))
            draw_stack_count(sl, it.count)
        else:
            sl = draw_slot("common", flash_white=False)
        win_img.alpha_composite(sl, (sx, sy))

    # Compose onto 320x240 floor backdrop with screen-blended round warm glow
    canvas_w, canvas_h = 320, 220
    floor = np.full((canvas_h, canvas_w, 3), 26.0, dtype=np.float32)
    wx, wy = (canvas_w - WINDOW_W) // 2, 26
    lit_floor = add_glow(floor, tau=0.45, t=1.55, win_rect=(wx, wy, WINDOW_W, WINDOW_H))
    bg_img = Image.fromarray(np.clip(lit_floor, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    bg_img.alpha_composite(win_img, (wx, wy))

    # Title plate + bottom button placeholders
    d = ImageDraw.Draw(bg_img)
    tx = wx + (WINDOW_W - TITLE_PLATE_SIZE[0]) // 2
    ty = wy + TITLE_TOP_OFFSET
    d.rectangle([tx, ty, tx + TITLE_PLATE_SIZE[0] - 1, ty + TITLE_PLATE_SIZE[1] - 1], fill=(102, 66, 44, 255), outline=(22, 16, 24, 255))
    bx = wx + (WINDOW_W - BUTTON_SIZE[0]) // 2
    by = wy + BUTTON_Y
    d.rectangle([bx, by, bx + BUTTON_SIZE[0] - 1, by + BUTTON_SIZE[1] - 1], fill=(212, 162, 62, 255), outline=(22, 16, 24, 255))

    scaled = bg_img.resize((canvas_w * scale, canvas_h * scale), Image.NEAREST)
    out_png = out_dir / "loot_window_preview.png"
    scaled.save(out_png)
    return {"preview_png": str(out_png), "scaled_size": list(scaled.size), "items": len(sample_items)}


def run_verify() -> dict[str, Any]:
    """Run all 6 automated verification tests for 9-slice, geometry, timing, FX, flash, and reveal toggle."""
    checks: dict[str, dict[str, Any]] = {}

    # 1. nine_slice(frame_96, 96, 96) equals source frame pixel for pixel
    src_96 = make_synthetic_frame_96()
    ns_96 = nine_slice(src_96, 96, 96, b=PATCH_B)
    exact_96 = bool(np.array_equal(np.asarray(src_96), np.asarray(ns_96)))
    checks["1_nine_slice_96x96_exact"] = {"exact_pixel_match": exact_96, "ok": exact_96}

    # 2. At 222x172, top edge x=16..79 matches x=80..143 identically (tiled, never stretched)
    ns_222 = nine_slice(src_96, WINDOW_W, WINDOW_H, b=PATCH_B)
    arr_222 = np.asarray(ns_222)
    top_tile_1 = arr_222[:PATCH_B, 16:80, :]
    top_tile_2 = arr_222[:PATCH_B, 80:144, :]
    tiles_repeat_exact = bool(np.array_equal(top_tile_1, top_tile_2))
    checks["2_top_edge_222x172_tiles_repeat"] = {
        "x16_79_equals_x80_143": tiles_repeat_exact,
        "ok": tiles_repeat_exact,
    }

    # 3. Slot 14 position == (168, 96)
    s14 = slot_position(14)
    checks["3_slot_14_at_168_96"] = {"slot_14": list(s14), "ok": (s14 == (168, 96))}

    # 4. 12 items: last lands 1.65s after first; slot border stays #5e6878 until its landing frame
    items_12 = [
        LootItem(f"Item{i}", ["common", "uncommon", "rare", "epic", "legendary"][min(4, i // 2 if i < 10 else 4)], 1)
        for i in range(12)
    ]
    st_before_last = simulate_reveal_at_time(items_12, t_sec=1.38 + 0.15 * 11 - 0.02, reveal_enabled=True)
    st_at_last = simulate_reveal_at_time(items_12, t_sec=1.38 + 0.15 * 11 + 0.001, reveal_enabled=True)
    land0 = st_at_last["slots"][0]["land_time"]
    land11 = st_at_last["slots"][11]["land_time"]
    dt_first_to_last = round(land11 - land0, 4)
    slot11_border_before = st_before_last["slots"][11]["border"]
    slot11_border_after = st_at_last["slots"][11]["border"]
    checks["4_12_items_timing_and_gray_before_land"] = {
        "first_to_last_sec": dt_first_to_last,
        "slot11_border_before": slot11_border_before,
        "slot11_border_after": slot11_border_after,
        "ok": (
            abs(dt_first_to_last - 1.65) < 1e-4
            and slot11_border_before == "#5e6878"
            and slot11_border_after != "#5e6878"
        ),
    }

    # 5. Sparkles per landing: [0, 4, 6, 8, 14] and ONLY legendary turns white for exact 2 frames
    items_5 = [
        LootItem("C", "common"),
        LootItem("U", "uncommon"),
        LootItem("R", "rare"),
        LootItem("E", "epic"),
        LootItem("L", "legendary"),
    ]
    sparkles_observed = []
    flash_counts = []
    for idx, it in enumerate(items_5):
        land_f = round((1.38 + 0.15 * idx) * 60)
        st_f0 = simulate_reveal_at_time(items_5, t_sec=land_f / 60.0)
        st_f1 = simulate_reveal_at_time(items_5, t_sec=(land_f + 1) / 60.0)
        st_f2 = simulate_reveal_at_time(items_5, t_sec=(land_f + 2) / 60.0)
        sparkles_observed.append(st_f0["slots"][idx]["sparkles_spawned"])
        flashes = int(st_f0["slots"][idx]["white_flash"]) + int(st_f1["slots"][idx]["white_flash"]) + int(st_f2["slots"][idx]["white_flash"])
        flash_counts.append(flashes)
    # Also check slot pixel drawing flashes pure white only when flash_white=True
    white_slot = draw_slot("legendary", flash_white=True)
    is_pure_white = bool(np.all(np.asarray(white_slot) == 255))
    checks["5_sparkles_and_legendary_2f_flash"] = {
        "sparkles_per_rarity": sparkles_observed,
        "flash_frames_per_rarity": flash_counts,
        "white_slot_all_255": is_pure_white,
        "ok": (sparkles_observed == [0, 4, 6, 8, 14] and flash_counts == [0, 0, 0, 0, 2] and is_pure_white),
    }

    # 6. Reveal turned off shows all loot immediately at t=0
    st_off = simulate_reveal_at_time(items_12, t_sec=0.0, reveal_enabled=False)
    all_shown_immediately = all(s["occupied"] and s["border"] == RARITIES[items_12[i].rarity]["border"] for i, s in enumerate(st_off["slots"][:12]))
    checks["6_reveal_off_shows_at_once"] = {
        "window_alpha_t0": st_off["window_alpha"],
        "all_12_shown_t0": all_shown_immediately,
        "ok": (st_off["window_alpha"] == 1.0 and all_shown_immediately),
    }

    all_passed = all(v["ok"] for v in checks.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in checks.values() if v["ok"]), "total": len(checks), "checks": checks}


GODOT4_LOOT_GD = """# LootWindow.gd — Pixel art 9-slice loot window (222x172 base, integer 4x, tiled patches)
class_name LootWindow
extends Control

const RARITIES := {
\t"common":    {"border": Color("5e6878"), "light": Color("8b96a6"), "fill": Color("26212e"), "sparkles": 0,  "ring": 0},
\t"uncommon":  {"border": Color("3a7d3a"), "light": Color("6cbf4a"), "fill": Color("1c2a22"), "sparkles": 4,  "ring": 0},
\t"rare":      {"border": Color("2f6fc4"), "light": Color("64b3f0"), "fill": Color("1b2440"), "sparkles": 6,  "ring": 3},
\t"epic":      {"border": Color("6d3aa8"), "light": Color("a974e0"), "fill": Color("261c3a"), "sparkles": 8,  "ring": 5},
\t"legendary": {"border": Color("d9a440"), "light": Color("f2d16b"), "fill": Color("33261a"), "sparkles": 14, "ring": 0},
}

@export var reveal_enabled := true
@export var item_interval := 0.15
@export var glow_node: ColorRect

var _frame: NinePatchRect


func _ready() -> void:
\t# Setup 96x96 NinePatchRect tiled on both axes so rivets never stretch
\t_frame = NinePatchRect.new()
\t_frame.patch_margin_left = 16
\t_frame.patch_margin_top = 16
\t_frame.patch_margin_right = 16
\t_frame.patch_margin_bottom = 16
\t_frame.axis_stretch_horizontal = NinePatchRect.AXIS_STRETCH_MODE_TILE
\t_frame.axis_stretch_vertical = NinePatchRect.AXIS_STRETCH_MODE_TILE
\t_frame.custom_minimum_size = Vector2(222, 172)
\t_frame.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
\tadd_child(_frame)


static func slot_position(idx: int) -> Vector2i:
\treturn Vector2i(20 + (idx % 5) * 37, 22 + (idx / 5) * 37)
"""

GODOT4_GLOW_SHADER = """// loot_glow.gdshader — Round elliptical glow + 7 rotating light shafts, screen blended
shader_type canvas_item;

uniform float reach = 0.6;
uniform float strength = 0.5;
uniform float shaft_strength = 0.35;
uniform float clock_t = 0.0;
uniform vec3 glow_color = vec3(1.0, 0.698, 0.329); // (255, 178, 84) / 255
uniform vec3 shaft_color = vec3(1.0, 0.855, 0.549);

void fragment() {
\tvec2 p = (UV - vec2(0.5)) * 2.0;
\tfloat r = length(p);
\tfloat a = atan(p.y, p.x);
\tfloat d = max(r - 0.55, 0.0);
\tfloat g = exp(-d * d / max(0.0001, 2.0 * reach * reach));
\tfloat wide = exp(-d * d / max(0.0001, 2.0 * pow(1.45 * reach, 2.0)));
\tfloat shafts = pow(0.5 + 0.5 * cos(7.0 * (a - 0.18 * clock_t)), 3.0);
\tvec3 col = glow_color * (g * 0.5 * strength) + shaft_color * (wide * shafts * 0.32 * shaft_strength);
\tCOLOR = vec4(col, clamp(max(g * strength, wide * shafts * shaft_strength), 0.0, 1.0));
}
"""

UNITY_LOOT_CS = """// LootWindowSlot.cs — 16px border Tiled 9-slice UI Image + programmatic 34x34 rarity slot helper
using UnityEngine;
using UnityEngine.UI;

public class LootWindowSlot : MonoBehaviour
{
    public Image frameImage;      // Set sprite Border=16 in Sprite Editor and Image.type = Image.Type.Tiled
    public Image borderImage;
    public Image fillImage;
    public Image notchImage;

    public static Vector2Int GetSlotPosition(int idx) => new(20 + (idx % 5) * 37, -(22 + (idx / 5) * 37));

    public void SetRarity(string rarity)
    {
        if (frameImage != null) frameImage.type = Image.Type.Tiled;
        (Color b, Color l, Color f) = rarity switch
        {
            "uncommon"  => (Hex("#3a7d3a"), Hex("#6cbf4a"), Hex("#1c2a22")),
            "rare"      => (Hex("#2f6fc4"), Hex("#64b3f0"), Hex("#1b2440")),
            "epic"      => (Hex("#6d3aa8"), Hex("#a974e0"), Hex("#261c3a")),
            "legendary" => (Hex("#d9a440"), Hex("#f2d16b"), Hex("#33261a")),
            _           => (Hex("#5e6878"), Hex("#8b96a6"), Hex("#26212e")),
        };
        if (borderImage != null) borderImage.color = b;
        if (fillImage != null) fillImage.color = f;
        if (notchImage != null) { notchImage.gameObject.SetActive(rarity != "common"); notchImage.color = l; }
    }

    private static Color Hex(string s) => ColorUtility.TryParseHtmlString(s, out var c) ? c : Color.white;
}
"""


def export_code(engine: str, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if engine == "godot4":
        p1 = out_dir / "LootWindow.gd"
        p2 = out_dir / "loot_glow.gdshader"
        p1.write_text(GODOT4_LOOT_GD, encoding="utf-8")
        p2.write_text(GODOT4_GLOW_SHADER, encoding="utf-8")
        written.extend([str(p1), str(p2)])
    elif engine == "unity":
        p1 = out_dir / "LootWindowSlot.cs"
        p1.write_text(UNITY_LOOT_CS, encoding="utf-8")
        written.append(str(p1))
    else:
        raise ValueError(f"Unsupported engine: {engine}")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Pixel Art Loot Window (9-slice, Rarity FX, Glow) CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify", help="Run all 6 automated checks (9-slice, layout, timing, FX, toggle)")
    p_ver.add_argument("--json", action="store_true")

    p_demo = sub.add_parser("demo", help="Render 4x integer-scaled loot window preview with elliptical glow")
    p_demo.add_argument("--out", type=Path, default=Path("exports/loot_window"))
    p_demo.add_argument("--scale", type=int, default=4)
    p_demo.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export Godot 4 / Unity 9-slice & glow templates")
    p_exp.add_argument("--engine", choices=["godot4", "unity"], required=True)
    p_exp.add_argument("--out-dir", type=Path, default=Path("exports/loot_window"))
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "verify":
        res = run_verify()
        print(json.dumps(res, indent=2) if args.json else f"Loot Window verify: {res['passed']}/{res['total']} passed")
        return 0 if res["all_passed"] else 1

    if args.cmd == "demo":
        res = render_demo(args.out, scale=max(1, args.scale))
        print(json.dumps(res, indent=2) if args.json else f"Rendered {res['preview_png']}")
        return 0

    if args.cmd == "export-code":
        files = export_code(args.engine, args.out_dir)
        print(json.dumps({"engine": args.engine, "files": files}, indent=2) if args.json else str(files))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
