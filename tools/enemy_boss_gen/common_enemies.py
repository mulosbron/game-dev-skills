"""
Common Enemies Sprite Generators for 'Aestra: The Last Wish'
Includes Shadow Imp, Cultist Mages, Crystal Spider, Ash Crawler, Swamp Slime, Lava Hound.
"""

import math
from typing import List, Tuple
from PIL import Image, ImageDraw
from .draw_utils import hex_to_rgba, pset, draw_circle, draw_rect, draw_poly, add_outline

# ==============================================================================
# 1. SHADOW IMP (Gölge İblisi) - 32x32
# ==============================================================================

def generate_shadow_imp_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 32, 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Imp Palette
    col_dark = (16, 12, 22, 255)
    col_mid = (36, 26, 50, 255)
    col_hi = (68, 50, 92, 255)
    col_rim = (110, 85, 145, 255)
    col_horn = (60, 36, 52, 255)
    col_horn_tip = (145, 80, 120, 255)
    col_eye_glow = (255, 20, 60, 255)
    col_eye_core = (255, 255, 255, 255)
    col_slash = (255, 45, 85, 220)

    # Base transforms per action
    bx, by = 16, 16
    eye_flare = False
    draw_slash = False
    dissolve = 0.0

    if action == "idle":
        # 4 frames: bobbing and tail twitch
        bobs = [0, 1, 0, -1]
        by += bobs[frame_idx % 4]
        tail_offsets = [0, 1, 2, 1]
        tail_y = tail_offsets[frame_idx % 4]
    elif action == "walk":
        # 6 frames: scampering stride
        walk_bobs = [0, -1, 0, 0, -1, 0]
        by += walk_bobs[frame_idx % 6]
        tail_y = (frame_idx % 3)
    elif action == "attack":
        # 4 frames
        if frame_idx == 0:
            bx -= 2  # Windup
            tail_y = -1
        elif frame_idx == 1:
            bx += 3  # Lunge
            draw_slash = True
            tail_y = 2
        elif frame_idx == 2:
            bx += 2  # Follow-through
            tail_y = 1
        else:
            bx += 0  # Recover
            tail_y = 0
    elif action == "death":
        # 4 frames: flinch, collapse, dissolve
        if frame_idx == 0:
            bx -= 2
            by -= 1
            eye_flare = True
            tail_y = 0
        elif frame_idx == 1:
            by += 4
            tail_y = 2
            dissolve = 0.2
        elif frame_idx == 2:
            by += 8
            tail_y = 3
            dissolve = 0.6
        else:
            by += 12
            tail_y = 4
            dissolve = 0.9

    if dissolve > 0.85:
        # Just a fading ash spot and wisp
        draw_circle(draw, bx, 28, 4, (30, 20, 35, 160))
        pset(img, bx - 1, 26, (120, 70, 150, 140))
        pset(img, bx + 2, 25, (180, 50, 100, 100))
        return img

    # 1. Shadow Tail (behind body)
    if dissolve < 0.6:
        tail_pts = [
            (bx - 3, by + 4),
            (bx - 7, by + 2 + tail_y),
            (bx - 10, by - 1 + tail_y),
            (bx - 12, by - 3 + tail_y)
        ]
        for p in tail_pts:
            draw_circle(draw, p[0], p[1], 1, col_dark)
        # Spade tip
        draw_poly(draw, [
            (bx - 13, by - 3 + tail_y),
            (bx - 15, by - 6 + tail_y),
            (bx - 11, by - 5 + tail_y)
        ], fill=col_horn_tip)

    # 2. Digitigrade Legs
    leg_l_x = bx - 4
    leg_r_x = bx + 4
    foot_y = 28
    if action == "walk":
        offsets = [-3, 0, 3, 2, 0, -2]
        leg_l_x += offsets[frame_idx % 6]
        leg_r_x -= offsets[frame_idx % 6]

    # Left leg
    draw.line([(bx - 3, by + 4), (leg_l_x, by + 8), (leg_l_x - 1, foot_y)], fill=col_mid, width=2)
    draw_poly(draw, [(leg_l_x - 2, foot_y), (leg_l_x + 1, foot_y), (leg_l_x - 1, foot_y - 2)], fill=col_dark)
    # Right leg
    draw.line([(bx + 3, by + 4), (leg_r_x, by + 8), (leg_r_x + 1, foot_y)], fill=col_dark, width=2)
    draw_poly(draw, [(leg_r_x - 1, foot_y), (leg_r_x + 2, foot_y), (leg_r_x + 1, foot_y - 2)], fill=col_dark)

    # 3. Hunched Torso
    draw_circle(draw, bx, by + 1, 5, col_dark)
    draw_circle(draw, bx, by + 1, 4, col_mid)
    draw_circle(draw, bx + 1, by, 2, col_hi)

    # 4. Long Clawed Arms
    arm_l_end = (bx - 7, by + 7)
    arm_r_end = (bx + 7, by + 7)
    if action == "attack":
        if frame_idx == 0:
            arm_r_end = (bx + 8, by - 2)
        elif frame_idx == 1:
            arm_r_end = (bx + 11, by + 5)
        elif frame_idx == 2:
            arm_r_end = (bx + 9, by + 8)

    draw.line([(bx - 3, by - 1), (arm_l_end[0], arm_l_end[1])], fill=col_mid, width=2)
    draw.line([(bx + 3, by - 1), (arm_r_end[0], arm_r_end[1])], fill=col_dark, width=2)
    # Claws
    draw_poly(draw, [arm_l_end, (arm_l_end[0] - 2, arm_l_end[1] + 2), (arm_l_end[0] + 1, arm_l_end[1] + 2)], fill=col_horn_tip)
    draw_poly(draw, [arm_r_end, (arm_r_end[0] + 2, arm_r_end[1] + 2), (arm_r_end[0] - 1, arm_r_end[1] + 2)], fill=col_horn_tip)

    # 5. Hunched Head & Curved Horns
    head_y = by - 5
    draw_circle(draw, bx, head_y, 4, col_dark)
    draw_circle(draw, bx, head_y, 3, col_mid)
    # Horns
    draw.line([(bx - 2, head_y - 2), (bx - 5, head_y - 7)], fill=col_horn, width=1)
    draw.line([(bx + 2, head_y - 2), (bx + 5, head_y - 7)], fill=col_horn, width=1)
    pset(img, bx - 6, head_y - 8, col_horn_tip)
    pset(img, bx + 6, head_y - 8, col_horn_tip)

    # 6. Glowing Red Eyes
    eye_y = head_y
    eye_r = 1 if not eye_flare else 2
    draw_circle(draw, bx - 2, eye_y, eye_r, col_eye_glow)
    draw_circle(draw, bx + 2, eye_y, eye_r, col_eye_glow)
    pset(img, bx - 2, eye_y, col_eye_core)
    pset(img, bx + 2, eye_y, col_eye_core)

    # 7. Slash Arc FX (if attack frame 1 or 2)
    if draw_slash:
        # Sweeping crescent slash arc
        arc_pts = [
            (bx + 6, by - 8),
            (bx + 11, by - 4),
            (bx + 14, by + 3),
            (bx + 12, by + 9),
            (bx + 8, by + 13)
        ]
        for idx in range(len(arc_pts) - 1):
            draw.line([arc_pts[idx], arc_pts[idx + 1]], fill=col_slash, width=2)
        # Glint
        draw_circle(draw, bx + 13, by + 2, 2, (255, 180, 200, 240))
        pset(img, bx + 13, by + 2, (255, 255, 255, 255))

    return add_outline(img, (10, 8, 14, 255))

# ==============================================================================
# 2. CULTIST MAGES (Tarikat Büyücüleri) - 32x32
# ==============================================================================

def generate_cultist_mage_frame(variant: str, frame_idx: int) -> Image.Image:
    w, h = 32, 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Levitation bob
    bobs = [0, -1, -2, -1]
    by = 15 + bobs[frame_idx % 4]
    bx = 15

    # Variant-specific palettes
    if variant == "blue":
        # Water/Frost Mage
        col_robe_dark = (18, 28, 52, 255)
        col_robe_mid = (32, 52, 95, 255)
        col_robe_hi = (54, 88, 155, 255)
        col_trim = (94, 240, 255, 255)
        col_eye = (94, 240, 255, 255)
        col_orb_core = (210, 248, 255, 255)
        col_orb_outer = (56, 197, 245, 220)
        mote_color = (130, 230, 255, 200)
    elif variant == "purple":
        # Arcane/Shadow Mage
        col_robe_dark = (34, 17, 43, 255)
        col_robe_mid = (58, 28, 75, 255)
        col_robe_hi = (92, 43, 118, 255)
        col_trim = (240, 190, 60, 255)  # Gold trim
        col_eye = (223, 77, 255, 255)
        col_orb_core = (245, 200, 255, 255)
        col_orb_outer = (156, 39, 176, 220)
        mote_color = (230, 130, 255, 200)
    else:  # green
        # Nature/Poison Mage
        col_robe_dark = (19, 36, 24, 255)
        col_robe_mid = (32, 64, 41, 255)
        col_robe_hi = (49, 99, 63, 255)
        col_trim = (153, 171, 140, 255)  # Bone trim
        col_eye = (56, 255, 114, 255)
        col_orb_core = (200, 255, 219, 255)
        col_orb_outer = (0, 230, 118, 220)
        mote_color = (100, 255, 170, 200)

    # 1. Robe Hem Ripple
    hem_wave = [-1, 0, 1, 0][frame_idx % 4]
    hem_pts = [
        (bx - 6, by + 12),
        (bx - 3, by + 13 + hem_wave),
        (bx + 1, by + 12),
        (bx + 4, by + 13 - hem_wave),
        (bx + 6, by + 12)
    ]
    # Robe body polygon
    robe_pts = [(bx, by - 6), (bx - 7, by + 4), (bx - 6, by + 12), (bx + 6, by + 12), (bx + 7, by + 4)]
    draw_poly(draw, robe_pts, fill=col_robe_mid)
    draw_poly(draw, [(bx, by - 5), (bx - 5, by + 4), (bx - 4, by + 11), (bx + 2, by + 11), (bx + 4, by + 4)], fill=col_robe_dark)
    # Highlight folds
    draw.line([(bx + 1, by), (bx + 3, by + 10)], fill=col_robe_hi, width=1)
    # Trim along hem
    for i in range(len(hem_pts) - 1):
        draw.line([hem_pts[i], hem_pts[i + 1]], fill=col_trim, width=1)

    # 2. Pointed Hood Cowl
    hood_pts = [
        (bx, by - 9),      # Tip of hood
        (bx - 5, by - 2),  # Left base
        (bx + 5, by - 2)   # Right base
    ]
    draw_poly(draw, hood_pts, fill=col_robe_hi)
    # Deep shadow face void inside hood
    draw_circle(draw, bx, by - 2, 3, (10, 10, 14, 255))
    # Glowing twin eyes
    pset(img, bx - 2, by - 2, col_eye)
    pset(img, bx + 1, by - 2, col_eye)

    # 3. Magic Wooden Staff
    staff_x = bx + 8
    staff_top_y = by - 7
    staff_bot_y = by + 12
    draw.line([(staff_x, staff_top_y), (staff_x, staff_bot_y)], fill=(62, 36, 21, 255), width=2)
    # Staff curved prong holding orb
    draw_circle(draw, staff_x - 1, staff_top_y + 1, 2, (92, 56, 33, 255))
    draw_circle(draw, staff_x + 1, staff_top_y + 1, 2, (92, 56, 33, 255))

    # 4. Floating Elemental Magic Orb
    orb_y = staff_top_y - 2
    orb_r = 3 if frame_idx % 2 == 0 else 4
    draw_circle(draw, staff_x, orb_y, orb_r, col_orb_outer)
    draw_circle(draw, staff_x, orb_y, orb_r - 1, col_orb_core)

    # 5. Orbiting Elemental Motes
    angle = frame_idx * (math.pi / 2.0)
    mx = int(staff_x + math.cos(angle) * 6)
    my = int(orb_y + math.sin(angle) * 4)
    pset(img, mx, my, mote_color)
    pset(img, int(staff_x - math.cos(angle) * 5), int(orb_y - math.sin(angle) * 3), mote_color)

    return add_outline(img, (12, 10, 16, 255))

# ==============================================================================
# 3. CRYSTAL SPIDER (Kristal Örümcek) - 32x32
# ==============================================================================

def generate_crystal_spider_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 32, 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Crystal Palette
    c_dark = (14, 30, 42, 255)
    c_mid = (22, 60, 84, 255)
    c_hi = (35, 122, 158, 255)
    c_bright = (56, 196, 219, 255)
    c_glint = (215, 248, 255, 255)
    c_eye = (98, 237, 255, 255)

    bx, by = 16, 17
    rearing = False
    strike = False

    if action == "walk":
        bobs = [0, -1, 0, 0, -1, 0]
        by += bobs[frame_idx % 6]
    elif action == "attack":
        if frame_idx == 0:
            rearing = True
            by -= 2
        elif frame_idx == 1:
            strike = True
            by += 2
        elif frame_idx == 2:
            by += 1
        else:
            by += 0

    # 1. Abdomen (Faceted crystal cluster)
    ab_pts = [
        (bx - 9, by),
        (bx - 4, by - 6),
        (bx + 1, by - 5),
        (bx + 2, by + 4),
        (bx - 5, by + 6)
    ]
    draw_poly(draw, ab_pts, fill=c_mid)
    draw_poly(draw, [(bx - 8, by), (bx - 4, by - 4), (bx, by - 4), (bx - 4, by + 4)], fill=c_hi)
    # Shimmer facet
    glint_x = bx - 6 + (frame_idx % 4)
    pset(img, glint_x, by - 2, c_glint)
    pset(img, glint_x + 1, by - 2, c_bright)

    # 2. Thorax & Head Prism
    th_pts = [
        (bx + 1, by - 3),
        (bx + 8, by - 2),
        (bx + 10, by + 2),
        (bx + 7, by + 5),
        (bx + 1, by + 4)
    ]
    draw_poly(draw, th_pts, fill=c_hi)
    draw_poly(draw, [(bx + 2, by - 2), (bx + 7, by - 1), (bx + 6, by + 3), (bx + 2, by + 3)], fill=c_bright)

    # 3. 4 Glowing Eyes
    pset(img, bx + 7, by - 1, c_eye)
    pset(img, bx + 9, by, c_eye)
    pset(img, bx + 7, by + 1, c_eye)
    pset(img, bx + 8, by + 2, c_eye)

    # 4. 6 Jointed Crystal Spire Legs
    leg_steps = [
        # Frame cycle offsets
        [(-2, 1), (2, -1), (-2, 2)],
        [(1, -1), (-1, 2), (1, -1)],
        [(2, -2), (0, 1), (-1, 1)],
        [(1, 1), (-2, -1), (2, -2)],
        [(-1, -1), (1, 1), (-1, -1)],
        [(0, 2), (-1, -2), (1, 2)]
    ]
    step = leg_steps[frame_idx % 6] if action == "walk" else [(0, 0), (0, 0), (0, 0)]

    # Left tripod
    l1_knee = (bx + 5, by - 7 if not rearing else by - 11)
    l1_foot = (bx + 10 + step[0][0], by - 9 if not rearing else by - 13)
    if strike:
        l1_knee = (bx + 8, by - 2)
        l1_foot = (bx + 12, by + 8)  # Stabbing down!

    draw.line([(bx + 4, by - 2), l1_knee, l1_foot], fill=c_bright if rearing or strike else c_mid, width=1)

    l2_knee = (bx, by - 8)
    l2_foot = (bx - 2 + step[1][0], by - 11 + step[1][1])
    draw.line([(bx, by - 3), l2_knee, l2_foot], fill=c_mid, width=1)

    l3_knee = (bx - 6, by - 7)
    l3_foot = (bx - 10 + step[2][0], by - 9 + step[2][1])
    draw.line([(bx - 4, by - 3), l3_knee, l3_foot], fill=c_dark, width=1)

    # Right tripod
    r1_knee = (bx + 5, by + 7 if not rearing else by - 9)
    r1_foot = (bx + 10 - step[0][0], by + 9 if not rearing else by - 11)
    if strike:
        r1_knee = (bx + 8, by + 2)
        r1_foot = (bx + 11, by + 9)  # Stabbing down!

    draw.line([(bx + 4, by + 2), r1_knee, r1_foot], fill=c_bright if rearing or strike else c_mid, width=1)

    r2_knee = (bx, by + 8)
    r2_foot = (bx - 2 - step[1][0], by + 11 - step[1][1])
    draw.line([(bx, by + 3), r2_knee, r2_foot], fill=c_mid, width=1)

    r3_knee = (bx - 6, by + 7)
    r3_foot = (bx - 10 - step[2][0], by + 9 - step[2][1])
    draw.line([(bx - 4, by + 3), r3_knee, r3_foot], fill=c_dark, width=1)

    if strike:
        # Cyan impact sparks
        draw_circle(draw, bx + 12, by + 9, 2, (180, 245, 255, 220))
        pset(img, bx + 14, by + 7, c_glint)
        pset(img, bx + 13, by + 11, c_glint)

    return add_outline(img, (10, 20, 28, 255))

# ==============================================================================
# 4. ASH CRAWLER (Kül Sürüngeni) - 32x32
# ==============================================================================

def generate_ash_crawler_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 32, 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Basalt & Lava Palette
    c_basalt_dark = (22, 20, 20, 255)
    c_basalt_mid = (44, 40, 39, 255)
    c_basalt_hi = (75, 68, 66, 255)
    c_lava_dark = (160, 25, 0, 255)
    c_lava_mid = (255, 75, 0, 255)
    c_lava_hi = (255, 175, 0, 255)
    c_eye = (255, 130, 0, 255)

    bx, by = 16, 17
    draw_fire_bite = False

    if action == "walk":
        bobs = [0, 1, 0, -1, 0, 1]
        by += bobs[frame_idx % 6]
        tail_whip = [-2, 0, 2, 2, 0, -2][frame_idx % 6]
    elif action == "attack":
        tail_whip = 1
        if frame_idx == 0:
            bx -= 2  # Coil back
        elif frame_idx == 1:
            bx += 3  # Lunge snap!
            draw_fire_bite = True
        elif frame_idx == 2:
            bx += 2
        else:
            bx += 0

    # 1. Reptilian Tail (Serpentine)
    tail_pts = [
        (bx - 6, by + 1),
        (bx - 10, by + 2 + tail_whip),
        (bx - 14, by + tail_whip)
    ]
    for p in tail_pts:
        draw_circle(draw, p[0], p[1], 2, c_basalt_dark)
    # Ember crack in tail
    pset(img, bx - 10, by + 2 + tail_whip, c_lava_mid)

    # 2. Splayed Reptilian Legs
    # Left front & rear
    f_step = [-2, 0, 2, 1, 0, -1][frame_idx % 6] if action == "walk" else 0
    draw.line([(bx + 3, by + 1), (bx + 6 + f_step, by + 7)], fill=c_basalt_dark, width=2)
    draw.line([(bx - 3, by + 2), (bx - 2 - f_step, by + 8)], fill=c_basalt_dark, width=2)
    # Right front & rear
    draw.line([(bx + 4, by - 1), (bx + 7 - f_step, by - 6)], fill=c_basalt_mid, width=2)
    draw.line([(bx - 2, by - 1), (bx - 1 + f_step, by - 7)], fill=c_basalt_mid, width=2)

    # 3. Scorched Torso
    draw_circle(draw, bx - 2, by, 5, c_basalt_mid)
    draw_circle(draw, bx + 2, by, 4, c_basalt_hi)

    # Molten lava cracks on back
    pulse = (frame_idx % 2 == 0)
    lava_c = c_lava_hi if pulse else c_lava_mid
    draw.line([(bx - 5, by), (bx + 1, by - 1)], fill=lava_c, width=1)
    draw.line([(bx - 2, by + 2), (bx + 2, by + 1)], fill=c_lava_dark, width=1)

    # 4. Horned Reptilian Head
    head_x = bx + 6
    head_y = by
    draw_circle(draw, head_x, head_y, 4, c_basalt_mid)
    # Snout
    draw_rect(draw, head_x + 1, head_y - 2, head_x + 5, head_y + 2, fill=c_basalt_dark)
    # Glowing molten eyes
    pset(img, head_x + 2, head_y - 1, c_eye)
    pset(img, head_x + 3, head_y - 1, (255, 255, 100, 255))
    # Small basalt horn on snout
    pset(img, head_x + 4, head_y - 3, c_basalt_hi)

    # 5. Fire Bite FX
    if draw_fire_bite:
        # Fiery snapping jaws & flame burst
        draw_circle(draw, head_x + 7, head_y, 3, (255, 90, 0, 220))
        draw_circle(draw, head_x + 8, head_y, 2, (255, 220, 50, 240))
        pset(img, head_x + 9, head_y - 2, c_lava_hi)
        pset(img, head_x + 9, head_y + 2, c_lava_hi)

    return add_outline(img, (15, 14, 14, 255))

# ==============================================================================
# 5. SWAMP SLIME (Bataklık Balçığı) - 32x32
# ==============================================================================

def generate_swamp_slime_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 32, 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Slime Palette
    c_dark = (28, 38, 22, 255)
    c_mid = (48, 66, 36, 255)
    c_hi = (75, 102, 54, 255)
    c_gloss = (120, 160, 85, 255)
    c_eye_sclera = (230, 225, 150, 255)
    c_eye_pupil = (25, 32, 18, 255)

    bx = 16
    draw_splash = False

    if action == "hop":
        # 6 frames squash and stretch:
        # 0: rest, 1: squash, 2: launch stretch, 3: airborne, 4: land squash, 5: rebound
        configs = [
            # rx, ry, cy
            (9, 7, 23),    # 0: rest
            (12, 4, 26),   # 1: squash flat
            (6, 11, 18),   # 2: launch stretch
            (8, 8, 12),    # 3: airborne peak
            (13, 4, 26),   # 4: landing squash
            (10, 6, 24)    # 5: rebound
        ]
        rx, ry, cy = configs[frame_idx % 6]
    elif action == "splash":
        # 4 frames:
        # 0: pancake, 1: pop burst, 2: droplet arc, 3: reform
        if frame_idx == 0:
            rx, ry, cy = 13, 3, 27
        elif frame_idx == 1:
            rx, ry, cy = 9, 8, 22
            draw_splash = True
        elif frame_idx == 2:
            rx, ry, cy = 8, 7, 23
            draw_splash = True
        else:
            rx, ry, cy = 9, 7, 23

    # Draw slime body ellipse
    draw.ellipse([bx - rx, cy - ry, bx + rx, cy + ry], fill=c_mid, outline=c_dark)
    # Interior highlight
    if ry > 4:
        draw.ellipse([bx - rx + 2, cy - ry + 1, bx + rx - 2, cy + 1], fill=c_hi)
        # Glossy glint
        draw.line([(bx - rx + 3, cy - ry + 2), (bx - rx + 5, cy - ry + 2)], fill=c_gloss, width=1)

    # Murky floating mud flecks inside
    if ry > 5:
        pset(img, bx - 3, cy + 2, c_dark)
        pset(img, bx + 4, cy + 1, c_dark)

    # Eyes
    eye_y = cy - 2 if ry > 5 else cy - 1
    eye_sep = max(3, int(rx * 0.45))
    draw_circle(draw, bx - eye_sep, eye_y, 2, c_eye_sclera)
    draw_circle(draw, bx + eye_sep, eye_y, 2, c_eye_sclera)
    pset(img, bx - eye_sep, eye_y, c_eye_pupil)
    pset(img, bx + eye_sep, eye_y, c_eye_pupil)

    # Splash particles
    if draw_splash:
        dist = 8 if frame_idx == 1 else 12
        # Droplets left & right
        draw_circle(draw, bx - dist, cy - 3, 2, c_hi)
        draw_circle(draw, bx + dist, cy - 3, 2, c_hi)
        pset(img, bx - dist - 2, cy - 6, c_gloss)
        pset(img, bx + dist + 2, cy - 6, c_gloss)

    return add_outline(img, (18, 24, 14, 255))

# ==============================================================================
# 6. LAVA HOUND (Lav Tazısı) - 40x32
# ==============================================================================

def generate_lava_hound_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 40, 32
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Volcanic Crust & Magma Palette
    c_crust_dark = (22, 14, 14, 255)
    c_crust_mid = (45, 26, 26, 255)
    c_crust_hi = (75, 42, 42, 255)
    c_magma_dark = (180, 35, 0, 255)
    c_magma_mid = (255, 95, 0, 255)
    c_flame_bright = (255, 210, 45, 255)
    c_flame_white = (255, 255, 200, 255)

    bx, by = 20, 18
    draw_bite = False

    if action == "run":
        # 6 frames canine gallop cycle:
        # 0: land, 1: coil, 2: launch, 3: flight extend, 4: reach, 5: impact
        bobs = [0, 2, -1, -3, -1, 1]
        by += bobs[frame_idx % 6]
        leg_phase = frame_idx % 6
    elif action == "bite":
        leg_phase = 0
        if frame_idx == 0:
            bx -= 2  # Crouch back
        elif frame_idx == 1:
            bx += 3  # Savage lunge!
            draw_bite = True
        elif frame_idx == 2:
            bx += 2
        else:
            bx += 0

    # 1. Paws / Legs
    foot_y = 28
    if action == "run":
        # Paws cycle
        f_offsets = [
            ((bx + 8, foot_y), (bx - 8, foot_y - 3)),    # 0
            ((bx + 4, foot_y), (bx - 4, foot_y)),        # 1: coil
            ((bx + 11, foot_y - 2), (bx - 10, foot_y)),  # 2: push
            ((bx + 14, foot_y - 6), (bx - 13, foot_y - 5)), # 3: airborne
            ((bx + 10, foot_y), (bx - 10, foot_y - 3)),  # 4: reach
            ((bx + 7, foot_y), (bx - 7, foot_y))         # 5: absorb
        ]
        f_paws, r_paws = f_offsets[leg_phase]
    else:
        f_paws = (bx + 8, foot_y)
        r_paws = (bx - 8, foot_y)

    # Front & Hind leg lines
    draw.line([(bx + 5, by + 1), (f_paws[0], f_paws[1])], fill=c_crust_dark, width=2)
    draw.line([(bx - 5, by + 1), (r_paws[0], r_paws[1])], fill=c_crust_dark, width=2)

    # 2. Muscular Carapace Body
    draw_rect(draw, bx - 8, by - 4, bx + 6, by + 4, fill=c_crust_mid)
    # Magma muscle veins
    draw.line([(bx - 6, by - 1), (bx + 4, by)], fill=c_magma_mid, width=1)
    draw.line([(bx - 4, by + 2), (bx + 2, by + 2)], fill=c_magma_dark, width=1)

    # 3. Blazing Flaming Mane along spine
    flame_cycle = (frame_idx % 3)
    for fx in range(bx - 6, bx + 5, 3):
        fy = by - 5 - (flame_cycle if fx % 2 == 0 else 2 - flame_cycle)
        draw.line([(fx, by - 4), (fx - 2, fy)], fill=c_magma_mid, width=2)
        pset(img, fx - 2, fy, c_flame_bright)
        pset(img, fx - 2, fy - 1, c_flame_white)

    # 4. Flaming Tail Plume
    tail_tip = (bx - 13, by - 3 - flame_cycle)
    draw.line([(bx - 8, by - 2), tail_tip], fill=c_magma_mid, width=2)
    pset(img, tail_tip[0], tail_tip[1], c_flame_bright)

    # 5. Volcanic Hound Head & Jaws
    hx = bx + 9
    hy = by - 3
    draw_circle(draw, hx, hy, 4, c_crust_hi)
    # Fiery eyes
    pset(img, hx + 1, hy - 1, c_flame_bright)
    pset(img, hx + 2, hy - 1, c_flame_white)

    # Muzzle & Teeth
    if not draw_bite:
        draw_rect(draw, hx + 3, hy - 1, hx + 6, hy + 2, fill=c_crust_dark)
        pset(img, hx + 5, hy + 1, c_flame_bright)
    else:
        # Jaws split wide open flaming!
        draw.line([(hx + 2, hy - 3), (hx + 8, hy - 4)], fill=c_crust_dark, width=2)
        draw.line([(hx + 2, hy + 2), (hx + 8, hy + 4)], fill=c_crust_dark, width=2)
        # Fire burst in mouth
        draw_circle(draw, hx + 6, hy, 3, (255, 120, 0, 240))
        draw_circle(draw, hx + 7, hy, 2, c_flame_bright)
        pset(img, hx + 9, hy, c_flame_white)

    return add_outline(img, (16, 10, 10, 255))
