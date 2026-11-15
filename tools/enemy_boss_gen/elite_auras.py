"""
Elite Aura Overlay Sprite Generators for 'Aestra: The Last Wish'
Includes Gold (Taming / Sacred Alpha) and Violet (Demonic / Arcane Alpha) overlays (48x48).
"""

import math
from typing import List, Tuple
from PIL import Image, ImageDraw
from .draw_utils import pset, draw_circle, draw_poly

def generate_elite_aura_frame(variant: str, frame_idx: int) -> Image.Image:
    w, h = 48, 48
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bx, by = 24, 24

    if variant == "gold":
        c_outer = (168, 120, 8, 160)
        c_mid = (240, 184, 24, 220)
        c_bright = (255, 230, 120, 240)
        c_core = (255, 255, 255, 255)
    else:  # violet
        c_outer = (85, 20, 120, 160)
        c_mid = (168, 55, 220, 220)
        c_bright = (220, 130, 255, 240)
        c_core = (255, 255, 255, 255)

    # 1. Rotating Sacred Ground Ring
    ring_cy = 40
    rx, ry = 18, 6
    num_pts = 12
    angle_offset = frame_idx * (math.pi / 6.0)
    for i in range(num_pts):
        ang = angle_offset + i * (2.0 * math.pi / num_pts)
        px = int(bx + math.cos(ang) * rx)
        py = int(ring_cy + math.sin(ang) * ry)
        # Alternate brightness
        color = c_bright if i % 2 == 0 else c_mid
        pset(img, px, py, color)

    # Inner ring
    draw.ellipse([bx - rx + 3, ring_cy - ry + 1, bx + rx - 3, ring_cy + ry - 1], outline=c_outer, width=1)

    # 2. Rising Motes / Flames
    mote_seeds = [
        (-10, 36, 1.2),
        (-4, 30, 1.5),
        (5, 34, 1.1),
        (11, 28, 1.4),
        (-8, 22, 1.3),
        (7, 20, 1.6)
    ]
    for mx_rel, my_start, speed in mote_seeds:
        cur_y = int(my_start - (frame_idx * speed * 3) % 24)
        cur_x = int(bx + mx_rel + math.sin(cur_y * 0.3) * 2)
        if 8 <= cur_y <= 42:
            pset(img, cur_x, cur_y, c_bright)
            pset(img, cur_x, cur_y - 1, c_core)

    # 3. Floating Alpha Crest Glyph (above head)
    glyph_y = 10 + (frame_idx % 2)
    if variant == "gold":
        # 3-Pointed Golden Alpha Crown
        crown_pts = [
            (bx - 8, glyph_y),
            (bx - 5, glyph_y - 5),
            (bx - 2, glyph_y - 2),
            (bx, glyph_y - 7),     # Center crown spire
            (bx + 2, glyph_y - 2),
            (bx + 5, glyph_y - 5),
            (bx + 8, glyph_y)
        ]
        for idx in range(len(crown_pts) - 1):
            draw.line([crown_pts[idx], crown_pts[idx + 1]], fill=c_mid, width=2)
        pset(img, bx, glyph_y - 7, c_core)
        pset(img, bx - 5, glyph_y - 5, c_bright)
        pset(img, bx + 5, glyph_y - 5, c_bright)
    else:
        # Demonic Horns & Arcane Sigil
        draw.line([(bx - 2, glyph_y), (bx - 7, glyph_y - 6)], fill=c_mid, width=2)
        draw.line([(bx + 2, glyph_y), (bx + 7, glyph_y - 6)], fill=c_mid, width=2)
        pset(img, bx - 8, glyph_y - 7, c_core)
        pset(img, bx + 8, glyph_y - 7, c_core)
        draw_circle(draw, bx, glyph_y - 2, 2, c_bright)
        pset(img, bx, glyph_y - 2, c_core)

    return img
