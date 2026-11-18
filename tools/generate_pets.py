#!/usr/bin/env python3
"""
Pet & Companion Sprite Generator for 'Aestra: The Last Wish' (projects/nos)
Generates high-detail 2.5D pixel art animations for all 4 Pets:
1. Kabuk (Tortoise - Tank/Taunt)
2. Curuf (Rock Golem - Slow/Taunt)
3. Cik (Raven - Fast Mule Courier)
4. Kivilcim (Fire Fox - Fire/Taunt)

Exports:
- 16 horizontal sprite strips (_stripN.png) at 48x48 frame resolution
- 16 dynamic 2D normal maps (_n.png) in projects/nos/assets/pets/normals/
- 4 Godot 4 SpriteFrames (.tres) resources
- Pixel-perfect .import files (Nearest, Lossless, No Mipmaps) for Godot 4
"""

import os
import sys
import math
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

FRAME_SIZE = 48  # 48x48 px standard per frame

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PETS_DIR = WORKSPACE_ROOT / "projects" / "nos" / "assets" / "pets"
NORMALS_DIR = PETS_DIR / "normals"
NORMAL_MAP_TOOL = WORKSPACE_ROOT / "tools" / "normal_map_gen.py"

def ensure_dirs():
    PETS_DIR.mkdir(parents=True, exist_ok=True)
    NORMALS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# COLOR PALETTES
# ---------------------------------------------------------------------------
# Kabuk (Tortoise - Moss green carapace matching reference)
C_KABUK_SHELL_DARK   = (30, 48, 20, 255)
C_KABUK_SHELL_MID    = (58, 92, 38, 255)
C_KABUK_SHELL_LIGHT  = (88, 137, 45, 255)
C_KABUK_SHELL_HI     = (122, 178, 62, 255)
C_KABUK_RIM_STONE    = (112, 102, 78, 255)
C_KABUK_RIM_DARK     = (72, 64, 48, 255)
C_KABUK_SKIN_BASE    = (68, 86, 52, 255)
C_KABUK_SKIN_LIGHT   = (96, 118, 72, 255)
C_KABUK_SKIN_SHADOW  = (46, 58, 34, 255)
C_KABUK_UNDERBELLY   = (148, 132, 98, 255)
C_KABUK_EYE_GOLD     = (242, 192, 44, 255)
C_KABUK_EYE_PUPIL    = (24, 20, 12, 255)
C_KABUK_EYE_WHITE    = (255, 250, 230, 255)
C_KABUK_CLAW         = (215, 210, 190, 255)
C_SHADOW             = (16, 20, 24, 85)

# Cüruf (Kristal Golemi - Basalt & Cyan Crystal)
C_CURUF_ROCK_DEEP    = (26, 28, 36, 255)
C_CURUF_ROCK_MID     = (48, 54, 68, 255)
C_CURUF_ROCK_LIGHT   = (78, 88, 106, 255)
C_CURUF_ROCK_HI      = (118, 130, 152, 255)
C_CURUF_CRACK        = (16, 18, 24, 255)
C_CURUF_CRYSTAL_DARK = (18, 110, 142, 255)
C_CURUF_CRYSTAL_MID  = (34, 185, 218, 255)
C_CURUF_CRYSTAL_HI   = (108, 236, 252, 255)
C_CURUF_CRYSTAL_CORE = (215, 250, 255, 255)

# Cik (Raven - Violet Midnight Raven)
C_CIK_FEATHER_BLACK  = (14, 14, 22, 255)
C_CIK_FEATHER_DARK   = (26, 24, 40, 255)
C_CIK_FEATHER_VIOLET = (48, 42, 72, 255)
C_CIK_FEATHER_HI     = (78, 68, 114, 255)
C_CIK_BEAK_BASE      = (42, 40, 48, 255)
C_CIK_BEAK_TIP       = (198, 160, 68, 255)
C_CIK_EYE_AMBER      = (245, 178, 36, 255)
C_CIK_TALON          = (214, 172, 44, 255)

# Kivilcim (Fire Fox - Ember Fox & Living Fire)
C_FOX_FUR_DARK       = (160, 52, 18, 255)
C_FOX_FUR_MID        = (212, 82, 24, 255)
C_FOX_FUR_LIGHT      = (242, 128, 38, 255)
C_FOX_FUR_CREAM      = (248, 238, 222, 255)
C_FOX_EAR_BLACK      = (28, 24, 28, 255)
C_FOX_NOSE_BLACK     = (22, 18, 22, 255)
C_FOX_EYE_GOLD       = (255, 210, 52, 255)
C_FLAME_RED          = (225, 40, 18, 255)
C_FLAME_ORANGE       = (255, 110, 22, 255)
C_FLAME_YELLOW       = (255, 210, 40, 255)
C_FLAME_WHITE        = (255, 255, 200, 255)

# Mule accessories
C_LEATHER_DARK       = (68, 38, 20, 255)
C_LEATHER_MID        = (112, 66, 34, 255)
C_LEATHER_LIGHT      = (154, 98, 52, 255)
C_BRASS_BUCKLE       = (232, 182, 48, 255)
C_CLOTH_SACK         = (182, 166, 134, 255)
C_SACK_SHADOW        = (134, 120, 92, 255)
C_ROPE               = (84, 66, 44, 255)

def create_strip(num_frames: int) -> Image.Image:
    """Creates a transparent RGBA image for a horizontal strip."""
    return Image.new("RGBA", (FRAME_SIZE * num_frames, FRAME_SIZE), (0, 0, 0, 0))

def draw_oval(draw: ImageDraw.ImageDraw, bbox, fill, outline=None):
    draw.ellipse(bbox, fill=fill, outline=outline)

def draw_shadow(draw: ImageDraw.ImageDraw, cx: int, cy: int, rx: int, ry: int):
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=C_SHADOW)

# ===========================================================================
# 1. KABUK (Tortoise)
# ===========================================================================
def draw_kabuk_frame(f_idx: int, anim_type: str, num_frames: int) -> Image.Image:
    img = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Base positioning
    cx, cy = 24, 28
    shell_w, shell_h = 24, 16

    # Animation offsets
    head_dx, head_dy = 0, 0
    shell_dy = 0
    shell_tilt = 0
    mouth_open = False
    eyes_glowing = False
    eyes_closed = False
    fl_step, fr_step, bl_step, br_step = 0, 0, 0, 0
    has_mule = (anim_type == "mule")
    dust_sparks = False
    roar_aura = False

    if anim_type == "idle":
        # Slow breathing
        if f_idx in (1, 2):
            shell_dy = -1
            head_dy = -1
        if f_idx == 2:
            eyes_closed = True

    elif anim_type == "walk":
        # 6-frame crawl: diagonal leg movement
        # frames: 0: neutral, 1: FL+BR forward, 2: passing, 3: FR+BL forward, 4: passing, 5: settle
        walk_cycle = [
            (0, 0, 0, 0, 0, 0),
            (2, -1, -1, 1, -1, 1),
            (1, 0, 0, 0, 0, 0),
            (-1, 2, 1, -1, 1, -1),
            (0, 1, 0, 0, 0, 0),
            (0, 0, 0, 0, 0, 0),
        ]
        fl_step, fr_step, bl_step, br_step, head_dx, shell_tilt = walk_cycle[f_idx % 6]
        head_dy = -1 if f_idx in (1, 3) else 0

    elif anim_type == "taunt":
        # Taunt stomping & hissing roar
        if f_idx == 0:
            # Anticipation
            head_dx, head_dy = -2, 1
            shell_dy = 1
        elif f_idx == 1:
            # Rearing up
            shell_dy = -3
            head_dy = -4
            fl_step, fr_step = -3, -3
        elif f_idx == 2:
            # Ground slam!
            shell_dy = 1
            head_dy = 0
            fl_step, fr_step = 1, 1
            dust_sparks = True
        elif f_idx in (3, 4):
            # Roaring hiss!
            shell_dy = 0
            head_dx = 3
            head_dy = -1
            mouth_open = True
            eyes_glowing = True
            roar_aura = True
        elif f_idx == 5:
            # Recovery
            head_dx = 1
            shell_dy = 0

    elif anim_type == "mule":
        # Walking loaded
        if f_idx in (1, 3):
            shell_dy = -1
            head_dy = -1
        walk_cycle = [(0, 0, 0, 0), (1, -1, -1, 1), (0, 0, 0, 0), (-1, 1, 1, -1)]
        fl_step, fr_step, bl_step, br_step = walk_cycle[f_idx % 4]

    # --- 1. Drop shadow ---
    shadow_rx = 13 + (1 if dust_sparks else 0)
    shadow_ry = 5
    draw_shadow(d, cx, cy + 9, shadow_rx, shadow_ry)

    # Dust particles on slam / taunt
    if dust_sparks:
        dust_pts = [(cx - 15, cy + 8), (cx - 13, cy + 6), (cx + 14, cy + 8), (cx + 12, cy + 6), (cx - 16, cy + 10), (cx + 15, cy + 10)]
        for px, py in dust_pts:
            d.point((px, py), fill=(188, 174, 142, 220))
            d.point((px + 1, py), fill=(214, 202, 175, 180))

    # Roar aura waves
    if roar_aura:
        aura_col = (255, 210, 60, 160) if f_idx == 3 else (255, 160, 40, 120)
        # 2 sonic crescent arcs in front of head
        hx = cx + 13 + head_dx
        hy = cy + 1 + head_dy
        d.arc([hx + 4, hy - 6, hx + 10, hy + 6], start=290, end=70, fill=aura_col, width=1)
        d.arc([hx + 8, hy - 9, hx + 16, hy + 9], start=290, end=70, fill=aura_col, width=1)

    # --- 2. Hind Legs (Back layer) ---
    # Back Left Leg
    bl_x = cx - 9
    bl_y = cy + 4 + shell_dy + bl_step
    draw_oval(d, [bl_x - 3, bl_y - 2, bl_x + 3, bl_y + 4], fill=C_KABUK_SKIN_SHADOW)
    d.rectangle([bl_x - 3, bl_y + 2, bl_x + 3, bl_y + 4], fill=C_KABUK_SKIN_BASE)
    d.point((bl_x - 2, bl_y + 4), fill=C_KABUK_CLAW)
    d.point((bl_x + 1, bl_y + 4), fill=C_KABUK_CLAW)

    # Back Right Leg (far side, darker)
    br_x = cx + 8
    br_y = cy + 3 + shell_dy + br_step
    draw_oval(d, [br_x - 3, br_y - 2, br_x + 3, br_y + 4], fill=C_KABUK_SKIN_SHADOW)
    d.point((br_x, br_y + 4), fill=C_KABUK_CLAW)

    # Tiny tail
    tail_x = cx - 12
    tail_y = cy + 3 + shell_dy
    draw_oval(d, [tail_x - 2, tail_y - 1, tail_x + 1, tail_y + 2], fill=C_KABUK_SKIN_SHADOW)

    # --- 3. Carapace (Shell) ---
    sx = cx - shell_w // 2
    sy = cy - shell_h // 2 + shell_dy
    # Shell base outline
    draw_oval(d, [sx - 1, sy - 1, sx + shell_w + 1, sy + shell_h + 1], fill=C_KABUK_SHELL_DARK)
    # Main shell body
    draw_oval(d, [sx, sy, sx + shell_w, sy + shell_h], fill=C_KABUK_SHELL_MID)
    # Interior moss highlights
    draw_oval(d, [sx + 3, sy + 2, sx + shell_w - 3, sy + shell_h - 4], fill=C_KABUK_SHELL_LIGHT)
    # Top dome highlight
    draw_oval(d, [sx + 6, sy + 3, sx + shell_w - 7, sy + 8], fill=C_KABUK_SHELL_HI)

    # Carapace scute lines (hexagonal plates pattern)
    # Central spine line & ridge grooves
    for rx in range(sx + 6, sx + shell_w - 5, 5):
        d.line([(rx, sy + 3), (rx, sy + shell_h - 4)], fill=C_KABUK_SHELL_DARK, width=1)
    d.line([(sx + 4, sy + 7), (sx + shell_w - 4, sy + 7)], fill=C_KABUK_SHELL_DARK, width=1)

    # Moss specks on shell
    d.point((sx + 8, sy + 5), fill=C_KABUK_SHELL_HI)
    d.point((sx + 14, sy + 4), fill=C_KABUK_SHELL_HI)
    d.point((sx + 11, sy + 9), fill=C_KABUK_SHELL_HI)

    # Shell Rim / Margin (Stone-like Keratin Lip)
    rim_y = sy + shell_h - 4
    draw_oval(d, [sx - 1, rim_y, sx + shell_w + 1, rim_y + 5], fill=C_KABUK_RIM_DARK)
    draw_oval(d, [sx, rim_y + 1, sx + shell_w, rim_y + 4], fill=C_KABUK_RIM_STONE)
    # Notch segments on rim
    for nx in range(sx + 2, sx + shell_w, 4):
        d.point((nx, rim_y + 2), fill=C_KABUK_RIM_DARK)

    # Plastron (Underbelly peek)
    d.line([(sx + 5, rim_y + 4), (sx + shell_w - 5, rim_y + 4)], fill=C_KABUK_UNDERBELLY, width=1)

    # --- 4. Forelegs (Front Layer) ---
    # Front Left Leg (nearer viewer)
    fl_x = cx - 5
    fl_y = cy + 5 + shell_dy + fl_step
    draw_oval(d, [fl_x - 3, fl_y - 2, fl_x + 3, fl_y + 4], fill=C_KABUK_SKIN_SHADOW)
    draw_oval(d, [fl_x - 2, fl_y - 1, fl_x + 3, fl_y + 3], fill=C_KABUK_SKIN_LIGHT)
    d.rectangle([fl_x - 3, fl_y + 2, fl_x + 3, fl_y + 4], fill=C_KABUK_SKIN_BASE)
    d.point((fl_x - 2, fl_y + 4), fill=C_KABUK_CLAW)
    d.point((fl_x, fl_y + 4), fill=C_KABUK_CLAW)
    d.point((fl_x + 2, fl_y + 4), fill=C_KABUK_CLAW)

    # Front Right Leg (stepping forward)
    fr_x = cx + 11
    fr_y = cy + 4 + shell_dy + fr_step
    draw_oval(d, [fr_x - 3, fr_y - 2, fr_x + 3, fr_y + 4], fill=C_KABUK_SKIN_SHADOW)
    draw_oval(d, [fr_x - 2, fr_y - 1, fr_x + 3, fr_y + 3], fill=C_KABUK_SKIN_BASE)
    d.point((fr_x - 1, fr_y + 4), fill=C_KABUK_CLAW)
    d.point((fr_x + 2, fr_y + 4), fill=C_KABUK_CLAW)

    # --- 5. Neck & Head ---
    nx = cx + 9 + head_dx
    ny = cy + 1 + head_dy
    # Neck
    d.rectangle([nx - 3, ny + 1, nx + 2, ny + 5], fill=C_KABUK_SKIN_BASE)
    d.line([(nx - 3, ny + 1), (nx - 3, ny + 5)], fill=C_KABUK_SKIN_SHADOW, width=1)

    # Head
    draw_oval(d, [nx - 1, ny - 3, nx + 6, ny + 3], fill=C_KABUK_SKIN_SHADOW)
    draw_oval(d, [nx, ny - 2, nx + 5, ny + 2], fill=C_KABUK_SKIN_BASE)
    # Snout / beak highlight
    d.point((nx + 5, ny), fill=C_KABUK_SKIN_LIGHT)
    d.point((nx + 4, ny - 1), fill=C_KABUK_SKIN_LIGHT)

    # Mouth
    if mouth_open:
        d.line([(nx + 2, ny + 1), (nx + 5, ny + 3)], fill=(140, 40, 40, 255), width=1)
        d.point((nx + 4, ny + 1), fill=(220, 100, 100, 255))
    else:
        d.line([(nx + 2, ny + 1), (nx + 5, ny + 1)], fill=C_KABUK_SKIN_SHADOW, width=1)

    # Eye
    if eyes_closed:
        d.line([(nx + 2, ny - 1), (nx + 4, ny - 1)], fill=C_KABUK_SKIN_SHADOW, width=1)
    else:
        eye_col = (255, 235, 90, 255) if eyes_glowing else C_KABUK_EYE_GOLD
        d.rectangle([nx + 2, ny - 1, nx + 3, ny], fill=eye_col)
        d.point((nx + 3, ny), fill=C_KABUK_EYE_PUPIL)
        d.point((nx + 2, ny - 1), fill=C_KABUK_EYE_WHITE)

    # --- 6. Mule Pack Accessories (if mule mode) ---
    if has_mule:
        pack_dy = shell_dy
        # Straps wrapping over shell
        d.line([(sx + 5, sy + 3), (sx + 7, sy + shell_h - 3)], fill=C_ROPE, width=1)
        d.line([(sx + 15, sy + 3), (sx + 17, sy + shell_h - 3)], fill=C_ROPE, width=1)

        # Left leather satchel
        draw_oval(d, [sx + 2, sy + 1 + pack_dy, sx + 9, sy + 9 + pack_dy], fill=C_LEATHER_DARK)
        draw_oval(d, [sx + 3, sy + 2 + pack_dy, sx + 8, sy + 8 + pack_dy], fill=C_LEATHER_MID)
        d.line([(sx + 3, sy + 5 + pack_dy), (sx + 8, sy + 5 + pack_dy)], fill=C_LEATHER_LIGHT, width=1)
        d.point((sx + 5, sy + 5 + pack_dy), fill=C_BRASS_BUCKLE)

        # Right cloth sack (bulging with herbs & loot)
        draw_oval(d, [sx + 13, sy + 1 + pack_dy, sx + 21, sy + 10 + pack_dy], fill=C_SACK_SHADOW)
        draw_oval(d, [sx + 14, sy + 2 + pack_dy, sx + 20, sy + 9 + pack_dy], fill=C_CLOTH_SACK)
        # Sack tied top
        d.point((sx + 17, sy + 1 + pack_dy), fill=C_ROPE)
        d.point((sx + 17, sy + pack_dy), fill=C_CLOTH_SACK)

        # Rolled bedroll on top
        draw_oval(d, [sx + 7, sy - 3 + pack_dy, sx + 17, sy + 2 + pack_dy], fill=C_LEATHER_DARK)
        draw_oval(d, [sx + 8, sy - 2 + pack_dy, sx + 16, sy + 1 + pack_dy], fill=(138, 126, 96, 255))
        d.line([(sx + 10, sy - 2 + pack_dy), (sx + 10, sy + 1 + pack_dy)], fill=C_ROPE, width=1)
        d.line([(sx + 14, sy - 2 + pack_dy), (sx + 14, sy + 1 + pack_dy)], fill=C_ROPE, width=1)

    return img

# ===========================================================================
# 2. CÜRUF (Kaya Golemi / Rock Golem)
# ===========================================================================
def draw_curuf_frame(f_idx: int, anim_type: str, num_frames: int) -> Image.Image:
    img = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy = 24, 25
    body_dy = 0
    arm_l_dx, arm_l_dy = 0, 0
    arm_r_dx, arm_r_dy = 0, 0
    core_pulse = 0
    shockwave = False
    crystals_up = False
    has_mule = (anim_type == "mule")

    if anim_type == "idle":
        # Slow rock breathing & core glow pulsing
        pulse_table = [0, 1, 2, 1]
        core_pulse = pulse_table[f_idx % 4]
        if f_idx in (1, 2):
            body_dy = -1

    elif anim_type == "walk":
        # Heavy 6-frame stomping gait
        walk_offsets = [
            (0, 0, 0, 0, 0),
            (-1, -1, 2, 2, -1),
            (-1, 0, 1, 1, 0),
            (0, 1, -1, -1, 1),
            (-1, 2, -2, -2, 2),
            (-1, 0, -1, 0, 0),
        ]
        body_dy, arm_l_dx, arm_l_dy, arm_r_dx, arm_r_dy = walk_offsets[f_idx % 6]
        core_pulse = 1 if f_idx % 2 == 0 else 0

    elif anim_type == "taunt":
        # Ground pound creating small shockwave
        if f_idx == 0:
            body_dy = 1
            arm_l_dy, arm_r_dy = 1, 1
        elif f_idx == 1:
            # Raising both arms high
            body_dy = -3
            arm_l_dy, arm_r_dy = -8, -8
            crystals_up = True
            core_pulse = 2
        elif f_idx == 2:
            # Apex before slam
            body_dy = -4
            arm_l_dy, arm_r_dy = -9, -9
            crystals_up = True
            core_pulse = 3
        elif f_idx == 3:
            # FISTS SLAM THE GROUND!
            body_dy = 2
            arm_l_dy, arm_r_dy = 5, 5
            shockwave = True
            core_pulse = 3
        elif f_idx == 4:
            # Shockwave expands & crystal fissures
            body_dy = 1
            arm_l_dy, arm_r_dy = 4, 4
            shockwave = True
            core_pulse = 2
        elif f_idx == 5:
            # Recovery
            body_dy = 0
            arm_l_dy, arm_r_dy = 1, 1
            core_pulse = 1

    elif anim_type == "mule":
        # Heavy walking with stone chest
        pulse_table = [0, 1, 2, 1]
        core_pulse = pulse_table[f_idx % 4]
        if f_idx in (1, 3):
            body_dy = -1
            arm_l_dy, arm_r_dy = 1, -1

    # --- 1. Drop shadow & shockwave ---
    shadow_rx = 14 + (4 if shockwave else 0)
    shadow_ry = 6 + (2 if shockwave else 0)
    draw_shadow(d, cx, cy + 14, shadow_rx, shadow_ry)

    if shockwave:
        # Radial rock spikes and cyan crystal shards
        radius = 18 if f_idx == 4 else 13
        # Cyan frost wave
        d.ellipse([cx - radius, cy + 14 - radius//3, cx + radius, cy + 14 + radius//3],
                  outline=C_CURUF_CRYSTAL_MID, width=1)
        # Ground fissure cracks
        d.line([(cx - 14, cy + 14), (cx - 7, cy + 12), (cx - 2, cy + 15)], fill=C_CURUF_CRACK, width=1)
        d.line([(cx + 2, cy + 15), (cx + 8, cy + 13), (cx + 15, cy + 14)], fill=C_CURUF_CRACK, width=1)
        # Crystal shard spikes
        shard_coords = [(cx - 12, cy + 10), (cx + 11, cy + 9), (cx - 16, cy + 13), (cx + 15, cy + 12)]
        for sx, sy in shard_coords:
            d.polygon([(sx, sy + 3), (sx + 2, sy - 2), (sx + 4, sy + 3)], fill=C_CURUF_CRYSTAL_HI)
            d.point((sx + 2, sy - 3), fill=C_CURUF_CRYSTAL_CORE)

    # --- 2. Legs / Stumps ---
    leg_y = cy + 8 + body_dy
    # Left leg
    d.rectangle([cx - 8, leg_y, cx - 3, leg_y + 6], fill=C_CURUF_ROCK_DEEP)
    d.rectangle([cx - 7, leg_y, cx - 4, leg_y + 5], fill=C_CURUF_ROCK_MID)
    d.point((cx - 7, leg_y + 5), fill=C_CURUF_ROCK_LIGHT)
    # Right leg
    d.rectangle([cx + 3, leg_y, cx + 8, leg_y + 6], fill=C_CURUF_ROCK_DEEP)
    d.rectangle([cx + 4, leg_y, cx + 7, leg_y + 5], fill=C_CURUF_ROCK_MID)
    d.point((cx + 7, leg_y + 5), fill=C_CURUF_ROCK_LIGHT)

    # --- 3. Crystals on Back / Shoulders (Background Layer) ---
    cryst_y = cy - 8 + body_dy + (-3 if crystals_up else 0)
    # Left crystal spire
    d.polygon([(cx - 10, cryst_y + 4), (cx - 8, cryst_y - 4), (cx - 6, cryst_y + 4)], fill=C_CURUF_CRYSTAL_DARK)
    d.line([(cx - 8, cryst_y - 4), (cx - 7, cryst_y + 4)], fill=C_CURUF_CRYSTAL_HI, width=1)
    d.point((cx - 8, cryst_y - 5), fill=C_CURUF_CRYSTAL_CORE)

    # Right crystal cluster
    d.polygon([(cx + 6, cryst_y + 5), (cx + 9, cryst_y - 5), (cx + 11, cryst_y + 5)], fill=C_CURUF_CRYSTAL_DARK)
    d.line([(cx + 8, cryst_y - 5), (cx + 9, cryst_y + 5)], fill=C_CURUF_CRYSTAL_MID, width=1)
    d.point((cx + 9, cryst_y - 6), fill=C_CURUF_CRYSTAL_CORE)

    # Central back crystal
    d.polygon([(cx - 2, cryst_y + 2), (cx + 1, cryst_y - 6), (cx + 3, cryst_y + 2)], fill=C_CURUF_CRYSTAL_MID)
    d.point((cx + 1, cryst_y - 7), fill=C_CURUF_CRYSTAL_CORE)

    # --- 4. Main Torso / Boulder Chest ---
    bx = cx - 11
    by = cy - 6 + body_dy
    # Chiseled granite boulder
    d.rectangle([bx - 1, by - 1, bx + 23, by + 15], fill=C_CURUF_ROCK_DEEP)
    d.rectangle([bx, by, bx + 22, by + 14], fill=C_CURUF_ROCK_MID)
    # Top chiseled highlight
    d.line([(bx + 2, by), (bx + 20, by)], fill=C_CURUF_ROCK_HI, width=1)
    d.line([(bx + 1, by + 1), (bx + 5, by + 1)], fill=C_CURUF_ROCK_LIGHT, width=1)
    # Rock facet crack lines
    d.line([(bx + 4, by + 3), (bx + 8, by + 8)], fill=C_CURUF_CRACK, width=1)
    d.line([(bx + 14, by + 2), (bx + 18, by + 7)], fill=C_CURUF_CRACK, width=1)

    # Glowing Crystal Heart / Core in chest
    core_x = cx - 2
    core_y = by + 5
    core_colors = [C_CURUF_CRYSTAL_DARK, C_CURUF_CRYSTAL_MID, C_CURUF_CRYSTAL_HI, C_CURUF_CRYSTAL_CORE]
    core_c = core_colors[min(core_pulse, 3)]
    d.rectangle([core_x - 2, core_y - 2, core_x + 4, core_y + 4], fill=C_CURUF_CRACK)
    d.rectangle([core_x - 1, core_y - 1, core_x + 3, core_y + 3], fill=C_CURUF_CRYSTAL_MID)
    d.rectangle([core_x, core_y, core_x + 2, core_y + 2], fill=core_c)
    if core_pulse >= 2:
        d.point((core_x + 1, core_y + 1), fill=C_CURUF_CRYSTAL_CORE)

    # --- 5. Rock Head & Visor ---
    hx = cx - 5
    hy = by - 7
    d.rectangle([hx, hy, hx + 10, hy + 7], fill=C_CURUF_ROCK_DEEP)
    d.rectangle([hx + 1, hy + 1, hx + 9, hy + 6], fill=C_CURUF_ROCK_MID)
    d.line([(hx + 2, hy + 1), (hx + 8, hy + 1)], fill=C_CURUF_ROCK_HI, width=1)

    # Crystal Glowing Eye Slit Visor
    d.line([(hx + 2, hy + 3), (hx + 8, hy + 3)], fill=C_CURUF_CRACK, width=1)
    d.line([(hx + 3, hy + 3), (hx + 7, hy + 3)], fill=core_c, width=1)
    d.point((hx + 5, hy + 3), fill=C_CURUF_CRYSTAL_CORE)

    # --- 6. Arms & Massive Boulder Fists ---
    # Left Arm
    lax = cx - 14 + arm_l_dx
    lay = cy - 2 + body_dy + arm_l_dy
    d.rectangle([lax, lay, lax + 5, lay + 10], fill=C_CURUF_ROCK_DEEP)
    d.rectangle([lax + 1, lay + 1, lax + 4, lay + 9], fill=C_CURUF_ROCK_MID)
    # Left Fist (Big knuckle boulder)
    draw_oval(d, [lax - 2, lay + 7, lax + 6, lay + 14], fill=C_CURUF_ROCK_DEEP)
    draw_oval(d, [lax - 1, lay + 8, lax + 5, lay + 13], fill=C_CURUF_ROCK_MID)
    d.point((lax, lay + 8), fill=C_CURUF_ROCK_HI)
    # Embedded crystal shard on left fist
    d.point((lax + 2, lay + 10), fill=C_CURUF_CRYSTAL_HI)

    # Right Arm
    rax = cx + 9 + arm_r_dx
    ray = cy - 2 + body_dy + arm_r_dy
    d.rectangle([rax, ray, rax + 5, ray + 10], fill=C_CURUF_ROCK_DEEP)
    d.rectangle([rax + 1, ray + 1, rax + 4, ray + 9], fill=C_CURUF_ROCK_MID)
    # Right Fist
    draw_oval(d, [rax - 1, ray + 7, rax + 7, ray + 14], fill=C_CURUF_ROCK_DEEP)
    draw_oval(d, [rax, ray + 8, rax + 6, ray + 13], fill=C_CURUF_ROCK_MID)
    d.point((rax + 5, ray + 8), fill=C_CURUF_ROCK_HI)
    d.point((rax + 3, ray + 10), fill=C_CURUF_CRYSTAL_HI)

    # --- 7. Mule Mode: Rock Chest Backpack ---
    if has_mule:
        ch_x = cx - 8
        ch_y = by - 4
        # Ironbound stone chest
        d.rectangle([ch_x, ch_y, ch_x + 16, ch_y + 10], fill=(22, 24, 30, 255))
        d.rectangle([ch_x + 1, ch_y + 1, ch_x + 15, ch_y + 9], fill=(62, 68, 80, 255))
        # Iron bands
        d.line([(ch_x + 3, ch_y), (ch_x + 3, ch_y + 9)], fill=(120, 128, 140, 255), width=1)
        d.line([(ch_x + 12, ch_y), (ch_x + 12, ch_y + 9)], fill=(120, 128, 140, 255), width=1)
        d.line([(ch_x, ch_y + 4), (ch_x + 15, ch_y + 4)], fill=(100, 108, 120, 255), width=1)
        # Glowing cyan lock rune
        d.point((ch_x + 8, ch_y + 4), fill=C_CURUF_CRYSTAL_CORE)
        d.point((ch_x + 7, ch_y + 4), fill=C_CURUF_CRYSTAL_HI)
        d.point((ch_x + 9, ch_y + 4), fill=C_CURUF_CRYSTAL_HI)
        # Leather harness strapping around golem torso
        d.line([(cx - 10, by + 1), (ch_x, ch_y + 5)], fill=C_LEATHER_DARK, width=1)
        d.line([(cx + 10, by + 1), (ch_x + 15, ch_y + 5)], fill=C_LEATHER_DARK, width=1)

    return img

# ===========================================================================
# 3. CIK (Kuzgun / Raven)
# ===========================================================================
def draw_cik_frame(f_idx: int, anim_type: str, num_frames: int) -> Image.Image:
    img = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy = 24, 24
    is_flying = anim_type in ("fly", "mule")
    has_mule = (anim_type == "mule")
    head_tilt = 0
    wing_phase = 0
    caw_wave = False
    eye_blink = False

    if anim_type == "idle":
        cy = 26
        head_offsets = [0, -1, 1, 0]
        head_tilt = head_offsets[f_idx % 4]
        if f_idx == 2:
            eye_blink = True

    elif anim_type == "fly":
        cy = 20
        wing_phase = f_idx % 6
        # Flying altitude bobbing
        fly_bobs = [0, -2, -3, 1, 2, 0]
        cy += fly_bobs[wing_phase]

    elif anim_type == "caw":
        cy = 26
        if f_idx in (1, 2):
            caw_wave = True
            head_tilt = -2
        elif f_idx == 3:
            head_tilt = 1

    elif anim_type == "mule":
        cy = 18
        wing_phase = f_idx % 6
        fly_bobs = [0, -1, -2, 1, 1, 0]
        cy += fly_bobs[wing_phase]

    # --- 1. Drop Shadow ---
    if is_flying:
        shadow_y = 42
        shadow_rx = 9 - (cy - 18) // 3
        draw_shadow(d, cx, shadow_y, max(shadow_rx, 5), 3)
    else:
        draw_shadow(d, cx, cy + 13, 8, 3)

    # Caw sound wave
    if caw_wave:
        snd_x = cx + 11
        snd_y = cy - 4 + head_tilt
        snd_col = (250, 210, 80, 200) if f_idx == 1 else (235, 175, 40, 140)
        d.arc([snd_x, snd_y - 5, snd_x + 8, snd_y + 5], start=300, end=60, fill=snd_col, width=1)
        d.arc([snd_x + 4, snd_y - 8, snd_x + 14, snd_y + 8], start=300, end=60, fill=snd_col, width=1)

    # --- 2. Talons / Perch / Ground Feet ---
    if not is_flying:
        # Perched legs
        leg_y = cy + 6
        d.line([(cx - 3, leg_y), (cx - 3, leg_y + 5)], fill=C_CIK_FEATHER_BLACK, width=1)
        d.line([(cx + 2, leg_y), (cx + 2, leg_y + 5)], fill=C_CIK_FEATHER_BLACK, width=1)
        # Talons
        d.line([(cx - 5, leg_y + 5), (cx - 1, leg_y + 5)], fill=C_CIK_TALON, width=1)
        d.line([(cx, leg_y + 5), (cx + 4, leg_y + 5)], fill=C_CIK_TALON, width=1)
    else:
        # Tucked or clutching talons
        talon_y = cy + 6
        d.line([(cx - 2, talon_y), (cx - 1, talon_y + 2)], fill=C_CIK_TALON, width=1)
        d.line([(cx + 1, talon_y), (cx + 2, talon_y + 2)], fill=C_CIK_TALON, width=1)

    # --- 3. Body Plumage & Tail ---
    # Tail feathers (pointing back-down)
    tail_x = cx - 10
    tail_y = cy + 4
    if not is_flying:
        d.polygon([(tail_x, tail_y + 6), (cx - 4, tail_y), (tail_x + 3, tail_y + 7)], fill=C_CIK_FEATHER_BLACK)
        d.line([(tail_x + 1, tail_y + 2), (tail_x + 1, tail_y + 6)], fill=C_CIK_FEATHER_VIOLET, width=1)
    else:
        # Tail spread in flight
        d.polygon([(tail_x - 3, cy), (cx - 4, cy + 2), (tail_x - 2, cy + 4)], fill=C_CIK_FEATHER_BLACK)
        d.line([(tail_x - 3, cy + 1), (cx - 4, cy + 2)], fill=C_CIK_FEATHER_VIOLET, width=1)

    # Body egg silhouette
    draw_oval(d, [cx - 6, cy - 3, cx + 5, cy + 7], fill=C_CIK_FEATHER_BLACK)
    draw_oval(d, [cx - 5, cy - 2, cx + 4, cy + 6], fill=C_CIK_FEATHER_DARK)
    draw_oval(d, [cx - 3, cy - 1, cx + 3, cy + 4], fill=C_CIK_FEATHER_VIOLET)
    d.point((cx, cy + 1), fill=C_CIK_FEATHER_HI)

    # --- 4. Wings ---
    if not is_flying:
        # Folded wing at rest
        wx = cx - 5
        wy = cy - 2
        d.polygon([(wx, wy), (wx + 8, wy + 2), (wx + 3, wy + 8), (wx - 2, wy + 5)], fill=C_CIK_FEATHER_BLACK)
        d.polygon([(wx + 1, wy + 1), (wx + 7, wy + 2), (wx + 3, wy + 7)], fill=C_CIK_FEATHER_DARK)
        d.line([(wx + 2, wy + 2), (wx + 5, wy + 6)], fill=C_CIK_FEATHER_VIOLET, width=1)
        d.point((wx + 4, wy + 3), fill=C_CIK_FEATHER_HI)
    else:
        # 6-frame flight flapping cycle
        # 0: Glide flat, 1: Upward stroke 1, 2: Apex up, 3: Downward drive, 4: Full bottom, 5: Return
        if wing_phase == 0:
            # Glide horizontal
            d.polygon([(cx - 16, cy - 2), (cx - 2, cy), (cx - 14, cy + 4)], fill=C_CIK_FEATHER_BLACK)
            d.polygon([(cx + 2, cy), (cx + 16, cy - 2), (cx + 14, cy + 4)], fill=C_CIK_FEATHER_BLACK)
            d.line([(cx - 14, cy - 1), (cx - 4, cy)], fill=C_CIK_FEATHER_VIOLET, width=1)
            d.line([(cx + 4, cy), (cx + 14, cy - 1)], fill=C_CIK_FEATHER_VIOLET, width=1)
        elif wing_phase == 1:
            # Sweeping high
            d.polygon([(cx - 13, cy - 10), (cx - 2, cy - 1), (cx - 9, cy - 3)], fill=C_CIK_FEATHER_BLACK)
            d.polygon([(cx + 2, cy - 1), (cx + 13, cy - 10), (cx + 9, cy - 3)], fill=C_CIK_FEATHER_BLACK)
            d.line([(cx - 11, cy - 8), (cx - 4, cy - 2)], fill=C_CIK_FEATHER_VIOLET, width=1)
            d.line([(cx + 4, cy - 2), (cx + 11, cy - 8)], fill=C_CIK_FEATHER_VIOLET, width=1)
        elif wing_phase == 2:
            # Wings at highest apex
            d.polygon([(cx - 10, cy - 14), (cx - 1, cy - 2), (cx - 5, cy - 4)], fill=C_CIK_FEATHER_BLACK)
            d.polygon([(cx + 1, cy - 2), (cx + 10, cy - 14), (cx + 5, cy - 4)], fill=C_CIK_FEATHER_BLACK)
            d.line([(cx - 8, cy - 11), (cx - 2, cy - 3)], fill=C_CIK_FEATHER_HI, width=1)
            d.line([(cx + 2, cy - 3), (cx + 8, cy - 11)], fill=C_CIK_FEATHER_HI, width=1)
        elif wing_phase == 3:
            # Powerful downstroke
            d.polygon([(cx - 15, cy + 2), (cx - 2, cy), (cx - 12, cy - 3)], fill=C_CIK_FEATHER_BLACK)
            d.polygon([(cx + 2, cy), (cx + 15, cy + 2), (cx + 12, cy - 3)], fill=C_CIK_FEATHER_BLACK)
            d.line([(cx - 13, cy + 1), (cx - 4, cy)], fill=C_CIK_FEATHER_VIOLET, width=1)
            d.line([(cx + 4, cy), (cx + 13, cy + 1)], fill=C_CIK_FEATHER_VIOLET, width=1)
        elif wing_phase == 4:
            # Fully down
            d.polygon([(cx - 12, cy + 8), (cx - 2, cy + 2), (cx - 8, cy + 3)], fill=C_CIK_FEATHER_BLACK)
            d.polygon([(cx + 2, cy + 2), (cx + 12, cy + 8), (cx + 8, cy + 3)], fill=C_CIK_FEATHER_BLACK)
            d.line([(cx - 10, cy + 6), (cx - 3, cy + 2)], fill=C_CIK_FEATHER_VIOLET, width=1)
            d.line([(cx + 3, cy + 2), (cx + 10, cy + 6)], fill=C_CIK_FEATHER_VIOLET, width=1)
        elif wing_phase == 5:
            # Returning to glide
            d.polygon([(cx - 14, cy + 1), (cx - 2, cy), (cx - 11, cy + 5)], fill=C_CIK_FEATHER_BLACK)
            d.polygon([(cx + 2, cy), (cx + 14, cy + 1), (cx + 11, cy + 5)], fill=C_CIK_FEATHER_BLACK)
            d.line([(cx - 12, cy + 1), (cx - 4, cy)], fill=C_CIK_FEATHER_VIOLET, width=1)
            d.line([(cx + 4, cy), (cx + 12, cy + 1)], fill=C_CIK_FEATHER_VIOLET, width=1)

    # --- 5. Raven Head & Sharp Beak ---
    hx = cx + 3
    hy = cy - 4 + head_tilt
    # Skull
    draw_oval(d, [hx - 2, hy - 3, hx + 5, hy + 4], fill=C_CIK_FEATHER_BLACK)
    draw_oval(d, [hx - 1, hy - 2, hx + 4, hy + 3], fill=C_CIK_FEATHER_DARK)
    d.point((hx + 1, hy - 1), fill=C_CIK_FEATHER_VIOLET)

    # Beak (sharp curved horn with gold tip)
    bx = hx + 4
    by = hy
    if caw_wave:
        # Beak snapped open
        d.line([(bx, by - 1), (bx + 5, by - 2)], fill=C_CIK_BEAK_BASE, width=1)
        d.point((bx + 5, by - 2), fill=C_CIK_BEAK_TIP)
        d.line([(bx, by + 1), (bx + 4, by + 2)], fill=C_CIK_BEAK_BASE, width=1)
        d.point((bx + 2, by), fill=(160, 40, 40, 255))
    else:
        d.polygon([(bx, by - 1), (bx + 5, by + 1), (bx, by + 2)], fill=C_CIK_BEAK_BASE)
        d.point((bx + 4, by + 1), fill=C_CIK_BEAK_TIP)
        d.point((bx + 5, by + 1), fill=C_CIK_BEAK_TIP)

    # Eye
    if eye_blink:
        d.line([(hx + 1, hy), (hx + 3, hy)], fill=C_CIK_FEATHER_BLACK, width=1)
    else:
        d.rectangle([hx + 1, hy - 1, hx + 2, hy], fill=C_CIK_EYE_AMBER)
        d.point((hx + 2, hy), fill=(20, 18, 20, 255))
        d.point((hx + 1, hy - 1), fill=(255, 250, 210, 255))

    # --- 6. Mule Mode: Golden Courier Satchel ---
    if has_mule:
        sat_x = cx - 4 + (wing_phase % 2)
        sat_y = cy + 7
        # Straps gripped by talons
        d.line([(cx - 2, cy + 5), (sat_x + 2, sat_y + 1)], fill=C_LEATHER_DARK, width=1)
        d.line([(cx + 2, cy + 5), (sat_x + 6, sat_y + 1)], fill=C_LEATHER_DARK, width=1)

        # Golden courier satchel pouch
        draw_oval(d, [sat_x - 1, sat_y, sat_x + 9, sat_y + 8], fill=(165, 115, 20, 255))
        draw_oval(d, [sat_x, sat_y + 1, sat_x + 8, sat_y + 7], fill=(235, 175, 40, 255))
        # Satchel highlight & flap
        d.line([(sat_x + 1, sat_y + 3), (sat_x + 7, sat_y + 3)], fill=(255, 215, 65, 255), width=1)
        # Ruby/gem buckle
        d.point((sat_x + 4, sat_y + 4), fill=(220, 40, 40, 255))

    return img

# ===========================================================================
# 4. KIVILCIM (Fire Fox)
# ===========================================================================
def draw_kivilcim_frame(f_idx: int, anim_type: str, num_frames: int) -> Image.Image:
    img = Image.new("RGBA", (FRAME_SIZE, FRAME_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx, cy = 24, 25
    has_mule = (anim_type == "mule")
    flame_sparks = []
    tail_angle = 0
    body_stretch = 0
    leap_dy = 0
    taunt_ring = False

    if anim_type == "idle":
        # Alert breathing & tail undulation
        tail_offsets = [0, 2, 4, 2]
        tail_angle = tail_offsets[f_idx % 4]
        if f_idx in (1, 2):
            cy -= 1
        # 2 floating spark embers
        flame_sparks = [(cx - 16, cy - 4 - f_idx), (cx - 12, cy - 10 + f_idx % 2)]

    elif anim_type == "run":
        # Swift low gallop cycle
        run_cycle = [
            (2, 0, 1),
            (1, 1, 0),
            (-1, 2, -1),
            (-2, 1, 1),
            (1, -2, 2),
            (2, -1, 1),
        ]
        body_stretch, leap_dy, tail_angle = run_cycle[f_idx % 6]
        cy += leap_dy
        # Trailing sparks
        flame_sparks = [(cx - 16, cy + 2), (cx - 20, cy - 1)]

    elif anim_type == "taunt":
        # Fox leap + spinning tail swipe + ground sparks
        if f_idx == 0:
            # Crouch
            cy += 2
            tail_angle = -2
        elif f_idx == 1:
            # Springing up
            cy -= 5
            tail_angle = 4
        elif f_idx == 2:
            # Apex spin
            cy -= 7
            tail_angle = 8
            taunt_ring = True
        elif f_idx == 3:
            # Tail swipe across ground
            cy += 1
            tail_angle = -4
            taunt_ring = True
            flame_sparks = [(cx - 10, cy + 10), (cx, cy + 11), (cx + 8, cy + 9), (cx - 4, cy + 8)]
        elif f_idx == 4:
            # Proud landing
            cy += 0
            tail_angle = 3
            flame_sparks = [(cx + 10, cy + 8), (cx - 8, cy + 9)]
        elif f_idx == 5:
            # Settling
            tail_angle = 1

    elif anim_type == "mule":
        # Gallop with saddlebags
        run_cycle = [(2, 0), (1, 1), (-1, 2), (-2, 1), (1, -2), (2, -1)]
        body_stretch, leap_dy = run_cycle[f_idx % 6]
        cy += leap_dy
        tail_angle = 1

    # --- 1. Drop shadow & Taunt ring ---
    draw_shadow(d, cx, cy + 11 - leap_dy, 12, 4)

    if taunt_ring:
        # Ground scorch ring & fire arc
        ring_col = C_FLAME_ORANGE if f_idx == 2 else C_FLAME_YELLOW
        d.arc([cx - 16, cy + 6, cx + 16, cy + 14], start=180, end=360, fill=ring_col, width=1)
        d.arc([cx - 14, cy + 7, cx + 14, cy + 13], start=180, end=360, fill=C_FLAME_RED, width=1)

    # --- 2. Floating Fire Sparks ---
    for sp_x, sp_y in flame_sparks:
        d.point((sp_x, sp_y), fill=C_FLAME_WHITE)
        d.point((sp_x + 1, sp_y), fill=C_FLAME_YELLOW)
        d.point((sp_x, sp_y + 1), fill=C_FLAME_ORANGE)

    # --- 3. Living Fiery Bushy Tail ---
    # Base tail anchor at rear of fox body
    tx = cx - 8
    ty = cy + 1
    # Tail plume curve
    t_tip_x = tx - 9 - tail_angle
    t_tip_y = ty - 9 - (tail_angle // 2)

    # Outer fire red silhouette
    d.polygon([(tx, ty + 2), (t_tip_x - 3, t_tip_y + 2), (t_tip_x, t_tip_y - 4), (tx + 2, ty - 4)], fill=C_FLAME_RED)
    # Bright orange core
    d.polygon([(tx, ty + 1), (t_tip_x - 1, t_tip_y + 1), (t_tip_x + 1, t_tip_y - 2), (tx + 1, ty - 3)], fill=C_FLAME_ORANGE)
    # Yellow flame heart
    d.polygon([(tx, ty), (t_tip_x + 1, t_tip_y), (t_tip_x + 2, t_tip_y - 1), (tx + 1, ty - 1)], fill=C_FLAME_YELLOW)
    # White incandescent flame tip
    d.point((t_tip_x, t_tip_y - 3), fill=C_FLAME_WHITE)
    d.point((t_tip_x + 1, t_tip_y - 2), fill=C_FLAME_WHITE)

    # --- 4. Hind Legs & Paws ---
    hl_x = cx - 6
    hl_y = cy + 4
    # Hind left leg
    d.line([(hl_x, hl_y), (hl_x - 2, hl_y + 5)], fill=C_FOX_FUR_DARK, width=2)
    d.point((hl_x - 2, hl_y + 6), fill=C_FOX_EAR_BLACK)
    # Hind right leg
    d.line([(hl_x + 4, hl_y), (hl_x + 2, hl_y + 5)], fill=C_FOX_FUR_DARK, width=2)
    d.point((hl_x + 2, hl_y + 6), fill=C_FOX_EAR_BLACK)

    # --- 5. Fox Torso ---
    bx = cx - 8
    by = cy - 2
    bw = 14 + body_stretch
    # Auburn fox back
    draw_oval(d, [bx, by, bx + bw, by + 7], fill=C_FOX_FUR_DARK)
    draw_oval(d, [bx + 1, by + 1, bx + bw - 1, by + 6], fill=C_FOX_FUR_MID)
    # Creamy belly
    d.line([(bx + 3, by + 6), (bx + bw - 3, by + 6)], fill=C_FOX_FUR_CREAM, width=1)

    # --- 6. Forelegs & Paws ---
    fl_x = cx + 5
    fl_y = cy + 3
    # Fore left leg
    d.line([(fl_x, fl_y), (fl_x + 1, fl_y + 6)], fill=C_FOX_FUR_MID, width=2)
    d.point((fl_x + 1, fl_y + 7), fill=C_FOX_EAR_BLACK)
    # Fore right leg
    d.line([(fl_x + 3, fl_y), (fl_x + 4, fl_y + 6)], fill=C_FOX_FUR_MID, width=2)
    d.point((fl_x + 4, fl_y + 7), fill=C_FOX_EAR_BLACK)

    # --- 7. Head, Ears & Fox Muzzle ---
    hx = cx + 8
    hy = cy - 4
    # Chest ruff / mane (creamy white)
    d.polygon([(hx - 2, hy + 3), (hx + 3, hy + 6), (hx - 3, hy + 7)], fill=C_FOX_FUR_CREAM)

    # Fox skull
    draw_oval(d, [hx - 2, hy - 3, hx + 5, hy + 4], fill=C_FOX_FUR_DARK)
    draw_oval(d, [hx - 1, hy - 2, hx + 4, hy + 3], fill=C_FOX_FUR_MID)
    d.point((hx + 1, hy - 1), fill=C_FOX_FUR_LIGHT)

    # Pointy triangular ears with black outer tips
    # Left ear
    d.polygon([(hx - 1, hy - 3), (hx, hy - 8), (hx + 2, hy - 3)], fill=C_FOX_FUR_DARK)
    d.point((hx, hy - 8), fill=C_FOX_EAR_BLACK)
    d.point((hx + 1, hy - 5), fill=C_FOX_FUR_CREAM)
    # Right ear
    d.polygon([(hx + 2, hy - 3), (hx + 4, hy - 7), (hx + 5, hy - 3)], fill=C_FOX_FUR_DARK)
    d.point((hx + 4, hy - 7), fill=C_FOX_EAR_BLACK)

    # Sharp fox snout
    sx = hx + 4
    sy = hy + 1
    d.polygon([(sx, sy - 1), (sx + 4, sy + 1), (sx, sy + 2)], fill=C_FOX_FUR_LIGHT)
    d.point((sx + 4, sy + 1), fill=C_FOX_NOSE_BLACK)
    d.point((sx + 1, sy + 2), fill=C_FOX_FUR_CREAM)

    # Golden fox eye
    d.point((hx + 2, hy), fill=C_FOX_EYE_GOLD)
    d.point((hx + 3, hy), fill=(24, 20, 24, 255))

    # --- 8. Mule Mode: Leather Saddlebags ---
    if has_mule:
        sb_x = cx - 3
        sb_y = cy - 1
        # Girth strap over flank
        d.line([(sb_x, sb_y - 1), (sb_x + 1, sb_y + 6)], fill=C_LEATHER_DARK, width=1)
        # Saddlebag pouch
        draw_oval(d, [sb_x - 2, sb_y + 1, sb_x + 5, sb_y + 7], fill=C_LEATHER_DARK)
        draw_oval(d, [sb_x - 1, sb_y + 2, sb_x + 4, sb_y + 6], fill=C_LEATHER_MID)
        # Gold buckle
        d.point((sb_x + 1, sb_y + 4), fill=C_BRASS_BUCKLE)

    return img

# ---------------------------------------------------------------------------
# STRIP BUILDER & EXPORT
# ---------------------------------------------------------------------------
PET_SPECS = [
    {
        "name": "kabuk",
        "display": "Kabuk (Tortoise)",
        "draw_func": draw_kabuk_frame,
        "anims": [
            ("idle", 4, 6.0, True),
            ("walk", 6, 10.0, True),
            ("taunt", 6, 8.0, False),
            ("mule", 4, 8.0, True),
        ]
    },
    {
        "name": "curuf",
        "display": "Curuf (Rock Golem)",
        "draw_func": draw_curuf_frame,
        "anims": [
            ("idle", 4, 6.0, True),
            ("walk", 6, 9.0, True),
            ("taunt", 6, 8.0, False),
            ("mule", 4, 8.0, True),
        ]
    },
    {
        "name": "cik",
        "display": "Cik (Raven)",
        "draw_func": draw_cik_frame,
        "anims": [
            ("idle", 4, 6.0, True),
            ("fly", 6, 12.0, True),
            ("caw", 4, 8.0, False),
            ("mule", 6, 11.0, True),
        ]
    },
    {
        "name": "kivilcim",
        "display": "Kivilcim (Fire Fox)",
        "draw_func": draw_kivilcim_frame,
        "anims": [
            ("idle", 4, 6.0, True),
            ("run", 6, 12.0, True),
            ("taunt", 6, 10.0, False),
            ("mule", 6, 11.0, True),
        ]
    },
]

def generate_all_sprites():
    ensure_dirs()
    generated_strips = []

    print("=== Generating Pet Sprite Strips (48x48) ===")
    for pet in PET_SPECS:
        pet_name = pet["name"]
        print(f"\nProcessing {pet['display']}...")

        for anim_name, num_frames, fps, loop in pet["anims"]:
            strip_filename = f"{pet_name}_{anim_name}_strip{num_frames}.png"
            strip_path = PETS_DIR / strip_filename

            strip_img = create_strip(num_frames)
            for f in range(num_frames):
                frame_img = pet["draw_func"](f, anim_name, num_frames)
                strip_img.paste(frame_img, (f * FRAME_SIZE, 0), frame_img)

            strip_img.save(strip_path)
            print(f"  -> Generated strip: {strip_filename} ({strip_img.size[0]}x{strip_img.size[1]} px)")
            generated_strips.append((strip_path, anim_name, num_frames, fps, loop))

    return generated_strips

# ---------------------------------------------------------------------------
# NORMAL MAPS GENERATION (Pillow Shading + Distance Transform Normal Engine)
# ---------------------------------------------------------------------------
def generate_normal_map(input_png: Path, output_png: Path):
    """
    Generates a 2D normal map using Sobel + Distance Transform / Pillow Shading
    compatible with Pixel Art Lighter v3.6.0.
    """
    img = Image.open(input_png).convert("RGBA")
    arr = np.array(img, dtype=np.float32)

    alpha = arr[:, :, 3] / 255.0
    has_alpha = alpha > 0.1

    if not np.any(has_alpha):
        # Empty image fallback
        norm_img = Image.new("RGBA", img.size, (128, 128, 255, 0))
        norm_img.save(output_png)
        return

    # Luminance relief
    lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0

    # Distance transform (pillow shading)
    from scipy.ndimage import distance_transform_edt, sobel
    dist = distance_transform_edt(has_alpha)
    max_d = np.max(dist) or 1.0
    pillow = dist / max_d

    # Combined height map
    height = pillow * 0.65 + lum * 0.35

    # Sobel gradients
    dx = sobel(height, axis=1) * 1.8
    dy = sobel(height, axis=0) * 1.8
    dz = np.ones_like(dx) * 1.2

    # Normalization
    length = np.sqrt(dx * dx + dy * dy + dz * dz)
    length[length == 0] = 1.0
    nx = -dx / length
    ny = -dy / length
    nz = dz / length

    # Map [-1, 1] to [0, 255]
    r = np.clip((nx * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    g = np.clip((ny * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    b = np.clip((nz * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    a = (has_alpha * 255).astype(np.uint8)

    norm_arr = np.stack([r, g, b, a], axis=-1)
    norm_img = Image.fromarray(norm_arr, "RGBA")
    norm_img.save(output_png)

def generate_all_normals(strips):
    print("\n=== Generating Dynamic 2D Normal Maps (_n.png) ===")
    for strip_path, anim_name, num_frames, fps, loop in strips:
        norm_filename = f"{strip_path.stem}_n.png"
        norm_path = NORMALS_DIR / norm_filename
        generate_normal_map(strip_path, norm_path)
        print(f"  -> Generated normal map: normals/{norm_filename}")

# ---------------------------------------------------------------------------
# GODOT 4 SPRITEFRAMES (.tres) GENERATION
# ---------------------------------------------------------------------------
def generate_godot_spriteframes():
    print("\n=== Generating Godot 4 SpriteFrames Resources (.tres) ===")
    for pet in PET_SPECS:
        pet_name = pet["name"]
        tres_filename = f"{pet_name}_spriteframes.tres"
        tres_path = PETS_DIR / tres_filename

        ext_resources = []
        sub_resources = []
        anim_blocks = []

        ext_id = 1
        sub_id = 1

        for anim_name, num_frames, fps, loop in pet["anims"]:
            strip_filename = f"{pet_name}_{anim_name}_strip{num_frames}.png"
            ext_res_id = f"{ext_id}_{anim_name}"
            ext_resources.append(
                f'[ext_resource type="Texture2D" path="res://assets/pets/{strip_filename}" id="{ext_res_id}"]'
            )

            frame_refs = []
            for f in range(num_frames):
                sub_res_id = f"AtlasTexture_{pet_name}_{anim_name}_{f}"
                x_offset = f * FRAME_SIZE
                sub_resources.append(
                    f'[sub_resource type="AtlasTexture" id="{sub_res_id}"]\n'
                    f'atlas = ExtResource("{ext_res_id}")\n'
                    f'region = Rect2({x_offset}, 0, {FRAME_SIZE}, {FRAME_SIZE})'
                )
                frame_refs.append(
                    f'{{\n"duration": 1.0,\n"texture": SubResource("{sub_res_id}")\n}}'
                )

            frames_str = ",\n".join(frame_refs)
            loop_str = "true" if loop else "false"
            anim_blocks.append(
                f'{{\n"frames": [\n{frames_str}\n],\n'
                f'"loop": {loop_str},\n'
                f'"name": &"{anim_name}",\n'
                f'"speed": {float(fps)}\n}}'
            )

            ext_id += 1

        total_steps = len(ext_resources) + len(sub_resources) + 1
        anims_joined = ",\n".join(anim_blocks)

        tres_content = (
            f'[gd_resource type="SpriteFrames" load_steps={total_steps} format=3 uid="uid://pet_{pet_name}_sf"]\n\n'
            + "\n".join(ext_resources) + "\n\n"
            + "\n\n".join(sub_resources) + "\n\n"
            + f'[resource]\nanimations = [\n{anims_joined}\n]\n'
        )

        tres_path.write_text(tres_content, encoding="utf-8")
        print(f"  -> Generated SpriteFrames: {tres_filename}")

# ---------------------------------------------------------------------------
# GODOT 4 .import FILES GENERATION (Nearest, Lossless, No Mipmaps)
# ---------------------------------------------------------------------------
def generate_import_file(texture_path: Path):
    import_path = texture_path.with_name(texture_path.name + ".import")
    h = abs(hash(texture_path.name)) & 0xFFFFFFF
    uid = f"uid://{texture_path.stem}_{h:x}"
    ctex_path = f"res://.godot/imported/{texture_path.name}-{h:x}.ctex"

    # Relative to projects/nos/
    rel_source = texture_path.relative_to(WORKSPACE_ROOT / "projects" / "nos").as_posix()

    config = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="{uid}"
path="{ctex_path}"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://{rel_source}"
dest_files=["{ctex_path}"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossless_compression_factor=0.7
mipmaps/generate=false
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""
    import_path.write_text(config, encoding="utf-8")
    return import_path

def generate_all_imports():
    print("\n=== Generating Godot 4 .import Files ===")
    count = 0
    # Base strips
    for p in PETS_DIR.glob("*.png"):
        generate_import_file(p)
        count += 1
    # Normal maps
    for p in NORMALS_DIR.glob("*.png"):
        generate_import_file(p)
        count += 1
    print(f"  -> Generated {count} .import files (Nearest, Lossless, Mipmaps=Off)")

def main():
    strips = generate_all_sprites()
    generate_all_normals(strips)
    generate_godot_spriteframes()
    generate_all_imports()
    print("\n=== ALL PET ASSETS GENERATED SUCCESSFULLY! ===")

if __name__ == "__main__":
    main()
