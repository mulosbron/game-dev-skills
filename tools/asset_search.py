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

# Huge modular LPC character layer trees are indexed compactly in catalogs/lpc_catalog.json
SKIP_RAW_WALK_LIBS = {
    "com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator",
    "com.github.elizawy.lpc",
}

ALL_CATALOG_SOURCES = (
    "libraries",
    "lpc",
    "abo",
    "pixelfx",
    "atlas",
    "threejs",
    "polyspoon",
    "sand3d",
)

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

    for lib_entry in sorted(LIBRARIES_DIR.iterdir(), key=lambda p: p.name):
        if not lib_entry.is_dir() or lib_entry.name.startswith("."):
            continue

        lib_name = lib_entry.name
        if lib_name in SKIP_RAW_WALK_LIBS:
            libraries_summary[lib_name] = {
                "file_count": 0,
                "extensions": {},
                "indexed_via": "catalogs/lpc_catalog.json",
                "catalog_ref": "catalogs/lpc_catalog.json",
                "note": "Indexed by layer/sheet definition in lpc_catalog.json to keep assets_index.json compact",
            }
            continue

        lib_count = 0
        lib_exts = {}

        for root, dirs, files in os.walk(lib_entry):
            # Skip git internals and virtualenvs/caches
            for skip_dir in (".git", "__pycache__", ".venv", "node_modules"):
                if skip_dir in dirs:
                    dirs.remove(skip_dir)

            for file in sorted(files):
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
        json.dump(catalog_data, f, ensure_ascii=False, separators=(",", ":"))

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


def _load_json_safe(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _matches_tokens(text: str, tokens: List[str]) -> bool:
    hay = text.lower()
    return all(t in hay for t in tokens)


def search_catalog_source(
    source: str,
    query: str,
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    tokens = query.lower().split() if query else []
    cat_filter = category.lower() if category else None
    out: List[Dict[str, Any]] = []

    if source == "libraries":
        for item in search_assets(query, category=category, ext=ext, library=library, limit=limit):
            out.append({
                "source": "libraries",
                "name": item["name"],
                "category": item["category"],
                "library": item["library"],
                "path": item["path"],
                "ext": item["ext"],
                "size": item["size"],
            })
        return out

    if source == "lpc":
        data = _load_json_safe(CATALOG_DIR / "lpc_catalog.json") or {}
        for d in data.get("definitions", []):
            if cat_filter and d.get("category", "").lower() != cat_filter:
                continue
            hay = " ".join([d.get("id", ""), d.get("name", ""), d.get("category", ""), d.get("type_name", ""), " ".join(d.get("layer_paths", []))])
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "lpc",
                    "name": d.get("name") or d.get("id"),
                    "category": d.get("category", "lpc"),
                    "path": d.get("definition_file", ""),
                    "animations": d.get("animations", []),
                    "layer_paths": d.get("layer_paths", []),
                })
                if len(out) >= limit:
                    return out
        for p in data.get("parts", []):
            if cat_filter and p.get("category", "").lower() != cat_filter:
                continue
            hay = " ".join([p.get("part_path", ""), p.get("category", ""), " ".join(p.get("animations", []))])
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "lpc",
                    "name": p.get("part_path", ""),
                    "category": p.get("category", "lpc"),
                    "path": f"libraries/com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator/spritesheets/{p.get('part_path', '')}",
                    "animations": p.get("animations", []),
                })
                if len(out) >= limit:
                    return out
        return out

    if source == "abo":
        data = _load_json_safe(CATALOG_DIR / "abo_catalog.json") or {}
        for item in data.get("items", []):
            ptype = item.get("product_type", "")
            if cat_filter and ptype.lower() != cat_filter:
                continue
            hay = f"{item.get('id', '')} {item.get('name', '')} {ptype} {item.get('brand', '')}"
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "abo",
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "category": ptype,
                    "brand": item.get("brand"),
                    "size_cm": item.get("size_cm"),
                    "triangles": item.get("triangles"),
                    "license": "CC-BY-4.0",
                    "path": f"assets/com.amazon.berkeley.abo/models/{item.get('id')}.glb",
                })
                if len(out) >= limit:
                    return out
        return out

    if source == "pixelfx":
        data = _load_json_safe(CATALOG_DIR / "pixelfx_catalog.json") or {}
        for fx in data.get("effects", []):
            fx_cat = fx.get("category", "")
            if cat_filter and fx_cat.lower() != cat_filter:
                continue
            hay = " ".join([fx.get("id", ""), fx.get("name", ""), fx.get("desc", ""), fx_cat, " ".join(fx.get("tags", []))])
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "pixelfx",
                    "id": fx.get("id"),
                    "name": fx.get("name") or fx.get("id"),
                    "category": fx_cat,
                    "size": fx.get("size"),
                    "duration": fx.get("duration"),
                    "loop": fx.get("loop"),
                    "tags": fx.get("tags", []),
                    "path": f"libraries/com.github.patch-gg.pixelfx/src/{fx.get('id')}.mjs",
                })
                if len(out) >= limit:
                    return out
        return out

    if source == "atlas":
        data = _load_json_safe(CATALOG_DIR / "pixel_art_atlas_index.json") or {}
        cats = data.get("categories", {})
        for subject, meta in cats.items():
            if cat_filter and cat_filter not in subject.lower():
                continue
            if _matches_tokens(subject, tokens):
                out.append({
                    "source": "atlas",
                    "name": subject,
                    "category": "pixel-art-atlas",
                    "count": meta.get("count", 0) if isinstance(meta, dict) else 0,
                    "sample_ids": meta.get("sample_ids", [])[:5] if isinstance(meta, dict) else [],
                    "license": data.get("license", "CC0 1.0 Universal"),
                    "path": "assets/co.huggingface.angais.pixel-art-atlas-1.4m",
                })
                if len(out) >= limit:
                    return out
        return out

    if source == "threejs":
        data = _load_json_safe(CATALOG_DIR / "threejsassets_catalog.json") or []
        if isinstance(data, list):
            for item in data:
                hay = f"{item.get('slug', '')} {item.get('name', '')} {item.get('file_name', '')}"
                if _matches_tokens(hay, tokens):
                    out.append({
                        "source": "threejs",
                        "id": item.get("slug"),
                        "name": item.get("name"),
                        "category": "threejs-3d",
                        "license": item.get("license", "Free Commercial License"),
                        "model_url": item.get("model_url"),
                        "path": f"assets/com.threejsassets/models/{item.get('file_name', '')}",
                    })
                    if len(out) >= limit:
                        return out
        return out

    if source == "polyspoon":
        data = _load_json_safe(CATALOG_DIR / "polyspoon_catalog.json") or []
        if isinstance(data, list):
            for item in data:
                hay = f"{item.get('id', '')} {item.get('title', '')} {item.get('description', '')}"
                if _matches_tokens(hay, tokens):
                    out.append({
                        "source": "polyspoon",
                        "id": item.get("id"),
                        "name": item.get("title"),
                        "category": "procedural-3d",
                        "version": item.get("version"),
                        "presets": [p.get("id") for p in item.get("presets", [])],
                        "path": f".polyspoon/recipes/{item.get('id')}",
                    })
                    if len(out) >= limit:
                        return out
        return out

    if source == "sand3d":
        data = _load_json_safe(CATALOG_DIR / "sand3d_index.json") or {}
        for item in data.get("assets", []):
            fam = str(item.get("family", ""))
            if cat_filter and fam.lower() != cat_filter:
                continue
            hay = f"{item.get('id', '')} {fam} {item.get('source', '')} {item.get('entry_function', '')}"
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "sand3d",
                    "id": item.get("id"),
                    "name": item.get("entry_function") or item.get("id"),
                    "category": fam or item.get("source", "sand3d"),
                    "license": item.get("license", "CC-BY-4.0"),
                    "path": item.get("relative_path", ""),
                })
                if len(out) >= limit:
                    return out
        for prog in data.get("reference_programs", []):
            hay = f"{prog.get('id', '')} {prog.get('entry_function', '')} {prog.get('description', '')}"
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "sand3d",
                    "id": prog.get("id"),
                    "name": prog.get("id"),
                    "category": "reference_program",
                    "license": "Apache-2.0",
                    "path": prog.get("path", ""),
                })
                if len(out) >= limit:
                    return out
        for g in data.get("gallery_articulated_models", []):
            hay = f"{g.get('id', '')} {g.get('name', '')} {' '.join(g.get('joint_names', []))}"
            if _matches_tokens(hay, tokens):
                out.append({
                    "source": "sand3d",
                    "id": g.get("id"),
                    "name": g.get("name"),
                    "category": "articulated_gallery",
                    "n_joints": g.get("n_joints", 0),
                    "path": "libraries/com.github.sandflow-ai.sand3d/site/gallery.html",
                })
                if len(out) >= limit:
                    return out
        return out

    return out


def search_all_sources(
    query: str,
    source: str = "libraries",
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    if source != "all":
        return search_catalog_source(
            source, query, category=category, ext=ext, library=library, limit=limit
        )

    combined: List[Dict[str, Any]] = []
    per_source_cap = max(3, min(limit, max(5, limit // 2)))
    for src in ALL_CATALOG_SOURCES:
        if len(combined) >= limit:
            break
        remaining = limit - len(combined)
        hits = search_catalog_source(
            src,
            query,
            category=category,
            ext=ext,
            library=library,
            limit=min(per_source_cap, remaining),
        )
        combined.extend(hits)
    return combined[:limit]

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
    search_p = subparsers.add_parser("search", help="Search assets across libraries and catalogs")
    search_p.add_argument("query", nargs="?", default="", help="Keyword to search in filename, path, or metadata")
    search_p.add_argument("--category", "-c", help=f"Filter by category ({', '.join(CATEGORY_MAPPINGS.keys())} or catalog category)")
    search_p.add_argument("--ext", "-e", help="Filter by extension (png, wav, etc.)")
    search_p.add_argument("--library", "-l", help="Filter by library name (for libraries source)")
    search_p.add_argument(
        "--source", "-s",
        default="libraries",
        choices=["all", *ALL_CATALOG_SOURCES],
        help="Catalog source to search (default: libraries; use 'all' for unified cross-catalog search)",
    )
    search_p.add_argument("--limit", "-n", type=int, default=20, help="Max results to return")
    search_p.add_argument("--json", action="store_true", help="Output JSON results")

    # inspect command
    inspect_p = subparsers.add_parser("inspect", help="Inspect an image or sound asset")
    inspect_p.add_argument("path", help="Relative or absolute path to the asset file")

    # categories command
    subparsers.add_parser("categories", help="List available categories and counts")

    args = parser.parse_args()

    if args.command == "index":
        build_index(verbose=True)

    elif args.command == "search":
        res = search_all_sources(
            args.query,
            source=args.source,
            category=args.category,
            ext=args.ext,
            library=args.library,
            limit=args.limit,
        )
        if args.json:
            print(json.dumps({"query": args.query, "source": args.source, "count": len(res), "results": res}, indent=2, ensure_ascii=False))
        else:
            print(f"Found {len(res)} results (source={args.source}):")
            for r in res:
                if r.get("source") == "libraries":
                    print(f"- [{r['category']}] {r['name']} ({round(r['size']/1024, 1)} KB) -> {r['path']}")
                else:
                    label = r.get("id") or r.get("name")
                    print(f"- [{r['source']}:{r.get('category', '')}] {label} -> {r.get('path', '')}")

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
