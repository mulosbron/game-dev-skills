#!/usr/bin/env python3
"""
GameMaker & Pixel Asset Hub - Asset Search & Inspector Tool
Designed for AI agents and game developers to query, inspect, and index assets
across multiple libraries in the workspace without context overflow.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def _find_workspace_root() -> Path:
    curr = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "AGENTS.md").exists() or (parent / "libraries").exists():
            return parent
    return curr.parent

WORKSPACE_ROOT = _find_workspace_root()
LIBRARIES_DIR = WORKSPACE_ROOT / "libraries"
CATALOG_DIR = WORKSPACE_ROOT / "catalogs"
INDEX_FILE = CATALOG_DIR / "assets_index.json"

CATEGORY_MAPPINGS = {
    "buildings": ["building", "buildings", "建筑", "castle", "town", "dungeon", "house"],
    "interior": ["interior", "decoration", "室内", "decor", "furniture", "table", "chair", "bed"],
    "asset_packs": ["asset_packs", "套图", "bundle", "complete_pack"],
    "characters": ["character", "characters", "角色", "hero", "npc", "player", "enemy"],
    "creatures": ["creature", "creatures", "生物", "animal", "monster", "beast", "pet"],
    "weapons": ["weapon", "weapons", "武器", "sword", "armor", "shield", "bow"],
    "costumes": ["costume", "costumes", "服装", "apparel", "cloth"],
    "effects": ["effect", "effects", "特效", "skill_effect", "magic", "spell", "particle"],
    "icons": ["icon", "icons", "图标", "skill_icon", "ui_icon", "item_icon"],
    "sounds": ["sound", "sounds", "音效", "audio", "sfx", "bgm", "music", "wav", "mp3", "ogg"],
    "terrain": ["terrain", "地形", "tile", "tileset", "map", "ground", "grass", "water"],
    "ui": ["ui", "interface", "界面", "button", "hud", "bar", "frame", "window"],
    "other": ["other", "其他", "misc"]
}

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
SUPPORTED_AUDIO_EXTS = {".wav", ".ogg", ".mp3", ".flac"}
SUPPORTED_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_AUDIO_EXTS

def guess_category(relative_path: str) -> str:
    path_lower = relative_path.lower()
    for cat, keywords in CATEGORY_MAPPINGS.items():
        for kw in keywords:
            if kw in path_lower:
                return cat
    return "general"

def build_index(verbose: bool = True) -> Dict[str, Any]:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    if not LIBRARIES_DIR.exists():
        if verbose:
            print(f"Libraries directory not found: {LIBRARIES_DIR}")
        return {"total": 0, "libraries": {}, "items": []}

    items = []
    libraries_summary = {}

    if verbose:
        print(f"Scanning libraries in {LIBRARIES_DIR}...")

    for lib_entry in LIBRARIES_DIR.iterdir():
        if not lib_entry.is_dir() or lib_entry.name.startswith("."):
            continue

        lib_name = lib_entry.name
        lib_count = 0
        lib_exts = {}

        for root, dirs, files in os.walk(lib_entry):
            # Skip git internals
            if ".git" in dirs:
                dirs.remove(".git")

            for file in files:
                ext = Path(file).suffix.lower()
                if ext in SUPPORTED_EXTS:
                    full_path = Path(root) / file
                    rel_to_ws = full_path.relative_to(WORKSPACE_ROOT).as_posix()
                    rel_to_lib = full_path.relative_to(lib_entry).as_posix()
                    category = guess_category(rel_to_lib)
                    file_size = full_path.stat().st_size

                    item_data = {
                        "path": rel_to_ws,
                        "name": file,
                        "library": lib_name,
                        "category": category,
                        "ext": ext,
                        "size": file_size,
                    }
                    items.append(item_data)
                    lib_count += 1
                    lib_exts[ext] = lib_exts.get(ext, 0) + 1

        libraries_summary[lib_name] = {
            "file_count": lib_count,
            "extensions": lib_exts
        }

    catalog_data = {
        "total_assets": len(items),
        "libraries": libraries_summary,
        "items": items
    }

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"Index built successfully: {len(items)} assets cataloged.")
        print(f"Saved to: {INDEX_FILE}")

    return catalog_data

def load_or_build_index() -> Dict[str, Any]:
    if INDEX_FILE.exists():
        try:
            with open(INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return build_index(verbose=False)

def search_assets(query: str, category: Optional[str] = None, ext: Optional[str] = None, 
                  library: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
    catalog = load_or_build_index()
    results = []
    tokens = query.lower().split() if query else []

    for item in catalog.get("items", []):
        if category and item["category"] != category.lower():
            continue
        if ext:
            target_ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            if item["ext"] != target_ext:
                continue
        if library and item["library"].lower() != library.lower():
            continue

        item_text = (item["name"] + " " + item["path"] + " " + item["category"]).lower()
        if all(token in item_text for token in tokens):
            results.append(item)
            if len(results) >= limit:
                break

    return results

def inspect_asset(rel_or_abs_path: str) -> Dict[str, Any]:
    target = Path(rel_or_abs_path)
    if not target.is_absolute():
        target = WORKSPACE_ROOT / rel_or_abs_path
    target = target.resolve()

    if not target.exists():
        return {"error": f"File not found: {target.as_posix()}"}

    ext = target.suffix.lower()
    stat = target.stat()
    info = {
        "file": target.name,
        "path": target.relative_to(WORKSPACE_ROOT).as_posix() if target.is_relative_to(WORKSPACE_ROOT) else target.as_posix(),
        "size_bytes": stat.st_size,
        "size_kb": round(stat.st_size / 1024, 2),
        "extension": ext,
        "type": "image" if ext in SUPPORTED_IMAGE_EXTS else "audio" if ext in SUPPORTED_AUDIO_EXTS else "other",
    }

    if ext in SUPPORTED_IMAGE_EXTS and HAS_PIL:
        try:
            with Image.open(target) as img:
                info["width"] = img.width
                info["height"] = img.height
                info["format"] = img.format
                info["mode"] = img.mode
                info["is_animated"] = getattr(img, "is_animated", False)
                info["n_frames"] = getattr(img, "n_frames", 1)

                # GameMaker recommendations
                cat = guess_category(str(target))
                prefix = "spr_"
                if cat == "terrain":
                    prefix = "ts_"
                elif cat == "sounds":
                    prefix = "snd_"

                clean_stem = "".join(c if c.isalnum() or c == "_" else "_" for c in target.stem).lower()
                info["gamemaker_suggestion"] = {
                    "resource_type": "TileSet" if cat == "terrain" else "Sprite",
                    "resource_name": f"{prefix}{clean_stem}",
                    "suggested_origin": "Bottom-Center" if cat in ("characters", "creatures") else "Top-Left",
                    "tile_grid_estimates": [16, 24, 32, 48] if cat in ("terrain", "buildings") else None
                }
        except Exception as e:
            info["image_error"] = str(e)

    return info

def main():
    parser = argparse.ArgumentParser(description="Asset Search & Inspector for GameMaker / PixelSRPG-Forge")
    subparsers = parser.add_subparsers(dest="command")

    # index command
    subparsers.add_parser("index", help="Scan libraries/ and rebuild assets_index.json")

    # search command
    search_p = subparsers.add_parser("search", help="Search assets across libraries")
    search_p.add_argument("query", nargs="?", default="", help="Keyword to search in filename or path")
    search_p.add_argument("--category", "-c", help=f"Filter by category ({', '.join(CATEGORY_MAPPINGS.keys())})")
    search_p.add_argument("--ext", "-e", help="Filter by extension (png, wav, etc.)")
    search_p.add_argument("--library", "-l", help="Filter by library name (e.g. PixelSRPG-Forge)")
    search_p.add_argument("--limit", "-n", type=int, default=20, help="Max results to return")

    # inspect command
    inspect_p = subparsers.add_parser("inspect", help="Inspect an image or sound asset")
    inspect_p.add_argument("path", help="Relative or absolute path to the asset file")

    # categories command
    subparsers.add_parser("categories", help="List available categories and counts")

    args = parser.parse_args()

    if args.command == "index":
        build_index(verbose=True)

    elif args.command == "search":
        res = search_assets(args.query, category=args.category, ext=args.ext, library=args.library, limit=args.limit)
        print(f"Found {len(res)} results:")
        for r in res:
            print(f"- [{r['category']}] {r['name']} ({round(r['size']/1024, 1)} KB) -> {r['path']}")

    elif args.command == "inspect":
        info = inspect_asset(args.path)
        print(json.dumps(info, indent=2, ensure_ascii=False))

    elif args.command == "categories":
        cat = load_or_build_index()
        summary = {}
        for item in cat.get("items", []):
            c = item.get("category", "other")
            summary[c] = summary.get(c, 0) + 1
        print("Libraries summary:", json.dumps(cat.get("libraries", {}), indent=2, ensure_ascii=False))
        print("Asset counts by category:")
        for c, count in sorted(summary.items(), key=lambda x: -x[1]):
            print(f"  {c:15s}: {count} assets")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
