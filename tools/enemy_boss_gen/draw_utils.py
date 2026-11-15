"""
Drawing and Pixel Art Utilities for Enemy & Boss Generation
"""

from typing import Tuple, List, Optional
import math
from PIL import Image, ImageDraw

def hex_to_rgba(hex_str: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        return (r, g, b, alpha)
    elif len(hex_str) == 8:
        r = int(hex_str[0:2], 16)
        g = int(hex_str[2:4], 16)
        b = int(hex_str[4:6], 16)
        a = int(hex_str[6:8], 16)
        return (r, g, b, a)
    raise ValueError(f"Invalid hex color: {hex_str}")

def pset(img: Image.Image, x: int, y: int, color: Tuple[int, int, int, int]):
    if 0 <= x < img.width and 0 <= y < img.height:
        # Alpha blend over existing
        if color[3] == 255:
            img.putpixel((x, y), color)
        elif color[3] > 0:
            bg = img.getpixel((x, y))
            a_src = color[3] / 255.0
            a_bg = bg[3] / 255.0
            a_out = a_src + a_bg * (1.0 - a_src)
            if a_out > 0:
                r_out = int((color[0] * a_src + bg[0] * a_bg * (1.0 - a_src)) / a_out)
                g_out = int((color[1] * a_src + bg[1] * a_bg * (1.0 - a_src)) / a_out)
                b_out = int((color[2] * a_src + bg[2] * a_bg * (1.0 - a_src)) / a_out)
                img.putpixel((x, y), (r_out, g_out, b_out, int(a_out * 255)))

def draw_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill: Tuple[int, int, int, int], outline: Optional[Tuple[int, int, int, int]] = None):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline)

def draw_rect(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, fill: Tuple[int, int, int, int], outline: Optional[Tuple[int, int, int, int]] = None):
    draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline)

def draw_poly(draw: ImageDraw.ImageDraw, points: List[Tuple[int, int]], fill: Tuple[int, int, int, int], outline: Optional[Tuple[int, int, int, int]] = None):
    draw.polygon(points, fill=fill, outline=outline)

def draw_capsule(draw: ImageDraw.ImageDraw, x0: int, y0: int, x1: int, y1: int, r: int, fill: Tuple[int, int, int, int], outline: Optional[Tuple[int, int, int, int]] = None):
    draw.line([(x0, y0), (x1, y1)], fill=fill, width=r*2)
    draw_circle(draw, x0, y0, r, fill=fill, outline=outline)
    draw_circle(draw, x1, y1, r, fill=fill, outline=outline)

def add_outline(img: Image.Image, outline_color: Tuple[int, int, int, int] = (16, 14, 20, 255)) -> Image.Image:
    """Adds a 1px contour outline around non-transparent pixels."""
    w, h = img.size
    out = img.copy()
    src_pixels = img.load()
    out_pixels = out.load()
    
    # Identify transparent pixels bordering non-transparent ones
    border_pixels = []
    for y in range(h):
        for x in range(w):
            if src_pixels[x, y][3] == 0:
                # Check neighbors
                has_opaque_neighbor = False
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if src_pixels[nx, ny][3] > 64:
                            has_opaque_neighbor = True
                            break
                if has_opaque_neighbor:
                    border_pixels.append((x, y))
                    
    for bx, by in border_pixels:
        out_pixels[bx, by] = outline_color
        
    return out

def create_strip(frames: List[Image.Image]) -> Image.Image:
    """Concatenates a list of frame images horizontally into a strip."""
    if not frames:
        raise ValueError("Frames list cannot be empty")
    w, h = frames[0].size
    count = len(frames)
    strip = Image.new("RGBA", (w * count, h), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        strip.paste(frame, (i * w, 0))
    return strip
