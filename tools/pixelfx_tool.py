#!/usr/bin/env python3
"""
PixelFX GameMaker Bridge & Tool
Seamlessly bridges patch-gg/pixelfx (244+ procedural pixel VFX) with GameMaker Studio projects.
Handles searching, rendering, palette swapping, and converting to '_stripN.png'.
"""

import os
import sys
import json
import subprocess
import argparse
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PIXELFX_DIR = WORKSPACE_ROOT / "libraries" / "com.github.patch-gg.pixelfx"
TOOLS_DIR = WORKSPACE_ROOT / "tools"
SPRITE_SLICER = TOOLS_DIR / "sprite_slicer.py"

def run_node_cmd(cmd_args: list) -> subprocess.CompletedProcess:
    if not PIXELFX_DIR.exists():
        print(f"Error: PixelFX repository not found at {PIXELFX_DIR}")
        sys.exit(1)
    
    full_cmd = ["node"] + cmd_args
    return subprocess.run(full_cmd, cwd=str(PIXELFX_DIR), capture_output=True, text=True, encoding="utf-8")

def list_effects(query: str = ""):
    res = run_node_cmd(["tools/list.mjs", query] if query else ["tools/list.mjs"])
    if res.returncode == 0:
        print(res.stdout.strip())
    else:
        print(f"Error listing effects: {res.stderr}")

def render_and_export(effect_id: str, output_dir: Path = None, gamemaker_strip: bool = True,
                      palette: list = None, flip: bool = False):
    """
    Renders effect via pixelfx, extracts sheet and json, and optionally
    converts to a GameMaker '_stripN.png'.
    """
    cmd = ["tools/render.mjs", effect_id, "--sheet"]
    
    opts = {}
    if palette:
        opts["palette"] = palette
    if flip:
        opts["flip"] = True
    if opts:
        cmd += ["--opts", json.dumps(opts)]

    print(f"Rendering {effect_id} with PixelFX...", flush=True)
    res = run_node_cmd(cmd)
    if res.returncode != 0:
        print(f"Render failed: {res.stderr}")
        return None

    # Parse output path
    # Output is in records/<category>/<name>/
    parts = effect_id.split("/")
    if len(parts) != 2:
        print(f"Invalid effect id: {effect_id} (expected category/name)")
        return None

    cat, name = parts
    record_dir = PIXELFX_DIR / "records" / cat / name
    sheet_png = record_dir / f"{name}.png"
    sheet_json = record_dir / f"{name}.json"

    if not sheet_png.exists() or not sheet_json.exists():
        print(f"Exported files not found in {record_dir}")
        return None

    with open(sheet_json, "r", encoding="utf-8") as f:
        meta_data = json.load(f)

    frames = meta_data.get("frames", [])
    if not frames:
        print("No frames found in metadata.")
        return None

    total_frames = len(frames)
    first_frame = frames[0]["frame"]
    fw, fh = first_frame["w"], first_frame["h"]

    clean_name = name.replace("-", "_")
    target_dir = output_dir or (WORKSPACE_ROOT / "exports" / "com.github.patch-gg.pixelfx")
    target_dir.mkdir(parents=True, exist_ok=True)

    if gamemaker_strip:
        # Convert grid spritesheet to GameMaker horizontal _stripN
        final_filename = f"spr_fx_{clean_name}_strip{total_frames}.png"
        final_strip_path = target_dir / final_filename

        slicer_cmd = [
            sys.executable, str(SPRITE_SLICER), str(sheet_png),
            "-W", str(fw), "-H", str(fh),
            "--gamemaker-strip", "-o", str(final_strip_path)
        ]
        slicer_res = subprocess.run(slicer_cmd, capture_output=True, text=True)
        if slicer_res.returncode == 0:
            print(f"Successfully generated GameMaker strip:")
            print(f"-> {final_strip_path} ({total_frames} frames, {fw}x{fh} each)")
            
            # Save companion metadata JSON for timing & origin
            info_json = target_dir / f"spr_fx_{clean_name}_info.json"
            fps = meta_data.get("meta", {}).get("pixelfx", {}).get("fps", 30)
            pivot = meta_data.get("meta", {}).get("pixelfx", {}).get("pivot", [fw // 2, fh // 2])
            with open(info_json, "w", encoding="utf-8") as f:
                json.dump({
                    "sprite_name": f"spr_fx_{clean_name}",
                    "effect_id": effect_id,
                    "frame_count": total_frames,
                    "frame_width": fw,
                    "frame_height": fh,
                    "fps": fps,
                    "pivot": pivot,
                    "suggested_origin": "Custom",
                    "origin_x": pivot[0],
                    "origin_y": pivot[1]
                }, f, indent=2)
            print(f"-> Metadata: {info_json}")
            return final_strip_path
        else:
            print(f"Slicer error: {slicer_res.stderr}")
            return None
    else:
        # Just copy raw sheet and json
        dest_sheet = target_dir / f"{clean_name}.png"
        dest_json = target_dir / f"{clean_name}.json"
        dest_sheet.write_bytes(sheet_png.read_bytes())
        dest_json.write_bytes(sheet_json.read_bytes())
        print(f"Saved sprite sheet to: {dest_sheet}")
        return dest_sheet

def main():
    parser = argparse.ArgumentParser(description="PixelFX to GameMaker Bridge")
    subparsers = parser.add_subparsers(dest="command")

    # list
    list_p = subparsers.add_parser("list", help="Search or list available PixelFX effects")
    list_p.add_argument("query", nargs="?", default="", help="Search query (e.g. fire, slash, nova)")

    # export
    exp_p = subparsers.add_parser("export", help="Render and export an effect for GameMaker")
    exp_p.add_argument("effect_id", help="Effect id (e.g. ice/frost-nova, melee/sword-slash, fire/torch)")
    exp_p.add_argument("--output", "-o", default=None, help="Output destination folder")
    exp_p.add_argument("--palette", "-p", nargs="+", help="Hex color ramp from dark to bright")
    exp_p.add_argument("--flip", action="store_true", help="Mirror horizontally (face left)")
    exp_p.add_argument("--raw-sheet", action="store_true", help="Export raw grid sheet instead of GameMaker strip")

    # new
    new_p = subparsers.add_parser("new", help="Create a new procedural effect draft")
    new_p.add_argument("name", help="Effect category/name (e.g. arcane/my-blast)")
    new_p.add_argument("--loop", action="store_true", help="Create a looping effect")

    args = parser.parse_args()

    if args.command == "list":
        list_effects(args.query)
    elif args.command == "export":
        out_dir = Path(args.output) if args.output else None
        render_and_export(args.effect_id, output_dir=out_dir, gamemaker_strip=not args.raw_sheet, palette=args.palette, flip=args.flip)
    elif args.command == "new":
        cmd = ["tools/new.mjs", args.name]
        if args.loop:
            cmd.append("--loop")
        res = run_node_cmd(cmd)
        print(res.stdout.strip())
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
