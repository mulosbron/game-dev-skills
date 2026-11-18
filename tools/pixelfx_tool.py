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
CATALOG_FILE = WORKSPACE_ROOT / "catalogs" / "pixelfx_catalog.json"

def run_node_cmd(cmd_args: list) -> subprocess.CompletedProcess:
    if not PIXELFX_DIR.exists():
        print(f"Error: PixelFX repository not found at {PIXELFX_DIR}")
        sys.exit(1)
    
    full_cmd = ["node"] + cmd_args
    return subprocess.run(full_cmd, cwd=str(PIXELFX_DIR), capture_output=True, text=True, encoding="utf-8")


def build_pixelfx_catalog(verbose: bool = True) -> dict:
    """Extracts metadata for all PixelFX procedural effects into catalogs/pixelfx_catalog.json."""
    js = """
import { allIds, loadEffect } from "./tools/lib/fxlib.mjs";
const out = [];
for (const id of allIds()) {
  try {
    const e = await loadEffect(id);
    const m = e.meta || {};
    out.push({
      id,
      category: id.includes("/") ? id.split("/")[0] : "general",
      name: m.name || id,
      desc: m.desc || "",
      tags: Array.isArray(m.tags) ? m.tags : [],
      duration: m.duration,
      fps: m.fps,
      loop: Boolean(m.loop),
      size: m.size || [],
      origin: m.origin || [],
      actor: m.actor ?? null,
      bg: m.bg || "",
      palette: (m.options && Array.isArray(m.options.palette)) ? m.options.palette : []
    });
  } catch {}
}
console.log(JSON.stringify(out));
"""
    res = run_node_cmd(["--input-type=module", "-e", js])
    if res.returncode != 0:
        raise RuntimeError(f"Failed to extract PixelFX catalog: {res.stderr}")

    effects = json.loads(res.stdout)
    categories = {}
    tags = {}
    for fx in effects:
        cat = fx.get("category", "general")
        categories[cat] = categories.get(cat, 0) + 1
        for t in fx.get("tags", []):
            tags[t] = tags.get(t, 0) + 1

    catalog = {
        "repository": "com.github.patch-gg.pixelfx",
        "total_effects": len(effects),
        "total_categories": len(categories),
        "categories": dict(sorted(categories.items(), key=lambda x: -x[1])),
        "tags": dict(sorted(tags.items(), key=lambda x: -x[1])),
        "effects": effects,
    }

    CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"Built PixelFX catalog: {len(effects)} effects across {len(categories)} categories -> {CATALOG_FILE}")
    return catalog


def load_pixelfx_catalog() -> dict:
    if CATALOG_FILE.exists():
        try:
            return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return build_pixelfx_catalog(verbose=False)


def list_effects(query: str = "", category: str = None, tag: str = None, as_json: bool = False):
    try:
        catalog = load_pixelfx_catalog()
    except Exception:
        res = run_node_cmd(["tools/list.mjs", query] if query else ["tools/list.mjs"])
        if res.returncode == 0:
            print(res.stdout.strip())
        else:
            print(f"Error listing effects: {res.stderr}")
        return

    words = query.lower().split() if query else []
    cat_filter = category.lower() if category else None
    tag_filter = tag.lower() if tag else None
    matches = []

    for fx in catalog.get("effects", []):
        if cat_filter and fx.get("category", "").lower() != cat_filter:
            continue
        fx_tags = [t.lower() for t in fx.get("tags", [])]
        if tag_filter and tag_filter not in fx_tags:
            continue
        hay = " ".join([fx.get("id", ""), fx.get("name", ""), fx.get("desc", ""), fx.get("category", ""), *fx_tags]).lower()
        if all(w in hay for w in words):
            matches.append(fx)

    if as_json:
        print(json.dumps({"query": query, "category": category, "tag": tag, "count": len(matches), "effects": matches}, indent=2, ensure_ascii=False))
        return

    for m in matches:
        kind = f"{'loop' if m.get('loop') else 'once'} {m.get('duration', '')}s"
        sz = m.get("size", [0, 0])
        sz_str = f"{sz[0]}x{sz[1]}" if len(sz) >= 2 else ""
        actor_str = "actor  " if m.get("actor") else "       "
        print(f"{m['id']:30s} {kind:11s} {sz_str:8s} {actor_str}{m.get('desc', '')}")
    print(f"\n{len(matches)} effect{'s' if len(matches) == 1 else 's'}")


def list_categories(as_json: bool = False):
    catalog = load_pixelfx_catalog()
    cats = catalog.get("categories", {})
    if as_json:
        print(json.dumps({"total_effects": catalog.get("total_effects", 0), "categories": cats, "top_tags": dict(list(catalog.get("tags", {}).items())[:30])}, indent=2, ensure_ascii=False))
        return

    print(f"PixelFX Catalog ({catalog.get('total_effects', 0)} effects in {len(cats)} categories):")
    for c, n in cats.items():
        print(f"  {c:18s}: {n} effects")

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

    # index
    subparsers.add_parser("index", help="Build catalogs/pixelfx_catalog.json from PixelFX metadata")

    # categories
    cat_p = subparsers.add_parser("categories", help="List PixelFX effect categories")
    cat_p.add_argument("--json", action="store_true", help="Output JSON categories")

    # list
    list_p = subparsers.add_parser("list", help="Search or list available PixelFX effects")
    list_p.add_argument("query", nargs="?", default="", help="Search query (e.g. fire, slash, nova)")
    list_p.add_argument("--category", "-c", help="Filter by effect category (e.g. fire, arcane, melee)")
    list_p.add_argument("--tag", "-t", help="Filter by tag (e.g. loop, burst, directional)")
    list_p.add_argument("--json", action="store_true", help="Output JSON results")

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

    if args.command == "index":
        build_pixelfx_catalog(verbose=True)
    elif args.command == "categories":
        list_categories(as_json=args.json)
    elif args.command == "list":
        list_effects(args.query, category=args.category, tag=args.tag, as_json=args.json)
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
