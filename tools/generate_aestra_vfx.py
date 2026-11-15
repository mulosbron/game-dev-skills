#!/usr/bin/env python3
"""
tools/generate_aestra_vfx.py
Specialist VFX Generator for 'Aestra: The Last Wish' (projects/nos).
Generates all 20 combat/skill VFX strips, damage numbers sheet, Godot 4 .import files,
and Godot 4 SpriteFrames (.tres) resources.
"""

import math
import os
import random
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
TARGET_VFX_DIR = WORKSPACE_ROOT / "projects" / "nos" / "assets" / "vfx"
TARGET_VFX_DIR.mkdir(parents=True, exist_ok=True)

# Set deterministic random seed
random.seed(42)
np.random.seed(42)

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def hex_to_rgba(h: str, a: int = 255) -> tuple[int, int, int, int]:
    r, g, b = hex_to_rgb(h)
    return (r, g, b, a)

def save_strip_and_meta(name: str, frames: list[Image.Image], loop: bool = False, fps: float = 12.0):
    n_frames = len(frames)
    fw, fh = frames[0].size
    strip_w = fw * n_frames
    strip_h = fh
    strip_img = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip_img.paste(f, (i * fw, 0), f)
    
    png_path = TARGET_VFX_DIR / f"{name}_strip{n_frames}.png"
    strip_img.save(png_path, "PNG")
    print(f"[OK] Saved strip: {png_path.name} ({strip_w}x{strip_h})")

    # Generate Godot 4 .import file
    import_path = png_path.with_name(png_path.name + ".import")
    h_val = abs(hash(png_path.name)) & 0xFFFFFFF
    uid_str = f"uid://{png_path.stem}_{h_val:x}"
    ctex_dest = f"res://.godot/imported/{png_path.name}-{h_val:x}.ctex"
    import_content = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="{uid_str}"
path="{ctex_dest}"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://assets/vfx/{png_path.name}"
dest_files=["{ctex_dest}"]

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
    import_path.write_text(import_content, encoding="utf-8")

    # Generate Godot 4 SpriteFrames .tres resource
    tres_path = TARGET_VFX_DIR / f"{name}.tres"
    load_steps = n_frames + 2
    tres_lines = [
        f'[gd_resource type="SpriteFrames" load_steps={load_steps} format=3 uid="uid://sf_{name}_{h_val:x}"]\n',
        f'[ext_resource type="Texture2D" uid="{uid_str}" path="res://assets/vfx/{png_path.name}" id="1_tex"]\n'
    ]
    for i in range(n_frames):
        tres_lines.append(f"""[sub_resource type="AtlasTexture" id="AtlasTexture_{i}"]
atlas = ExtResource("1_tex")
region = Rect2({i * fw}, 0, {fw}, {fh})
""")

    frames_array = []
    for i in range(n_frames):
        frames_array.append(f"""{{
"duration": 1.0,
"texture": SubResource("AtlasTexture_{i}")
}}""")
    frames_joined = ",\n".join(frames_array)
    loop_str = "true" if loop else "false"

    tres_lines.append(f"""[resource]
animations = [{{
"frames": [
{frames_joined}
],
"loop": {loop_str},
"name": &"default",
"speed": {fps}
}}]
""")
    tres_path.write_text("\n".join(tres_lines), encoding="utf-8")


def save_single_texture_and_meta(name: str, img: Image.Image):
    png_path = TARGET_VFX_DIR / f"{name}.png"
    img.save(png_path, "PNG")
    print(f"[OK] Saved single texture: {png_path.name} ({img.width}x{img.height})")

    import_path = png_path.with_name(png_path.name + ".import")
    h_val = abs(hash(png_path.name)) & 0xFFFFFFF
    uid_str = f"uid://{png_path.stem}_{h_val:x}"
    ctex_dest = f"res://.godot/imported/{png_path.name}-{h_val:x}.ctex"
    import_content = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="{uid_str}"
path="{ctex_dest}"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://assets/vfx/{png_path.name}"
dest_files=["{ctex_dest}"]

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
    import_path.write_text(import_content, encoding="utf-8")


# ============================================================================
# 1. CRESCENT SWORD SLASHES (Purple, Cyan, Fire)
# ============================================================================

def generate_sword_slash_set():
    PALETTES = {
        "vfx_sword_slash_purple": {
            "name": "Purple Crescent Slash",
            "colors": [hex_to_rgb(c) for c in ["#22023F", "#5B0E8E", "#B020E0", "#F08CFF", "#FFFFFF"]],
            "sparks": [hex_to_rgb(c) for c in ["#E8A5FF", "#FFFFFF", "#C060FF", "#8A0EBF"]]
        },
        "vfx_sword_slash_cyan": {
            "name": "Cyan Frost Slash",
            "colors": [hex_to_rgb(c) for c in ["#092848", "#156C9E", "#34C4E8", "#A6F5FF", "#FFFFFF"]],
            "sparks": [hex_to_rgb(c) for c in ["#B2F7FF", "#FFFFFF", "#4ED4F5", "#1B82B5"]]
        },
        "vfx_sword_slash_fire": {
            "name": "Fire Kor Slash",
            "colors": [hex_to_rgb(c) for c in ["#4E0800", "#A81E00", "#FF6B00", "#FFD030", "#FFFFFF"]],
            "sparks": [hex_to_rgb(c) for c in ["#FFE066", "#FFFFFF", "#FF8800", "#D62828"]]
        }
    }

    w, h = 96, 96
    cx, cy = 48.0, 50.0

    # 6 frames definition: [start_deg, end_deg, r_base, thickness, spark_count, alpha_mult]
    # Sweeping from top-left (-130 deg) across down to bottom-right (+115 deg)
    FRAME_SPECS = [
        # Frame 0: Ignition sliver
        {"start": -120.0, "end": -80.0, "r": 34.0, "th": 5.0, "sparks": 4, "fade": 0.85},
        # Frame 1: Rapid slice
        {"start": -125.0, "end": 0.0, "r": 38.0, "th": 11.0, "sparks": 10, "fade": 1.0},
        # Frame 2: Peak extension (Exact match to screenshot sweeping blade arc!)
        {"start": -115.0, "end": 95.0, "r": 42.0, "th": 16.0, "sparks": 20, "fade": 1.0},
        # Frame 3: Follow-through and filament tearing
        {"start": -35.0, "end": 120.0, "r": 43.0, "th": 13.0, "sparks": 16, "fade": 0.90},
        # Frame 4: Dispersing arc remnants
        {"start": 30.0, "end": 135.0, "r": 44.0, "th": 8.0, "sparks": 12, "fade": 0.65},
        # Frame 5: Fading embers & spark dissipation
        {"start": 75.0, "end": 145.0, "r": 44.0, "th": 4.0, "sparks": 8, "fade": 0.35},
    ]

    for prefix, pinfo in PALETTES.items():
        pal = pinfo["colors"]
        spark_colors = pinfo["sparks"]
        frames = []

        for f_idx, spec in enumerate(FRAME_SPECS):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            start_d = spec["start"]
            end_d = spec["end"]
            span = end_d - start_d
            r_base = spec["r"]
            th = spec["th"]
            fade = spec["fade"]

            # Evaluate grid for crescent math
            yy, xx = np.mgrid[0:h, 0:w]
            dx = xx.astype(np.float32) - cx
            dy = yy.astype(np.float32) - cy
            dist = np.sqrt(dx * dx + dy * dy)
            ang = np.degrees(np.arctan2(dy, dx))

            # Angle relative to start
            rel_ang = (ang - start_d) % 360.0
            in_arc = rel_ang <= span
            u = np.clip(rel_ang / max(1.0, span), 0.0, 1.0) # 0 at tail, 1 at tip

            # Crescent taper profile: sharp tip, thick belly
            taper = (np.maximum(0.0, np.sin(u * math.pi)) ** 0.55) * (0.4 + 0.6 * u)
            cur_th = th * taper

            # Outer boundary is sharper than inner
            diff = dist - r_base
            in_body = in_arc & (diff >= -cur_th * 0.7) & (diff <= cur_th * 0.3)

            # Shading ramp: 1.0 at outer cutting edge, 0.0 at inner edge
            norm_edge = np.clip((diff + cur_th * 0.7) / np.maximum(0.1, cur_th), 0.0, 1.0)
            
            # Additional filament noise for frame 3 & 4
            noise = np.sin(dist * 0.8 + u * 12.0) * (0.15 if f_idx in (3, 4) else 0.0)
            norm_edge = np.clip(norm_edge + noise, 0.0, 1.0)

            # Paint crescent pixels
            px = np.zeros((h, w, 4), dtype=np.uint8)
            for y in range(h):
                for x in range(w):
                    if in_body[y, x] and cur_th[y, x] > 0.4:
                        v = norm_edge[y, x]
                        # Sharp white outer edge
                        if v > 0.88:
                            c = pal[4] # White edge
                            a = int(255 * fade)
                        elif v > 0.68:
                            c = pal[3] # Bright color
                            a = int(245 * fade)
                        elif v > 0.42:
                            c = pal[2] # Mid color
                            a = int(220 * fade)
                        elif v > 0.18:
                            c = pal[1] # Dark color
                            a = int(180 * fade)
                        else:
                            c = pal[0] # Deep shadow
                            a = int(120 * fade)
                        px[y, x] = (*c, a)

            frame_img = Image.fromarray(px, mode="RGBA")
            f_draw = ImageDraw.Draw(frame_img)

            # Add leading tip brilliant diamond flash on peak frames
            if f_idx in (1, 2, 3):
                tip_ang_rad = math.radians(end_d)
                tip_x = int(round(cx + r_base * math.cos(tip_ang_rad)))
                tip_y = int(round(cy + r_base * math.sin(tip_ang_rad)))
                flash_r = 3 if f_idx == 2 else 2
                f_draw.rectangle([tip_x - flash_r, tip_y - 1, tip_x + flash_r, tip_y + 1], fill=(*pal[4], int(255 * fade)))
                f_draw.rectangle([tip_x - 1, tip_y - flash_r, tip_x + 1, tip_y + flash_r], fill=(*pal[4], int(255 * fade)))

            # Draw trailing sparks along arc
            n_sparks = spec["sparks"]
            for s_i in range(n_sparks):
                s_seed = (f_idx * 17 + s_i * 29)
                s_u = (s_seed % 100) / 100.0
                if s_u > 0.95 and f_idx < 4:
                    continue # keep tip clean
                s_ang = math.radians(start_d + s_u * span)
                # Sparks spray outward from slash trajectory
                spray = ((s_seed * 7) % 11) - 4
                s_r = r_base + spray + (f_idx * 1.5)
                sx = int(round(cx + s_r * math.cos(s_ang)))
                sy = int(round(cy + s_r * math.sin(s_ang)))
                if 0 <= sx < w and 0 <= sy < h:
                    sc = random.choice(spark_colors)
                    sa = int(random.randint(160, 255) * fade)
                    if (s_i % 3) == 0:
                        # 2x2 spark
                        f_draw.rectangle([sx, sy, sx+1, sy+1], fill=(*sc, sa))
                    else:
                        f_draw.point((sx, sy), fill=(*sc, sa))

            frames.append(frame_img)

        save_strip_and_meta(prefix, frames, loop=False, fps=14.0)


# ============================================================================
# 2. KOR DÖNÜŞÜ / FIRE RING, TORNADO & BURST
# ============================================================================

def generate_fire_ring():
    w, h = 128, 96
    cx, cy = 64.0, 48.0
    y_scale = 0.68 # Top-down orthographic ground plane foreshortening

    PALETTE = [
        hex_to_rgb("#180202"), # 0: Dark charred soot
        hex_to_rgb("#5A0606"), # 1: Deep ember red
        hex_to_rgb("#B81400"), # 2: Roaring flame crimson
        hex_to_rgb("#FF5900"), # 3: Fiery orange
        hex_to_rgb("#FFB300"), # 4: Bright flame yellow
        hex_to_rgb("#FFFFFF"), # 5: Hot white core
    ]

    # 8 frames of expanding ground ring (exact match to circular ground flame in screenshot!)
    # radius, thickness, flame_height, ember_count, fade
    SPECS = [
        {"r": 12.0, "th": 5.0, "h_flame": 6.0, "embers": 10, "scorch_alpha": 70, "fade": 0.9},
        {"r": 22.0, "th": 8.0, "h_flame": 11.0, "embers": 18, "scorch_alpha": 120, "fade": 1.0},
        {"r": 34.0, "th": 12.0, "h_flame": 16.0, "embers": 30, "scorch_alpha": 180, "fade": 1.0},
        {"r": 44.0, "th": 14.0, "h_flame": 20.0, "embers": 45, "scorch_alpha": 220, "fade": 1.0}, # Full explosion ring!
        {"r": 48.0, "th": 13.0, "h_flame": 18.0, "embers": 40, "scorch_alpha": 240, "fade": 0.95},
        {"r": 50.0, "th": 10.0, "h_flame": 14.0, "embers": 32, "scorch_alpha": 200, "fade": 0.80},
        {"r": 51.0, "th": 7.0, "h_flame": 8.0, "embers": 20, "scorch_alpha": 150, "fade": 0.55},
        {"r": 52.0, "th": 4.0, "h_flame": 4.0, "embers": 10, "scorch_alpha": 90, "fade": 0.30},
    ]

    frames = []
    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx.astype(np.float32) - cx
    dy_ground = (yy.astype(np.float32) - cy) / y_scale
    dist_ground = np.sqrt(dx * dx + dy_ground * dy_ground)
    theta = np.arctan2(dy_ground, dx)

    for f_idx, spec in enumerate(SPECS):
        frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(frame)

        r_target = spec["r"]
        th = spec["th"]
        flame_h = spec["h_flame"]
        fade = spec["fade"]

        # 1. Scorch mark on ground inside the ring
        scorch_mask = dist_ground <= (r_target + 2.0)
        scorch_norm = np.clip(1.0 - dist_ground / max(1.0, r_target), 0.0, 1.0)
        px = np.zeros((h, w, 4), dtype=np.uint8)

        # FBM noise for jagged flames around ring
        fbm = np.sin(theta * 9.0 + f_idx * 1.7) * 0.5 + np.sin(theta * 19.0 - f_idx * 2.3) * 0.25
        flame_tongue = np.maximum(0.0, np.sin(theta * 7.0 + f_idx * 1.5)) * flame_h

        # Ring distance
        ring_diff = np.abs(dist_ground - r_target)
        in_ring = ring_diff <= (th * 0.5 + flame_tongue * 0.4)

        for y in range(h):
            for x in range(w):
                # Center scorch with glowing orange cracks
                if scorch_mask[y, x] and not in_ring[y, x]:
                    s_val = scorch_norm[y, x]
                    # Glowing center crack lines
                    crack = math.sin(dx[y, x] * 0.5) * math.cos(dy_ground[y, x] * 0.5)
                    if crack > 0.65 and f_idx in (2, 3, 4, 5):
                        px[y, x] = (*PALETTE[3], int(160 * fade * s_val))
                    else:
                        px[y, x] = (*PALETTE[0], int(spec["scorch_alpha"] * (0.4 + 0.6 * s_val)))

                # Blazing ring
                if in_ring[y, x]:
                    # Vertical flame displacement in screen space (flames rise up in -Y)
                    d_r = ring_diff[y, x]
                    rel_th = 1.0 - (d_r / (th * 0.5 + flame_tongue[y, x] * 0.4 + 0.1))
                    rel_th = np.clip(rel_th + fbm[y, x] * 0.2, 0.0, 1.0)

                    if rel_th > 0.85:
                        c = PALETTE[5] # White core
                        a = int(255 * fade)
                    elif rel_th > 0.68:
                        c = PALETTE[4] # Yellow
                        a = int(250 * fade)
                    elif rel_th > 0.45:
                        c = PALETTE[3] # Orange
                        a = int(235 * fade)
                    elif rel_th > 0.22:
                        c = PALETTE[2] # Red
                        a = int(200 * fade)
                    else:
                        c = PALETTE[1] # Dark red
                        a = int(140 * fade)
                    px[y, x] = (*c, a)

        frame = Image.fromarray(px, mode="RGBA")
        f_draw = ImageDraw.Draw(frame)

        # Draw floating rising fiery embers
        n_embers = spec["embers"]
        for e_i in range(n_embers):
            e_seed = (f_idx * 31 + e_i * 47)
            e_ang = (e_seed * 0.73) % (2.0 * math.pi)
            e_r = r_target + ((e_seed % 17) - 8)
            # Embers rise in -Y
            ex = int(round(cx + e_r * math.cos(e_ang)))
            ey = int(round(cy + (e_r * math.sin(e_ang) * y_scale) - (f_idx * 2.5 + (e_seed % 12))))
            if 0 <= ex < w and 0 <= ey < h:
                ec = PALETTE[4] if (e_i % 2 == 0) else PALETTE[3]
                ea = int(random.randint(180, 255) * fade)
                if (e_i % 3) == 0:
                    f_draw.rectangle([ex, ey, ex+1, ey+1], fill=(*ec, ea))
                else:
                    f_draw.point((ex, ey), fill=(*ec, ea))

        frames.append(frame)

    save_strip_and_meta("vfx_fire_ring", frames, loop=False, fps=12.0)


def generate_fire_tornado():
    w, h = 80, 112
    cx = 40.0
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#4E0800"),
        hex_to_rgb("#9C1A00"),
        hex_to_rgb("#E84E00"),
        hex_to_rgb("#FF9500"),
        hex_to_rgb("#FFDE4A"),
        hex_to_rgb("#FFFFFF"),
    ]

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = np.zeros((h, w, 4), dtype=np.uint8)

        # Vertical profile: Y goes from 10 (top) to 102 (base)
        phase = (f_idx / float(n_frames)) * 2.0 * math.pi

        for y in range(10, 104):
            v_norm = (y - 10) / 94.0 # 0 at top, 1 at ground
            # Funnel shape: wide at top (w=48), narrow at waist (w=22), medium at base (w=34)
            if v_norm < 0.6:
                funnel_r = 24.0 * (1.0 - v_norm * 0.7)
            else:
                funnel_r = 10.0 + 12.0 * (v_norm - 0.6) / 0.4

            # Helical ribbons (3 intertwining ribbons)
            for r_idx in range(3):
                ribbon_phase = phase + r_idx * (2.0 * math.pi / 3.0) + (1.0 - v_norm) * 5.0
                ribbon_center = cx + math.sin(ribbon_phase) * funnel_r
                ribbon_width = 3.5 + 4.0 * (1.0 - v_norm * 0.5)

                for x in range(w):
                    dx = abs(x - ribbon_center)
                    if dx <= ribbon_width:
                        rel = 1.0 - (dx / ribbon_width)
                        # Ribbon intensity
                        if rel > 0.8:
                            c = PALETTE[5]
                            a = 255
                        elif rel > 0.6:
                            c = PALETTE[4]
                            a = 240
                        elif rel > 0.4:
                            c = PALETTE[3]
                            a = 210
                        elif rel > 0.2:
                            c = PALETTE[2]
                            a = 160
                        else:
                            c = PALETTE[1]
                            a = 110
                        if a > px[y, x, 3]:
                            px[y, x] = (*c, a)

        frame = Image.fromarray(px, mode="RGBA")
        draw = ImageDraw.Draw(frame)

        # Ground fire contact swirl
        draw.ellipse([cx - 18, 98, cx + 18, 106], fill=(*PALETTE[3], 150), outline=(*PALETTE[4], 220))
        draw.ellipse([cx - 10, 100, cx + 10, 104], fill=(*PALETTE[5], 255))

        # Spiraling embers
        for e_i in range(16):
            e_seed = f_idx * 23 + e_i * 37
            ey = 12 + (e_seed % 88)
            v_norm = (ey - 10) / 94.0
            r_outer = 18.0 + 14.0 * (1.0 - v_norm)
            e_ang = (e_seed * 1.1 + f_idx * 1.2)
            ex = int(round(cx + math.sin(e_ang) * r_outer))
            if 0 <= ex < w and 0 <= ey < h:
                ec = PALETTE[4] if e_i % 2 == 0 else PALETTE[3]
                draw.rectangle([ex, ey, ex+1, ey+1], fill=(*ec, 230))

        frames.append(frame)

    save_strip_and_meta("vfx_fire_tornado", frames, loop=True, fps=12.0)


def generate_flame_burst():
    w, h = 96, 96
    cx, cy = 48.0, 52.0
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#450600"),
        hex_to_rgb("#991400"),
        hex_to_rgb("#F05000"),
        hex_to_rgb("#FF9D00"),
        hex_to_rgb("#FFE252"),
        hex_to_rgb("#FFFFFF"),
    ]

    # Radii and parameters for 6 frames explosive burst
    SPECS = [
        {"r": 12.0, "lobes": 5, "fade": 0.9, "core_r": 8.0},
        {"r": 26.0, "lobes": 7, "fade": 1.0, "core_r": 14.0},
        {"r": 38.0, "lobes": 8, "fade": 1.0, "core_r": 16.0}, # Peak blast!
        {"r": 42.0, "lobes": 8, "fade": 0.85, "core_r": 10.0},
        {"r": 44.0, "lobes": 7, "fade": 0.55, "core_r": 5.0},
        {"r": 45.0, "lobes": 6, "fade": 0.25, "core_r": 0.0},
    ]

    frames = []
    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx.astype(np.float32) - cx
    dy = yy.astype(np.float32) - cy
    dist = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dy, dx)

    for f_idx, spec in enumerate(SPECS):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = np.zeros((h, w, 4), dtype=np.uint8)

        max_r = spec["r"]
        n_lobes = spec["lobes"]
        fade = spec["fade"]
        core_r = spec["core_r"]

        # Lobe shape: modulated radius with angular frequency
        lobe_var = np.abs(np.sin(theta * (n_lobes * 0.5) + f_idx * 0.8)) ** 1.6
        bound_r = max_r * (0.65 + 0.35 * lobe_var)

        in_burst = dist <= bound_r
        rel_r = np.clip(1.0 - (dist / np.maximum(1.0, bound_r)), 0.0, 1.0)

        for y in range(h):
            for x in range(w):
                if in_burst[y, x]:
                    d = dist[y, x]
                    val = rel_r[y, x]
                    if d <= core_r:
                        c = PALETTE[5] # White core
                        a = int(255 * fade)
                    elif val > 0.70:
                        c = PALETTE[4] # Yellow
                        a = int(245 * fade)
                    elif val > 0.45:
                        c = PALETTE[3] # Orange
                        a = int(220 * fade)
                    elif val > 0.20:
                        c = PALETTE[2] # Red
                        a = int(180 * fade)
                    else:
                        c = PALETTE[1] # Dark red
                        a = int(120 * fade)
                    px[y, x] = (*c, a)

        frame = Image.fromarray(px, mode="RGBA")
        draw = ImageDraw.Draw(frame)

        # Debris sparks flying outward
        n_sparks = 14 + f_idx * 4
        for s_i in range(n_sparks):
            s_seed = f_idx * 19 + s_i * 31
            s_ang = (s_seed * 0.8) % (2.0 * math.pi)
            s_dist = max_r * (0.8 + 0.5 * ((s_seed % 10) / 10.0))
            sx = int(round(cx + s_dist * math.cos(s_ang)))
            sy = int(round(cy + s_dist * math.sin(s_ang)))
            if 0 <= sx < w and 0 <= sy < h:
                sc = PALETTE[4] if s_i % 2 == 0 else PALETTE[3]
                sa = int(240 * fade)
                draw.rectangle([sx, sy, sx+1, sy+1], fill=(*sc, sa))

        frames.append(frame)

    save_strip_and_meta("vfx_flame_burst", frames, loop=False, fps=12.0)


# ============================================================================
# 3. RADIUS SHOCKWAVE & BLADE STORM
# ============================================================================

def generate_radius_shockwave():
    w, h = 128, 96
    cx, cy = 64.0, 48.0
    y_scale = 0.68
    n_frames = 6

    PALETTE = [
        hex_to_rgb("#141D2B"), # Shadow
        hex_to_rgb("#31445E"), # Dust
        hex_to_rgb("#6684A6"), # Air compression
        hex_to_rgb("#B8D0E8"), # Shock vapor
        hex_to_rgb("#FFFFFF"), # Razor shock front
    ]

    SPECS = [
        {"r": 14.0, "th": 5.0, "dust": 8, "crack": 10.0, "fade": 1.0},
        {"r": 26.0, "th": 7.0, "dust": 16, "crack": 14.0, "fade": 1.0},
        {"r": 38.0, "th": 9.0, "dust": 24, "crack": 12.0, "fade": 0.95},
        {"r": 48.0, "th": 8.0, "dust": 28, "crack": 8.0, "fade": 0.80},
        {"r": 54.0, "th": 6.0, "dust": 20, "crack": 4.0, "fade": 0.55},
        {"r": 58.0, "th": 4.0, "dust": 12, "crack": 0.0, "fade": 0.30},
    ]

    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx.astype(np.float32) - cx
    dy_ground = (yy.astype(np.float32) - cy) / y_scale
    dist_ground = np.sqrt(dx * dx + dy_ground * dy_ground)
    theta = np.arctan2(dy_ground, dx)

    frames = []
    for f_idx, spec in enumerate(SPECS):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = np.zeros((h, w, 4), dtype=np.uint8)

        r_target = spec["r"]
        th = spec["th"]
        fade = spec["fade"]
        crack_r = spec["crack"]

        ring_diff = np.abs(dist_ground - r_target)
        in_ring = ring_diff <= (th * 0.5)

        for y in range(h):
            for x in range(w):
                # Center impact cracks during early frames
                if crack_r > 1.0 and dist_ground[y, x] <= crack_r:
                    # 4 radial crack lines
                    c_pattern = abs(math.sin(theta[y, x] * 2.0))
                    if c_pattern > 0.85:
                        px[y, x] = (*PALETTE[4], int(230 * fade))
                    elif c_pattern > 0.65:
                        px[y, x] = (*PALETTE[1], int(160 * fade))

                # Expanding shock boundary ring
                if in_ring[y, x]:
                    # Leading outer boundary is brilliant white
                    rel = 1.0 - (ring_diff[y, x] / (th * 0.5))
                    is_outer = (dist_ground[y, x] >= r_target - 1.0) and (dist_ground[y, x] <= r_target + 1.5)
                    if is_outer:
                        c = PALETTE[4] # White leading edge
                        a = int(255 * fade)
                    elif rel > 0.6:
                        c = PALETTE[3]
                        a = int(230 * fade)
                    elif rel > 0.3:
                        c = PALETTE[2]
                        a = int(180 * fade)
                    else:
                        c = PALETTE[1]
                        a = int(120 * fade)
                    px[y, x] = (*c, a)

        frame = Image.fromarray(px, mode="RGBA")
        draw = ImageDraw.Draw(frame)

        # Draw billowing dust clumps trailing behind the shockwave
        n_dust = spec["dust"]
        for d_i in range(n_dust):
            d_seed = f_idx * 29 + d_i * 43
            d_ang = (d_seed * 0.61) % (2.0 * math.pi)
            d_r = r_target - ((d_seed % 10) + 2)
            dx_p = int(round(cx + d_r * math.cos(d_ang)))
            dy_p = int(round(cy + d_r * math.sin(d_ang) * y_scale))
            if 0 <= dx_p < w and 0 <= dy_p < h:
                dc = PALETTE[2] if d_i % 2 == 0 else PALETTE[1]
                da = int(150 * fade)
                d_size = 2 if d_i % 3 == 0 else 1
                draw.rectangle([dx_p, dy_p, dx_p + d_size, dy_p + d_size], fill=(*dc, da))

        frames.append(frame)

    save_strip_and_meta("vfx_radius_shockwave", frames, loop=False, fps=12.0)


def generate_blade_storm():
    w, h = 112, 112
    cx, cy = 56.0, 56.0
    n_frames = 8
    PALETTE = [
        hex_to_rgb("#240342"), # Deep shadow
        hex_to_rgb("#5E0F9E"), # Dark purple
        hex_to_rgb("#B123E0"), # Vivid magenta
        hex_to_rgb("#F28AFF"), # Bright lavender
        hex_to_rgb("#FFFFFF"), # Pure white blade edge
    ]

    frames = []
    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx.astype(np.float32) - cx
    dy = yy.astype(np.float32) - cy
    dist = np.sqrt(dx * dx + dy * dy)
    theta = np.degrees(np.arctan2(dy, dx))

    # 3 interlocking crescent blades rotating at continuous high speed (45 deg per frame)
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        px = np.zeros((h, w, 4), dtype=np.uint8)

        base_rot = f_idx * 45.0 # Continuous 360 rotation over 8 frames
        r_blades = [36.0, 42.0, 40.0]
        spans = [110.0, 100.0, 115.0]

        for b_idx in range(3):
            b_start = (base_rot + b_idx * 120.0) % 360.0
            b_span = spans[b_idx]
            b_r = r_blades[b_idx]
            th = 10.0

            rel_ang = (theta - b_start) % 360.0
            in_blade = rel_ang <= b_span
            u = np.clip(rel_ang / b_span, 0.0, 1.0)
            taper = (np.maximum(0.0, np.sin(u * math.pi)) ** 0.6) * (0.3 + 0.7 * u)
            cur_th = th * taper

            diff = dist - b_r
            in_body = in_blade & (diff >= -cur_th * 0.7) & (diff <= cur_th * 0.3) & (cur_th > 0.4)
            norm_edge = np.clip((diff + cur_th * 0.7) / np.maximum(0.1, cur_th), 0.0, 1.0)

            for y in range(h):
                for x in range(w):
                    if in_body[y, x]:
                        v = norm_edge[y, x]
                        if v > 0.85:
                            c = PALETTE[4]
                            a = 255
                        elif v > 0.65:
                            c = PALETTE[3]
                            a = 240
                        elif v > 0.40:
                            c = PALETTE[2]
                            a = 210
                        elif v > 0.18:
                            c = PALETTE[1]
                            a = 160
                        else:
                            c = PALETTE[0]
                            a = 110
                        if a > px[y, x, 3]:
                            px[y, x] = (*c, a)

        frame = Image.fromarray(px, mode="RGBA")
        draw = ImageDraw.Draw(frame)

        # Center energy vortex core
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(*PALETTE[3], 180), outline=(*PALETTE[4], 255))
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(*PALETTE[4], 255))

        # Orbiting vortex sparks
        for s_i in range(18):
            s_seed = f_idx * 17 + s_i * 29
            s_ang = math.radians((s_seed * 4.3 + f_idx * 40.0) % 360.0)
            s_r = 20.0 + ((s_seed * 5) % 28)
            sx = int(round(cx + s_r * math.cos(s_ang)))
            sy = int(round(cy + s_r * math.sin(s_ang)))
            if 0 <= sx < w and 0 <= sy < h:
                sc = PALETTE[3] if s_i % 2 == 0 else PALETTE[4]
                draw.rectangle([sx, sy, sx+1, sy+1], fill=(*sc, 230))

        frames.append(frame)

    save_strip_and_meta("vfx_blade_storm", frames, loop=True, fps=12.0)


# ============================================================================
# 4. ARCHER SKILLS: ARROW RAIN, PIERCING BEAM, STORM VOLLEY CONE
# ============================================================================

def generate_arrow_rain():
    w, h = 112, 128
    cx, cy = 56.0, 92.0 # Ground impact center
    n_frames = 8
    y_scale = 0.65

    PALETTE = [
        hex_to_rgb("#0F2847"), # Reticle dark
        hex_to_rgb("#1F66A3"), # Arrow body
        hex_to_rgb("#40BCE6"), # Cyan energy
        hex_to_rgb("#96EEFF"), # Bright blue-white
        hex_to_rgb("#FFFFFF"), # Impact white flash
    ]

    # Arrow trajectories diving at 75 degree angle (dx = -0.27 * dy)
    ARROW_DATA = [
        {"gx": 40.0, "gy": 82.0, "t_impact": 2},
        {"gx": 68.0, "gy": 96.0, "t_impact": 2},
        {"gx": 54.0, "gy": 74.0, "t_impact": 3},
        {"gx": 32.0, "gy": 100.0, "t_impact": 3},
        {"gx": 76.0, "gy": 86.0, "t_impact": 4},
        {"gx": 56.0, "gy": 94.0, "t_impact": 4},
        {"gx": 46.0, "gy": 106.0, "t_impact": 5},
    ]

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 1. Ground targeted area runic reticle
        ret_fade = 1.0 if f_idx <= 4 else max(0.0, (7 - f_idx) / 3.0)
        ret_rx, ret_ry = 44.0, 44.0 * y_scale
        draw.ellipse([cx - ret_rx, cy - ret_ry, cx + ret_rx, cy + ret_ry],
                     outline=(*PALETTE[2], int(180 * ret_fade)), width=1)
        draw.ellipse([cx - ret_rx * 0.6, cy - ret_ry * 0.6, cx + ret_rx * 0.6, cy + ret_ry * 0.6],
                     outline=(*PALETTE[1], int(120 * ret_fade)), width=1)

        # 2. Draw descending or impacted arrows
        for arr in ARROW_DATA:
            gx, gy = arr["gx"], arr["gy"]
            t_imp = arr["t_impact"]

            if f_idx < t_imp:
                # Arrow is descending from above
                # At impact, tip is at (gx, gy). Earlier frames: tip is higher
                dt = t_imp - f_idx
                tip_y = gy - dt * 38.0
                tip_x = gx + dt * 10.0
                tail_y = tip_y - 24.0
                tail_x = tip_x + 6.5

                if tip_y > -10:
                    # Draw arrow shaft and luminous speed trail
                    draw.line([(tail_x, tail_y), (tip_x, tip_y)], fill=(*PALETTE[3], 240), width=2)
                    draw.line([(tail_x + 1, tail_y - 8), (tail_x, tail_y)], fill=(*PALETTE[2], 140), width=1)
                    # Arrow head
                    draw.rectangle([int(tip_x - 1), int(tip_y - 1), int(tip_x + 1), int(tip_y + 1)], fill=(*PALETTE[4], 255))

            elif f_idx == t_imp:
                # Impact frame! White starburst and splash rings
                draw.ellipse([gx - 12, gy - 6, gx + 12, gy + 6], outline=(*PALETTE[3], 240), width=2)
                draw.rectangle([int(gx - 3), int(gy - 1), int(gx + 3), int(gy + 1)], fill=(*PALETTE[4], 255))
                draw.rectangle([int(gx - 1), int(gy - 3), int(gx + 1), int(gy + 3)], fill=(*PALETTE[4], 255))
                # Embedded shaft
                draw.line([(gx + 5, gy - 18), (gx, gy)], fill=(*PALETTE[3], 255), width=2)

            else:
                # Post-impact: embedded arrow vibrating or shattering
                age = f_idx - t_imp
                if age <= 2:
                    # Embedded glowing arrow
                    draw.line([(gx + 5, gy - 18), (gx, gy)], fill=(*PALETTE[3], int(255 - age * 70)), width=1)
                    draw.ellipse([gx - 6, gy - 3, gx + 6, gy + 3], outline=(*PALETTE[2], int(160 - age * 60)), width=1)
                elif age == 3:
                    # Shattering glints
                    for gl in range(4):
                        gl_x = int(gx + (gl * 3 - 5))
                        gl_y = int(gy - 10 - gl * 4)
                        draw.point((gl_x, gl_y), fill=(*PALETTE[4], 180))

        frames.append(img)

    save_strip_and_meta("vfx_arrow_rain", frames, loop=False, fps=12.0)


def generate_piercing_arrow_beam():
    w, h = 160, 64
    cy = 32.0
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#1A1238"),
        hex_to_rgb("#40308C"),
        hex_to_rgb("#8055E8"),
        hex_to_rgb("#B89CFF"),
        hex_to_rgb("#FFFFFF"),
    ]

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Frame 0: Focus laser and initial flash
        if f_idx == 0:
            draw.line([(0, cy), (160, cy)], fill=(*PALETTE[2], 140), width=1)
            draw.ellipse([10, cy - 8, 26, cy + 8], fill=(*PALETTE[4], 255))

        # Frame 1: Spearhead piercing across
        elif f_idx == 1:
            draw.line([(0, cy), (120, cy)], fill=(*PALETTE[3], 240), width=4)
            draw.line([(0, cy), (120, cy)], fill=(*PALETTE[4], 255), width=2)
            # Arrowhead
            draw.polygon([(135, cy), (115, cy - 8), (120, cy), (115, cy + 8)], fill=(*PALETTE[4], 255))
            # Conical sonic cone
            draw.line([(120, cy - 8), (80, cy - 20)], fill=(*PALETTE[2], 180), width=2)
            draw.line([(120, cy + 8), (80, cy + 20)], fill=(*PALETTE[2], 180), width=2)

        # Frame 2: Full beam at peak radiance!
        elif f_idx == 2:
            # Outer plasma sheath
            draw.rectangle([0, int(cy - 9), 160, int(cy + 9)], fill=(*PALETTE[1], 120))
            draw.rectangle([0, int(cy - 6), 160, int(cy + 6)], fill=(*PALETTE[2], 190))
            draw.rectangle([0, int(cy - 3), 160, int(cy + 3)], fill=(*PALETTE[3], 240))
            draw.line([(0, cy), (160, cy)], fill=(*PALETTE[4], 255), width=2)
            # 3 Sonic shock diamonds along the shaft
            for sx in (40, 85, 130):
                draw.polygon([(sx + 8, cy), (sx, cy - 12), (sx - 8, cy), (sx, cy + 12)], outline=(*PALETTE[4], 255), width=1)

        # Frame 3: Sustained beam with spiraling helix
        elif f_idx == 3:
            draw.rectangle([0, int(cy - 5), 160, int(cy + 5)], fill=(*PALETTE[2], 160))
            draw.line([(0, cy), (160, cy)], fill=(*PALETTE[4], 255), width=2)
            # Wavy helix
            for x in range(0, 160, 2):
                hy = int(cy + math.sin(x * 0.15) * 8.0)
                draw.point((x, hy), fill=(*PALETTE[3], 220))
                draw.point((x, int(2 * cy - hy)), fill=(*PALETTE[3], 220))

        # Frame 4: Segmented beam decay
        elif f_idx == 4:
            for seg in range(0, 160, 18):
                draw.line([(seg, cy), (seg + 12, cy)], fill=(*PALETTE[3], 180), width=2)
                draw.line([(seg + 2, cy), (seg + 10, cy)], fill=(*PALETTE[4], 230), width=1)

        # Frame 5: Dissipating sparkles
        elif f_idx == 5:
            for s in range(22):
                sx = (s * 31) % 160
                sy = int(cy + ((s * 17) % 19) - 9)
                draw.point((sx, sy), fill=(*PALETTE[3], 150))

        frames.append(img)

    save_strip_and_meta("vfx_piercing_arrow_beam", frames, loop=False, fps=12.0)


def generate_storm_volley_cone():
    w, h = 128, 96
    cx, cy = 16.0, 48.0 # Origin
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#0E2A38"),
        hex_to_rgb("#1C6A8C"),
        hex_to_rgb("#34BCE8"),
        hex_to_rgb("#96EEFF"),
        hex_to_rgb("#FFFFFF"),
    ]

    # 5 arrow angles spanning 50 degree cone (-24, -12, 0, 12, 24 deg)
    ANGLES = [-24.0, -12.0, 0.0, 12.0, 24.0]
    DISTANCES = [8.0, 26.0, 56.0, 88.0, 105.0, 112.0]

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        d_cur = DISTANCES[f_idx]
        fade = 1.0 if f_idx < 4 else (1.0 - (f_idx - 3) * 0.45)

        # Frame 0: Launch burst at origin
        if f_idx == 0:
            draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(*PALETTE[4], 255))
            draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], outline=(*PALETTE[3], 200), width=2)

        # Frames 1-3: Surging arrows with trails
        elif f_idx in (1, 2, 3):
            for ang_deg in ANGLES:
                rad = math.radians(ang_deg)
                tx = cx + d_cur * math.cos(rad)
                ty = cy + d_cur * math.sin(rad)
                trail_len = min(d_cur - 4.0, 26.0 + f_idx * 10.0)
                bx = tx - trail_len * math.cos(rad)
                by = ty - trail_len * math.sin(rad)

                # Trail
                draw.line([(bx, by), (tx, ty)], fill=(*PALETTE[2], int(180 * fade)), width=2)
                draw.line([(bx + 4 * math.cos(rad), by + 4 * math.sin(rad)), (tx, ty)], fill=(*PALETTE[3], int(240 * fade)), width=1)
                # Head
                draw.rectangle([int(tx - 1), int(ty - 1), int(tx + 1), int(ty + 1)], fill=(*PALETTE[4], int(255 * fade)))

        # Frame 4: Detonation starbursts at cone perimeter
        elif f_idx == 4:
            for ang_deg in ANGLES:
                rad = math.radians(ang_deg)
                tx = int(cx + d_cur * math.cos(rad))
                ty = int(cy + d_cur * math.sin(rad))
                if 0 <= tx < w and 0 <= ty < h:
                    draw.rectangle([tx - 3, ty - 1, tx + 3, ty + 1], fill=(*PALETTE[4], 255))
                    draw.rectangle([tx - 1, ty - 3, tx + 1, ty + 3], fill=(*PALETTE[4], 255))
                    draw.ellipse([tx - 5, ty - 5, tx + 5, ty + 5], outline=(*PALETTE[3], 200), width=1)

        # Frame 5: Dispersing sparkles
        elif f_idx == 5:
            for ang_deg in ANGLES:
                rad = math.radians(ang_deg)
                for s in range(5):
                    tx = int(cx + (d_cur + s * 3 - 6) * math.cos(rad))
                    ty = int(cy + (d_cur + s * 3 - 6) * math.sin(rad) + (s % 3 - 1) * 3)
                    if 0 <= tx < w and 0 <= ty < h:
                        draw.point((tx, ty), fill=(*PALETTE[3], 150))

        frames.append(img)

    save_strip_and_meta("vfx_storm_volley_cone", frames, loop=False, fps=12.0)


# ============================================================================
# 5. WATER & FROST ELEMENTAL REACTIONS (GDD 3.4)
# ============================================================================

def generate_frost_shatter():
    w, h = 96, 96
    cx, cy = 48.0, 48.0
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#0A2540"),
        hex_to_rgb("#186596"),
        hex_to_rgb("#30BBE6"),
        hex_to_rgb("#96ECFF"),
        hex_to_rgb("#FFFFFF"),
    ]

    # 12 shard directions & velocities
    SHARDS = []
    for i in range(12):
        a = i * (2.0 * math.pi / 12.0) + (i % 3) * 0.1
        spd = 1.0 + (i % 4) * 0.25
        SHARDS.append((a, spd))

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Frame 0: Hexagonal crystal intact with deep cyan glow
        if f_idx == 0:
            draw.polygon([
                (cx, cy - 20), (cx + 17, cy - 10), (cx + 17, cy + 10),
                (cx, cy + 20), (cx - 17, cy + 10), (cx - 17, cy - 10)
            ], fill=(*PALETTE[1], 200), outline=(*PALETTE[3], 255))
            draw.polygon([
                (cx, cy - 12), (cx + 10, cy - 6), (cx + 10, cy + 6),
                (cx, cy + 12), (cx - 10, cy + 6), (cx - 10, cy - 6)
            ], fill=(*PALETTE[2], 230), outline=(*PALETTE[4], 255))
            draw.line([(cx, cy - 20), (cx, cy + 20)], fill=(*PALETTE[4], 255), width=1)
            draw.line([(cx - 17, cy), (cx + 17, cy)], fill=(*PALETTE[4], 255), width=1)

        # Frame 1: Fracture stress cracks
        elif f_idx == 1:
            draw.polygon([
                (cx, cy - 20), (cx + 17, cy - 10), (cx + 17, cy + 10),
                (cx, cy + 20), (cx - 17, cy + 10), (cx - 17, cy - 10)
            ], fill=(*PALETTE[2], 220), outline=(*PALETTE[4], 255))
            # Fissure lines
            draw.line([(cx - 14, cy - 8), (cx - 2, cy), (cx + 6, cy - 12), (cx + 16, cy - 4)], fill=(*PALETTE[4], 255), width=2)
            draw.line([(cx - 8, cy + 14), (cx + 2, cy + 4), (cx + 14, cy + 12)], fill=(*PALETTE[4], 255), width=2)

        # Frame 2: Explosive shattering!
        elif f_idx == 2:
            draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(*PALETTE[4], 255))
            for a, spd in SHARDS:
                dist = 18.0 * spd
                sx = cx + dist * math.cos(a)
                sy = cy + dist * math.sin(a)
                # Diamond needle shard
                nx, ny = -math.sin(a) * 3, math.cos(a) * 3
                draw.polygon([(sx + math.cos(a)*6, sy + math.sin(a)*6),
                              (sx + nx, sy + ny),
                              (sx - math.cos(a)*6, sy - math.sin(a)*6),
                              (sx - nx, sy - ny)], fill=(*PALETTE[3], 255), outline=(*PALETTE[4], 255))

        # Frame 3: Shards flying out + frost mist
        elif f_idx == 3:
            # Frost mist cloud
            draw.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(*PALETTE[1], 80), outline=(*PALETTE[2], 140))
            for a, spd in SHARDS:
                dist = 32.0 * spd
                sx = cx + dist * math.cos(a)
                sy = cy + dist * math.sin(a)
                if 0 <= sx < w and 0 <= sy < h:
                    draw.rectangle([int(sx-2), int(sy-2), int(sx+2), int(sy+2)], fill=(*PALETTE[3], 240), outline=(*PALETTE[4], 255))

        # Frame 4: Shards dissolving to glitter
        elif f_idx == 4:
            draw.ellipse([cx - 34, cy - 34, cx + 34, cy + 34], fill=(*PALETTE[1], 40))
            for a, spd in SHARDS:
                dist = 40.0 * spd
                sx = int(cx + dist * math.cos(a))
                sy = int(cy + dist * math.sin(a))
                if 0 <= sx < w and 0 <= sy < h:
                    draw.point((sx, sy), fill=(*PALETTE[4], 220))
                    draw.point((sx+1, sy), fill=(*PALETTE[3], 180))

        # Frame 5: Fading frost mist
        elif f_idx == 5:
            for s in range(16):
                sa = (s * 0.39) % (2.0 * math.pi)
                sr = 20.0 + (s * 7) % 24
                sx = int(cx + sr * math.cos(sa))
                sy = int(cy + sr * math.sin(sa))
                if 0 <= sx < w and 0 <= sy < h:
                    draw.point((sx, sy), fill=(*PALETTE[3], 110))

        frames.append(img)

    save_strip_and_meta("vfx_frost_shatter", frames, loop=False, fps=12.0)


def generate_water_splash():
    w, h = 96, 80
    cx, cy = 48.0, 52.0
    y_scale = 0.65
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#0B2A4A"),
        hex_to_rgb("#185F96"),
        hex_to_rgb("#32AEE0"),
        hex_to_rgb("#94E6FF"),
        hex_to_rgb("#FFFFFF"),
    ]

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Frame 0: Splash crown impact
        if f_idx == 0:
            draw.ellipse([cx - 16, cy - 8, cx + 16, cy + 8], fill=(*PALETTE[2], 220), outline=(*PALETTE[4], 255))
            # 6 crown spikes
            for sp in range(6):
                ang = sp * (math.pi / 5.0)
                sp_x = cx + math.cos(ang) * 16.0
                sp_y = cy - 4.0 - math.sin(ang) * 10.0
                draw.line([(cx + math.cos(ang)*14.0, cy), (sp_x, sp_y)], fill=(*PALETTE[4], 255), width=2)

        # Frame 1: Upward water geyser eruption
        elif f_idx == 1:
            draw.ellipse([cx - 24, cy - 12, cx + 24, cy + 12], outline=(*PALETTE[3], 200), width=2)
            # Central geyser & 4 parabolic arcs
            draw.polygon([(cx - 8, cy), (cx, cy - 36), (cx + 8, cy)], fill=(*PALETTE[2], 230), outline=(*PALETTE[4], 255))
            draw.ellipse([cx - 3, cy - 38, cx + 3, cy - 32], fill=(*PALETTE[4], 255))
            # Left & right jets
            draw.line([(cx - 6, cy - 10), (cx - 24, cy - 28)], fill=(*PALETTE[3], 240), width=2)
            draw.line([(cx + 6, cy - 10), (cx + 24, cy - 28)], fill=(*PALETTE[3], 240), width=2)
            draw.ellipse([cx - 27, cy - 31, cx - 21, cy - 25], fill=(*PALETTE[4], 255))
            draw.ellipse([cx + 21, cy - 31, cx + 27, cy - 25], fill=(*PALETTE[4], 255))

        # Frame 2: Geyser crest & droplet spray
        elif f_idx == 2:
            draw.ellipse([cx - 32, cy - 16, cx + 32, cy + 16], outline=(*PALETTE[2], 180), width=2)
            draw.polygon([(cx - 6, cy), (cx, cy - 26), (cx + 6, cy)], fill=(*PALETTE[2], 200))
            # Droplets falling back
            for drop in [(-18, -22), (-28, -14), (18, -22), (28, -14), (0, -32), (-8, -30), (8, -30)]:
                dx_p = int(cx + drop[0])
                dy_p = int(cy + drop[1])
                draw.rectangle([dx_p-1, dy_p-1, dx_p+1, dy_p+1], fill=(*PALETTE[4], 255))

        # Frame 3: Puddle with foam & plinking ripples
        elif f_idx == 3:
            draw.ellipse([cx - 36, cy - 18, cx + 36, cy + 18], fill=(*PALETTE[1], 120), outline=(*PALETTE[3], 200))
            draw.ellipse([cx - 20, cy - 10, cx + 20, cy + 10], outline=(*PALETTE[4], 220), width=1)
            for d in [(-12, -4), (10, 2), (-4, 6), (14, -6)]:
                draw.point((int(cx + d[0]), int(cy + d[1])), fill=(*PALETTE[4], 255))

        # Frame 4: Expanding ripples
        elif f_idx == 4:
            draw.ellipse([cx - 40, cy - 20, cx + 40, cy + 20], outline=(*PALETTE[2], 150), width=1)
            draw.ellipse([cx - 26, cy - 13, cx + 26, cy + 13], outline=(*PALETTE[3], 140), width=1)

        # Frame 5: Fading ripple rings
        elif f_idx == 5:
            draw.ellipse([cx - 44, cy - 22, cx + 44, cy + 22], outline=(*PALETTE[1], 80), width=1)

        frames.append(img)

    save_strip_and_meta("vfx_water_splash", frames, loop=False, fps=12.0)


def generate_steam_burst():
    w, h = 96, 96
    cx, cy = 48.0, 52.0
    n_frames = 6
    PALETTE = [
        hex_to_rgb("#4A4E54"), # Deep vapor gray
        hex_to_rgb("#7E8691"), # Cool vapor mid
        hex_to_rgb("#BAC4D1"), # Light mist
        hex_to_rgb("#E8F0FA"), # Crisp white puff
        hex_to_rgb("#FFFFFF"), # Hot white steam core
    ]
    HOT_EMBERS = [hex_to_rgb("#FF6B00"), hex_to_rgb("#FFBB33")]

    frames = []
    for f_idx in range(n_frames):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Frame 0: Violent contact flash
        if f_idx == 0:
            draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(*HOT_EMBERS[1], 255))
            draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(*PALETTE[4], 255))
            # Rapid puff rim
            draw.ellipse([cx - 18, cy - 18, cx + 18, cy + 18], outline=(*PALETTE[3], 200), width=2)

        # Frame 1: Expanding dense steam cloud
        elif f_idx == 1:
            draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(*PALETTE[3], 240), outline=(*PALETTE[4], 255))
            draw.ellipse([cx - 14, cy - 18, cx + 14, cy + 10], fill=(*PALETTE[4], 255))
            # Outer steam lobes
            for ang in (0.3, 1.2, 2.1, 3.2, 4.3, 5.4):
                lx = cx + math.cos(ang) * 22.0
                ly = cy + math.sin(ang) * 22.0
                draw.ellipse([lx - 10, ly - 10, lx + 10, ly + 10], fill=(*PALETTE[2], 190), outline=(*PALETTE[3], 240))

        # Frame 2: Peak volumetric puffiness
        elif f_idx == 2:
            # Overlapping translucent spheres
            LOBES = [
                (0, -6, 26), (-18, -10, 20), (18, -10, 20),
                (-24, 8, 18), (24, 8, 18), (0, 14, 20)
            ]
            for lx_off, ly_off, r in LOBES:
                lx, ly = cx + lx_off, cy + ly_off - 4.0
                draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=(*PALETTE[2], 160), outline=(*PALETTE[3], 220))
            draw.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=(*PALETTE[4], 230))

        # Frame 3: Steam lifts and thins
        elif f_idx == 3:
            LOBES = [
                (0, -16, 28), (-20, -18, 22), (20, -18, 22),
                (-16, 4, 18), (16, 4, 18)
            ]
            for lx_off, ly_off, r in LOBES:
                lx, ly = cx + lx_off, cy + ly_off - 8.0
                draw.ellipse([lx - r, ly - r, lx + r, ly + r], fill=(*PALETTE[1], 110), outline=(*PALETTE[2], 160))

        # Frame 4: Wispy tendrils
        elif f_idx == 4:
            for s in range(12):
                sx = int(cx + (s * 11) % 50 - 25)
                sy = int(cy - 20 - (s * 7) % 24)
                sr = 8 + (s % 6)
                draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(*PALETTE[1], 60))

        # Frame 5: Dissipating into air
        elif f_idx == 5:
            for s in range(8):
                sx = int(cx + (s * 13) % 40 - 20)
                sy = int(cy - 30 - (s * 5) % 18)
                sr = 5 + (s % 4)
                draw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(*PALETTE[1], 25))

        frames.append(img)

    save_strip_and_meta("vfx_steam_burst", frames, loop=False, fps=12.0)


# ============================================================================
# 6. MAGIC PROJECTILES: GREEN, YELLOW, PURPLE
# ============================================================================

def generate_magic_orbs():
    ORBS = {
        "vfx_magic_orb_green": {
            "name": "Green Nature/Poison Bolt",
            "colors": [hex_to_rgb(c) for c in ["#022B10", "#086E30", "#10D060", "#80FFB4", "#FFFFFF"]]
        },
        "vfx_magic_orb_yellow": {
            "name": "Yellow Holy/Lightning Spark",
            "colors": [hex_to_rgb(c) for c in ["#4A2800", "#D48002", "#FFC714", "#FFF38A", "#FFFFFF"]]
        },
        "vfx_magic_orb_purple": {
            "name": "Purple Shadow/Arcane Missile",
            "colors": [hex_to_rgb(c) for c in ["#20023B", "#580B94", "#A425F0", "#E499FF", "#FFFFFF"]]
        }
    }

    w, h = 48, 48
    cx, cy = 26.0, 24.0 # projectile moving left -> right, head at cx
    n_frames = 4

    for prefix, pinfo in ORBS.items():
        pal = pinfo["colors"]
        frames = []

        for f_idx in range(n_frames):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            phase = f_idx * (math.pi * 0.5) # 90 deg rotation per frame

            # 1. Wavy trail streaming to the left
            for x in range(2, int(cx)):
                u = x / float(cx) # 0 at tail, 1 at core
                trail_w = int(2 + u * 6)
                wave_y = int(cy + math.sin(x * 0.4 - f_idx * 1.5) * (2.0 + 3.0 * (1.0 - u)))
                c = pal[2] if u > 0.6 else pal[1]
                draw.line([(x, wave_y - trail_w // 2), (x, wave_y + trail_w // 2)], fill=(*c, int(180 * u)), width=1)

            # 2. Outer aura
            draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(*pal[1], 100), outline=(*pal[2], 180))

            # 3. Main Orb Body
            draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(*pal[2], 230), outline=(*pal[3], 255))
            draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(*pal[3], 255))
            draw.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill=(*pal[4], 255))

            # 4. Two orbiting satellites (at phase and phase + pi)
            for sat_i in (0, 1):
                ang = phase + sat_i * math.pi
                sat_x = int(cx + math.cos(ang) * 14.0)
                sat_y = int(cy + math.sin(ang) * 11.0)
                if 0 <= sat_x < w and 0 <= sat_y < h:
                    draw.rectangle([sat_x - 1, sat_y - 1, sat_x + 1, sat_y + 1], fill=(*pal[3], 240))
                    draw.point((sat_x, sat_y), fill=(*pal[4], 255))

            frames.append(img)

        save_strip_and_meta(prefix, frames, loop=True, fps=10.0)


# ============================================================================
# 7. COMBAT FEEDBACK & FLOATING NUMBERS
# ============================================================================

def generate_hit_feedback():
    # A) vfx_hit_spark_strip4
    w, h = 48, 48
    cx, cy = 24.0, 24.0
    PAL_SPARK = [
        hex_to_rgb("#7A2200"),
        hex_to_rgb("#E66A00"),
        hex_to_rgb("#FFB300"),
        hex_to_rgb("#FFF08A"),
        hex_to_rgb("#FFFFFF"),
    ]

    frames_spark = []
    for f_idx in range(4):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if f_idx == 0:
            draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(*PAL_SPARK[4], 255))
        elif f_idx == 1:
            # Massive 4-point cross star flash
            draw.line([(cx - 18, cy), (cx + 18, cy)], fill=(*PAL_SPARK[4], 255), width=3)
            draw.line([(cx, cy - 18), (cx, cy + 18)], fill=(*PAL_SPARK[4], 255), width=3)
            draw.line([(cx - 10, cy - 10), (cx + 10, cy + 10)], fill=(*PAL_SPARK[3], 255), width=2)
            draw.line([(cx - 10, cy + 10), (cx + 10, cy - 10)], fill=(*PAL_SPARK[3], 255), width=2)
            draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(*PAL_SPARK[4], 255))
        elif f_idx == 2:
            # Sparks fly outward
            for ang_deg in range(0, 360, 45):
                rad = math.radians(ang_deg)
                sx = int(cx + math.cos(rad) * 16.0)
                sy = int(cy + math.sin(rad) * 16.0)
                draw.rectangle([sx - 1, sy - 1, sx + 1, sy + 1], fill=(*PAL_SPARK[3], 240))
                draw.point((sx, sy), fill=(*PAL_SPARK[4], 255))
        elif f_idx == 3:
            for ang_deg in range(0, 360, 45):
                rad = math.radians(ang_deg)
                sx = int(cx + math.cos(rad) * 22.0)
                sy = int(cy + math.sin(rad) * 22.0)
                draw.point((sx, sy), fill=(*PAL_SPARK[1], 160))

        frames_spark.append(img)

    save_strip_and_meta("vfx_hit_spark", frames_spark, loop=False, fps=14.0)

    # B) vfx_impact_burst_strip4
    w, h = 64, 64
    cx, cy = 32.0, 32.0
    frames_impact = []
    for f_idx in range(4):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if f_idx == 0:
            draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(255, 255, 255, 255))
        elif f_idx == 1:
            draw.ellipse([cx - 20, cy - 20, cx + 20, cy + 20], outline=(255, 230, 100, 255), width=3)
            draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=(255, 255, 255, 255))
            for a in range(0, 360, 60):
                rad = math.radians(a)
                draw.line([(cx + math.cos(rad)*14, cy + math.sin(rad)*14),
                           (cx + math.cos(rad)*24, cy + math.sin(rad)*24)], fill=(255, 180, 50, 255), width=2)
        elif f_idx == 2:
            draw.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], outline=(255, 140, 30, 200), width=2)
            for a in range(0, 360, 60):
                rad = math.radians(a)
                sx = int(cx + math.cos(rad) * 28)
                sy = int(cy + math.sin(rad) * 28)
                draw.rectangle([sx-1, sy-1, sx+1, sy+1], fill=(255, 200, 80, 220))
        elif f_idx == 3:
            for a in range(0, 360, 60):
                rad = math.radians(a)
                sx = int(cx + math.cos(rad) * 31)
                sy = int(cy + math.sin(rad) * 31)
                draw.point((sx, sy), fill=(200, 80, 20, 120))

        frames_impact.append(img)

    save_strip_and_meta("vfx_impact_burst", frames_impact, loop=False, fps=12.0)

    # C) vfx_crit_burst_strip6
    w, h = 80, 80
    cx, cy = 40.0, 40.0
    frames_crit = []
    for f_idx in range(6):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        fade = 1.0 - (f_idx / 5.5)

        if f_idx == 0:
            draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 255, 255, 255))
            draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], outline=(255, 215, 0, 255), width=2)
        elif f_idx == 1:
            # 8-point massive starburst
            for a in range(0, 360, 45):
                rad = math.radians(a)
                draw.line([(cx, cy), (cx + math.cos(rad)*30, cy + math.sin(rad)*30)], fill=(255, 255, 255, 255), width=2)
                draw.line([(cx, cy), (cx + math.cos(rad)*24, cy + math.sin(rad)*24)], fill=(255, 80, 20, 255), width=4)
            draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], fill=(255, 255, 255, 255))
        elif f_idx in (2, 3):
            # Flying crit diamonds
            r_crit = 20.0 + f_idx * 12.0
            for a in range(0, 360, 45):
                rad = math.radians(a)
                sx = cx + math.cos(rad) * r_crit
                sy = cy + math.sin(rad) * r_crit
                draw.polygon([(sx, sy - 4), (sx + 3, sy), (sx, sy + 4), (sx - 3, sy)], fill=(255, 220, 50, int(255 * fade)), outline=(255, 255, 255, int(255 * fade)))
            draw.ellipse([cx - r_crit * 0.8, cy - r_crit * 0.8, cx + r_crit * 0.8, cy + r_crit * 0.8], outline=(255, 60, 20, int(180 * fade)), width=2)
        elif f_idx >= 4:
            r_crit = 36.0 + (f_idx - 4) * 4.0
            for a in range(0, 360, 45):
                rad = math.radians(a)
                sx = int(cx + math.cos(rad) * r_crit)
                sy = int(cy + math.sin(rad) * r_crit)
                draw.point((sx, sy), fill=(255, 215, 0, int(160 * fade)))

        frames_crit.append(img)

    save_strip_and_meta("vfx_crit_burst", frames_crit, loop=False, fps=12.0)


# ============================================================================
# 8. DAMAGE NUMBERS SPRITESHEET (Matching Screenshot!)
# ============================================================================

def generate_damage_numbers_sheet():
    """
    Renders retro bold pixel font numbers with dark outlines:
    - Digits: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, '-', '+'
    - Banner: 'CRIT!' badge
    - Sample composites matching screenshot: '-152', '-88', '-324'
    """
    sheet_w, sheet_h = 256, 128
    img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 5x7 Retro Pixel Font Bitmaps (standard height 7, width 4 or 5)
    FONT_MAP = {
        '0': [
            "1111",
            "1001",
            "1001",
            "1001",
            "1001",
            "1001",
            "1111"
        ],
        '1': [
            "0110",
            "1110",
            "0110",
            "0110",
            "0110",
            "0110",
            "1111"
        ],
        '2': [
            "1111",
            "0001",
            "0001",
            "1111",
            "1000",
            "1000",
            "1111"
        ],
        '3': [
            "1111",
            "0001",
            "0001",
            "1111",
            "0001",
            "0001",
            "1111"
        ],
        '4': [
            "1001",
            "1001",
            "1001",
            "1111",
            "0001",
            "0001",
            "0001"
        ],
        '5': [
            "1111",
            "1000",
            "1000",
            "1111",
            "0001",
            "0001",
            "1111"
        ],
        '6': [
            "1111",
            "1000",
            "1000",
            "1111",
            "1001",
            "1001",
            "1111"
        ],
        '7': [
            "1111",
            "0001",
            "0010",
            "0010",
            "0100",
            "0100",
            "0100"
        ],
        '8': [
            "1111",
            "1001",
            "1001",
            "1111",
            "1001",
            "1001",
            "1111"
        ],
        '9': [
            "1111",
            "1001",
            "1001",
            "1111",
            "0001",
            "0001",
            "1111"
        ],
        '-': [
            "0000",
            "0000",
            "0000",
            "1111",
            "0000",
            "0000",
            "0000"
        ],
        '+': [
            "0000",
            "0110",
            "0110",
            "1111",
            "0110",
            "0110",
            "0000"
        ],
        '!': [
            "0110",
            "0110",
            "0110",
            "0110",
            "0000",
            "0110",
            "0110"
        ]
    }

    def render_pixel_char(char: str, scale: int = 2, col_face=(255, 175, 20), col_grad=(230, 40, 20), col_outline=(0, 0, 0)) -> Image.Image:
        bitmap = FONT_MAP.get(char, FONT_MAP['-'])
        bh = len(bitmap)
        bw = len(bitmap[0])
        pw = (bw * scale) + 4
        ph = (bh * scale) + 4
        char_img = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))

        # 1. First pass: Outline (1px border around every active pixel)
        for y, row in enumerate(bitmap):
            for x, bit in enumerate(row):
                if bit == '1':
                    px_start = 2 + x * scale
                    py_start = 2 + y * scale
                    for oy in range(-1, scale + 1):
                        for ox in range(-1, scale + 1):
                            char_img.putpixel((px_start + ox, py_start + oy), (*col_outline, 255))

        # 2. Second pass: Face with vertical gradient (bright gold at top -> fiery red at bottom)
        for y, row in enumerate(bitmap):
            t = y / float(bh - 1)
            face_r = int(col_face[0] * (1.0 - t) + col_grad[0] * t)
            face_g = int(col_face[1] * (1.0 - t) + col_grad[1] * t)
            face_b = int(col_face[2] * (1.0 - t) + col_grad[2] * t)
            for x, bit in enumerate(row):
                if bit == '1':
                    px_start = 2 + x * scale
                    py_start = 2 + y * scale
                    for sy in range(scale):
                        for sx in range(scale):
                            char_img.putpixel((px_start + sx, py_start + sy), (face_r, face_g, face_b, 255))

        return char_img

    # 1. Place individual digits 0-9, '-', '+' along top row (Y = 8)
    chars = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-', '+']
    char_x = 8
    for ch in chars:
        ci = render_pixel_char(ch, scale=2)
        img.paste(ci, (char_x, 8), ci)
        char_x += ci.width + 4

    # 2. Render 'CRIT!' banner at (X=8, Y=36)
    banner_w, banner_h = 76, 22
    # Angled dynamic banner badge
    draw.polygon([(8, 38), (82, 36), (80, 56), (6, 58)], fill=(120, 10, 10, 255), outline=(255, 215, 0, 255))
    draw.polygon([(10, 40), (80, 38), (78, 54), (8, 56)], fill=(200, 25, 20, 255), outline=(255, 140, 0, 255))

    crit_str = "CRIT!"
    cx_offset = 14
    for ch in crit_str:
        ci = render_pixel_char(ch, scale=1, col_face=(255, 240, 80), col_grad=(255, 180, 20), col_outline=(40, 0, 0))
        img.paste(ci, (cx_offset, 40), ci)
        cx_offset += ci.width + 1

    # 3. Composite sample numbers matching screenshot exactly! (-152, -88, -324)
    # Row 3 (Y = 72):
    # -152 (Fiery orange-red bold damage number)
    def render_number_string(num_str: str, scale: int = 2) -> Image.Image:
        glyphs = [render_pixel_char(c, scale=scale) for c in num_str]
        total_w = sum(g.width - 2 for g in glyphs) + 2
        total_h = glyphs[0].height
        res = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        gx = 0
        for g in glyphs:
            res.paste(g, (gx, 0), g)
            gx += g.width - 2
        return res

    dmg1 = render_number_string("-152", scale=2)
    img.paste(dmg1, (8, 76), dmg1)

    dmg2 = render_number_string("-88", scale=2)
    img.paste(dmg2, (80, 76), dmg2)

    dmg3 = render_number_string("-324", scale=2)
    img.paste(dmg3, (140, 76), dmg3)

    # Critical hit version of -480 with golden sheen
    def render_crit_number(num_str: str) -> Image.Image:
        glyphs = [render_pixel_char(c, scale=2, col_face=(255, 255, 200), col_grad=(255, 120, 0), col_outline=(80, 0, 0)) for c in num_str]
        total_w = sum(g.width - 2 for g in glyphs) + 2
        total_h = glyphs[0].height
        res = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
        gx = 0
        for g in glyphs:
            res.paste(g, (gx, 0), g)
            gx += g.width - 2
        return res

    dmg_crit = render_crit_number("-480")
    img.paste(dmg_crit, (8, 102), dmg_crit)

    # Save texture and Godot 4 .import
    save_single_texture_and_meta("vfx_damage_numbers_sheet", img)


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================

def main():
    print("====================================================================")
    print("  AESTRA: THE LAST WISH — COMBAT VFX & FLOATING FEEDBACK FORGE")
    print("====================================================================")
    print(f"Target directory: {TARGET_VFX_DIR}")

    # 1. Crescent Sword Slashes
    generate_sword_slash_set()

    # 2. Fire Skills & Rings
    generate_fire_ring()
    generate_fire_tornado()
    generate_flame_burst()

    # 3. Radius AOE & Blade Storm
    generate_radius_shockwave()
    generate_blade_storm()

    # 4. Archer Skills
    generate_arrow_rain()
    generate_piercing_arrow_beam()
    generate_storm_volley_cone()

    # 5. Water & Frost Elemental Reactions
    generate_frost_shatter()
    generate_water_splash()
    generate_steam_burst()

    # 6. Magic Projectiles
    generate_magic_orbs()

    # 7. Combat Feedback & Numbers
    generate_hit_feedback()
    generate_damage_numbers_sheet()

    print("\n[SUCCESS] All 20 VFX animation strips, 1 damage sheet, .import files,")
    print("          and Godot 4 SpriteFrames (.tres) resources created!")

if __name__ == "__main__":
    main()
