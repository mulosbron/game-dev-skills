"""
Generates 90s Retro FPS (DUSK / DOOM / Cultic style) 2D Viewmodels for 2.5D Farming (GDD v1.0).
Builds 5 distinct animated viewmodels with miner gloves, leather sleeves, brass fittings,
motion blur swing arcs, and particles:
  1. VM_01_Kazma_Gold (Gold Tier Pickaxe - 4 frames: Idle, Windup, Strike Arc, Impact Recoil)
  2. VM_02_Capa_Gold (Gold Tier Hoe - 4 frames: Ready, Raise, Soil Smash, Recover)
  3. VM_03_SulamaKabi (Upgraded Watering Can - 4 frames: Ready, Tilt, Water Stream, Reset)
  4. VM_04_Tirpan_Gold (Gold Tier Scythe - 4 frames: Ready, Windup, Crescent Slash Arc, Followthrough)
  5. VM_05_Hitscan_Tabanca_ve_Fener (Miner Revolver + K4 Lantern - 4 frames: Aim, Muzzle Flash, Recoil Smoke, Settle)

Locked strictly to the 32-Color Reference Palette.
Outputs:
  - sprites_2d/viewmodels/ (strips & frames)
  - ui_ux/05_FPS_2D_VIEWMODELS_DOOM_DUSK_STYLE_SHEET.png
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

PROJECT_DIR = Path(r"D:\GameMaker\projects\farming_25d")
VM_DIR = PROJECT_DIR / "sprites_2d" / "viewmodels"
UI_UX_DIR = PROJECT_DIR / "ui_ux"
CUSTOM_BLENDER_DIR = PROJECT_DIR / "models_3d" / "custom_blender"
os.makedirs(VM_DIR, exist_ok=True)

# 32-Color Reference Palette (GDD 8.4)
PALETTE = {
    "black": (7, 11, 8, 255),
    "dark_green": (13, 22, 16, 255),
    "wood_dark": (42, 26, 18, 255),
    "wood_mid": (99, 62, 38, 255),
    "wood_light": (138, 88, 54, 255),
    "wood_hi": (186, 130, 85, 255),
    "glove_dark": (30, 18, 12, 255),
    "glove_mid": (66, 40, 27, 255),
    "glove_hi": (115, 75, 50, 255),
    "metal_dark": (38, 51, 45, 255),
    "metal_mid": (80, 94, 86, 255),
    "metal_light": (140, 156, 147, 255),
    "metal_hi": (212, 226, 217, 255),
    "gold_dark": (184, 134, 27, 255),
    "gold_mid": (255, 213, 65, 255),
    "gold_hi": (255, 245, 160, 255),
    "brass": (200, 150, 40, 255),
    "phosphor_dark": (35, 140, 80, 255),
    "phosphor_mid": (82, 255, 154, 255),
    "phosphor_hi": (200, 255, 225, 255),
    "water_dark": (30, 80, 160, 255),
    "water_mid": (90, 210, 255, 255),
    "water_hi": (220, 250, 255, 255),
    "fire_orange": (255, 140, 36, 255),
    "fire_yellow": (255, 230, 80, 255),
    "white": (255, 255, 255, 255),
}

# Standard FPS viewmodel resolution: 160x140
VW, VH = 160, 140


def draw_miner_hand(draw, bx, by, angle_deg=0, grip_tight=True):
    """Draws a rugged leather miner's glove with wrist strap and brass buckle."""
    # Forearm coming from bottom-right corner
    forearm_pts = [
        (bx + 45, by + 50),
        (bx + 90, by + 50),
        (bx + 110, VH + 20),
        (bx + 20, VH + 20),
    ]
    draw.polygon(forearm_pts, fill=PALETTE["glove_dark"])

    # Leather highlights & creases
    draw.line([(bx + 35, by + 65), (bx + 85, by + 65)], fill=PALETTE["glove_mid"], width=4)
    draw.line([(bx + 45, by + 85), (bx + 95, by + 85)], fill=PALETTE["glove_mid"], width=3)
    draw.line([(bx + 55, by + 60), (bx + 65, by + 80)], fill=PALETTE["glove_hi"], width=2)

    # Brass wrist rivets
    draw.ellipse([(bx + 38, by + 70), (bx + 44, by + 76)], fill=PALETTE["gold_mid"])
    draw.ellipse([(bx + 78, by + 70), (bx + 84, by + 76)], fill=PALETTE["gold_mid"])

    # Palm & Knuckles
    knuckle_poly = [
        (bx + 15, by + 10),
        (bx + 50, by + 5),
        (bx + 58, by + 35),
        (bx + 18, by + 40),
    ]
    draw.polygon(knuckle_poly, fill=PALETTE["glove_mid"])
    draw.polygon([
        (bx + 18, by + 8),
        (bx + 46, by + 5),
        (bx + 44, by + 20),
        (bx + 16, by + 22),
    ], fill=PALETTE["glove_hi"])

    # Curled fingers wrapped around shaft
    for i in range(4):
        fy = by + 10 + i * 8
        fx = bx + 16 - i * 2
        draw.ellipse([(fx, fy), (fx + 16, fy + 9)], fill=PALETTE["glove_dark"], outline=PALETTE["glove_mid"], width=2)
        draw.point([(fx + 4, fy + 3), (fx + 5, fy + 3)], fill=PALETTE["glove_hi"])

    # Thumb wrapped in front
    draw.polygon([
        (bx + 30, by + 25),
        (bx + 46, by + 16),
        (bx + 40, by + 32),
        (bx + 26, by + 35),
    ], fill=PALETTE["glove_hi"])


def render_gold_pickaxe_frames():
    """Builds 4 frames of Gold Pickaxe swing (DUSK style)."""
    frames = []

    # Frame 0: Ready / Idle
    f0 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(f0)
    # Wood shaft (diagonal from bottom-center to top-left)
    d0.line([(100, 110), (32, 22)], fill=PALETTE["wood_dark"], width=8)
    d0.line([(100, 110), (32, 22)], fill=PALETTE["wood_light"], width=4)
    # Leather grip wrap
    for s in range(4):
        sx = 80 + s * 7
        sy = 85 + s * 7
        d0.line([(sx - 4, sy + 3), (sx + 4, sy - 3)], fill=PALETTE["wood_hi"], width=2)
    # Heavy Gold Pick Head
    # Central eye collar
    d0.polygon([(26, 26), (40, 14), (32, 6), (18, 18)], fill=PALETTE["gold_dark"])
    # Front pick spike (curved downward)
    d0.polygon([(36, 12), (10, 8), (2, 20), (22, 22)], fill=PALETTE["gold_mid"])
    d0.polygon([(34, 14), (12, 10), (6, 18), (20, 20)], fill=PALETTE["gold_hi"])
    # Back hammer head
    d0.polygon([(32, 8), (56, 16), (50, 26), (26, 18)], fill=PALETTE["gold_mid"])
    # Specular shine
    d0.line([(10, 10), (22, 14)], fill=PALETTE["white"], width=2)
    # Hand
    draw_miner_hand(d0, 75, 75)
    frames.append(f0)

    # Frame 1: Wind-up (raised higher back to the right)
    f1 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(f1)
    d1.line([(110, 115), (75, 12)], fill=PALETTE["wood_dark"], width=8)
    d1.line([(110, 115), (75, 12)], fill=PALETTE["wood_light"], width=4)
    # Pick head tilted back
    d1.polygon([(70, 16), (44, 10), (38, 22), (64, 28)], fill=PALETTE["gold_mid"])
    d1.polygon([(68, 18), (46, 12), (42, 20), (62, 26)], fill=PALETTE["gold_hi"])
    d1.polygon([(74, 14), (96, 22), (90, 32), (68, 24)], fill=PALETTE["gold_mid"])
    draw_miner_hand(d1, 88, 70)
    frames.append(f1)

    # Frame 2: Power Strike Arc (slamming down with golden motion streak)
    f2 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(f2)
    # Golden slash arc streak
    d2.arc([(0, -20), (140, 120)], start=160, end=310, fill=PALETTE["gold_mid"], width=12)
    d2.arc([(4, -16), (136, 116)], start=165, end=305, fill=PALETTE["gold_hi"], width=6)
    d2.arc([(8, -12), (132, 112)], start=170, end=300, fill=PALETTE["white"], width=2)
    # Shaft slammed forward-downward
    d2.line([(115, 105), (18, 55)], fill=PALETTE["wood_dark"], width=8)
    d2.line([(115, 105), (18, 55)], fill=PALETTE["wood_light"], width=4)
    # Pick head biting into rock
    d2.polygon([(14, 52), (0, 72), (12, 80), (28, 62)], fill=PALETTE["gold_hi"])
    d2.polygon([(18, 50), (38, 42), (44, 54), (24, 62)], fill=PALETTE["gold_mid"])
    draw_miner_hand(d2, 85, 78)
    frames.append(f2)

    # Frame 3: Impact Recoil & Sparks
    f3 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(f3)
    # Sparks bouncing off
    spark_pts = [(12, 60), (20, 48), (28, 64), (6, 52), (18, 74), (32, 54)]
    for sx, sy in spark_pts:
        d3.line([(sx - 3, sy), (sx + 3, sy)], fill=PALETTE["fire_yellow"], width=2)
        d3.line([(sx, sy - 3), (sx, sy + 3)], fill=PALETTE["white"], width=2)
    # Shaft vibrating slightly back
    d3.line([(108, 108), (25, 45)], fill=PALETTE["wood_dark"], width=8)
    d3.line([(108, 108), (25, 45)], fill=PALETTE["wood_light"], width=4)
    d3.polygon([(22, 42), (4, 56), (14, 66), (32, 52)], fill=PALETTE["gold_mid"])
    draw_miner_hand(d3, 80, 76)
    frames.append(f3)

    return frames


def render_gold_hoe_frames():
    """Builds 4 frames of Gold Hoe ground tilling."""
    frames = []

    # Frame 0: Ready
    f0 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(f0)
    d0.line([(95, 110), (35, 30)], fill=PALETTE["wood_dark"], width=8)
    d0.line([(95, 110), (35, 30)], fill=PALETTE["wood_light"], width=4)
    # Broad Golden Hoe Blade (angled perpendicular to till soil)
    d0.polygon([(26, 26), (42, 14), (34, 6), (18, 18)], fill=PALETTE["gold_dark"])
    d0.polygon([(28, 20), (14, 42), (24, 46), (38, 24)], fill=PALETTE["gold_mid"])
    d0.polygon([(26, 22), (16, 40), (22, 44), (34, 26)], fill=PALETTE["gold_hi"])
    draw_miner_hand(d0, 70, 75)
    frames.append(f0)

    # Frame 1: Raise up
    f1 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(f1)
    d1.line([(105, 115), (65, 18)], fill=PALETTE["wood_dark"], width=8)
    d1.line([(105, 115), (65, 18)], fill=PALETTE["wood_light"], width=4)
    d1.polygon([(58, 16), (46, 36), (56, 40), (68, 20)], fill=PALETTE["gold_hi"])
    draw_miner_hand(d1, 80, 70)
    frames.append(f1)

    # Frame 2: Till Strike + Soil Dust
    f2 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(f2)
    # Soil dust particles
    for dx, dy in [(10, 70), (18, 85), (28, 75), (38, 90), (45, 80)]:
        d2.ellipse([(dx, dy), (dx + 8, dy + 6)], fill=PALETTE["wood_light"])
        d2.ellipse([(dx + 2, dy + 1), (dx + 6, dy + 4)], fill=PALETTE["wood_hi"])
    # Blade slammed into ground
    d2.line([(110, 105), (22, 60)], fill=PALETTE["wood_dark"], width=8)
    d2.line([(110, 105), (22, 60)], fill=PALETTE["wood_light"], width=4)
    d2.polygon([(16, 55), (4, 76), (16, 80), (28, 60)], fill=PALETTE["gold_mid"])
    draw_miner_hand(d2, 85, 76)
    frames.append(f2)

    # Frame 3: Pull back
    f3 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(f3)
    d3.line([(100, 110), (32, 40)], fill=PALETTE["wood_dark"], width=8)
    d3.line([(100, 110), (32, 40)], fill=PALETTE["wood_light"], width=4)
    d3.polygon([(26, 35), (14, 55), (24, 59), (36, 39)], fill=PALETTE["gold_hi"])
    draw_miner_hand(d3, 75, 75)
    frames.append(f3)

    return frames


def render_watering_can_frames():
    """Builds 4 frames of Watering Can pouring (authentic retro style)."""
    frames = []

    # Frame 0: Idle / Ready
    f0 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(f0)
    # Can body (polished brass/copper canister in lower right)
    d0.rounded_rectangle([(70, 45), (135, 105)], radius=8, fill=PALETTE["brass"], outline=PALETTE["gold_dark"], width=2)
    d0.rounded_rectangle([(74, 50), (131, 100)], radius=6, fill=PALETTE["gold_mid"])
    d0.rectangle([(80, 55), (92, 95)], fill=PALETTE["gold_hi"])
    # Top arched handle
    d0.arc([(80, 20), (125, 60)], start=180, end=360, fill=PALETTE["wood_mid"], width=6)
    # Spout (angled up-left)
    d0.polygon([(75, 80), (35, 45), (40, 38), (80, 72)], fill=PALETTE["gold_mid"], outline=PALETTE["gold_dark"])
    # Rose/Spout head
    d0.ellipse([(28, 34), (46, 50)], fill=PALETTE["brass"], outline=PALETTE["gold_dark"])
    # Hand holding top handle
    draw_miner_hand(d0, 75, 30)
    frames.append(f0)

    # Frame 1: Tip forward
    f1 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(f1)
    d1.rounded_rectangle([(65, 40), (130, 95)], radius=8, fill=PALETTE["gold_mid"], outline=PALETTE["gold_dark"], width=2)
    d1.polygon([(70, 75), (25, 48), (30, 42), (75, 68)], fill=PALETTE["gold_mid"])
    d1.ellipse([(18, 42), (36, 58)], fill=PALETTE["brass"])
    draw_miner_hand(d1, 70, 25)
    frames.append(f1)

    # Frame 2: Pouring Water Arc + Splash droplets
    f2 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(f2)
    # Water stream arching from spout (x=24, y=55) downwards
    d2.arc([(-20, 40), (60, 140)], start=260, end=360, fill=PALETTE["water_dark"], width=8)
    d2.arc([(-18, 42), (58, 138)], start=265, end=355, fill=PALETTE["water_mid"], width=5)
    d2.arc([(-16, 44), (56, 136)], start=270, end=350, fill=PALETTE["water_hi"], width=2)
    # Water droplets
    for drop in [(14, 85), (8, 98), (18, 110), (4, 120), (12, 128)]:
        d2.ellipse([(drop[0], drop[1]), (drop[0] + 5, drop[1] + 7)], fill=PALETTE["water_mid"])
        d2.point([(drop[0] + 2, drop[1] + 2)], fill=PALETTE["white"])
    # Can body tipped forward 30 deg
    d2.rounded_rectangle([(60, 42), (125, 95)], radius=8, fill=PALETTE["gold_mid"], outline=PALETTE["gold_dark"], width=2)
    d2.polygon([(65, 75), (18, 52), (24, 46), (70, 68)], fill=PALETTE["gold_mid"])
    d2.ellipse([(12, 46), (30, 62)], fill=PALETTE["brass"])
    draw_miner_hand(d2, 65, 25)
    frames.append(f2)

    # Frame 3: Settle
    f3 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(f3)
    # Remaining droplets
    for drop in [(10, 115), (6, 125)]:
        d3.ellipse([(drop[0], drop[1]), (drop[0] + 4, drop[1] + 5)], fill=PALETTE["water_mid"])
    d3.rounded_rectangle([(68, 44), (133, 102)], radius=8, fill=PALETTE["gold_mid"], outline=PALETTE["gold_dark"], width=2)
    d3.polygon([(73, 78), (32, 46), (38, 40), (78, 70)], fill=PALETTE["gold_mid"])
    d3.ellipse([(25, 36), (43, 52)], fill=PALETTE["brass"])
    draw_miner_hand(d3, 72, 28)
    frames.append(f3)

    return frames


def render_gold_scythe_frames():
    """Builds 4 frames of Gold Scythe wide horizontal crescent slash (Blood/DUSK style)."""
    frames = []

    # Frame 0: Ready
    f0 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(f0)
    # Long sturdy curved snaith shaft
    d0.line([(100, 120), (50, 15)], fill=PALETTE["wood_dark"], width=8)
    d0.line([(100, 120), (50, 15)], fill=PALETTE["wood_light"], width=4)
    # Massive curved crescent blade
    d0.arc([(0, -25), (110, 65)], start=160, end=330, fill=PALETTE["gold_dark"], width=10)
    d0.arc([(2, -23), (108, 63)], start=165, end=325, fill=PALETTE["gold_mid"], width=6)
    d0.arc([(4, -21), (106, 61)], start=170, end=320, fill=PALETTE["gold_hi"], width=2)
    d0.line([(8, 12), (32, 6)], fill=PALETTE["white"], width=2)
    draw_miner_hand(d0, 75, 75)
    frames.append(f0)

    # Frame 1: Pull right / Windup
    f1 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(f1)
    d1.line([(115, 120), (80, 15)], fill=PALETTE["wood_dark"], width=8)
    d1.line([(115, 120), (80, 15)], fill=PALETTE["wood_light"], width=4)
    d1.arc([(30, -25), (140, 65)], start=160, end=330, fill=PALETTE["gold_mid"], width=8)
    d1.arc([(32, -23), (138, 63)], start=165, end=325, fill=PALETTE["gold_hi"], width=3)
    draw_miner_hand(d1, 85, 70)
    frames.append(f1)

    # Frame 2: Crescent Slash Arc across entire screen!
    f2 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(f2)
    # Massive sweeping slash blade motion blur
    d2.arc([(-40, 10), (180, 130)], start=170, end=340, fill=PALETTE["gold_mid"], width=16)
    d2.arc([(-36, 14), (176, 126)], start=175, end=335, fill=PALETTE["gold_hi"], width=8)
    d2.arc([(-32, 18), (172, 122)], start=180, end=330, fill=PALETTE["white"], width=3)
    # Shaft swept low
    d2.line([(115, 100), (20, 65)], fill=PALETTE["wood_dark"], width=8)
    d2.line([(115, 100), (20, 65)], fill=PALETTE["wood_light"], width=4)
    draw_miner_hand(d2, 85, 76)
    frames.append(f2)

    # Frame 3: Follow-through
    f3 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(f3)
    d3.line([(95, 115), (28, 45)], fill=PALETTE["wood_dark"], width=8)
    d3.line([(95, 115), (28, 45)], fill=PALETTE["wood_light"], width=4)
    d3.arc([(-15, 15), (75, 95)], start=180, end=340, fill=PALETTE["gold_hi"], width=6)
    draw_miner_hand(d3, 72, 78)
    frames.append(f3)

    return frames


def render_revolver_and_lantern_frames():
    """Builds 4 frames of Revolver + K4 Phosphor Lantern (Left Lantern, Right Gun)."""
    frames = []

    def draw_lantern_left(d, glow=True):
        # Left hand holding glowing K4 lantern at bottom-left
        # Forearm
        d.polygon([(0, 95), (35, 80), (45, VH), (0, VH)], fill=PALETTE["glove_dark"])
        # Brass lantern housing
        d.rectangle([(20, 45), (55, 90)], fill=PALETTE["metal_dark"], outline=PALETTE["brass"], width=2)
        # Glowing phosphor crystal inside
        glow_color = PALETTE["phosphor_hi"] if glow else PALETTE["phosphor_dark"]
        d.rectangle([(25, 52), (50, 83)], fill=PALETTE["phosphor_mid"])
        d.rectangle([(30, 58), (45, 77)], fill=glow_color)
        # Volumetric light halo
        if glow:
            d.ellipse([(10, 35), (65, 100)], outline=PALETTE["phosphor_dark"], width=2)

    # Frame 0: Ready / Aiming
    f0 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d0 = ImageDraw.Draw(f0)
    draw_lantern_left(d0, glow=True)
    # Right hand Revolver
    # Barrel pointed forward
    d0.polygon([(88, 48), (145, 44), (145, 56), (88, 60)], fill=PALETTE["metal_mid"], outline=PALETTE["metal_dark"])
    d0.line([(90, 46), (145, 43)], fill=PALETTE["metal_hi"], width=2)
    # Fluted Cylinder
    d0.rounded_rectangle([(82, 45), (106, 68)], radius=4, fill=PALETTE["metal_dark"])
    d0.line([(86, 52), (102, 52)], fill=PALETTE["metal_hi"], width=2)
    d0.line([(86, 60), (102, 60)], fill=PALETTE["metal_hi"], width=2)
    # Hammer & Sight
    d0.polygon([(78, 42), (86, 40), (84, 48), (76, 48)], fill=PALETTE["metal_hi"])
    d0.rectangle([(140, 40), (144, 44)], fill=PALETTE["metal_hi"])  # Front sight
    # Grip & Right Hand
    draw_miner_hand(d0, 88, 62)
    frames.append(f0)

    # Frame 1: Muzzle Flash!
    f1 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d1 = ImageDraw.Draw(f1)
    draw_lantern_left(d1, glow=True)
    # Giant Starburst Muzzle Flash at (145, 50)
    mx, my = 145, 48
    d1.polygon([(mx, my - 25), (mx + 8, my - 6), (mx + 28, my), (mx + 8, my + 6),
                (mx, my + 25), (mx - 6, my + 6), (mx - 22, my), (mx - 6, my - 6)], fill=PALETTE["fire_yellow"])
    d1.polygon([(mx, my - 15), (mx + 5, my - 4), (mx + 18, my), (mx + 5, my + 4),
                (mx, my + 15), (mx - 4, my + 4), (mx - 14, my), (mx - 4, my - 4)], fill=PALETTE["white"])
    # Gun kicked back slightly
    d1.polygon([(86, 46), (140, 42), (140, 54), (86, 58)], fill=PALETTE["metal_hi"])
    draw_miner_hand(d1, 88, 64)
    frames.append(f1)

    # Frame 2: Recoil Upward + Cylinder Smoke
    f2 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d2 = ImageDraw.Draw(f2)
    draw_lantern_left(d2, glow=True)
    # Gun barrel kicked up 20 degrees
    d2.polygon([(84, 44), (136, 26), (139, 38), (87, 56)], fill=PALETTE["metal_mid"], outline=PALETTE["metal_dark"])
    # Smoke wisps
    d2.ellipse([(138, 22), (148, 30)], fill=PALETTE["metal_light"])
    d2.ellipse([(144, 14), (156, 24)], fill=PALETTE["metal_hi"])
    draw_miner_hand(d2, 86, 60)
    frames.append(f2)

    # Frame 3: Settle down
    f3 = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d3 = ImageDraw.Draw(f3)
    draw_lantern_left(d3, glow=True)
    d3.polygon([(87, 47), (143, 44), (143, 56), (87, 59)], fill=PALETTE["metal_mid"])
    draw_miner_hand(d3, 88, 62)
    frames.append(f3)

    return frames


def build_all_viewmodels_and_sheets():
    print("[1/3] Generating 5 retro FPS viewmodel sets (4 frames each)...")
    vms = [
        ("VM_01_Kazma_Gold", "FPS Viewmodel: Altın Kazma", "3x Hız | 0.35s Vuruş | Altın Bıçak & Madenci Eldiveni", render_gold_pickaxe_frames()),
        ("VM_02_Capa_Gold", "FPS Viewmodel: Altın Çapa", "5x5 Alan Sürme | Çift El Darbe & Toprak Tozu", render_gold_hoe_frames()),
        ("VM_03_SulamaKabi", "FPS Viewmodel: Sulama Kabı", "24 Karo Depo | Kavisli Pirinç Emzik & Su Akışı", render_watering_can_frames()),
        ("VM_04_Tirpan_Gold", "FPS Viewmodel: Altın Tırpan", "3x3 Alan Biçme | Hilal Kesim & Yatay Savurma", render_gold_scythe_frames()),
        ("VM_05_Hitscan_Tabanca_ve_Fener", "FPS Viewmodel: Tabanca + Fener", "14m Hitscan | 5.5m K4 Fosfor Feneri & Namlu Alevi", render_revolver_and_lantern_frames()),
    ]

    for slug, title, desc, frames in vms:
        # Save individual frames
        for i, f in enumerate(frames):
            f.save(VM_DIR / f"{slug}_frame{i}.png")
            if i == 0:
                # Also save default ready preview in custom_blender folder so the 12-model sheet can use it!
                f_large = f.resize((512, 512), Image.Resampling.NEAREST)
                f_large.save(CUSTOM_BLENDER_DIR / f"{slug}_preview.png")

        # Save horizontal strip (160 * 4 = 640 x 140)
        strip = Image.new("RGBA", (VW * len(frames), VH), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            strip.alpha_composite(f, (i * VW, 0))
        strip_path = VM_DIR / f"{slug}_strip{len(frames)}.png"
        strip.save(strip_path)
        print(f"  [OK] Saved {strip_path.name} ({strip.size})")

    # -----------------------------------------------------------------------
    # 2. Build Dedicated 90s FPS Viewmodel Showcase Sheet
    # -----------------------------------------------------------------------
    print("[2/3] Composing ui_ux/05_FPS_2D_VIEWMODELS_DOOM_DUSK_STYLE_SHEET.png...")
    sheet_w, sheet_h = 1920, 1080
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (11, 18, 14, 255))
    draw = ImageDraw.Draw(sheet)

    def get_font(size):
        for name in ["consola.ttf", "arial.ttf"]:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                pass
        return ImageFont.load_default()

    font_title = get_font(32)
    font_sub = get_font(16)
    font_bold = get_font(14)
    font_mono = get_font(12)

    # Header Box
    draw.rectangle([(20, 20), (sheet_w - 20, 120)], fill=(18, 30, 22, 240), outline=(82, 255, 154, 255), width=2)
    draw.text((40, 32), "BİRİNCİ ŞAHIS 2B RETRO FPS VIEWMODEL SETİ (DUSK / DOOM / CULTIC TARZI)", fill=(82, 255, 154), font=font_title)
    draw.text((42, 74), "GDD v1.0 Sözleşmesi · 480×270 Tampon @ 60 FPS · 32 Renk Paleti Kilitli · Madenci Deri Eldiveni & Savurma Animasyonları", fill=(179, 255, 212), font=font_sub)
    draw.text((42, 96), "Klasik 90'lar Piksel Sanatı · Sağ Alt Kadraj · Hazır / Geri Çekilme / Vuruş Efekti / Toparlanma Kareleri", fill=(138, 156, 147), font=font_mono)

    # 5 Weapon Rows
    y_start = 140
    row_h = 175
    for r_idx, (slug, title, desc, frames) in enumerate(vms):
        y0 = y_start + r_idx * (row_h + 10)

        # Row box
        draw.rectangle([(20, y0), (sheet_w - 20, y0 + row_h)], fill=(16, 25, 20, 230), outline=(42, 54, 46, 255), width=1)
        # Left Info Badge
        draw.rectangle([(20, y0), (320, y0 + row_h)], fill=(14, 22, 17, 255), outline=(58, 68, 62, 255), width=1)
        draw.rectangle([(20, y0), (26, y0 + row_h)], fill=(255, 213, 65) if "Gold" in slug or "Kazma" in slug else (82, 255, 154))
        draw.text((36, y0 + 18), f"{r_idx + 1}. {title}", fill=(255, 255, 255), font=font_bold)
        draw.text((36, y0 + 44), desc[:42], fill=(175, 192, 183), font=font_mono)
        draw.text((36, y0 + 66), desc[42:85], fill=(138, 156, 147), font=font_mono)
        draw.text((36, y0 + 105), f"{slug}_strip4.png", fill=(82, 255, 154), font=font_mono)
        draw.text((36, y0 + 125), "Çözünürlük: 640×140 (4× 160×140)", fill=(90, 210, 255), font=font_mono)

        # 4 Animation Frames
        stage_names = [
            ("Kare 0: Hazır / Duruş", "#75C782"),
            ("Kare 1: Geri Çekilme / Hazırlık", "#FFD541"),
            ("Kare 2: Vuruş / Savurma Arkı / Ateş", "#FF8C24"),
            ("Kare 3: Geri Tepme / Toparlanma", "#5AD2FF"),
        ]
        x_start = 340
        card_w = (sheet_w - x_start - 40) // 4
        for f_idx, frame_img in enumerate(frames):
            fx = x_start + f_idx * card_w
            fy = y0 + 8
            # Frame card
            draw.rectangle([(fx, fy), (fx + card_w - 12, fy + row_h - 16)], fill=(12, 18, 14, 255), outline=(35, 45, 38, 255), width=1)
            # Label
            s_name, s_color = stage_names[f_idx]
            draw.text((fx + 10, fy + 8), s_name, fill=s_color, font=font_mono)
            # Scaled frame display
            f_disp = frame_img.resize((150, 131), Image.Resampling.NEAREST)
            sheet.alpha_composite(f_disp, (fx + (card_w - 12 - 150) // 2, fy + 26))

    sheet_path = UI_UX_DIR / "05_FPS_2D_VIEWMODELS_DOOM_DUSK_STYLE_SHEET.png"
    sheet.save(sheet_path)
    print(f"[OK] Saved {sheet_path.name}")

    # -----------------------------------------------------------------------
    # 3. Re-compose 04_BLENDER_CUSTOM_ORES_VIEWMODELS_AND_HYBRID_TREES_12_GLBS.png
    # -----------------------------------------------------------------------
    print("[3/3] Re-composing models_3d/04_BLENDER_CUSTOM_ORES_VIEWMODELS_AND_HYBRID_TREES_12_GLBS.png...")
    import build_farming_25d_pipeline as pipe
    pipe.compose_custom_3d_sheet()
    pipe.compose_master_mega_board()
    print("[SUCCESS] All 2D Viewmodels, 3D Ores, and Showcase Boards completely updated!")


if __name__ == "__main__":
    build_all_viewmodels_and_sheets()
