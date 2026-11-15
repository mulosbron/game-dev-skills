"""
Biome Bosses Sprite Generators for 'Aestra: The Last Wish'
Includes Kök Devi, Prizma Golemi, Kül Kirpisi, Çamur Ana, Cevher Kralı (all 64x64).
"""

import math
from typing import List, Tuple
from PIL import Image, ImageDraw
from .draw_utils import hex_to_rgba, pset, draw_circle, draw_rect, draw_poly, draw_capsule, add_outline

# ==============================================================================
# 1. KÖK DEVİ (Root Giant - Kuzey Ormanı Boss) - 64x64
# ==============================================================================

def generate_kok_devi_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 64, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Ancient Oak & Runic Emerald Palette
    c_wood_dark = (35, 21, 11, 255)
    c_wood_mid = (56, 34, 18, 255)
    c_wood_hi = (82, 52, 27, 255)
    c_wood_light = (112, 72, 38, 255)
    c_moss_dark = (30, 54, 20, 255)
    c_moss_mid = (48, 84, 33, 255)
    c_moss_hi = (72, 125, 49, 255)
    c_leaf_bright = (110, 179, 75, 255)
    c_rune_dark = (11, 64, 28, 255)
    c_rune_mid = (37, 212, 93, 255)
    c_rune_bright = (125, 245, 159, 255)
    c_rune_white = (255, 255, 255, 255)

    bx, by = 32, 32
    draw_slam_fx = False
    draw_stomp_fx = False
    arms_up = False
    stomp_leg_up = False

    if action == "idle":
        bobs = [0, 1, 0, -1]
        by += bobs[frame_idx % 4]
        heart_pulse = frame_idx % 2 == 0
    elif action == "slam":
        heart_pulse = True
        if frame_idx == 0:
            by += 1
        elif frame_idx == 1:
            by -= 3
            arms_up = True
        elif frame_idx == 2:
            by -= 1
            arms_up = True
        elif frame_idx == 3:
            by += 3
            draw_slam_fx = True
        elif frame_idx == 4:
            by += 2
            draw_slam_fx = True
        else:
            by += 0
    elif action == "stomp":
        heart_pulse = False
        if frame_idx == 0:
            by += 0
        elif frame_idx == 1:
            stomp_leg_up = True
            by -= 2
        elif frame_idx == 2:
            by += 2
        elif frame_idx == 3:
            draw_stomp_fx = True
            by += 1
        elif frame_idx == 4:
            draw_stomp_fx = True
            by += 1
        else:
            by += 0

    # 1. Tree Trunk Legs & Root Feet
    foot_y = 58
    l_foot_y = foot_y - 6 if stomp_leg_up else foot_y
    # Left leg
    draw_rect(draw, bx - 14, by + 12, bx - 4, l_foot_y, fill=c_wood_mid)
    # Right leg
    draw_rect(draw, bx + 4, by + 12, bx + 14, foot_y, fill=c_wood_dark)
    # Root toes
    draw_poly(draw, [(bx - 16, l_foot_y), (bx - 2, l_foot_y), (bx - 9, l_foot_y - 4)], fill=c_wood_dark)
    draw_poly(draw, [(bx + 2, foot_y), (bx + 16, foot_y), (bx + 9, foot_y - 4)], fill=c_wood_dark)

    # 2. Knotted Ancient Torso
    draw_rect(draw, bx - 16, by - 6, bx + 16, by + 14, fill=c_wood_mid)
    draw_rect(draw, bx - 13, by - 4, bx + 13, by + 12, fill=c_wood_hi)
    # Bark texture ridges
    draw.line([(bx - 10, by - 4), (bx - 8, by + 10)], fill=c_wood_dark, width=2)
    draw.line([(bx + 8, by - 4), (bx + 10, by + 10)], fill=c_wood_dark, width=2)

    # 3. Glowing Runic Emerald Heart in Chest Cavity
    draw_circle(draw, bx, by + 4, 6, c_wood_dark)
    heart_r = 4 if heart_pulse else 3
    draw_circle(draw, bx, by + 4, heart_r, c_rune_mid)
    draw_circle(draw, bx, by + 4, heart_r - 1, c_rune_bright)
    pset(img, bx, by + 4, c_rune_white)

    # 4. Broad Mossy Shoulders & Leaf Canopy
    draw_rect(draw, bx - 22, by - 12, bx + 22, by - 4, fill=c_moss_mid)
    # Moss fringes
    for mx in range(bx - 20, bx + 21, 4):
        draw_circle(draw, mx, by - 12, 3, c_moss_hi)
        pset(img, mx, by - 14, c_leaf_bright)

    # 5. Wood-Carved Treant Head
    head_y = by - 16
    draw_rect(draw, bx - 8, head_y - 6, bx + 8, head_y + 4, fill=c_wood_hi)
    # Glowing rune eyes
    draw_circle(draw, bx - 4, head_y - 1, 2, c_rune_bright)
    draw_circle(draw, bx + 4, head_y - 1, 2, c_rune_bright)
    pset(img, bx - 4, head_y - 1, c_rune_white)
    pset(img, bx + 4, head_y - 1, c_rune_white)
    # Branch horns on head
    draw.line([(bx - 6, head_y - 6), (bx - 12, head_y - 13)], fill=c_wood_dark, width=2)
    draw.line([(bx + 6, head_y - 6), (bx + 12, head_y - 13)], fill=c_wood_dark, width=2)
    pset(img, bx - 13, head_y - 14, c_leaf_bright)
    pset(img, bx + 13, head_y - 14, c_leaf_bright)

    # 6. Massive Root Arms & Fists
    if arms_up:
        # Arms raised overhead for slam
        draw.line([(bx - 20, by - 8), (bx - 16, by - 24)], fill=c_wood_dark, width=6)
        draw.line([(bx + 20, by - 8), (bx + 16, by - 24)], fill=c_wood_dark, width=6)
        # Giant fists
        draw_circle(draw, bx - 16, by - 24, 7, c_wood_hi)
        draw_circle(draw, bx + 16, by - 24, 7, c_wood_hi)
    else:
        # Arms hanging at sides
        fist_l_y = by + 12
        fist_r_y = by + 12
        draw.line([(bx - 20, by - 8), (bx - 22, fist_l_y)], fill=c_wood_dark, width=6)
        draw.line([(bx + 20, by - 8), (bx + 22, fist_r_y)], fill=c_wood_dark, width=6)
        draw_circle(draw, bx - 22, fist_l_y, 6, c_wood_hi)
        draw_circle(draw, bx + 22, fist_r_y, 6, c_wood_hi)

    # 7. Slam FX: Ground fissures & shockwave
    if draw_slam_fx:
        # Cracked ground lines
        draw.line([(bx - 28, foot_y), (bx + 28, foot_y)], fill=c_rune_mid, width=2)
        draw.line([(bx - 20, foot_y), (bx - 12, foot_y - 3)], fill=c_rune_bright, width=1)
        draw.line([(bx + 12, foot_y - 3), (bx + 20, foot_y)], fill=c_rune_bright, width=1)
        # Green shockwave ring
        draw.ellipse([bx - 26, foot_y - 5, bx + 26, foot_y + 3], outline=c_rune_bright, width=1)
        # Flying wood debris
        pset(img, bx - 18, foot_y - 8, c_wood_light)
        pset(img, bx + 18, foot_y - 8, c_wood_light)

    # 8. Stomp FX: Root spikes bursting from earth
    if draw_stomp_fx:
        # Spikes shooting up in front of treant
        spike_heights = [12, 18, 14]
        for idx, sx in enumerate([bx + 18, bx + 24, bx + 30]):
            sh = spike_heights[idx]
            draw_poly(draw, [(sx - 3, foot_y), (sx + 3, foot_y), (sx, foot_y - sh)], fill=c_wood_mid)
            draw.line([(sx - 3, foot_y), (sx, foot_y - sh)], fill=c_rune_mid, width=1)

    return add_outline(img, (20, 12, 6, 255))

# ==============================================================================
# 2. PRİZMA GOLEMİ (Prism Golem - Kristal Vadi Boss) - 64x64
# ==============================================================================

def generate_prizma_golemi_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 64, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Crystal Sapphire & Refraction Palette
    c_facet_dark = (12, 33, 56, 255)
    c_facet_mid = (21, 62, 99, 255)
    c_facet_hi = (33, 98, 150, 255)
    c_facet_bright = (50, 146, 209, 255)
    c_facet_glint = (97, 197, 245, 255)
    c_facet_white = (217, 247, 255, 255)
    c_rainbow_pink = (224, 64, 251, 240)
    c_rainbow_cyan = (0, 229, 255, 240)
    c_rainbow_yellow = (255, 215, 0, 240)

    # Hover bob
    bobs = [0, -1, -2, -1]
    by = 30 + bobs[frame_idx % 4]
    bx = 32

    draw_beam = False
    fist_crush = False

    if action == "idle":
        pass
    elif action == "beam":
        if frame_idx in (2, 3, 4):
            draw_beam = True
    elif action == "crush":
        if frame_idx in (2, 3):
            fist_crush = True

    # 1. Monolithic Faceted Crystal Body
    poly_body = [
        (bx, by - 18),      # Top apex
        (bx - 16, by - 6),  # Left shoulder
        (bx - 12, by + 16), # Left hip
        (bx, by + 22),      # Bottom tip
        (bx + 12, by + 16), # Right hip
        (bx + 16, by - 6)   # Right shoulder
    ]
    draw_poly(draw, poly_body, fill=c_facet_mid)

    # Faceted crystal segments
    draw_poly(draw, [(bx, by - 18), (bx - 16, by - 6), (bx, by)], fill=c_facet_hi)
    draw_poly(draw, [(bx, by - 18), (bx + 16, by - 6), (bx, by)], fill=c_facet_bright)
    draw_poly(draw, [(bx - 16, by - 6), (bx - 12, by + 16), (bx, by)], fill=c_facet_dark)
    draw_poly(draw, [(bx + 16, by - 6), (bx + 12, by + 16), (bx, by)], fill=c_facet_hi)

    # Specular glint line across facet
    glint_pos = (frame_idx % 4) * 3
    draw.line([(bx - 10 + glint_pos, by - 8), (bx - 4 + glint_pos, by + 6)], fill=c_facet_glint, width=1)

    # 2. Refraction Star Core (Chest)
    core_y = by
    draw_circle(draw, bx, core_y, 5, c_rainbow_cyan)
    draw_circle(draw, bx, core_y, 3, c_rainbow_pink)
    draw_circle(draw, bx, core_y, 1, c_facet_white)
    # Refraction motes
    pset(img, bx - 7, core_y, c_rainbow_yellow)
    pset(img, bx + 7, core_y, c_rainbow_cyan)

    # 3. Crystal Crown Head
    head_y = by - 22
    crown_pts = [(bx, head_y - 6), (bx - 6, head_y), (bx + 6, head_y)]
    draw_poly(draw, crown_pts, fill=c_facet_white)
    draw.line([(bx, head_y - 6), (bx, head_y + 2)], fill=c_facet_glint, width=1)

    # 4. Floating Spiked Crystal Fists
    fist_dist = 6 if fist_crush else 24
    fist_l_x = bx - fist_dist
    fist_r_x = bx + fist_dist
    fist_y = by + 2

    # Left Fist
    fist_l_pts = [(fist_l_x, fist_y - 8), (fist_l_x - 8, fist_y), (fist_l_x, fist_y + 8), (fist_l_x + 8, fist_y)]
    draw_poly(draw, fist_l_pts, fill=c_facet_hi)
    draw_poly(draw, [(fist_l_x, fist_y - 8), (fist_l_x - 8, fist_y), (fist_l_x, fist_y)], fill=c_facet_bright)

    # Right Fist
    fist_r_pts = [(fist_r_x, fist_y - 8), (fist_r_x - 8, fist_y), (fist_r_x, fist_y + 8), (fist_r_x + 8, fist_y)]
    draw_poly(draw, fist_r_pts, fill=c_facet_dark)
    draw_poly(draw, [(fist_r_x, fist_y - 8), (fist_r_x + 8, fist_y), (fist_r_x, fist_y)], fill=c_facet_bright)

    # 5. Prism Laser Beam FX
    if draw_beam:
        # Giant concentrated refractive beam shooting right
        beam_y = core_y
        beam_start_x = bx + 6
        beam_end_x = 64
        # Outer corona
        draw.line([(beam_start_x, beam_y - 3), (beam_end_x, beam_y - 3)], fill=c_rainbow_pink, width=1)
        draw.line([(beam_start_x, beam_y + 3), (beam_end_x, beam_y + 3)], fill=c_rainbow_cyan, width=1)
        # Inner laser
        draw.line([(beam_start_x, beam_y), (beam_end_x, beam_y)], fill=c_facet_white, width=4)
        # Light rings
        draw_circle(draw, beam_start_x + 4, beam_y, 6, c_rainbow_yellow)

    # 6. Crush FX: Crystalline shatter shockwave
    if fist_crush:
        draw_circle(draw, bx, fist_y, 8, c_facet_white)
        # Flying shards
        for shard in [(bx - 12, fist_y - 8), (bx + 12, fist_y - 8), (bx - 10, fist_y + 8), (bx + 10, fist_y + 8)]:
            draw_poly(draw, [shard, (shard[0] + 2, shard[1] - 3), (shard[0] + 3, shard[1] + 2)], fill=c_facet_glint)

    return add_outline(img, (8, 20, 35, 255))

# ==============================================================================
# 3. KÜL KİRPİSİ (Spiky Ash Beast - Külden Çalılıklar Boss) - 64x64
# ==============================================================================

def generate_kul_kirpisi_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 64, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Armored Basalt & Molten Glass Palette
    c_hide_dark = (26, 24, 25, 255)
    c_hide_mid = (41, 37, 39, 255)
    c_hide_hi = (64, 59, 62, 255)
    c_quill_base = (16, 14, 18, 255)
    c_quill_mid = (32, 28, 36, 255)
    c_quill_tip = (255, 60, 0, 255)
    c_horn_dark = (153, 31, 0, 255)
    c_horn_mid = (255, 122, 0, 255)
    c_horn_bright = (255, 204, 0, 255)
    c_horn_white = (255, 255, 136, 255)

    bx, by = 28, 38
    draw_charge_streak = False
    draw_spike_barrage = False
    quills_retracted = False

    if action == "idle":
        bobs = [0, 1, 0, -1]
        by += bobs[frame_idx % 4]
    elif action == "charge":
        if frame_idx == 0:
            bx -= 4
        elif frame_idx in (1, 2, 3):
            bx += (frame_idx * 4)
            draw_charge_streak = True
        elif frame_idx == 4:
            bx += 10
        else:
            bx += 2
    elif action == "spikes":
        if frame_idx == 0:
            by += 2
        elif frame_idx == 1:
            by += 3
        elif frame_idx == 2:
            draw_spike_barrage = True
            quills_retracted = True
        elif frame_idx == 3:
            quills_retracted = True
        else:
            quills_retracted = False

    # 1. Armored Claws / Heavy Legs
    foot_y = 56
    draw_rect(draw, bx - 14, by + 8, bx - 6, foot_y, fill=c_hide_dark)
    draw_rect(draw, bx - 2, by + 8, bx + 6, foot_y, fill=c_hide_mid)
    draw_rect(draw, bx + 10, by + 8, bx + 18, foot_y, fill=c_hide_dark)

    # 2. Heavy Armored Body
    draw_rect(draw, bx - 16, by - 8, bx + 18, by + 12, fill=c_hide_mid)
    draw_rect(draw, bx - 12, by - 6, bx + 14, by + 10, fill=c_hide_hi)

    # Molten cracks in armor
    draw.line([(bx - 8, by), (bx + 8, by - 2)], fill=c_horn_mid, width=1)
    draw.line([(bx - 4, by + 4), (bx + 4, by + 4)], fill=c_horn_dark, width=1)

    # 3. Giant Obsidian Quills along back
    if not quills_retracted:
        quill_origins = [
            (bx - 14, by - 8), (bx - 10, by - 10), (bx - 6, by - 12),
            (bx - 2, by - 12), (bx + 2, by - 12), (bx + 6, by - 10),
            (bx + 10, by - 8)
        ]
        for qx, qy in quill_origins:
            # Arching quills pointing backward
            q_tip = (qx - 10, qy - 12)
            draw.line([(qx, qy), q_tip], fill=c_quill_mid, width=3)
            # Fiery quill tip
            pset(img, q_tip[0], q_tip[1], c_quill_tip)
            pset(img, q_tip[0] + 1, q_tip[1] + 1, c_horn_bright)

    # 4. Armored Head & Colossal Molten Horn
    hx = bx + 20
    hy = by - 2
    draw_rect(draw, hx - 4, hy - 6, hx + 8, hy + 6, fill=c_hide_hi)
    # Molten glowing eye
    pset(img, hx + 2, hy - 2, c_horn_bright)
    pset(img, hx + 3, hy - 2, c_horn_white)

    # Molten Horn (Spike curving forward & up)
    horn_poly = [
        (hx + 4, hy - 2),
        (hx + 14, hy - 14),
        (hx + 8, hy)
    ]
    draw_poly(draw, horn_poly, fill=c_horn_mid)
    draw.line([(hx + 5, hy - 1), (hx + 14, hy - 14)], fill=c_horn_bright, width=2)
    pset(img, hx + 14, hy - 14, c_horn_white)

    # 5. Charge Streaks FX
    if draw_charge_streak:
        # Red fiery motion streaks
        draw.line([(bx - 24, by - 6), (bx - 14, by - 6)], fill=c_horn_mid, width=2)
        draw.line([(bx - 28, by + 2), (bx - 16, by + 2)], fill=c_quill_tip, width=1)
        # Ash cloud at rear
        draw_circle(draw, bx - 22, foot_y - 2, 4, (80, 75, 75, 180))

    # 6. Spike Barrage FX: Flying Quill Missiles
    if draw_spike_barrage:
        angles = [0, 45, 90, 135, 180, 225, 270, 315]
        for ang in angles:
            rad = math.radians(ang)
            dist = 22
            mx = int(bx + math.cos(rad) * dist)
            my = int(by + math.sin(rad) * dist)
            draw_circle(draw, mx, my, 2, c_quill_tip)
            pset(img, mx, my, c_horn_white)

    return add_outline(img, (16, 14, 15, 255))

# ==============================================================================
# 4. ÇAMUR ANA (Mud Mother - Bataklık Kıyısı Boss) - 64x64
# ==============================================================================

def generate_camur_ana_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 64, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Swamp Mire & Bioluminescent Spore Palette
    c_mire_dark = (22, 30, 16, 255)
    c_mire_mid = (37, 49, 26, 255)
    c_mire_hi = (57, 75, 39, 255)
    c_mire_gloss = (86, 110, 56, 255)
    c_shroom_stem = (45, 25, 48, 255)
    c_shroom_cap = (176, 56, 184, 255)
    c_shroom_glow = (240, 100, 247, 255)
    c_shroom_dots = (255, 180, 255, 255)
    c_eye_wisp = (68, 255, 34, 255)
    c_bile_acid = (130, 255, 40, 240)

    bx, by = 32, 38
    draw_arm_slam = False
    draw_bile_spit = False

    if action == "idle":
        pass
    elif action == "slam":
        if frame_idx in (2, 3, 4):
            draw_arm_slam = True
    elif action == "spit":
        if frame_idx in (2, 3):
            draw_bile_spit = True

    # 1. Mountainous Undulating Swamp Bulk
    ripple = [0, 1, 2, 1][frame_idx % 4]
    poly_bulk = [
        (bx - 24, by + 18),
        (bx - 22, by - 6 + ripple),
        (bx - 10, by - 16),
        (bx + 12, by - 14 - ripple),
        (bx + 24, by - 4),
        (bx + 26, by + 18)
    ]
    draw_poly(draw, poly_bulk, fill=c_mire_mid)
    draw_poly(draw, [(bx - 20, by + 16), (bx - 18, by - 4 + ripple), (bx - 8, by - 12), (bx + 10, by - 10 - ripple), (bx + 20, by - 2), (bx + 22, by + 16)], fill=c_mire_hi)

    # Surface slime dripping tendrils
    for tx in [bx - 16, bx - 6, bx + 8, bx + 18]:
        draw.line([(tx, by + 14), (tx, by + 18 + ((tx + frame_idx) % 3))], fill=c_mire_dark, width=2)

    # 2. Bioluminescent Mushroom Clusters (Shoulder)
    shroom_pulse = frame_idx % 2 == 0
    cap_c = c_shroom_glow if shroom_pulse else c_shroom_cap
    # Shroom 1
    draw.line([(bx - 12, by - 14), (bx - 14, by - 20)], fill=c_shroom_stem, width=2)
    draw_circle(draw, bx - 14, by - 21, 4, cap_c)
    pset(img, bx - 14, by - 22, c_shroom_dots)
    # Shroom 2
    draw.line([(bx - 8, by - 14), (bx - 6, by - 19)], fill=c_shroom_stem, width=2)
    draw_circle(draw, bx - 6, by - 20, 3, cap_c)

    # 3. Multiple Glowing Will-o'-the-Wisp Eyes
    pset(img, bx + 4, by - 6, c_eye_wisp)
    pset(img, bx + 8, by - 4, c_eye_wisp)
    pset(img, bx + 12, by - 7, c_eye_wisp)
    pset(img, bx + 7, by - 8, (200, 255, 150, 255))

    # 4. Colossal Mud Arm Slam FX
    if draw_arm_slam:
        # Colossal tentacle arm smashing down
        draw_capsule(draw, bx - 18, by - 10, bx - 26, by + 16, 4, fill=c_mire_dark)
        # Splash wave
        draw_circle(draw, bx - 26, by + 18, 8, c_mire_gloss)
        pset(img, bx - 30, by + 12, c_bile_acid)
        pset(img, bx - 22, by + 14, c_bile_acid)

    # 5. Acidic Bile Spit Projectiles
    if draw_bile_spit:
        # Mouth stretches
        draw_circle(draw, bx + 16, by - 2, 4, (10, 15, 8, 255))
        # 3 Bile globs flying
        draw_circle(draw, bx + 24, by - 8, 3, c_bile_acid)
        draw_circle(draw, bx + 28, by - 2, 4, c_bile_acid)
        draw_circle(draw, bx + 24, by + 4, 3, c_bile_acid)

    return add_outline(img, (14, 20, 10, 255))

# ==============================================================================
# 5. CEVHER KRALI (Ore King - Volkanik Yol Boss) - 64x64
# ==============================================================================

def generate_cevher_krali_frame(action: str, frame_idx: int) -> Image.Image:
    w, h = 64, 64
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Molten Slag & Basalt Palette
    c_basalt_dark = (19, 17, 23, 255)
    c_basalt_mid = (35, 31, 41, 255)
    c_basalt_hi = (56, 49, 66, 255)
    c_lava_dark = (153, 25, 0, 255)
    c_lava_mid = (255, 93, 0, 255)
    c_lava_bright = (255, 180, 0, 255)
    c_lava_white = (255, 255, 180, 255)
    c_ruby = (255, 0, 55, 255)

    bx, by = 28, 34
    draw_smash_fx = False
    draw_eruption = False
    hammer_up = False

    if action == "idle":
        bobs = [0, 1, 0, -1]
        by += bobs[frame_idx % 4]
    elif action == "smash":
        if frame_idx in (1, 2):
            hammer_up = True
            by -= 2
        elif frame_idx in (3, 4):
            draw_smash_fx = True
            by += 2
        else:
            by += 0
    elif action == "eruption":
        if frame_idx in (2, 3, 4):
            draw_eruption = True
            by += 1

    # 1. Colossal Basalt Legs
    foot_y = 56
    draw_rect(draw, bx - 12, by + 12, bx - 4, foot_y, fill=c_basalt_dark)
    draw_rect(draw, bx + 2, by + 12, bx + 10, foot_y, fill=c_basalt_mid)
    # Lava veins in legs
    draw.line([(bx - 8, by + 14), (bx - 8, foot_y - 2)], fill=c_lava_mid, width=1)
    draw.line([(bx + 6, by + 14), (bx + 6, foot_y - 2)], fill=c_lava_dark, width=1)

    # 2. Slag Titan Torso
    draw_rect(draw, bx - 14, by - 8, bx + 14, by + 12, fill=c_basalt_mid)
    draw_rect(draw, bx - 11, by - 6, bx + 11, by + 10, fill=c_basalt_hi)

    # Boiling lava core channels
    draw.line([(bx - 8, by - 4), (bx, by + 2)], fill=c_lava_bright, width=2)
    draw.line([(bx + 8, by - 4), (bx, by + 2)], fill=c_lava_bright, width=2)
    draw.line([(bx, by + 2), (bx, by + 8)], fill=c_lava_mid, width=2)

    # 3. Volcanic Back Smokestacks
    draw_rect(draw, bx - 12, by - 16, bx - 8, by - 8, fill=c_basalt_dark)
    draw_rect(draw, bx + 8, by - 16, bx + 12, by - 8, fill=c_basalt_dark)

    # 4. Basalt Head & Crown with Ruby Spikes
    hx = bx
    hy = by - 14
    draw_rect(draw, hx - 6, hy - 4, hx + 6, hy + 4, fill=c_basalt_hi)
    # Eyes
    pset(img, hx - 3, hy - 1, c_lava_bright)
    pset(img, hx + 3, hy - 1, c_lava_bright)
    # Crown & Ruby gems
    draw_poly(draw, [(hx - 6, hy - 4), (hx - 4, hy - 10), (hx - 2, hy - 4)], fill=c_basalt_dark)
    draw_poly(draw, [(hx - 2, hy - 4), (hx, hy - 12), (hx + 2, hy - 4)], fill=c_basalt_dark)
    draw_poly(draw, [(hx + 2, hy - 4), (hx + 4, hy - 10), (hx + 6, hy - 4)], fill=c_basalt_dark)
    pset(img, hx - 4, hy - 8, c_ruby)
    pset(img, hx, hy - 10, c_ruby)
    pset(img, hx + 4, hy - 8, c_ruby)

    # 5. Magma Hammer
    if hammer_up:
        # Lifted high overhead
        ham_x = bx
        ham_y = by - 24
        draw.line([(bx, by - 6), (ham_x, ham_y)], fill=(50, 45, 55, 255), width=3)
        draw_rect(draw, ham_x - 10, ham_y - 6, ham_x + 10, ham_y + 4, fill=c_basalt_dark)
        draw_rect(draw, ham_x - 8, ham_y - 4, ham_x + 8, ham_y + 2, fill=c_lava_bright)
    else:
        # Resting grounded beside king
        ham_x = bx + 20
        ham_y = foot_y - 6
        draw.line([(bx + 8, by), (ham_x, ham_y)], fill=(50, 45, 55, 255), width=3)
        draw_rect(draw, ham_x - 6, ham_y - 6, ham_x + 6, ham_y + 6, fill=c_basalt_dark)
        draw_rect(draw, ham_x - 4, ham_y - 4, ham_x + 4, ham_y + 4, fill=c_lava_bright)
        pset(img, ham_x, ham_y, c_lava_white)

    # 6. Smash FX: Rupturing Fissures
    if draw_smash_fx:
        impact_x = bx + 16
        draw.line([(impact_x - 20, foot_y), (impact_x + 20, foot_y)], fill=c_lava_bright, width=3)
        draw.line([(impact_x - 14, foot_y - 4), (impact_x + 14, foot_y + 2)], fill=c_lava_white, width=1)
        # Flying magma sparks
        pset(img, impact_x - 10, foot_y - 8, c_lava_bright)
        pset(img, impact_x + 10, foot_y - 8, c_lava_bright)

    # 7. Eruption FX: Magma geysers from back stacks
    if draw_eruption:
        # Magma bursting upward
        draw.line([(bx - 10, by - 16), (bx - 12, by - 32)], fill=c_lava_bright, width=3)
        draw.line([(bx + 10, by - 16), (bx + 12, by - 32)], fill=c_lava_bright, width=3)
        draw_circle(draw, bx - 12, by - 32, 4, c_lava_white)
        draw_circle(draw, bx + 12, by - 32, 4, c_lava_white)

    return add_outline(img, (14, 12, 17, 255))
