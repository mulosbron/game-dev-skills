#!/usr/bin/env python3
"""
Pixel Art Grid Snapper & Palette Quantizer
Designed to clean messy AI-generated pixel art (midjourney, dalle, flux, sdxl)
by locking pixels to a true grid, eliminating subpixel jitter, and quantizing
to crisp indexed palettes (matching SpriteFusion Pixel Snapper & Ritmo pixel fix).
"""

import sys
import argparse
from pathlib import Path
import numpy as np
from PIL import Image

# Well-known retro pixel art palettes
PALETTES = {
    "pico8": [
        "#000000", "#1D2B53", "#7E2553", "#008751", "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
        "#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA"
    ],
    "db16": [
        "#140c1c", "#442434", "#30346d", "#4e4a4e", "#854c30", "#346524", "#d04648", "#757161",
        "#597dce", "#d27d2c", "#8595a1", "#6daa2c", "#d2aa99", "#6dc2ca", "#dad45e", "#deeed6"
    ],
    "gameboy": [
        "#0f380f", "#306230", "#8bac0f", "#9bbc0f"
    ]
}

def hex_to_rgb(hex_str: str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def detect_pixel_size(img_arr: np.ndarray, max_check: int = 16) -> int:
    """
    Estimates the logical pixel size by checking color transition spacing.
    """
    h, w = img_arr.shape[:2]
    # Check horizontal diffs
    diffs = np.abs(np.diff(img_arr.astype(int), axis=1)).sum(axis=-1)
    diff_cols = np.where(diffs > 20)
    
    if len(diff_cols[1]) < 2:
        return 1
        
    distances = np.diff(diff_cols[1])
    distances = distances[(distances > 0) & (distances <= max_check)]
    if len(distances) == 0:
        return 1
    
    # Return most common interval
    counts = np.bincount(distances)
    candidate = int(np.argmax(counts))
    return candidate if candidate > 0 else 1

def snap_to_grid(img: Image.Image, pixel_size: int = None, colors: int = 16, palette_name: str = None, custom_palette: list = None) -> Image.Image:
    """
    Snaps an image to a clean pixel grid and strict palette.
    """
    rgba = img.convert("RGBA")
    arr = np.array(rgba)
    w, h = img.size

    # 1. Determine logical grid size
    if pixel_size is None or pixel_size <= 0:
        pixel_size = detect_pixel_size(arr)
        if pixel_size < 1:
            pixel_size = 1

    # Logical dimensions
    log_w = max(1, w // pixel_size)
    log_h = max(1, h // pixel_size)

    # Downscale with Resampling.BOX or NEAREST to merge messy subpixels into logical cells
    downscaled = rgba.resize((log_w, log_h), resample=Image.Resampling.BOX)

    # Separate Alpha
    down_arr = np.array(downscaled)
    rgb_img = downscaled.convert("RGB")
    alpha_channel = down_arr[:, :, 3]
    binary_alpha = np.where(alpha_channel > 127, 255, 0).astype(np.uint8)

    # 2. Quantize Palette
    if custom_palette:
        # Build palette image
        pal_img = Image.new("P", (1, 1))
        pal_data = []
        for c in custom_palette:
            rgb = hex_to_rgb(c) if isinstance(c, str) else c
            pal_data.extend(rgb[:3])
        pal_data.extend([0] * (768 - len(pal_data)))
        pal_img.putpalette(pal_data)
        quantized = rgb_img.quantize(palette=pal_img, dither=Image.Dither.NONE)
    elif palette_name and palette_name.lower() in PALETTES:
        pal_colors = PALETTES[palette_name.lower()]
        pal_img = Image.new("P", (1, 1))
        pal_data = []
        for c in pal_colors:
            pal_data.extend(hex_to_rgb(c))
        pal_data.extend([0] * (768 - len(pal_data)))
        pal_img.putpalette(pal_data)
        quantized = rgb_img.quantize(palette=pal_img, dither=Image.Dither.NONE)
    else:
        # Fast k-means / median cut quantization
        quantized = rgb_img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)

    # Restore RGBA
    q_rgb = quantized.convert("RGBA")
    q_arr = np.array(q_rgb)
    q_arr[:, :, 3] = binary_alpha
    snapped = Image.fromarray(q_arr, mode="RGBA")

    # Upscale back to original dimensions using Nearest Neighbor for crisp pixel edges
    final_output = snapped.resize((w, h), resample=Image.Resampling.NEAREST)
    return final_output, snapped, pixel_size

def main():
    parser = argparse.ArgumentParser(description="AI Pixel Art Grid Snapper & Palette Quantizer")
    parser.add_argument("input", help="Path to input messy pixel art image")
    parser.add_argument("-o", "--output", help="Path to output cleaned image (default: <name>_snapped.png)")
    parser.add_argument("--grid-size", "-g", type=int, default=None, help="Logical pixel cell size (auto-detected if omitted)")
    parser.add_argument("--colors", "-c", type=int, default=16, help="Target palette size (default: 16)")
    parser.add_argument("--palette", "-p", choices=list(PALETTES.keys()), help="Lock to curated palette: pico8, db16, gameboy")
    parser.add_argument("--custom-hex", help="Comma-separated hex colors (e.g. '#ff0000,#00ff00,#0000ff')")
    parser.add_argument("--native", action="store_true", help="Save at native 1x logical resolution instead of upscaled")

    args = parser.parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Error: {in_path} not found.")
        sys.exit(1)

    custom_colors = [c.strip() for c in args.custom_hex.split(",")] if args.custom_hex else None

    img = Image.open(in_path)
    upscaled, native, detected_grid = snap_to_grid(
        img,
        pixel_size=args.grid_size,
        colors=args.colors,
        palette_name=args.palette,
        custom_palette=custom_colors
    )

    out_path = Path(args.output) if args.output else in_path.parent / f"{in_path.stem}_snapped.png"
    result_img = native if args.native else upscaled
    out_path.parent.mkdir(parents=True, exist_ok=True)
    result_img.save(out_path)

    print(f"Success: Snapped {in_path.name} to {detected_grid}x grid. Saved to {out_path} ({result_img.width}x{result_img.height})")

if __name__ == "__main__":
    main()
