#!/usr/bin/env python3
"""
Character Sprite Specialist Pipeline for 'Aestra: The Last Wish'
Generates all 24 horizontal animation strips (_stripN.png), 24 dynamic 2D normal maps (_n.png),
6 Godot 4 SpriteFrames (.tres) resources, and 48 .import files.
"""

import math
import os
from pathlib import Path
import numpy as np
from PIL import Image

try:
    from scipy.ndimage import distance_transform_edt
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

WORKSPACE = Path(__file__).resolve().parent.parent
LPC_ROOT = WORKSPACE / "libraries" / "com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator" / "spritesheets"
TARGET_DIR = WORKSPACE / "projects" / "nos" / "assets" / "characters"
NORMALS_DIR = TARGET_DIR / "normals"

TARGET_DIR.mkdir(parents=True, exist_ok=True)
NORMALS_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------------------
# PALETTE DEFINITIONS & RECOLOR HELPERS
# -------------------------------------------------------------------------

def recolor_image(img: Image.Image, color_map: dict) -> Image.Image:
    """Replaces exact RGBA colors based on color_map: (r, g, b) -> (nr, ng, nb)."""
    if not color_map:
        return img
    arr = np.array(img.convert("RGBA"))
    for src, dst in color_map.items():
        match = (arr[:, :, 0] == src[0]) & (arr[:, :, 1] == src[1]) & (arr[:, :, 2] == src[2]) & (arr[:, :, 3] > 0)
        arr[match, 0] = dst[0]
        arr[match, 1] = dst[1]
        arr[match, 2] = dst[2]
    return Image.fromarray(arr)

def tint_hue_saturation(img: Image.Image, hue_shift: float, sat_mult: float, val_mult: float) -> Image.Image:
    """Tints an RGBA image in HSV space."""
    im = img.convert("RGBA")
    arr = np.array(im, dtype=np.float32)
    alpha = arr[:, :, 3].copy()
    mask = alpha > 0
    if not np.any(mask):
        return im
    
    r, g, b = arr[:, :, 0] / 255.0, arr[:, :, 1] / 255.0, arr[:, :, 2] / 255.0
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin
    
    h = np.zeros_like(r)
    # delta > 0 mask
    dmask = (delta > 1e-5) & mask
    mr = dmask & (cmax == r)
    mg = dmask & (cmax == g)
    mb = dmask & (cmax == b)
    h[mr] = ((g[mr] - b[mr]) / delta[mr]) % 6
    h[mg] = ((b[mg] - r[mg]) / delta[mg]) + 2
    h[mb] = ((r[mb] - g[mb]) / delta[mb]) + 4
    h = h / 6.0
    
    s = np.zeros_like(r)
    s[mask & (cmax > 0)] = delta[mask & (cmax > 0)] / cmax[mask & (cmax > 0)]
    v = cmax
    
    h = (h + hue_shift) % 1.0
    s = np.clip(s * sat_mult, 0.0, 1.0)
    v = np.clip(v * val_mult, 0.0, 1.0)
    
    # HSV to RGB
    i = (h * 6.0).astype(int)
    f = (h * 6.0) - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    
    rgb = np.zeros_like(arr[:, :, :3])
    idx = i % 6
    rgb[idx == 0] = np.stack([v[idx == 0], t[idx == 0], p[idx == 0]], axis=-1)
    rgb[idx == 1] = np.stack([q[idx == 1], v[idx == 1], p[idx == 1]], axis=-1)
    rgb[idx == 2] = np.stack([p[idx == 2], v[idx == 2], t[idx == 2]], axis=-1)
    rgb[idx == 3] = np.stack([p[idx == 3], q[idx == 3], v[idx == 3]], axis=-1)
    rgb[idx == 4] = np.stack([t[idx == 4], p[idx == 4], v[idx == 4]], axis=-1)
    rgb[idx == 5] = np.stack([v[idx == 5], p[idx == 5], q[idx == 5]], axis=-1)
    
    out = np.zeros_like(arr, dtype=np.uint8)
    out[:, :, :3] = (rgb * 255.0).astype(np.uint8)
    out[:, :, 3] = alpha.astype(np.uint8)
    return Image.fromarray(out)

# 1. WARRIOR BASE (Steel Blue Plate & Dark Navy Cape)
PLATE_STEEL_BLUE = {
    (0x1d, 0x13, 0x1e): (0x1a, 0x24, 0x3b),
    (0x4d, 0x4a, 0x5d): (0x26, 0x3b, 0x5f),
    (0x72, 0x6b, 0x7e): (0x3b, 0x58, 0x8a),
    (0x86, 0x7e, 0x7f): (0x5a, 0x7b, 0xb5),
    (0xc4, 0xb5, 0x9f): (0x88, 0xa7, 0xdb),
    (0xff, 0xff, 0xff): (0xd0, 0xe1, 0xf9),
}

CAPE_DARK_NAVY = {
    (0x28, 0x18, 0x20): (0x10, 0x15, 0x24),
    (0x4d, 0x4a, 0x5d): (0x1b, 0x29, 0x44),
    (0x95, 0x80, 0x80): (0x26, 0x3e, 0x68),
    (0xc4, 0xb5, 0x9f): (0x3b, 0x5e, 0x9e),
}

# 2. ARCHER BASE (Forest Green & Tanned Leather)
ARCHER_LEATHERS = {
    (0x2b, 0x1c, 0x14): (0x24, 0x3e, 0x26),
    (0x42, 0x2c, 0x1e): (0x34, 0x58, 0x31),
    (0x61, 0x41, 0x2b): (0x4d, 0x7c, 0x3b),
    (0x85, 0x5b, 0x3d): (0x73, 0xa8, 0x46),
    (0xad, 0x7d, 0x53): (0x98, 0xc8, 0x5e),
}

# 3. KOR MUHAFIZI (Warrior + Fire: Obsidian Plate, Molten Magma Seams & Burning Crimson Cape)
PLATE_OBSIDIAN_FIRE = {
    (0x1d, 0x13, 0x1e): (0x18, 0x10, 0x15),
    (0x4d, 0x4a, 0x5d): (0x2f, 0x1c, 0x22),
    (0x72, 0x6b, 0x7e): (0x4a, 0x23, 0x24),
    (0x86, 0x7e, 0x7f): (0xb8, 0x3b, 0x12),
    (0xc4, 0xb5, 0x9f): (0xe6, 0x68, 0x19),
    (0xff, 0xff, 0xff): (0xff, 0xf2, 0x75),
}

CAPE_BURNING_CRIMSON = {
    (0x28, 0x18, 0x20): (0x24, 0x07, 0x07),
    (0x4d, 0x4a, 0x5d): (0x4f, 0x0f, 0x0c),
    (0x95, 0x80, 0x80): (0x9c, 0x1b, 0x12),
    (0xc4, 0xb5, 0x9f): (0xe6, 0x4a, 0x19),
}

SWORD_FIRE = {
    (0x7f, 0x7f, 0x7f): (0xb8, 0x3b, 0x12),
    (0xa5, 0xa5, 0xa5): (0xe6, 0x68, 0x19),
    (0xcc, 0xcc, 0xcc): (0xfa, 0xb1, 0x2c),
    (0xff, 0xff, 0xff): (0xff, 0xf2, 0x75),
}

# 4. AYAZ SOVALYESI (Warrior + Frost: Crystalline Frost Cyan Plate & Mist Cloak)
PLATE_FROST_CYAN = {
    (0x1d, 0x13, 0x1e): (0x08, 0x19, 0x26),
    (0x4d, 0x4a, 0x5d): (0x0d, 0x3f, 0x4d),
    (0x72, 0x6b, 0x7e): (0x13, 0x67, 0x75),
    (0x86, 0x7e, 0x7f): (0x1a, 0x9b, 0xa8),
    (0xc4, 0xb5, 0x9f): (0x2d, 0xd4, 0xdb),
    (0xff, 0xff, 0xff): (0xc2, 0xff, 0xfd),
}

CAPE_FROST_MIST = {
    (0x28, 0x18, 0x20): (0x0e, 0x22, 0x30),
    (0x4d, 0x4a, 0x5d): (0x1b, 0x45, 0x5c),
    (0x95, 0x80, 0x80): (0x31, 0x75, 0x94),
    (0xc4, 0xb5, 0x9f): (0x68, 0xb2, 0xce),
}

SWORD_FROST = {
    (0x7f, 0x7f, 0x7f): (0x13, 0x67, 0x75),
    (0xa5, 0xa5, 0xa5): (0x1a, 0x9b, 0xa8),
    (0xcc, 0xcc, 0xcc): (0x2d, 0xd4, 0xdb),
    (0xff, 0xff, 0xff): (0xc2, 0xff, 0xfd),
}

# 5. KUL GOZU (Archer + Fire: Ash Charcoal Leathers & Fiery Bow)
ARCHER_ASH_CHARCOAL = {
    (0x2b, 0x1c, 0x14): (0x1b, 0x1c, 0x20),
    (0x42, 0x2c, 0x1e): (0x2d, 0x2e, 0x38),
    (0x61, 0x41, 0x2b): (0x47, 0x49, 0x59),
    (0x85, 0x5b, 0x3d): (0xb8, 0x3b, 0x12),
    (0xad, 0x7d, 0x53): (0xe6, 0x68, 0x19),
}

# 6. TUFAN OKCUSU (Archer + Water/Storm: Abyssal Ocean Navy & Seafoam Hydro Bow)
ARCHER_STORM_NAVY = {
    (0x2b, 0x1c, 0x14): (0x10, 0x22, 0x36),
    (0x42, 0x2c, 0x1e): (0x18, 0x35, 0x52),
    (0x61, 0x41, 0x2b): (0x26, 0x50, 0x7a),
    (0x85, 0x5b, 0x3d): (0x1a, 0x9b, 0xa8),
    (0xad, 0x7d, 0x53): (0x7a, 0xf5, 0xf0),
}

# -------------------------------------------------------------------------
# LAYER LOADING & COMPOSITING FUNCTIONS
# -------------------------------------------------------------------------

def get_layer_img(rel_path: str, color_map: dict = None) -> Image.Image:
    """Loads a PNG layer relative to LPC_ROOT and applies optional color_map."""
    p = LPC_ROOT / rel_path
    if not p.exists():
        return None
    im = Image.open(p).convert("RGBA")
    if color_map:
        im = recolor_image(im, color_map)
    return im

def build_character_animation(layers_spec: list, row: int, frame_indices: list, cell_size: int = 64) -> Image.Image:
    """
    Composites a list of (layer_path, color_map, z_offset_func) tuples
    across given frame_indices for a specific row direction (2 = down).
    Returns a horizontal Image of size (len(frame_indices) * 64, 64).
    """
    strip = Image.new("RGBA", (len(frame_indices) * cell_size, cell_size), (0, 0, 0, 0))
    
    # Preload layer images
    loaded_layers = []
    for spec in layers_spec:
        rel_path, cmap, extra = spec
        p = LPC_ROOT / rel_path
        if p.exists():
            im = Image.open(p).convert("RGBA")
            if cmap:
                im = recolor_image(im, cmap)
            loaded_layers.append((im, extra))
    
    y_start = row * cell_size
    for out_idx, frame_col in enumerate(frame_indices):
        cell_comp = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
        for im, extra in loaded_layers:
            # Handle standard 64x64 grids vs special grids
            if im.width >= (frame_col + 1) * cell_size and im.height >= y_start + cell_size:
                frame_img = im.crop((frame_col * cell_size, y_start, (frame_col + 1) * cell_size, y_start + cell_size))
                # Optional vertical bobbing for breathing in idle
                if extra and "bob_y" in extra and frame_col in extra["bob_y"]:
                    dy = extra["bob_y"][frame_col]
                    temp = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
                    temp.paste(frame_img, (0, dy))
                    frame_img = temp
                cell_comp.alpha_composite(frame_img)
            elif im.height == cell_size: # 1-row animation like hurt
                if im.width >= (frame_col + 1) * cell_size:
                    frame_img = im.crop((frame_col * cell_size, 0, (frame_col + 1) * cell_size, cell_size))
                    cell_comp.alpha_composite(frame_img)
        
        strip.paste(cell_comp, (out_idx * cell_size, 0))
        
    return strip

# -------------------------------------------------------------------------
# NORMAL MAP GENERATION (Distance Transform Pillow + Sobel Filter)
# -------------------------------------------------------------------------

def generate_tangent_normal_map(img: Image.Image, strength: float = 1.6, pillow_weight: float = 0.65) -> Image.Image:
    """
    Generates a dynamic 2D tangent normal map using Euclidean distance transform
    (convex pillow volume) blended with surface luminance relief and Sobel filtering.
    Format: RGB unit vectors where R=X, G=Y, B=Z with alpha preserved.
    """
    arr = np.array(img.convert("RGBA"), dtype=np.float32)
    h, w, _ = arr.shape
    alpha = arr[:, :, 3]
    mask = alpha > 10.0
    
    if not np.any(mask):
        # Empty transparent normal map (flat default normal: 128, 128, 255)
        out = np.zeros((h, w, 4), dtype=np.uint8)
        out[:, :, 0] = 128
        out[:, :, 1] = 128
        out[:, :, 2] = 255
        return Image.fromarray(out)
        
    # 1. Luminance relief
    lum = (arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722) / 255.0
    
    # 2. Distance field (pillow convex shading)
    if HAS_SCIPY:
        dist = distance_transform_edt(mask)
    else:
        # Fallback simple Manhattan distance
        dist = np.zeros((h, w), dtype=np.float32)
        dist[mask] = 1.0
        for _ in range(8):
            for y in range(h):
                for x in range(w):
                    if mask[y, x]:
                        nbs = []
                        if x > 0 and mask[y, x-1]: nbs.append(dist[y, x-1])
                        if x < w-1 and mask[y, x+1]: nbs.append(dist[y, x+1])
                        if y > 0 and mask[y-1, x]: nbs.append(dist[y-1, x])
                        if y < h-1 and mask[y+1, x]: nbs.append(dist[y+1, x])
                        if nbs:
                            dist[y, x] = min(dist[y, x], min(nbs) + 1.0)
                            
    # Normalize pillow height
    max_d = np.max(dist) or 1.0
    norm_dist = np.sqrt(np.clip(dist / max_d, 0.0, 1.0))
    
    # Blended elevation surface
    height = pillow_weight * norm_dist + (1.0 - pillow_weight) * lum
    height *= mask
    
    # Sobel Gradients
    dx = np.zeros((h, w), dtype=np.float32)
    dy = np.zeros((h, w), dtype=np.float32)
    
    # Sobel kernels
    # dx: [-1 0 1; -2 0 2; -1 0 1]
    # dy: [-1 -2 -1; 0 0 0; 1 2 1]
    padded = np.pad(height, 1, mode="edge")
    dx = (
        (padded[0:-2, 2:] + 2.0 * padded[1:-1, 2:] + padded[2:, 2:]) -
        (padded[0:-2, 0:-2] + 2.0 * padded[1:-1, 0:-2] + padded[2:, 0:-2])
    ) * (strength / 8.0)
    
    dy = (
        (padded[2:, 0:-2] + 2.0 * padded[2:, 1:-1] + padded[2:, 2:]) -
        (padded[0:-2, 0:-2] + 2.0 * padded[0:-2, 1:-1] + padded[0:-2, 2:])
    ) * (strength / 8.0)
    
    # Normal vector normalization
    nx = -dx
    ny = dy  # OpenGL / Godot convention
    nz = np.ones((h, w), dtype=np.float32)
    
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    length[length == 0] = 1.0
    nx /= length
    ny /= length
    nz /= length
    
    # Pack to [0, 255]
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[:, :, 0] = np.clip((nx * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    out[:, :, 1] = np.clip((ny * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    out[:, :, 2] = np.clip((nz * 0.5 + 0.5) * 255.0, 0, 255).astype(np.uint8)
    out[:, :, 3] = alpha.astype(np.uint8)
    
    return Image.fromarray(out)

# -------------------------------------------------------------------------
# AURA GENERATOR (6 Frames, 384x64 px)
# -------------------------------------------------------------------------

def generate_aura_strip(aura_type: str) -> Image.Image:
    """
    Renders a 6-frame procedural pixel-art aura horizontal strip (384x64 px).
    Types: 'kor_muhafizi' (fire embers), 'ayaz_sovalyesi' (frost crystals),
           'kul_gozu' (ash & sparks), 'tufan_okcusu' (water ripples & droplets).
    """
    strip = Image.new("RGBA", (6 * 64, 64), (0, 0, 0, 0))
    
    for f in range(6):
        frame = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        arr = np.array(frame, dtype=np.uint8)
        
        # Center of character feet: (32, 56)
        cx, cy = 32, 56
        t = f / 6.0
        
        if aura_type == "kor_muhafizi":
            # Smouldering ember aura: expanding heat ground ring + rising flame cinders
            # 1. Elliptical ground flame ring
            r_x = 14 + int(2 * math.sin(t * 2 * math.pi))
            r_y = 6 + int(1 * math.sin(t * 2 * math.pi))
            for deg in range(0, 360, 10):
                rad = math.radians(deg)
                px = int(cx + r_x * math.cos(rad))
                py = int(cy + r_y * math.sin(rad))
                if 0 <= px < 64 and 0 <= py < 64:
                    col = (255, 242, 117, 220) if deg % 30 == 0 else (230, 104, 25, 180)
                    arr[py, px] = col
                    if py > 0: arr[py - 1, px] = (184, 59, 18, 140)
            # 2. Rising glowing embers
            np.random.seed(42 + f)
            for _ in range(12):
                ex = cx + np.random.randint(-18, 19)
                ey = cy - np.random.randint(6, 48) - int(t * 8)
                if 0 <= ex < 64 and 0 <= ey < 64:
                    arr[ey, ex] = (255, 242, 117, 240)
                    if ey > 0: arr[ey - 1, ex] = (250, 177, 44, 180)
                    if ex > 0: arr[ey, ex - 1] = (230, 104, 25, 120)

        elif aura_type == "ayaz_sovalyesi":
            # Frosty crystal footstep aura: creeping frost ferns & drifting snowflake glints
            # 1. Ground frost crystalline snowflake ring
            r_x = 15 + int(1.5 * math.cos(t * 2 * math.pi))
            r_y = 7
            for deg in range(0, 360, 15):
                rad = math.radians(deg + t * 60)
                px = int(cx + r_x * math.cos(rad))
                py = int(cy + r_y * math.sin(rad))
                if 0 <= px < 64 and 0 <= py < 64:
                    arr[py, px] = (194, 255, 253, 230)
                    if px > 0 and deg % 45 == 0:
                        arr[py, px - 1] = (45, 212, 219, 180)
                        arr[py, px + 1] = (26, 155, 168, 160)
            # 2. Orbiting snowflake motes
            for i in range(8):
                angle = (i / 8.0) * 2 * math.pi + (t * 2 * math.pi)
                dist_orbit = 16 + int(3 * math.sin(t * 4 * math.pi + i))
                sx = int(cx + dist_orbit * math.cos(angle))
                sy = int((cy - 22) + (dist_orbit * 0.6) * math.sin(angle))
                if 0 <= sx < 64 and 0 <= sy < 64:
                    arr[sy, sx] = (255, 255, 255, 250)
                    if sy > 0: arr[sy - 1, sx] = (122, 245, 240, 200)
                    if sy < 63: arr[sy + 1, sx] = (45, 212, 219, 160)

        elif aura_type == "kul_gozu":
            # Ash and ember trail: ground scorch particles + spiraling smoke wisps
            r_x = 12
            r_y = 5
            for deg in range(0, 360, 18):
                rad = math.radians(deg)
                px = int(cx + r_x * math.cos(rad))
                py = int(cy + r_y * math.sin(rad))
                if 0 <= px < 64 and 0 <= py < 64:
                    arr[py, px] = (80, 75, 80, 160)
            # Rising ash flecks
            np.random.seed(100 + f)
            for _ in range(10):
                ax = cx + np.random.randint(-14, 15)
                ay = cy - np.random.randint(4, 44)
                if 0 <= ax < 64 and 0 <= ay < 64:
                    arr[ay, ax] = (250, 177, 44, 220)
                    if ay < 63: arr[ay + 1, ax] = (115, 30, 12, 140)

        elif aura_type == "tufan_okcusu":
            # Flowing water/mist aura: expanding concentric ripple rings & droplet spray
            ripple_radius = int(8 + (t * 14)) % 20 + 4
            for deg in range(0, 360, 8):
                rad = math.radians(deg)
                rx = int(cx + ripple_radius * math.cos(rad))
                ry = int(cy + (ripple_radius * 0.42) * math.sin(rad))
                fade = max(0, int(255 * (1.0 - ripple_radius / 24.0)))
                if 0 <= rx < 64 and 0 <= ry < 64:
                    arr[ry, rx] = (45, 212, 219, fade)
            # Water vapor droplet spray
            for i in range(6):
                ang = (i / 6.0) * 2 * math.pi - (t * 2 * math.pi)
                wx = int(cx + 12 * math.cos(ang))
                wy = int((cy - 20) + 16 * math.sin(ang))
                if 0 <= wx < 64 and 0 <= wy < 64:
                    arr[wy, wx] = (194, 255, 253, 230)
                    if wy > 0: arr[wy - 1, wx] = (19, 103, 117, 160)

        frame = Image.fromarray(arr, mode="RGBA")
        strip.paste(frame, (f * 64, 0))
        
    return strip

# -------------------------------------------------------------------------
# GODOT 4 SPRITEFRAMES & IMPORT EXPORTERS
# -------------------------------------------------------------------------

def generate_godot_import_file(png_path: Path):
    """Creates a Godot 4 CompressedTexture2D .import file with Lossless/Nearest."""
    import_path = png_path.with_name(png_path.name + ".import")
    h_name = abs(hash(png_path.name)) & 0xFFFFFFF
    uid = f"uid://{png_path.stem}_{h_name:x}"
    dest = f"res://.godot/imported/{png_path.name}-{h_name:x}.ctex"
    
    # Check if normal map to flag normal_map_invert_y
    is_normal = png_path.stem.endswith("_n")
    
    cfg = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="{uid}"
path="{dest}"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://assets/characters/{png_path.relative_to(TARGET_DIR).as_posix()}"
dest_files=["{dest}"]

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
    import_path.write_text(cfg, encoding="utf-8")
    return import_path

def generate_spriteframes_tres(character_id: str, anims_dict: dict, output_path: Path):
    """
    Writes a 100% Godot 4 compatible SpriteFrames .tres resource using AtlasTexture slices.
    anims_dict: { "anim_name": (strip_filename, frame_count, fps, loop) }
    """
    ext_resources = []
    sub_resources = []
    anim_entries = []
    
    ext_id = 1
    sub_id = 1
    
    for anim_name, (strip_fn, frame_count, fps, loop) in anims_dict.items():
        res_ext_id = f"ExtResource(\"{ext_id}_{anim_name}\")"
        ext_resources.append(
            f'[ext_resource type="Texture2D" path="res://assets/characters/{strip_fn}" id="{ext_id}_{anim_name}"]'
        )
        ext_id += 1
        
        frame_refs = []
        for fc in range(frame_count):
            sub_name = f"AtlasTexture_{anim_name}_{fc}"
            sub_resources.append(f"""[sub_resource type="AtlasTexture" id="{sub_name}"]
atlas = {res_ext_id}
region = Rect2({fc * 64}, 0, 64, 64)
""")
            frame_refs.append(f"""{{
"duration": 1.0,
"texture": SubResource("{sub_name}")
}}""")
            sub_id += 1
            
        frames_joined = ",\n".join(frame_refs)
        anim_entries.append(f"""{{
"frames": [{frames_joined}],
"loop": {"true" if loop else "false"},
"name": &"{anim_name}",
"speed": {fps:.1f}
}}""")
        
    ext_text = "\n".join(ext_resources)
    sub_text = "\n".join(sub_resources)
    anims_text = ",\n".join(anim_entries)
    
    uid_hash = abs(hash(character_id)) & 0xFFFFFFF
    tres_content = f"""[gd_resource type="SpriteFrames" format=3 uid="uid://sf_{character_id}_{uid_hash:x}"]

{ext_text}

{sub_text}

[resource]
animations = [{anims_text}]
"""
    output_path.write_text(tres_content, encoding="utf-8")
    print(f"Generated Godot 4 SpriteFrames: {output_path}")

# -------------------------------------------------------------------------
# MAIN BUILD DISPATCHER
# -------------------------------------------------------------------------

def build_all_characters():
    print("=" * 70)
    print("Starting Aestra Character Sprite Generation...")
    print(f"Target directory: {TARGET_DIR}")
    print("=" * 70)
    
    all_generated_strips = []
    
    # ---------------------------------------------------------------------
    # 1. SAVASCI (WARRIOR BASE)
    # ---------------------------------------------------------------------
    print("\n--- [1/6] Building Savasci (Warrior Base) ---")
    w_idle_spec = [
        ("cape/solid/bg/idle.png", CAPE_DARK_NAVY, None),
        ("body/bodies/male/idle.png", None, None),
        ("head/heads/human/male/idle.png", None, None),
        ("eyes/human/adult/default/idle.png", None, None),
        ("legs/armour/plate/male/idle.png", PLATE_STEEL_BLUE, None),
        ("feet/armour/plate/male/idle.png", PLATE_STEEL_BLUE, None),
        ("torso/armour/plate/male/idle.png", PLATE_STEEL_BLUE, None),
        ("shoulders/pauldrons/male/idle.png", PLATE_STEEL_BLUE, None),
        ("hat/helmet/armet/adult/idle.png", PLATE_STEEL_BLUE, None),
        ("cape/solid/fg/idle.png", CAPE_DARK_NAVY, None),
        ("weapon/sword/longsword/walk/longsword.png", None, None),
    ]
    # 4-frame breathing idle loop: [0, 1, 1, 0]
    w_idle = build_character_animation(w_idle_spec, row=2, frame_indices=[0, 1, 1, 0])
    w_idle_path = TARGET_DIR / "warrior_idle_strip4.png"
    w_idle.save(w_idle_path)
    all_generated_strips.append(w_idle_path)
    
    w_walk_spec = [
        ("cape/solid/bg/walk.png", CAPE_DARK_NAVY, None),
        ("body/bodies/male/walk.png", None, None),
        ("head/heads/human/male/walk.png", None, None),
        ("eyes/human/adult/default/walk.png", None, None),
        ("legs/armour/plate/male/walk.png", PLATE_STEEL_BLUE, None),
        ("feet/armour/plate/male/walk.png", PLATE_STEEL_BLUE, None),
        ("torso/armour/plate/male/walk.png", PLATE_STEEL_BLUE, None),
        ("shoulders/pauldrons/male/walk.png", PLATE_STEEL_BLUE, None),
        ("hat/helmet/armet/adult/walk.png", PLATE_STEEL_BLUE, None),
        ("cape/solid/fg/walk.png", CAPE_DARK_NAVY, None),
        ("weapon/sword/longsword/walk/longsword.png", None, None),
    ]
    # 6-frame walk cycle [1, 2, 4, 5, 6, 8]
    w_walk = build_character_animation(w_walk_spec, row=2, frame_indices=[1, 2, 4, 5, 6, 8])
    w_walk_path = TARGET_DIR / "warrior_walk_strip6.png"
    w_walk.save(w_walk_path)
    all_generated_strips.append(w_walk_path)
    
    w_run_spec = [
        ("cape/solid/bg/walk.png", CAPE_DARK_NAVY, None),
        ("body/bodies/male/run.png", None, None),
        ("head/heads/human/male/run.png", None, None),
        ("eyes/human/adult/default/run.png", None, None),
        ("legs/pants/male/run.png", PLATE_STEEL_BLUE, None),
        ("feet/armour/plate/male/run.png", PLATE_STEEL_BLUE, None),
        ("torso/armour/plate/male/run.png", PLATE_STEEL_BLUE, None),
        ("shoulders/pauldrons/male/run.png", PLATE_STEEL_BLUE, None),
        ("hat/helmet/armet/adult/run.png", PLATE_STEEL_BLUE, None),
        ("cape/solid/fg/walk.png", CAPE_DARK_NAVY, None),
        ("weapon/sword/longsword/walk/longsword.png", None, None),
    ]
    # 6-frame run cycle [1, 2, 3, 5, 6, 7]
    w_run = build_character_animation(w_run_spec, row=2, frame_indices=[1, 2, 3, 5, 6, 7])
    w_run_path = TARGET_DIR / "warrior_run_strip6.png"
    w_run.save(w_run_path)
    all_generated_strips.append(w_run_path)
    
    # 6-frame dynamic wide slash [0, 1, 2, 3, 4, 5]
    w_slash_spec = [
        ("cape/solid/bg/slash.png", CAPE_DARK_NAVY, None),
        ("body/bodies/male/slash.png", None, None),
        ("head/heads/human/male/slash.png", None, None),
        ("eyes/human/adult/default/slash.png", None, None),
        ("legs/armour/plate/male/slash.png", PLATE_STEEL_BLUE, None),
        ("feet/armour/plate/male/slash.png", PLATE_STEEL_BLUE, None),
        ("torso/armour/plate/male/slash.png", PLATE_STEEL_BLUE, None),
        ("shoulders/pauldrons/male/slash.png", PLATE_STEEL_BLUE, None),
        ("hat/helmet/armet/adult/slash.png", PLATE_STEEL_BLUE, None),
        ("cape/solid/fg/slash.png", CAPE_DARK_NAVY, None),
    ]
    w_slash_body = build_character_animation(w_slash_spec, row=2, frame_indices=[0, 1, 2, 3, 4, 5])
    # Composite two-handed longsword slash arc
    sw_slash_img = Image.open(LPC_ROOT / "weapon/sword/longsword/attack_slash/longsword.png").convert("RGBA")
    w_slash = Image.new("RGBA", (6 * 64, 64), (0, 0, 0, 0))
    for c in range(6):
        f = w_slash_body.crop((c * 64, 0, (c + 1) * 64, 64)).copy()
        sw_f = sw_slash_img.crop((c * 192 + 64, 2 * 192 + 64, c * 192 + 128, 2 * 192 + 128))
        f.alpha_composite(sw_f)
        w_slash.paste(f, (c * 64, 0))
    w_slash_path = TARGET_DIR / "warrior_slash_strip6.png"
    w_slash.save(w_slash_path)
    all_generated_strips.append(w_slash_path)
    
    # 3-frame hurt [0, 1, 0]
    w_hurt_spec = [
        ("cape/solid/bg/hurt.png", CAPE_DARK_NAVY, None),
        ("body/bodies/male/hurt.png", None, None),
        ("head/heads/human/male/hurt.png", None, None),
        ("eyes/human/adult/default/hurt.png", None, None),
        ("legs/armour/plate/male/hurt.png", PLATE_STEEL_BLUE, None),
        ("feet/armour/plate/male/hurt.png", PLATE_STEEL_BLUE, None),
        ("torso/armour/plate/male/hurt.png", PLATE_STEEL_BLUE, None),
        ("shoulders/pauldrons/male/hurt.png", PLATE_STEEL_BLUE, None),
        ("hat/helmet/armet/adult/hurt.png", PLATE_STEEL_BLUE, None),
        ("cape/solid/fg/hurt.png", CAPE_DARK_NAVY, None),
        ("weapon/sword/longsword/hurt/longsword.png", None, None),
    ]
    w_hurt = build_character_animation(w_hurt_spec, row=0, frame_indices=[0, 1, 0])
    w_hurt_path = TARGET_DIR / "warrior_hurt_strip3.png"
    w_hurt.save(w_hurt_path)
    all_generated_strips.append(w_hurt_path)
    
    # 5-frame death [1, 2, 3, 4, 5]
    w_death = build_character_animation(w_hurt_spec, row=0, frame_indices=[1, 2, 3, 4, 5])
    w_death_path = TARGET_DIR / "warrior_death_strip5.png"
    w_death.save(w_death_path)
    all_generated_strips.append(w_death_path)
    
    # ---------------------------------------------------------------------
    # 2. OKCU (ARCHER BASE)
    # ---------------------------------------------------------------------
    print("\n--- [2/6] Building Okcu (Archer Base) ---")
    a_idle_spec = [
        ("quiver/walk/quiver.png", None, None),
        ("body/bodies/male/idle.png", None, None),
        ("head/heads/human/male/idle.png", None, None),
        ("eyes/human/adult/default/idle.png", None, None),
        ("hair/messy/adult/idle.png", None, None),
        ("legs/pants/male/idle.png", ARCHER_LEATHERS, None),
        ("feet/boots/basic/male/idle.png", None, None),
        ("torso/armour/leather/male/idle.png", ARCHER_LEATHERS, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", None, None),
    ]
    a_idle = build_character_animation(a_idle_spec, row=2, frame_indices=[0, 1, 1, 0])
    a_idle_path = TARGET_DIR / "archer_idle_strip4.png"
    a_idle.save(a_idle_path)
    all_generated_strips.append(a_idle_path)
    
    a_walk_spec = [
        ("quiver/walk/quiver.png", None, None),
        ("body/bodies/male/walk.png", None, None),
        ("head/heads/human/male/walk.png", None, None),
        ("eyes/human/adult/default/walk.png", None, None),
        ("hair/messy/adult/walk.png", None, None),
        ("legs/pants/male/walk.png", ARCHER_LEATHERS, None),
        ("feet/boots/basic/male/walk.png", None, None),
        ("torso/armour/leather/male/walk.png", ARCHER_LEATHERS, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", None, None),
    ]
    a_walk = build_character_animation(a_walk_spec, row=2, frame_indices=[1, 2, 4, 5, 6, 8])
    a_walk_path = TARGET_DIR / "archer_walk_strip6.png"
    a_walk.save(a_walk_path)
    all_generated_strips.append(a_walk_path)
    
    a_run_spec = [
        ("quiver/walk/quiver.png", None, None),
        ("body/bodies/male/run.png", None, None),
        ("head/heads/human/male/run.png", None, None),
        ("eyes/human/adult/default/run.png", None, None),
        ("hair/messy/adult/run.png", None, None),
        ("legs/pants/male/run.png", ARCHER_LEATHERS, None),
        ("feet/boots/basic/male/run.png", None, None),
        ("torso/armour/leather/male/run.png", ARCHER_LEATHERS, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", None, None),
    ]
    a_run = build_character_animation(a_run_spec, row=2, frame_indices=[1, 2, 3, 5, 6, 7])
    a_run_path = TARGET_DIR / "archer_run_strip6.png"
    a_run.save(a_run_path)
    all_generated_strips.append(a_run_path)
    
    # 8-frame archery shoot [0, 2, 4, 6, 8, 9, 10, 12]
    a_shoot_spec = [
        ("quiver/shoot/quiver.png", None, None),
        ("weapon/ranged/bow/normal/universal/background/shoot/normal.png", None, None),
        ("body/bodies/male/shoot.png", None, None),
        ("head/heads/human/male/shoot.png", None, None),
        ("eyes/human/adult/default/shoot.png", None, None),
        ("hair/messy/adult/shoot.png", None, None),
        ("legs/pants/male/shoot.png", ARCHER_LEATHERS, None),
        ("feet/boots/basic/male/shoot.png", None, None),
        ("torso/armour/leather/male/shoot.png", ARCHER_LEATHERS, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", None, None),
        ("weapon/ranged/bow/arrow/shoot/arrow.png", None, None),
    ]
    a_shoot = build_character_animation(a_shoot_spec, row=2, frame_indices=[0, 2, 4, 6, 8, 9, 10, 12])
    a_shoot_path = TARGET_DIR / "archer_shoot_strip8.png"
    a_shoot.save(a_shoot_path)
    all_generated_strips.append(a_shoot_path)
    
    # 3-frame hurt [0, 1, 0]
    a_hurt_spec = [
        ("quiver/hurt/quiver.png", None, None),
        ("weapon/ranged/bow/normal/universal/background/hurt/normal.png", None, None),
        ("body/bodies/male/hurt.png", None, None),
        ("head/heads/human/male/hurt.png", None, None),
        ("eyes/human/adult/default/hurt.png", None, None),
        ("hair/messy/adult/hurt.png", None, None),
        ("legs/pants/male/hurt.png", ARCHER_LEATHERS, None),
        ("feet/boots/basic/male/hurt.png", None, None),
        ("torso/armour/leather/male/hurt.png", ARCHER_LEATHERS, None),
        ("weapon/ranged/bow/normal/universal/foreground/hurt/normal.png", None, None),
    ]
    a_hurt = build_character_animation(a_hurt_spec, row=0, frame_indices=[0, 1, 0])
    a_hurt_path = TARGET_DIR / "archer_hurt_strip3.png"
    a_hurt.save(a_hurt_path)
    all_generated_strips.append(a_hurt_path)
    
    # 5-frame death [1, 2, 3, 4, 5]
    a_death = build_character_animation(a_hurt_spec, row=0, frame_indices=[1, 2, 3, 4, 5])
    a_death_path = TARGET_DIR / "archer_death_strip5.png"
    a_death.save(a_death_path)
    all_generated_strips.append(a_death_path)

    # ---------------------------------------------------------------------
    # 3. KOR MUHAFIZI (WARRIOR + FIRE SP FORM)
    # ---------------------------------------------------------------------
    print("\n--- [3/6] Building Kor Muhafizi (Warrior + Fire SP) ---")
    km_idle_spec = [
        ("cape/solid/bg/idle.png", CAPE_BURNING_CRIMSON, None),
        ("body/bodies/male/idle.png", None, None),
        ("head/heads/human/male/idle.png", None, None),
        ("eyes/human/adult/default/idle.png", None, None),
        ("legs/armour/plate/male/idle.png", PLATE_OBSIDIAN_FIRE, None),
        ("feet/armour/plate/male/idle.png", PLATE_OBSIDIAN_FIRE, None),
        ("torso/armour/plate/male/idle.png", PLATE_OBSIDIAN_FIRE, None),
        ("shoulders/pauldrons/male/idle.png", PLATE_OBSIDIAN_FIRE, None),
        ("hat/helmet/armet/adult/idle.png", PLATE_OBSIDIAN_FIRE, None),
        ("cape/solid/fg/idle.png", CAPE_BURNING_CRIMSON, None),
        ("weapon/sword/longsword/walk/longsword.png", SWORD_FIRE, None),
    ]
    km_idle = build_character_animation(km_idle_spec, row=2, frame_indices=[0, 1, 1, 0])
    km_idle_path = TARGET_DIR / "kor_muhafizi_idle_strip4.png"
    km_idle.save(km_idle_path)
    all_generated_strips.append(km_idle_path)
    
    km_slash_spec = [
        ("cape/solid/bg/slash.png", CAPE_BURNING_CRIMSON, None),
        ("body/bodies/male/slash.png", None, None),
        ("head/heads/human/male/slash.png", None, None),
        ("eyes/human/adult/default/slash.png", None, None),
        ("legs/armour/plate/male/slash.png", PLATE_OBSIDIAN_FIRE, None),
        ("feet/armour/plate/male/slash.png", PLATE_OBSIDIAN_FIRE, None),
        ("torso/armour/plate/male/slash.png", PLATE_OBSIDIAN_FIRE, None),
        ("shoulders/pauldrons/male/slash.png", PLATE_OBSIDIAN_FIRE, None),
        ("hat/helmet/armet/adult/slash.png", PLATE_OBSIDIAN_FIRE, None),
        ("cape/solid/fg/slash.png", CAPE_BURNING_CRIMSON, None),
    ]
    km_slash_body = build_character_animation(km_slash_spec, row=2, frame_indices=[0, 1, 2, 3, 4, 5])
    # Fire molten sword recolor
    sw_fire_img = recolor_image(
        Image.open(LPC_ROOT / "weapon/sword/longsword/attack_slash/longsword.png").convert("RGBA"),
        SWORD_FIRE
    )
    km_slash = Image.new("RGBA", (6 * 64, 64), (0, 0, 0, 0))
    for c in range(6):
        f = km_slash_body.crop((c * 64, 0, (c + 1) * 64, 64)).copy()
        sw_f = sw_fire_img.crop((c * 192 + 64, 2 * 192 + 64, c * 192 + 128, 2 * 192 + 128))
        f.alpha_composite(sw_f)
        km_slash.paste(f, (c * 64, 0))
    km_slash_path = TARGET_DIR / "kor_muhafizi_slash_strip6.png"
    km_slash.save(km_slash_path)
    all_generated_strips.append(km_slash_path)
    
    # Aura
    km_aura = generate_aura_strip("kor_muhafizi")
    km_aura_path = TARGET_DIR / "kor_muhafizi_aura_strip6.png"
    km_aura.save(km_aura_path)
    all_generated_strips.append(km_aura_path)

    # ---------------------------------------------------------------------
    # 4. AYAZ SOVALYESI (WARRIOR + WATER/FROST SP FORM)
    # ---------------------------------------------------------------------
    print("\n--- [4/6] Building Ayaz Sovalyesi (Warrior + Frost SP) ---")
    as_idle_spec = [
        ("cape/solid/bg/idle.png", CAPE_FROST_MIST, None),
        ("body/bodies/male/idle.png", None, None),
        ("head/heads/human/male/idle.png", None, None),
        ("eyes/human/adult/default/idle.png", None, None),
        ("legs/armour/plate/male/idle.png", PLATE_FROST_CYAN, None),
        ("feet/armour/plate/male/idle.png", PLATE_FROST_CYAN, None),
        ("torso/armour/plate/male/idle.png", PLATE_FROST_CYAN, None),
        ("shoulders/pauldrons/male/idle.png", PLATE_FROST_CYAN, None),
        ("hat/helmet/armet/adult/idle.png", PLATE_FROST_CYAN, None),
        ("cape/solid/fg/idle.png", CAPE_FROST_MIST, None),
        ("weapon/sword/longsword/walk/longsword.png", SWORD_FROST, None),
    ]
    as_idle = build_character_animation(as_idle_spec, row=2, frame_indices=[0, 1, 1, 0])
    as_idle_path = TARGET_DIR / "ayaz_sovalyesi_idle_strip4.png"
    as_idle.save(as_idle_path)
    all_generated_strips.append(as_idle_path)
    
    as_slash_spec = [
        ("cape/solid/bg/slash.png", CAPE_FROST_MIST, None),
        ("body/bodies/male/slash.png", None, None),
        ("head/heads/human/male/slash.png", None, None),
        ("eyes/human/adult/default/slash.png", None, None),
        ("legs/armour/plate/male/slash.png", PLATE_FROST_CYAN, None),
        ("feet/armour/plate/male/slash.png", PLATE_FROST_CYAN, None),
        ("torso/armour/plate/male/slash.png", PLATE_FROST_CYAN, None),
        ("shoulders/pauldrons/male/slash.png", PLATE_FROST_CYAN, None),
        ("hat/helmet/armet/adult/slash.png", PLATE_FROST_CYAN, None),
        ("cape/solid/fg/slash.png", CAPE_FROST_MIST, None),
    ]
    as_slash_body = build_character_animation(as_slash_spec, row=2, frame_indices=[0, 1, 2, 3, 4, 5])
    sw_frost_img = recolor_image(
        Image.open(LPC_ROOT / "weapon/sword/longsword/attack_slash/longsword.png").convert("RGBA"),
        SWORD_FROST
    )
    as_slash = Image.new("RGBA", (6 * 64, 64), (0, 0, 0, 0))
    for c in range(6):
        f = as_slash_body.crop((c * 64, 0, (c + 1) * 64, 64)).copy()
        sw_f = sw_frost_img.crop((c * 192 + 64, 2 * 192 + 64, c * 192 + 128, 2 * 192 + 128))
        f.alpha_composite(sw_f)
        as_slash.paste(f, (c * 64, 0))
    as_slash_path = TARGET_DIR / "ayaz_sovalyesi_slash_strip6.png"
    as_slash.save(as_slash_path)
    all_generated_strips.append(as_slash_path)
    
    # Aura
    as_aura = generate_aura_strip("ayaz_sovalyesi")
    as_aura_path = TARGET_DIR / "ayaz_sovalyesi_aura_strip6.png"
    as_aura.save(as_aura_path)
    all_generated_strips.append(as_aura_path)

    # ---------------------------------------------------------------------
    # 5. KUL GOZU (ARCHER + FIRE SP FORM)
    # ---------------------------------------------------------------------
    print("\n--- [5/6] Building Kul Gozu (Archer + Fire SP) ---")
    kg_idle_spec = [
        ("quiver/walk/quiver.png", ARCHER_ASH_CHARCOAL, None),
        ("body/bodies/male/idle.png", None, None),
        ("head/heads/human/male/idle.png", None, None),
        ("eyes/human/adult/default/idle.png", None, None),
        ("hair/messy/adult/idle.png", None, None),
        ("legs/pants/male/idle.png", ARCHER_ASH_CHARCOAL, None),
        ("feet/boots/basic/male/idle.png", None, None),
        ("torso/armour/leather/male/idle.png", ARCHER_ASH_CHARCOAL, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", SWORD_FIRE, None),
    ]
    kg_idle = build_character_animation(kg_idle_spec, row=2, frame_indices=[0, 1, 1, 0])
    kg_idle_path = TARGET_DIR / "kul_gozu_idle_strip4.png"
    kg_idle.save(kg_idle_path)
    all_generated_strips.append(kg_idle_path)
    
    kg_shoot_spec = [
        ("quiver/shoot/quiver.png", ARCHER_ASH_CHARCOAL, None),
        ("weapon/ranged/bow/normal/universal/background/shoot/normal.png", SWORD_FIRE, None),
        ("body/bodies/male/shoot.png", None, None),
        ("head/heads/human/male/shoot.png", None, None),
        ("eyes/human/adult/default/shoot.png", None, None),
        ("hair/messy/adult/shoot.png", None, None),
        ("legs/pants/male/shoot.png", ARCHER_ASH_CHARCOAL, None),
        ("feet/boots/basic/male/shoot.png", None, None),
        ("torso/armour/leather/male/shoot.png", ARCHER_ASH_CHARCOAL, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", SWORD_FIRE, None),
        ("weapon/ranged/bow/arrow/shoot/arrow.png", SWORD_FIRE, None),
    ]
    kg_shoot = build_character_animation(kg_shoot_spec, row=2, frame_indices=[0, 2, 4, 6, 8, 9, 10, 12])
    kg_shoot_path = TARGET_DIR / "kul_gozu_shoot_strip8.png"
    kg_shoot.save(kg_shoot_path)
    all_generated_strips.append(kg_shoot_path)
    
    # Aura
    kg_aura = generate_aura_strip("kul_gozu")
    kg_aura_path = TARGET_DIR / "kul_gozu_aura_strip6.png"
    kg_aura.save(kg_aura_path)
    all_generated_strips.append(kg_aura_path)

    # ---------------------------------------------------------------------
    # 6. TUFAN OKCUSU (ARCHER + WATER/STORM SP FORM)
    # ---------------------------------------------------------------------
    print("\n--- [6/6] Building Tufan Okcusu (Archer + Water/Storm SP) ---")
    to_idle_spec = [
        ("quiver/walk/quiver.png", ARCHER_STORM_NAVY, None),
        ("body/bodies/male/idle.png", None, None),
        ("head/heads/human/male/idle.png", None, None),
        ("eyes/human/adult/default/idle.png", None, None),
        ("hair/messy/adult/idle.png", None, None),
        ("legs/pants/male/idle.png", ARCHER_STORM_NAVY, None),
        ("feet/boots/basic/male/idle.png", None, None),
        ("torso/armour/leather/male/idle.png", ARCHER_STORM_NAVY, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", SWORD_FROST, None),
    ]
    to_idle = build_character_animation(to_idle_spec, row=2, frame_indices=[0, 1, 1, 0])
    to_idle_path = TARGET_DIR / "tufan_okcusu_idle_strip4.png"
    to_idle.save(to_idle_path)
    all_generated_strips.append(to_idle_path)
    
    to_shoot_spec = [
        ("quiver/shoot/quiver.png", ARCHER_STORM_NAVY, None),
        ("weapon/ranged/bow/normal/universal/background/shoot/normal.png", SWORD_FROST, None),
        ("body/bodies/male/shoot.png", None, None),
        ("head/heads/human/male/shoot.png", None, None),
        ("eyes/human/adult/default/shoot.png", None, None),
        ("hair/messy/adult/shoot.png", None, None),
        ("legs/pants/male/shoot.png", ARCHER_STORM_NAVY, None),
        ("feet/boots/basic/male/shoot.png", None, None),
        ("torso/armour/leather/male/shoot.png", ARCHER_STORM_NAVY, None),
        ("weapon/ranged/bow/normal/universal/foreground/shoot/normal.png", SWORD_FROST, None),
        ("weapon/ranged/bow/arrow/shoot/arrow.png", SWORD_FROST, None),
    ]
    to_shoot = build_character_animation(to_shoot_spec, row=2, frame_indices=[0, 2, 4, 6, 8, 9, 10, 12])
    to_shoot_path = TARGET_DIR / "tufan_okcusu_shoot_strip8.png"
    to_shoot.save(to_shoot_path)
    all_generated_strips.append(to_shoot_path)
    
    # Aura
    to_aura = generate_aura_strip("tufan_okcusu")
    to_aura_path = TARGET_DIR / "tufan_okcusu_aura_strip6.png"
    to_aura.save(to_aura_path)
    all_generated_strips.append(to_aura_path)

    # ---------------------------------------------------------------------
    # DYNAMIC 2D NORMAL MAPS
    # ---------------------------------------------------------------------
    print("\n--- Generating Dynamic 2D Normal Maps in normals/ ---")
    all_normals = []
    for strip_path in all_generated_strips:
        n_img = Image.open(strip_path)
        norm_map = generate_tangent_normal_map(n_img, strength=1.7, pillow_weight=0.7)
        norm_path = NORMALS_DIR / f"{strip_path.stem}_n.png"
        norm_map.save(norm_path)
        all_normals.append(norm_path)
        print(f"  [Normal Map] {norm_path.name} ({norm_map.width}x{norm_map.height})")

    # ---------------------------------------------------------------------
    # GODOT 4 SPRITEFRAMES (.tres)
    # ---------------------------------------------------------------------
    print("\n--- Generating Godot 4 SpriteFrames (.tres) ---")
    # 1. Warrior
    generate_spriteframes_tres("warrior", {
        "idle":  ("warrior_idle_strip4.png", 4, 4.0, True),
        "walk":  ("warrior_walk_strip6.png", 6, 8.0, True),
        "run":   ("warrior_run_strip6.png", 6, 10.0, True),
        "slash": ("warrior_slash_strip6.png", 6, 12.0, False),
        "hurt":  ("warrior_hurt_strip3.png", 3, 8.0, False),
        "death": ("warrior_death_strip5.png", 5, 6.0, False),
    }, TARGET_DIR / "warrior_spriteframes.tres")
    
    # 2. Archer
    generate_spriteframes_tres("archer", {
        "idle":  ("archer_idle_strip4.png", 4, 4.0, True),
        "walk":  ("archer_walk_strip6.png", 6, 8.0, True),
        "run":   ("archer_run_strip6.png", 6, 10.0, True),
        "shoot": ("archer_shoot_strip8.png", 8, 12.0, False),
        "hurt":  ("archer_hurt_strip3.png", 3, 8.0, False),
        "death": ("archer_death_strip5.png", 5, 6.0, False),
    }, TARGET_DIR / "archer_spriteframes.tres")
    
    # 3. Kor Muhafizi
    generate_spriteframes_tres("kor_muhafizi", {
        "idle":  ("kor_muhafizi_idle_strip4.png", 4, 4.0, True),
        "slash": ("kor_muhafizi_slash_strip6.png", 6, 12.0, False),
        "aura":  ("kor_muhafizi_aura_strip6.png", 6, 8.0, True),
    }, TARGET_DIR / "kor_muhafizi_spriteframes.tres")
    
    # 4. Ayaz Sovalyesi
    generate_spriteframes_tres("ayaz_sovalyesi", {
        "idle":  ("ayaz_sovalyesi_idle_strip4.png", 4, 4.0, True),
        "slash": ("ayaz_sovalyesi_slash_strip6.png", 6, 12.0, False),
        "aura":  ("ayaz_sovalyesi_aura_strip6.png", 6, 8.0, True),
    }, TARGET_DIR / "ayaz_sovalyesi_spriteframes.tres")
    
    # 5. Kul Gozu
    generate_spriteframes_tres("kul_gozu", {
        "idle":  ("kul_gozu_idle_strip4.png", 4, 4.0, True),
        "shoot": ("kul_gozu_shoot_strip8.png", 8, 12.0, False),
        "aura":  ("kul_gozu_aura_strip6.png", 6, 8.0, True),
    }, TARGET_DIR / "kul_gozu_spriteframes.tres")
    
    # 6. Tufan Okcusu
    generate_spriteframes_tres("tufan_okcusu", {
        "idle":  ("tufan_okcusu_idle_strip4.png", 4, 4.0, True),
        "shoot": ("tufan_okcusu_shoot_strip8.png", 8, 12.0, False),
        "aura":  ("tufan_okcusu_aura_strip6.png", 6, 8.0, True),
    }, TARGET_DIR / "tufan_okcusu_spriteframes.tres")

    # ---------------------------------------------------------------------
    # GODOT 4 .IMPORT FILES (48 Total)
    # ---------------------------------------------------------------------
    print("\n--- Generating Godot 4 .import files for all textures ---")
    all_textures = all_generated_strips + all_normals
    for tex in all_textures:
        imp = generate_godot_import_file(tex)
    print(f"Generated {len(all_textures)} .import files with Nearest/Lossless settings.")

    print("\n" + "=" * 70)
    print("SUCCESS: Character Sprite Specialist Pipeline Complete!")
    print(f"Total Main Strips: {len(all_generated_strips)}")
    print(f"Total Normal Maps: {len(all_normals)}")
    print("Total SpriteFrames: 6 (.tres)")
    print(f"Total Import Files: {len(all_textures)} (.import)")
    print("=" * 70)

if __name__ == "__main__":
    build_all_characters()
