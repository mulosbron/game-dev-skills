#!/usr/bin/env python3
"""
Sprite Slicer & GameMaker Strip Exporter
Allows slicing grid-based pixel sprite sheets into individual frames
or reassembling them into GameMaker-friendly '_stripN.png' files.
"""

import sys
import argparse
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Run 'pip install Pillow'")
    sys.exit(1)

def slice_spritesheet(sheet_path: Path, frame_w: int, frame_h: int, output_dir: Path, prefix: str = ""):
    output_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet_path) as img:
        img_w, img_h = img.size
        cols = img_w // frame_w
        rows = img_h // frame_h
        total_frames = cols * rows

        print(f"Slicing {sheet_path.name} ({img_w}x{img_h}) -> {cols} cols x {rows} rows ({total_frames} frames of {frame_w}x{frame_h})")

        frame_idx = 0
        pfx = prefix or sheet_path.stem
        for r in range(rows):
            for c in range(cols):
                box = (c * frame_w, r * frame_h, (c + 1) * frame_w, (r + 1) * frame_h)
                frame = img.crop(box)
                
                # Check if frame is completely transparent
                extrema = frame.getextrema()
                if frame.mode in ("RGBA", "LA") and extrema[-1][1] == 0:
                    # Skip fully empty frames if desired, or keep indexing
                    pass

                out_file = output_dir / f"{pfx}_{frame_idx:03d}.png"
                frame.save(out_file)
                frame_idx += 1

        print(f"Exported {frame_idx} frames to {output_dir}")

def make_gamemaker_strip(sheet_path: Path, frame_w: int, frame_h: int, output_path: Path):
    """
    GameMaker recognizes files ending with _stripN.png where N is the frame count.
    Arranges all valid frames horizontally into a single 1-row strip.
    """
    with Image.open(sheet_path) as img:
        img_w, img_h = img.size
        cols = img_w // frame_w
        rows = img_h // frame_h
        total_frames = cols * rows

        frames = []
        for r in range(rows):
            for c in range(cols):
                box = (c * frame_w, r * frame_h, (c + 1) * frame_w, (r + 1) * frame_h)
                frame = img.crop(box)
                frames.append(frame)

        strip_w = frame_w * total_frames
        strip_h = frame_h
        strip_img = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))

        for i, frame in enumerate(frames):
            strip_img.paste(frame, (i * frame_w, 0))

        clean_stem = sheet_path.stem.split("_strip")[0]
        final_filename = f"{clean_stem}_strip{total_frames}.png"
        final_dest = output_path if output_path.is_file() else output_path / final_filename

        final_dest.parent.mkdir(parents=True, exist_ok=True)
        strip_img.save(final_dest)
        print(f"Saved GameMaker strip: {final_dest} ({strip_w}x{strip_h}, {total_frames} frames)")

def main():
    parser = argparse.ArgumentParser(description="Sprite Slicer & GameMaker Strip Tool")
    parser.add_argument("image", help="Path to spritesheet image")
    parser.add_argument("--width", "-W", type=int, required=True, help="Frame width in pixels")
    parser.add_argument("--height", "-H", type=int, required=True, help="Frame height in pixels")
    parser.add_argument("--output", "-o", default="./output", help="Output directory or file path")
    parser.add_argument("--gamemaker-strip", "-g", action="store_true", help="Generate GameMaker _stripN.png horizontal strip")
    parser.add_argument("--prefix", "-p", default="", help="Prefix for frame names")

    args = parser.parse_args()
    img_path = Path(args.image)
    if not img_path.exists():
        print(f"Error: {img_path} not found.")
        sys.exit(1)

    out_path = Path(args.output)
    if args.gamemaker_strip:
        make_gamemaker_strip(img_path, args.width, args.height, out_path)
    else:
        slice_spritesheet(img_path, args.width, args.height, out_path, prefix=args.prefix)

if __name__ == "__main__":
    main()
