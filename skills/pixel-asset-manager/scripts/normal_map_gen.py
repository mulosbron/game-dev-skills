#!/usr/bin/env python3
"""
Pixel Art Normal Map Generator for GameMaker & 2D Engines
Generates tangent-space normal maps from 2D pixel art sprites using
distance-transform 'pillow shading' combined with luminance relief.
"""

import sys
import argparse
from pathlib import Path
import numpy as np
from PIL import Image

try:
    from scipy.ndimage import distance_transform_edt, sobel
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

def generate_normal_map(image_path: Path, output_path: Path = None, strength: float = 1.5, 
                        smoothness: float = 0.5, pillow_weight: float = 0.65, 
                        invert_y: bool = False) -> Path:
    """
    Takes a 2D PNG sprite (with transparent background) and creates a 2D Normal Map.
    - pillow_weight: 0.0 = only luminance bumps, 1.0 = purely rounded body volume (pillow)
    - strength: height multiplier for bump depth
    - invert_y: flip Green channel (DirectX vs OpenGL standard, GameMaker usually uses OpenGL standard Y-up or Y-down based on shader)
    """
    img = Image.open(image_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)

    # Alpha mask (0.0 to 1.0)
    alpha = arr[:, :, 3] / 255.0
    mask = alpha > 0.1

    if not np.any(mask):
        print(f"Warning: {image_path} has no opaque pixels.")
        return None

    # 1. Luminance (grayscale detail)
    # Standard Rec. 709 luminance
    lum = (arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722) / 255.0

    # 2. Distance Transform (Pillow volume estimation)
    if HAS_SCIPY:
        dist = distance_transform_edt(mask)
        max_dist = np.max(dist)
        if max_dist > 0:
            dist = dist / max_dist
    else:
        # Fallback simple distance approximation
        dist = mask.astype(np.float32)

    # Combine pillow volume with luminance detail
    # pillow gives 3D body curvature, luminance gives interior texture (buckles, cloth folds)
    height_map = (dist * pillow_weight) + (lum * (1.0 - pillow_weight))
    height_map = height_map * mask

    # 3. Calculate surface normal gradients (dx, dy)
    if HAS_SCIPY:
        dx = sobel(height_map, axis=1) * strength
        dy = sobel(height_map, axis=0) * strength
    else:
        # Simple finite difference
        dx = np.gradient(height_map, axis=1) * strength * 4.0
        dy = np.gradient(height_map, axis=0) * strength * 4.0

    if invert_y:
        dy = -dy

    # Normal vector N = normalize([-dx, -dy, 1.0])
    dz = np.ones_like(dx)
    length = np.sqrt(dx * dx + dy * dy + dz * dz)
    length = np.maximum(length, 1e-6)

    nx = -dx / length
    ny = -dy / length
    nz = dz / length

    # 4. Map [-1.0, 1.0] -> [0, 255]
    r = ((nx * 0.5 + 0.5) * 255.0).clip(0, 255)
    g = ((ny * 0.5 + 0.5) * 255.0).clip(0, 255)
    b = ((nz * 0.5 + 0.5) * 255.0).clip(0, 255)

    # Transparent areas default to neutral normal vector (0, 0, 1) -> (128, 128, 255)
    r[~mask] = 128
    g[~mask] = 128
    b[~mask] = 255

    normal_arr = np.stack([r, g, b, arr[:, :, 3]], axis=-1).astype(np.uint8)
    normal_img = Image.fromarray(normal_arr, mode="RGBA")

    if output_path is None:
        clean_stem = image_path.stem
        output_path = image_path.parent / f"{clean_stem}_n.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    normal_img.save(output_path)
    print(f"Generated normal map: {output_path} ({normal_img.width}x{normal_img.height})")
    return output_path

def render_lighting_preview(sprite_path: Path, normal_path: Path, output_gif: Path, num_frames: int = 16):
    """
    Renders an animated GIF showing a 2D rotating light source illuminating the sprite
    using the generated normal map.
    """
    sprite_img = Image.open(sprite_path).convert("RGBA")
    normal_img = Image.open(normal_path).convert("RGBA")

    s_arr = np.array(sprite_img, dtype=np.float32) / 255.0
    n_arr = np.array(normal_img, dtype=np.float32) / 255.0

    mask = s_arr[:, :, 3] > 0.05

    # Decode normals from [0, 1] to [-1, 1]
    nx = n_arr[:, :, 0] * 2.0 - 1.0
    ny = n_arr[:, :, 1] * 2.0 - 1.0
    nz = n_arr[:, :, 2] * 2.0 - 1.0

    frames = []
    w, h = sprite_img.size

    for i in range(num_frames):
        angle = (2.0 * np.pi * i) / num_frames
        # Light orbiting around sprite in 3D
        lx = np.cos(angle)
        ly = np.sin(angle)
        lz = 0.6  # slightly above surface
        l_len = np.sqrt(lx * lx + ly * ly + lz * lz)
        lx, ly, lz = lx / l_len, ly / l_len, lz / l_len

        # Dot product
        dot = np.maximum(0.15, nx * lx + ny * ly + nz * lz)  # 0.15 ambient light

        # Apply lighting to RGB
        lit_r = (s_arr[:, :, 0] * dot * 255.0).clip(0, 255)
        lit_g = (s_arr[:, :, 1] * dot * 255.0).clip(0, 255)
        lit_b = (s_arr[:, :, 2] * dot * 255.0).clip(0, 255)
        lit_a = s_arr[:, :, 3] * 255.0

        lit_frame = np.stack([lit_r, lit_g, lit_b, lit_a], axis=-1).astype(np.uint8)
        frames.append(Image.fromarray(lit_frame, mode="RGBA"))

    output_gif.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output_gif, save_all=True, append_images=frames[1:], duration=80, loop=0, disposal=2)
    print(f"Saved lighting simulation GIF: {output_gif}")

def main():
    parser = argparse.ArgumentParser(description="Pixel Art Normal Map Generator")
    parser.add_argument("image", help="Input 2D PNG sprite image")
    parser.add_argument("--output", "-o", default=None, help="Output path for normal map (default: <name>_n.png)")
    parser.add_argument("--strength", "-s", type=float, default=2.0, help="Bump / bevel depth strength (default: 2.0)")
    parser.add_argument("--pillow", "-p", type=float, default=0.7, help="Pillow rounding vs texture ratio [0.0 - 1.0] (default: 0.7)")
    parser.add_argument("--invert-y", action="store_true", help="Invert Y (Green channel) for DirectX compatibility")
    parser.add_argument("--preview", action="store_true", help="Generate animated lighting preview GIF")

    args = parser.parse_args()
    in_path = Path(args.image)
    if not in_path.exists():
        print(f"Error: {in_path} not found.")
        sys.exit(1)

    out_path = Path(args.output) if args.output else None
    res_normal = generate_normal_map(in_path, out_path, strength=args.strength, pillow_weight=args.pillow, invert_y=args.invert_y)

    if args.preview and res_normal:
        preview_gif = in_path.parent / f"{in_path.stem}_lit_preview.gif"
        render_lighting_preview(in_path, res_normal, preview_gif)

if __name__ == "__main__":
    main()
