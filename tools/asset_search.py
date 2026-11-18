#!/usr/bin/env python3
"""
GameMaker & Pixel/3D Asset Hub - Unified Asset Search & Inspector Tool
Designed for AI agents and game developers to query, inspect, and index assets
across all 8 workspace catalogs without context overflow.
"""

import argparse
import html
import json
import os
import re
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

SOURCE_ALIASES = {
    "all": ALL_CATALOG_SOURCES,
    "2d": ("libraries", "lpc", "pixelfx", "atlas"),
    "3d": ("threejs", "polyspoon", "abo", "sand3d"),
}

SOURCE_METADATA = {
    "libraries": {
        "catalog": "catalogs/assets_index.json",
        "manager": "tools/asset_search.py",
        "dimension": "2d+audio",
        "license": "Mixed open licenses (see library LICENSES / CREDITS)",
        "aliases": ("libraries", "pixelsrpg", "opengameart", "lpc_starter"),
    },
    "lpc": {
        "catalog": "catalogs/lpc_catalog.json",
        "manager": "tools/lpc_character_builder.py",
        "dimension": "2d",
        "license": "CC-BY-SA 3.0/4.0, CC-BY 3.0/4.0, OGA-BY 3.0, CC0 1.0, GPL 3.0",
        "aliases": ("lpc", "liberatedpixelcup", "elizawy"),
    },
    "abo": {
        "catalog": "catalogs/abo_catalog.json",
        "manager": "tools/abo_manager.py",
        "dimension": "3d",
        "license": "CC-BY-4.0",
        "aliases": ("abo", "amazon", "com.amazon.berkeley.abo"),
    },
    "pixelfx": {
        "catalog": "catalogs/pixelfx_catalog.json",
        "manager": "tools/pixelfx_tool.py",
        "dimension": "2d",
        "license": "MIT / Open (com.github.patch-gg.pixelfx)",
        "aliases": ("pixelfx", "patch-gg", "com.github.patch-gg.pixelfx"),
    },
    "atlas": {
        "catalog": "catalogs/pixel_art_atlas_index.json",
        "manager": "tools/pixel_atlas_manager.py",
        "dimension": "2d",
        "license": "CC0 1.0 Universal",
        "aliases": ("atlas", "angais", "pixel-art-atlas", "co.huggingface.angais.pixel-art-atlas-1.4m"),
    },
    "threejs": {
        "catalog": "catalogs/threejsassets_catalog.json",
        "manager": "tools/threejsassets_manager.py",
        "dimension": "3d",
        "license": "Free Commercial License",
        "aliases": ("threejs", "threejsassets", "com.threejsassets"),
    },
    "polyspoon": {
        "catalog": "catalogs/polyspoon_catalog.json",
        "manager": "tools/polyspoon_tool.py",
        "dimension": "3d",
        "license": "Polyspoon Procedural Toolkit (local recipes)",
        "aliases": ("polyspoon", "ditlied", "com.github.ditlied.polyspoon"),
    },
    "sand3d": {
        "catalog": "catalogs/sand3d_index.json",
        "manager": "tools/sand3d_manager.py",
        "dimension": "3d",
        "license": "CC-BY-4.0 / CC0 / Apache-2.0",
        "aliases": ("sand3d", "sandflow", "co.huggingface.sandflow.sand3d", "com.github.sandflow-ai.sand3d"),
    },
}

SOURCE_COMPATIBLE_EXTS = {
    "lpc": {".png", ".json"},
    "abo": {".glb"},
    "pixelfx": {".mjs", ".png"},
    "atlas": {".png"},
    "threejs": {".glb"},
    "polyspoon": {".glb"},
    "sand3d": {".py", ".png", ".html", ".usda"},
}

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
    "other": ["other", "其他", "misc"],
}

SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
SUPPORTED_AUDIO_EXTS = {".wav", ".ogg", ".mp3", ".flac"}
SUPPORTED_3D_EXTS = {".glb"}
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"} | SUPPORTED_AUDIO_EXTS


def guess_category(relative_path: str) -> str:
    path_lower = relative_path.lower()
    for cat, keywords in CATEGORY_MAPPINGS.items():
        for kw in keywords:
            if kw in path_lower:
                return cat
    return "general"


def _resolve_sources(source_spec: Optional[str]) -> List[str]:
    """Resolves single sources, aliases ('all', '2d', '3d'), or comma-separated lists."""
    if not source_spec or not source_spec.strip():
        return ["libraries"]

    resolved: List[str] = []
    seen = set()
    valid_names = [*SOURCE_ALIASES.keys(), *ALL_CATALOG_SOURCES]

    for raw_part in source_spec.split(","):
        part = raw_part.strip().lower()
        if not part:
            raise ValueError(
                f"Empty source entry in '{source_spec}'. Valid sources: {', '.join(valid_names)}"
            )
        if part in SOURCE_ALIASES:
            targets = SOURCE_ALIASES[part]
        elif part in ALL_CATALOG_SOURCES:
            targets = (part,)
        else:
            raise ValueError(
                f"Unknown catalog source '{part}'. Valid sources: {', '.join(valid_names)}"
            )
        for src in targets:
            if src not in seen:
                seen.add(src)
                resolved.append(src)
    return resolved


def _tokenize_words(text: str) -> List[str]:
    return [w for w in re.split(r"[^a-z0-9]+", text.lower()) if w]


def _score_match(query: str, tokens: List[str], primary: str, category: str, hay: str) -> int:
    """Deterministic relevance score so exact and primary hits rank ahead of incidental mentions."""
    if not tokens:
        return 0

    q = query.strip().lower()
    p = primary.strip().lower()
    c = category.strip().lower()
    p_last = p.split("/")[-1]
    p_stem = Path(p_last).stem if "." in p_last else p_last
    p_words = set(_tokenize_words(p))

    score = 0
    if p == q:
        score += 120
    if p_stem == q or p_last == q:
        score += 100
    if c == q:
        score += 70
    if q and (p.startswith(q) or p_stem.startswith(q)):
        score += 50
    if p_words and all(t in p_words for t in tokens):
        score += 45
    if all(t in p for t in tokens):
        score += 30
    if score == 0:
        score += 10
    return score


def _matches_tokens(text: str, tokens: List[str]) -> bool:
    if not tokens:
        return True
    hay = text.lower()
    return all(t in hay for t in tokens)


def _matches_category(cat_value: str, cat_filter: Optional[str], exact_only: bool = False) -> bool:
    if not cat_filter:
        return True
    c_low = (cat_value or "").strip().lower()
    if c_low == cat_filter:
        return True
    if exact_only:
        return False
    if c_low.rstrip("s") == cat_filter.rstrip("s"):
        return True
    c_words = set(_tokenize_words(c_low))
    f_words = _tokenize_words(cat_filter)
    if f_words and all(w in c_words for w in f_words):
        return True
    return len(cat_filter) >= 3 and cat_filter in c_low


def _normalize_ext(ext: Optional[str]) -> Optional[str]:
    if not ext:
        return None
    e = ext.strip().lower()
    return e if e.startswith(".") else f".{e}"


def _matches_library_filter(source: str, library: Optional[str], item_library: str = "") -> bool:
    if not library:
        return True
    lib_low = library.strip().lower()
    if source == "libraries":
        return item_library.lower() == lib_low
    aliases = SOURCE_METADATA.get(source, {}).get("aliases", ())
    return lib_low in aliases


def _parse_threejs_item(item: Dict[str, Any]) -> Tuple[str, str]:
    raw_name = html.unescape(item.get("name", "") or "")
    if " 3D model: " in raw_name:
        cat, title = raw_name.split(" 3D model: ", 1)
        return cat.strip() or "threejs-3d", title.strip() or item.get("slug", "")
    return "threejs-3d", raw_name or item.get("slug", "")


def _load_json_safe(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_index(verbose: bool = True) -> Dict[str, Any]:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    if not LIBRARIES_DIR.exists():
        if verbose:
            print(f"Libraries directory not found: {LIBRARIES_DIR}")
        return {"total_assets": 0, "libraries": {}, "items": []}

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
        lib_exts: Dict[str, int] = {}

        for root, dirs, files in os.walk(lib_entry):
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

                    items.append({
                        "path": rel_to_ws,
                        "name": file,
                        "library": lib_name,
                        "category": category,
                        "ext": ext,
                        "size": file_size,
                    })
                    lib_count += 1
                    lib_exts[ext] = lib_exts.get(ext, 0) + 1

        libraries_summary[lib_name] = {
            "file_count": lib_count,
            "extensions": lib_exts,
        }

    catalog_data = {
        "total_assets": len(items),
        "libraries": libraries_summary,
        "items": items,
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


def _search_libraries_scored(
    query: str,
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> Tuple[int, List[Tuple[int, str, Dict[str, Any]]]]:
    catalog = load_or_build_index()
    tokens = query.lower().split() if query else []
    cat_filter = category.lower() if category else None
    target_ext = _normalize_ext(ext)
    scored: List[Tuple[int, str, Dict[str, Any]]] = []

    for item in catalog.get("items", []):
        if not _matches_category(item.get("category", ""), cat_filter, exact_only=True):
            continue
        if target_ext and item.get("ext") != target_ext:
            continue
        if not _matches_library_filter("libraries", library, item.get("library", "")):
            continue

        hay = f"{item['name']} {item['path']} {item['category']}"
        if _matches_tokens(hay, tokens):
            score = _score_match(query, tokens, item["name"], item["category"], hay)
            rec = {
                "source": "libraries",
                "id": Path(item["name"]).stem,
                "name": item["name"],
                "category": item["category"],
                "library": item["library"],
                "path": item["path"],
                "ext": item["ext"],
                "size": item["size"],
                "exists": True,
            }
            scored.append((score, item["name"], rec))

    total_hits = len(scored)
    if tokens:
        scored.sort(key=lambda x: (-x[0], len(x[1]), x[1].lower()))
    return total_hits, scored[:limit]


def search_assets(
    query: str,
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """Backward-compatible search against assets_index.json (libraries)."""
    _, top = _search_libraries_scored(query, category=category, ext=ext, library=library, limit=limit)
    return [entry[2] for entry in top]


def _load_abo_items() -> List[Dict[str, Any]]:
    data = _load_json_safe(CATALOG_DIR / "abo_catalog.json")
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    raw_jsonl = WORKSPACE_ROOT / "assets" / "com.amazon.berkeley.abo" / "catalog.jsonl"
    items: List[Dict[str, Any]] = []
    if raw_jsonl.exists():
        try:
            with open(raw_jsonl, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        items.append(json.loads(line))
        except Exception:
            pass
    return items


def _search_catalog_source_scored(
    source: str,
    query: str,
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> Tuple[int, List[Tuple[int, str, Dict[str, Any]]]]:
    if source == "libraries":
        return _search_libraries_scored(query, category=category, ext=ext, library=library, limit=limit)

    if not _matches_library_filter(source, library):
        return 0, []

    target_ext = _normalize_ext(ext)
    if target_ext and target_ext not in SOURCE_COMPATIBLE_EXTS.get(source, set()):
        return 0, []

    tokens = query.lower().split() if query else []
    cat_filter = category.strip().lower() if category else None
    scored: List[Tuple[int, str, Dict[str, Any]]] = []

    if source == "lpc":
        data = _load_json_safe(CATALOG_DIR / "lpc_catalog.json") or {}
        if not target_ext or target_ext == ".json":
            for d in data.get("definitions", []):
                d_cat = d.get("category", "lpc")
                if not _matches_category(d_cat, cat_filter):
                    continue
                name = d.get("name") or d.get("id", "")
                hay = " ".join([
                    d.get("id", ""),
                    name,
                    d_cat,
                    d.get("type_name", ""),
                    " ".join(d.get("layer_paths", [])),
                ])
                if _matches_tokens(hay, tokens):
                    score = _score_match(query, tokens, name, d_cat, hay)
                    scored.append((score, name, {
                        "source": "lpc",
                        "kind": "definition",
                        "id": d.get("id"),
                        "name": name,
                        "category": d_cat,
                        "path": d.get("definition_file", ""),
                        "animations": d.get("animations", []),
                        "layer_paths": d.get("layer_paths", []),
                    }))
        if not target_ext or target_ext == ".png":
            for p in data.get("parts", []):
                p_cat = p.get("category", "lpc")
                if not _matches_category(p_cat, cat_filter):
                    continue
                part_path = p.get("part_path", "")
                hay = " ".join([part_path, p_cat, " ".join(p.get("animations", []))])
                if _matches_tokens(hay, tokens):
                    score = _score_match(query, tokens, part_path, p_cat, hay)
                    scored.append((score, part_path, {
                        "source": "lpc",
                        "kind": "part",
                        "id": part_path,
                        "name": part_path,
                        "category": p_cat,
                        "path": f"libraries/com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator/spritesheets/{part_path}",
                        "animations": p.get("animations", []),
                    }))

    elif source == "abo":
        for item in _load_abo_items():
            ptype = item.get("product_type", "")
            if not _matches_category(ptype, cat_filter):
                continue
            item_id = item.get("id", "")
            name = item.get("name") or item_id
            hay = f"{item_id} {name} {ptype} {item.get('brand', '')}"
            if _matches_tokens(hay, tokens):
                rel_path = f"assets/com.amazon.berkeley.abo/models/{item_id}.glb"
                primary = item_id if query.strip().upper() == item_id.upper() else name
                score = _score_match(query, tokens, primary, ptype, hay)
                scored.append((score, primary, {
                    "source": "abo",
                    "id": item_id,
                    "name": name,
                    "category": ptype,
                    "brand": item.get("brand"),
                    "size_cm": item.get("size_cm"),
                    "triangles": item.get("triangles"),
                    "license": "CC-BY-4.0",
                    "installed": (WORKSPACE_ROOT / rel_path).exists(),
                    "path": rel_path,
                }))

    elif source == "pixelfx":
        data = _load_json_safe(CATALOG_DIR / "pixelfx_catalog.json") or {}
        for fx in data.get("effects", []):
            fx_cat = fx.get("category", "")
            if not _matches_category(fx_cat, cat_filter):
                continue
            fx_id = fx.get("id", "")
            fx_name = fx.get("name") or fx_id
            hay = " ".join([fx_id, fx_name, fx.get("desc", ""), fx_cat, " ".join(fx.get("tags", []))])
            if _matches_tokens(hay, tokens):
                primary = fx_id if "/" in query else fx_name
                score = _score_match(query, tokens, primary, fx_cat, hay)
                scored.append((score, primary, {
                    "source": "pixelfx",
                    "id": fx_id,
                    "name": fx_name,
                    "category": fx_cat,
                    "size": fx.get("size"),
                    "duration": fx.get("duration"),
                    "loop": fx.get("loop"),
                    "tags": fx.get("tags", []),
                    "path": f"libraries/com.github.patch-gg.pixelfx/src/{fx_id}.mjs",
                }))

    elif source == "atlas":
        data = _load_json_safe(CATALOG_DIR / "pixel_art_atlas_index.json") or {}
        cats = data.get("categories", {})
        for subject, meta in cats.items():
            if cat_filter and cat_filter != "pixel-art-atlas" and not _matches_category(subject, cat_filter):
                continue
            if _matches_tokens(subject, tokens):
                score = _score_match(query, tokens, subject, "pixel-art-atlas", subject)
                scored.append((score, subject, {
                    "source": "atlas",
                    "id": subject,
                    "name": subject,
                    "category": "pixel-art-atlas",
                    "count": meta.get("count", 0) if isinstance(meta, dict) else 0,
                    "sample_ids": meta.get("sample_ids", [])[:5] if isinstance(meta, dict) else [],
                    "license": data.get("license", "CC0 1.0 Universal"),
                    "path": "assets/co.huggingface.angais.pixel-art-atlas-1.4m",
                }))

    elif source == "threejs":
        data = _load_json_safe(CATALOG_DIR / "threejsassets_catalog.json") or []
        if isinstance(data, list):
            for item in data:
                cat, title = _parse_threejs_item(item)
                if not _matches_category(cat, cat_filter):
                    continue
                slug = item.get("slug", "")
                file_name = item.get("file_name", "")
                hay = f"{slug} {title} {cat} {item.get('name', '')} {file_name}"
                if _matches_tokens(hay, tokens):
                    rel_path = f"assets/com.threejsassets/models/{file_name}"
                    primary = slug if slug == query.strip().lower() else title
                    score = _score_match(query, tokens, primary, cat, hay)
                    scored.append((score, primary, {
                        "source": "threejs",
                        "id": slug,
                        "name": title,
                        "category": cat,
                        "license": item.get("license", "Free Commercial License"),
                        "installed": (WORKSPACE_ROOT / rel_path).exists(),
                        "model_url": item.get("model_url"),
                        "path": rel_path,
                    }))

    elif source == "polyspoon":
        data = _load_json_safe(CATALOG_DIR / "polyspoon_catalog.json") or []
        if isinstance(data, list):
            for item in data:
                if cat_filter and not _matches_category("procedural-3d", cat_filter) and not _matches_tokens(
                    f"{item.get('id', '')} {item.get('title', '')} {item.get('description', '')}",
                    [cat_filter],
                ):
                    continue
                pid = item.get("id", "")
                title = item.get("title") or pid
                presets = item.get("presets", [])
                preset_text = " ".join(
                    f"{p.get('id', '')} {p.get('name', '')} {p.get('description', '')}" for p in presets
                )
                hay = f"{pid} {title} {item.get('description', '')} {preset_text}"
                if _matches_tokens(hay, tokens):
                    primary = pid if pid == query.strip().lower() else title
                    score = _score_match(query, tokens, primary, "procedural-3d", hay)
                    scored.append((score, primary, {
                        "source": "polyspoon",
                        "id": pid,
                        "name": title,
                        "category": "procedural-3d",
                        "version": item.get("version"),
                        "presets": [p.get("id") for p in presets],
                        "path": f".polyspoon/recipes/{pid}",
                    }))

    elif source == "sand3d":
        data = _load_json_safe(CATALOG_DIR / "sand3d_index.json") or {}
        seen_ids = set()

        for item in data.get("assets", []):
            fam = str(item.get("family", "") or item.get("source", "sand3d"))
            if not _matches_category(fam, cat_filter):
                continue
            item_id = item.get("id", "")
            entry_fn = item.get("entry_function") or item_id
            hay = f"{item_id} {fam} {item.get('source', '')} {entry_fn}"
            if _matches_tokens(hay, tokens):
                seen_ids.add(item_id)
                primary = f"{entry_fn} {item_id}" if entry_fn != item_id else item_id
                score = _score_match(query, tokens, primary, fam, hay)
                scored.append((score, entry_fn, {
                    "source": "sand3d",
                    "kind": "local_asset",
                    "id": item_id,
                    "name": entry_fn,
                    "category": fam,
                    "license": item.get("license", "CC-BY-4.0"),
                    "path": item.get("relative_path", ""),
                }))

        for prog in data.get("reference_programs", []):
            if not _matches_category("reference_program", cat_filter) and (
                not cat_filter or not _matches_tokens(prog.get("description", ""), [cat_filter])
            ):
                continue
            pid = prog.get("id", "")
            pname = prog.get("name", pid)
            funcs = prog.get("functions", [])
            hay = f"{pid} {pname} {prog.get('entry_function', '')} {prog.get('description', '')} {' '.join(funcs)}"
            if _matches_tokens(hay, tokens):
                seen_ids.add(pid)
                score = _score_match(query, tokens, pname, "reference_program", hay)
                scored.append((score, pname, {
                    "source": "sand3d",
                    "kind": "reference_program",
                    "id": pid,
                    "name": pname,
                    "category": "reference_program",
                    "license": prog.get("license", "Apache-2.0"),
                    "path": prog.get("path", ""),
                }))

        for g in data.get("gallery_articulated_models", []):
            if not _matches_category("articulated_gallery", cat_filter) and (
                not cat_filter or not _matches_tokens(g.get("name", ""), [cat_filter])
            ):
                continue
            gid = g.get("id", "")
            gname = g.get("name", gid)
            parts_txt = " ".join(g.get("part_names", []))
            joints_txt = " ".join(g.get("joint_names", []))
            hay = f"{gid} {gname} {parts_txt} {joints_txt}"
            if _matches_tokens(hay, tokens):
                seen_ids.add(gid)
                score = _score_match(query, tokens, gname, "articulated_gallery", hay)
                scored.append((score, gname, {
                    "source": "sand3d",
                    "kind": "articulated_gallery",
                    "id": gid,
                    "name": gname,
                    "category": "articulated_gallery",
                    "n_joints": g.get("n_joints", 0),
                    "license": g.get("license", "Apache-2.0 / CC-BY-4.0"),
                    "path": "libraries/com.github.sandflow-ai.sand3d/site/gallery.html",
                }))

        cache = _load_json_safe(CATALOG_DIR / "sand3d_search_cache.json") or {}
        cache_candidates: List[Dict[str, Any]] = []
        if isinstance(cache.get("matches"), list):
            cache_candidates.extend(cache["matches"])
        for q_entry in (cache.get("queries") or {}).values():
            if isinstance(q_entry, dict) and isinstance(q_entry.get("matches"), list):
                cache_candidates.extend(q_entry["matches"])

        for citem in cache_candidates:
            cid = citem.get("id", "")
            if not cid or cid in seen_ids:
                continue
            fam = str(citem.get("family", "") or "sand3d")
            if not _matches_category(fam, cat_filter):
                continue
            entry_fn = citem.get("entry") or cid
            hay = f"{cid} {entry_fn} {fam} {citem.get('attribution', '')}"
            if _matches_tokens(hay, tokens):
                seen_ids.add(cid)
                score = _score_match(query, tokens, entry_fn, fam, hay)
                scored.append((score, entry_fn, {
                    "source": "sand3d",
                    "kind": "cached_remote",
                    "id": cid,
                    "name": entry_fn,
                    "category": fam,
                    "license": citem.get("license", "CC-BY-4.0"),
                    "dataset": citem.get("dataset", ""),
                    "path": citem.get("usda_path", ""),
                }))

    total_hits = len(scored)
    if tokens:
        scored.sort(key=lambda x: (-x[0], len(x[1]), x[1].lower()))
    return total_hits, scored[:limit]


def search_catalog_source(
    source: str,
    query: str,
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    _, top = _search_catalog_source_scored(
        source, query, category=category, ext=ext, library=library, limit=limit
    )
    return [entry[2] for entry in top]


def search_unified(
    query: str,
    source: str = "libraries",
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    """Searches one or more sources with relevance ranking and fair round-robin interleaving."""
    sources = _resolve_sources(source)

    if len(sources) == 1:
        src = sources[0]
        total_hits, scored = _search_catalog_source_scored(
            src, query, category=category, ext=ext, library=library, limit=limit
        )
        results = [entry[2] for entry in scored]
        return {
            "query": query,
            "source": source,
            "sources_searched": sources,
            "count": len(results),
            "by_source": {src: len(results)} if results else {},
            "total_matches_by_source": {src: total_hits},
            "results": results,
        }

    scored_by_src: Dict[str, List[Tuple[int, str, Dict[str, Any]]]] = {}
    total_by_src: Dict[str, int] = {}
    for src in sources:
        total_hits, hits = _search_catalog_source_scored(
            src, query, category=category, ext=ext, library=library, limit=limit
        )
        total_by_src[src] = total_hits
        if hits:
            scored_by_src[src] = hits

    active_sources = [src for src in sources if src in scored_by_src]
    active_sources.sort(key=lambda s: (-scored_by_src[s][0][0], sources.index(s)))

    combined: List[Dict[str, Any]] = []
    by_source: Dict[str, int] = {}
    idx = 0
    while len(combined) < limit:
        added_this_round = False
        for src in active_sources:
            hits = scored_by_src[src]
            if idx < len(hits):
                rec = hits[idx][2]
                combined.append(rec)
                by_source[src] = by_source.get(src, 0) + 1
                added_this_round = True
                if len(combined) >= limit:
                    break
        if not added_this_round:
            break
        idx += 1

    return {
        "query": query,
        "source": source,
        "sources_searched": sources,
        "count": len(combined),
        "by_source": by_source,
        "total_matches_by_source": total_by_src,
        "results": combined,
    }


def search_all_sources(
    query: str,
    source: str = "libraries",
    category: Optional[str] = None,
    ext: Optional[str] = None,
    library: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    return search_unified(
        query,
        source=source,
        category=category,
        ext=ext,
        library=library,
        limit=limit,
    )["results"]


def _inspect_glb_file(target: Path) -> Dict[str, Any]:
    """Parses glTF 2.0 binary header and JSON chunk for quick 3D model inspection."""
    info: Dict[str, Any] = {}
    try:
        with open(target, "rb") as f:
            header = f.read(12)
            if len(header) < 12:
                return {"glb_error": "File too short for GLB header"}
            magic, version, total_length = struct.unpack("<III", header)
            if magic != 0x46546C67:  # 'glTF'
                return {"glb_error": "Invalid GLB magic header"}
            info["gltf_version"] = version
            info["glb_declared_bytes"] = total_length

            chunk_hdr = f.read(8)
            if len(chunk_hdr) == 8:
                chunk_len, chunk_type = struct.unpack("<II", chunk_hdr)
                if chunk_type == 0x4E4F534A:  # 'JSON'
                    raw_json = f.read(chunk_len).decode("utf-8", errors="replace").rstrip("\x00 ")
                    gltf = json.loads(raw_json)
                    accessors = gltf.get("accessors", [])
                    meshes = gltf.get("meshes", [])
                    materials = gltf.get("materials", [])
                    animations = gltf.get("animations", [])

                    total_primitives = 0
                    total_vertices = 0
                    for mesh in meshes:
                        for prim in mesh.get("primitives", []):
                            total_primitives += 1
                            pos_idx = (prim.get("attributes") or {}).get("POSITION")
                            if isinstance(pos_idx, int) and 0 <= pos_idx < len(accessors):
                                total_vertices += int(accessors[pos_idx].get("count", 0))

                    info["asset"] = gltf.get("asset", {})
                    info["scenes_count"] = len(gltf.get("scenes", []))
                    info["nodes_count"] = len(gltf.get("nodes", []))
                    info["meshes_count"] = len(meshes)
                    info["primitives_count"] = total_primitives
                    info["vertices_count"] = total_vertices
                    info["materials_count"] = len(materials)
                    info["textures_count"] = len(gltf.get("textures", []))
                    info["images_count"] = len(gltf.get("images", []))
                    info["animations_count"] = len(animations)
                    info["skins_count"] = len(gltf.get("skins", []))
                    if meshes:
                        info["mesh_names"] = [m.get("name", f"mesh_{i}") for i, m in enumerate(meshes[:10])]
                    if materials:
                        info["material_names"] = [m.get("name", f"mat_{i}") for i, m in enumerate(materials[:10])]
                    if animations:
                        info["animation_names"] = [a.get("name", f"anim_{i}") for i, a in enumerate(animations[:10])]
    except Exception as e:
        info["glb_error"] = str(e)
    return info


def _inspect_audio_file(target: Path, ext: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {}
    if ext == ".wav":
        try:
            with wave.open(str(target), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                rate = wf.getframerate()
                frames = wf.getnframes()
                info["channels"] = channels
                info["sample_width_bytes"] = sample_width
                info["bit_depth"] = sample_width * 8
                info["sample_rate"] = rate
                info["frame_count"] = frames
                info["duration_sec"] = round(frames / float(rate), 3) if rate else 0.0
        except Exception as e:
            info["audio_error"] = str(e)
    return info


def _lookup_catalog_entry(target_or_id: str, source: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Looks up an item by ID, slug, subject, or workspace-relative path across catalogs."""
    sources = _resolve_sources(source) if source else list(ALL_CATALOG_SOURCES)
    key = target_or_id.strip()
    key_norm = key.replace("\\", "/").lstrip("./").lower()
    key_stem = Path(key_norm).stem if "." in Path(key_norm).name else key_norm

    for src in sources:
        if src == "polyspoon":
            data = _load_json_safe(CATALOG_DIR / "polyspoon_catalog.json") or []
            for item in data:
                pid = str(item.get("id", ""))
                if pid.lower() == key_norm or f".polyspoon/recipes/{pid}".lower() == key_norm:
                    return {
                        "source": "polyspoon",
                        "matched_by": "exact_id",
                        "id": pid,
                        "name": item.get("title", pid),
                        "version": item.get("version"),
                        "description": item.get("description", ""),
                        "presets": item.get("presets", []),
                        "controls_count": len(item.get("controls", [])),
                        "controls": [
                            {
                                "key": c.get("key"),
                                "label": c.get("label"),
                                "kind": c.get("kind"),
                                "default": c.get("default"),
                                "min": c.get("min"),
                                "max": c.get("max"),
                            }
                            for c in item.get("controls", [])
                        ],
                        "palettes": item.get("palettes", []),
                        "build_command": f"python tools/polyspoon_tool.py build --family {pid} --json",
                    }

        elif src == "abo":
            for item in _load_abo_items():
                iid = str(item.get("id", ""))
                rel = f"assets/com.amazon.berkeley.abo/models/{iid}.glb"
                if iid.lower() == key_norm or iid.lower() == key_stem or rel.lower() == key_norm:
                    local_glb = WORKSPACE_ROOT / rel
                    res: Dict[str, Any] = {
                        "source": "abo",
                        "matched_by": "exact_id",
                        **item,
                        "license": "CC-BY-4.0",
                        "installed": local_glb.exists(),
                        "path": rel,
                        "download_command": f"python tools/abo_manager.py download {iid}",
                    }
                    if local_glb.exists():
                        res["glb_inspection"] = _inspect_glb_file(local_glb)
                    return res

        elif src == "threejs":
            data = _load_json_safe(CATALOG_DIR / "threejsassets_catalog.json") or []
            for item in data:
                slug = str(item.get("slug", ""))
                rel = f"assets/com.threejsassets/models/{item.get('file_name', '')}"
                if slug.lower() == key_norm or slug.lower() == key_stem or rel.lower() == key_norm:
                    cat, title = _parse_threejs_item(item)
                    local_glb = WORKSPACE_ROOT / rel
                    res = {
                        "source": "threejs",
                        "matched_by": "exact_id",
                        "slug": slug,
                        "name": title,
                        "raw_name": item.get("name"),
                        "category": cat,
                        "license": item.get("license", "Free Commercial License"),
                        "model_url": item.get("model_url"),
                        "page_url": item.get("page_url"),
                        "installed": local_glb.exists(),
                        "path": rel,
                    }
                    if local_glb.exists():
                        res["glb_inspection"] = _inspect_glb_file(local_glb)
                    return res

        elif src == "pixelfx":
            data = _load_json_safe(CATALOG_DIR / "pixelfx_catalog.json") or {}
            for fx in data.get("effects", []):
                fx_id = str(fx.get("id", ""))
                rel = f"libraries/com.github.patch-gg.pixelfx/src/{fx_id}.mjs"
                if fx_id.lower() == key_norm or rel.lower() == key_norm or fx_id.split("/")[-1].lower() == key_norm:
                    return {
                        "source": "pixelfx",
                        "matched_by": "exact_id",
                        **fx,
                        "path": rel,
                        "export_command": f"python tools/pixelfx_tool.py export {fx_id}",
                    }

        elif src == "atlas":
            data = _load_json_safe(CATALOG_DIR / "pixel_art_atlas_index.json") or {}
            cats = data.get("categories", {})
            for subject, meta in cats.items():
                if subject.lower() == key_norm:
                    return {
                        "source": "atlas",
                        "matched_by": "exact_subject",
                        "subject": subject,
                        "count": meta.get("count", 0) if isinstance(meta, dict) else 0,
                        "sample_ids": meta.get("sample_ids", []) if isinstance(meta, dict) else [],
                        "license": data.get("license", "CC0 1.0 Universal"),
                        "path": "assets/co.huggingface.angais.pixel-art-atlas-1.4m",
                        "export_command": f'python tools/pixel_atlas_manager.py strip --subject "{subject}" --count 6 --scale 2',
                    }

        elif src == "lpc":
            data = _load_json_safe(CATALOG_DIR / "lpc_catalog.json") or {}
            for d in data.get("definitions", []):
                if d.get("id", "").lower() == key_norm or d.get("definition_file", "").lower() == key_norm:
                    return {"source": "lpc", "kind": "definition", "matched_by": "exact_id", **d}
            for p in data.get("parts", []):
                if p.get("part_path", "").lower() == key_norm:
                    return {"source": "lpc", "kind": "part", "matched_by": "exact_path", **p}

        elif src == "sand3d":
            data = _load_json_safe(CATALOG_DIR / "sand3d_index.json") or {}
            for item in data.get("assets", []):
                if item.get("id", "").lower() == key_norm or item.get("relative_path", "").lower() == key_norm:
                    return {"source": "sand3d", "kind": "local_asset", "matched_by": "exact_id", **item}
            for prog in data.get("reference_programs", []):
                if prog.get("id", "").lower() == key_norm or prog.get("path", "").lower() == key_norm:
                    return {"source": "sand3d", "kind": "reference_program", "matched_by": "exact_id", **prog}
            for g in data.get("gallery_articulated_models", []):
                if g.get("id", "").lower() == key_norm or g.get("name", "").lower() == key_norm:
                    return {"source": "sand3d", "kind": "articulated_gallery", "matched_by": "exact_id", **g}

    # Fallback: top-ranked search match in requested source(s)
    hits = search_all_sources(target_or_id, source=source or "all", limit=1)
    if hits:
        return {"matched_by": "search_top_hit", **hits[0]}
    return None


def inspect_asset(rel_or_abs_path: str, source: Optional[str] = None) -> Dict[str, Any]:
    target_cand = Path(rel_or_abs_path)
    if not target_cand.is_absolute():
        target_cand = WORKSPACE_ROOT / rel_or_abs_path
    target = target_cand.resolve()

    if target.exists() and not source:
        if target.is_dir():
            entries = sorted(p.name for p in target.iterdir())
            info: Dict[str, Any] = {
                "type": "directory",
                "name": target.name,
                "path": target.relative_to(WORKSPACE_ROOT).as_posix() if target.is_relative_to(WORKSPACE_ROOT) else target.as_posix(),
                "entries_count": len(entries),
                "entries": entries[:50],
            }
            meta_json = target / "metadata.json"
            if meta_json.exists():
                info["metadata"] = _load_json_safe(meta_json)
            return info

        ext = target.suffix.lower()
        stat = target.stat()
        rel_path = target.relative_to(WORKSPACE_ROOT).as_posix() if target.is_relative_to(WORKSPACE_ROOT) else target.as_posix()
        asset_type = (
            "image" if ext in SUPPORTED_IMAGE_EXTS
            else "audio" if ext in SUPPORTED_AUDIO_EXTS
            else "3d_model" if ext in SUPPORTED_3D_EXTS
            else "other"
        )
        info = {
            "file": target.name,
            "path": rel_path,
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "extension": ext,
            "type": asset_type,
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

                    cat = guess_category(str(target))
                    prefix = "ts_" if cat == "terrain" else "snd_" if cat == "sounds" else "spr_"
                    clean_stem = "".join(c if c.isalnum() or c == "_" else "_" for c in target.stem).lower()
                    info["gamemaker_suggestion"] = {
                        "resource_type": "TileSet" if cat == "terrain" else "Sprite",
                        "resource_name": f"{prefix}{clean_stem}",
                        "suggested_origin": "Bottom-Center" if cat in ("characters", "creatures") else "Top-Left",
                        "tile_grid_estimates": [16, 24, 32, 48] if cat in ("terrain", "buildings") else None,
                    }
            except Exception as e:
                info["image_error"] = str(e)
        elif ext in SUPPORTED_AUDIO_EXTS:
            info.update(_inspect_audio_file(target, ext))
        elif ext == ".glb":
            info.update(_inspect_glb_file(target))
            cat_meta = _lookup_catalog_entry(rel_path)
            if cat_meta and cat_meta.get("matched_by") == "exact_id":
                info["catalog_metadata"] = {
                    k: v for k, v in cat_meta.items() if k != "glb_inspection"
                }

        return info

    cat_hit = _lookup_catalog_entry(rel_or_abs_path, source=source)
    if cat_hit:
        return cat_hit

    return {"error": f"File or catalog entry not found: {rel_or_abs_path}"}


def collect_categories(source: str = "all") -> Dict[str, Any]:
    sources = _resolve_sources(source)
    out: Dict[str, Any] = {}

    for src in sources:
        if src == "libraries":
            cat = load_or_build_index()
            summary: Dict[str, int] = {}
            for item in cat.get("items", []):
                c = item.get("category", "other")
                summary[c] = summary.get(c, 0) + 1
            out["libraries"] = {
                "total_assets": cat.get("total_assets", len(cat.get("items", []))),
                "libraries": cat.get("libraries", {}),
                "by_category": dict(sorted(summary.items(), key=lambda x: -x[1])),
            }
        elif src == "lpc":
            data = _load_json_safe(CATALOG_DIR / "lpc_catalog.json") or {}
            def_cats: Dict[str, int] = {}
            for d in data.get("definitions", []):
                c = d.get("category", "general")
                def_cats[c] = def_cats.get(c, 0) + 1
            out["lpc"] = {
                "total_definitions": data.get("total_definitions", len(data.get("definitions", []))),
                "total_part_folders": data.get("total_part_folders", len(data.get("parts", []))),
                "definition_categories": dict(sorted(def_cats.items(), key=lambda x: -x[1])),
                "parts_by_category": data.get("parts_by_category", {}),
            }
        elif src == "abo":
            data = _load_json_safe(CATALOG_DIR / "abo_catalog.json") or {}
            out["abo"] = {
                "total_models": data.get("total_models", len(data.get("items", []))),
                "total_categories": data.get("total_categories", len(data.get("categories", {}))),
                "by_category": data.get("categories", {}),
            }
        elif src == "pixelfx":
            data = _load_json_safe(CATALOG_DIR / "pixelfx_catalog.json") or {}
            out["pixelfx"] = {
                "total_effects": data.get("total_effects", len(data.get("effects", []))),
                "by_category": data.get("categories", {}),
            }
        elif src == "atlas":
            data = _load_json_safe(CATALOG_DIR / "pixel_art_atlas_index.json") or {}
            cats = data.get("categories", {})
            top_subjects = {
                k: (v.get("count", 0) if isinstance(v, dict) else 0)
                for k, v in sorted(
                    cats.items(),
                    key=lambda kv: -(kv[1].get("count", 0) if isinstance(kv[1], dict) else 0),
                )[:25]
            }
            out["atlas"] = {
                "total_sprites": data.get("total_sprites", 0),
                "total_subjects": data.get("total_subjects", len(cats)),
                "top_subjects": top_subjects,
            }
        elif src == "threejs":
            data = _load_json_safe(CATALOG_DIR / "threejsassets_catalog.json") or []
            cats: Dict[str, int] = {}
            for item in data:
                c, _ = _parse_threejs_item(item)
                cats[c] = cats.get(c, 0) + 1
            out["threejs"] = {
                "total_models": len(data),
                "total_categories": len(cats),
                "by_category": dict(sorted(cats.items(), key=lambda x: -x[1])),
            }
        elif src == "polyspoon":
            data = _load_json_safe(CATALOG_DIR / "polyspoon_catalog.json") or []
            out["polyspoon"] = {
                "total_families": len(data),
                "by_category": {"procedural-3d": len(data)},
                "families": [item.get("id") for item in data],
            }
        elif src == "sand3d":
            data = _load_json_safe(CATALOG_DIR / "sand3d_index.json") or {}
            out["sand3d"] = {
                "total_3d_assets": data.get("total_3d_assets", len(data.get("assets", []))),
                "total_reference_programs": data.get("total_reference_programs", len(data.get("reference_programs", []))),
                "total_gallery_articulated_models": data.get(
                    "total_gallery_articulated_models", len(data.get("gallery_articulated_models", []))
                ),
                "sources_summary": data.get("sources_summary", {}),
                "families_summary": data.get("families_summary", {}),
            }

    return {"sources": sources, "categories": out}


def collect_sources_status() -> List[Dict[str, Any]]:
    statuses: List[Dict[str, Any]] = []
    for src in ALL_CATALOG_SOURCES:
        meta = SOURCE_METADATA[src]
        cat_rel = meta["catalog"]
        cat_path = WORKSPACE_ROOT / cat_rel
        exists = cat_path.exists()
        size_kb = round(cat_path.stat().st_size / 1024, 1) if exists else 0.0
        item_count = 0
        extra: Dict[str, Any] = {}

        data = _load_json_safe(cat_path) if exists else None
        if src == "libraries" and isinstance(data, dict):
            item_count = data.get("total_assets", len(data.get("items", [])))
            extra["libraries_count"] = len(data.get("libraries", {}))
        elif src == "lpc" and isinstance(data, dict):
            defs = data.get("total_definitions", len(data.get("definitions", [])))
            parts = data.get("total_part_folders", len(data.get("parts", [])))
            item_count = defs + parts
            extra["definitions"] = defs
            extra["part_folders"] = parts
            extra["spritesheet_pngs"] = data.get("total_spritesheet_pngs", 0)
        elif src == "abo" and isinstance(data, dict):
            item_count = data.get("total_models", len(data.get("items", [])))
        elif src == "pixelfx" and isinstance(data, dict):
            item_count = data.get("total_effects", len(data.get("effects", [])))
        elif src == "atlas" and isinstance(data, dict):
            item_count = data.get("total_subjects", len(data.get("categories", {})))
            extra["total_sprites"] = data.get("total_sprites", 0)
        elif src == "threejs" and isinstance(data, list):
            item_count = len(data)
        elif src == "polyspoon" and isinstance(data, list):
            item_count = len(data)
        elif src == "sand3d" and isinstance(data, dict):
            assets_n = data.get("total_3d_assets", len(data.get("assets", [])))
            progs_n = data.get("total_reference_programs", len(data.get("reference_programs", [])))
            gal_n = data.get("total_gallery_articulated_models", len(data.get("gallery_articulated_models", [])))
            item_count = assets_n + progs_n + gal_n
            extra["local_assets"] = assets_n
            extra["reference_programs"] = progs_n
            extra["gallery_models"] = gal_n

        entry: Dict[str, Any] = {
            "source": src,
            "dimension": meta["dimension"],
            "catalog_file": cat_rel,
            "exists": exists,
            "size_kb": size_kb,
            "item_count": item_count,
            "manager_tool": meta["manager"],
            "license": meta["license"],
        }
        entry.update(extra)
        statuses.append(entry)
    return statuses


INDEXABLE_SCRIPTS = {
    "lpc": ("tools/lpc_character_builder.py", ["index"]),
    "abo": ("tools/abo_manager.py", ["index"]),
    "pixelfx": ("tools/pixelfx_tool.py", ["index"]),
    "sand3d": ("tools/sand3d_manager.py", ["index"]),
}


def run_index_sources(source: str = "libraries", as_json: bool = False) -> Dict[str, Any]:
    targets = ["libraries", "lpc", "abo", "pixelfx", "sand3d"] if source == "all" else [source]
    results: Dict[str, Any] = {}

    for tgt in targets:
        if tgt == "libraries":
            data = build_index(verbose=not as_json)
            results["libraries"] = {
                "status": "ok",
                "total_assets": data.get("total_assets", 0),
                "catalog": "catalogs/assets_index.json",
            }
        elif tgt in INDEXABLE_SCRIPTS:
            script_rel, args_list = INDEXABLE_SCRIPTS[tgt]
            cmd = [sys.executable, str(WORKSPACE_ROOT / script_rel), *args_list]
            proc = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, encoding="utf-8")
            msg = (proc.stdout or proc.stderr or "").strip()
            if not as_json and msg:
                print(msg)
            results[tgt] = {
                "status": "ok" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "message": msg,
            }

    if as_json:
        print(json.dumps({"indexed": targets, "results": results}, indent=2, ensure_ascii=False))
    return results


def _print_search_plain(payload: Dict[str, Any]) -> None:
    res = payload["results"]
    by_src = payload.get("by_source", {})
    breakdown = ", ".join(f"{k}={v}" for k, v in by_src.items())
    header = f"Found {len(res)} results (source={payload['source']}"
    if breakdown and len(payload["sources_searched"]) > 1:
        header += f", breakdown: {breakdown}"
    header += "):"
    print(header)

    for r in res:
        src = r.get("source")
        if src == "libraries":
            print(f"- [libraries:{r['category']}] {r['name']} ({round(r['size'] / 1024, 1)} KB) -> {r['path']}")
        elif src == "atlas":
            print(f"- [atlas:pixel-art-atlas] {r['name']} ({r.get('count', 0)} sprites) -> {r.get('path', '')}")
        elif src == "threejs":
            status = "installed" if r.get("installed") else "remote"
            print(f"- [threejs:{r.get('category', '')}] {r.get('name')} ({r.get('id')}, {status}) -> {r.get('path', '')}")
        elif src == "abo":
            status = "installed" if r.get("installed") else "available"
            print(f"- [abo:{r.get('category', '')}] {r.get('id')}: {r.get('name')} ({status}) -> {r.get('path', '')}")
        elif src == "polyspoon":
            presets = ",".join(r.get("presets", []))
            print(f"- [polyspoon:{r.get('id')}] {r.get('name')} (presets: {presets}) -> {r.get('path', '')}")
        elif src == "pixelfx":
            print(f"- [pixelfx:{r.get('category', '')}] {r.get('id')} -> {r.get('path', '')}")
        else:
            label = r.get("name") or r.get("id")
            print(f"- [{src}:{r.get('category', '')}] {label} -> {r.get('path', '')}")


def _print_categories_plain(data: Dict[str, Any]) -> None:
    cats = data["categories"]
    if data["sources"] == ["libraries"] and "libraries" in cats:
        lib_data = cats["libraries"]
        print("Libraries summary:", json.dumps(lib_data.get("libraries", {}), indent=2, ensure_ascii=False))
        print("Asset counts by category:")
        for c, count in lib_data.get("by_category", {}).items():
            print(f"  {c:15s}: {count} assets")
        return

    for src in data["sources"]:
        info = cats.get(src, {})
        print(f"\n[{src}]")
        if src == "libraries":
            print(f"  total_assets: {info.get('total_assets', 0)}")
            for c, cnt in info.get("by_category", {}).items():
                print(f"  {c:18s}: {cnt}")
        elif src == "lpc":
            print(f"  definitions: {info.get('total_definitions', 0)}, part_folders: {info.get('total_part_folders', 0)}")
            for c, cnt in list(info.get("parts_by_category", {}).items())[:15]:
                print(f"  {c:18s}: {cnt} part folders")
        elif src == "abo":
            print(f"  total_models: {info.get('total_models', 0)}, categories: {info.get('total_categories', 0)}")
            for c, cnt in list(info.get("by_category", {}).items())[:15]:
                print(f"  {c:24s}: {cnt}")
        elif src == "pixelfx":
            print(f"  total_effects: {info.get('total_effects', 0)}")
            for c, cnt in info.get("by_category", {}).items():
                print(f"  {c:18s}: {cnt}")
        elif src == "atlas":
            print(f"  total_sprites: {info.get('total_sprites', 0):,}, total_subjects: {info.get('total_subjects', 0):,}")
            for subj, cnt in list(info.get("top_subjects", {}).items())[:10]:
                print(f"  {subj:24s}: {cnt} sprites")
        elif src == "threejs":
            print(f"  total_models: {info.get('total_models', 0)}, categories: {info.get('total_categories', 0)}")
            for c, cnt in list(info.get("by_category", {}).items())[:15]:
                print(f"  {c:24s}: {cnt}")
        elif src == "polyspoon":
            print(f"  total_families: {info.get('total_families', 0)} -> {', '.join(info.get('families', []))}")
        elif src == "sand3d":
            print(
                f"  local_assets: {info.get('total_3d_assets', 0)}, "
                f"reference_programs: {info.get('total_reference_programs', 0)}, "
                f"gallery_models: {info.get('total_gallery_articulated_models', 0)}"
            )


def main():
    parser = argparse.ArgumentParser(description="Unified Asset Search & Inspector across all workspace catalogs")
    subparsers = parser.add_subparsers(dest="command")

    # index command
    index_p = subparsers.add_parser("index", help="Build or rebuild catalog indexes")
    index_p.add_argument(
        "--source", "-s",
        default="libraries",
        choices=["all", "libraries", "lpc", "abo", "pixelfx", "sand3d"],
        help="Catalog index to rebuild (default: libraries)",
    )
    index_p.add_argument("--json", action="store_true", help="Output JSON summary")

    # search command
    search_p = subparsers.add_parser("search", help="Search assets across libraries and catalogs")
    search_p.add_argument("query", nargs="?", default="", help="Keyword to search in filename, path, or metadata")
    search_p.add_argument("--category", "-c", help=f"Filter by category ({', '.join(CATEGORY_MAPPINGS.keys())} or catalog category)")
    search_p.add_argument("--ext", "-e", help="Filter by extension (png, wav, glb, etc.)")
    search_p.add_argument("--library", "-l", help="Filter by library name (or source reverse-DNS id)")
    search_p.add_argument(
        "--source", "-s",
        default="libraries",
        help=(
            "Catalog source to search: libraries (default), lpc, abo, pixelfx, atlas, threejs, "
            "polyspoon, sand3d, group aliases (all, 2d, 3d), or comma-separated lists (e.g. threejs,abo)"
        ),
    )
    search_p.add_argument("--limit", "-n", type=int, default=20, help="Max results to return")
    search_p.add_argument("--json", action="store_true", help="Output JSON results")

    # inspect command
    inspect_p = subparsers.add_parser("inspect", help="Inspect a local asset file (PNG/WAV/GLB) or catalog item ID")
    inspect_p.add_argument("path", help="Relative/absolute file path or catalog item ID/slug/subject")
    inspect_p.add_argument("--source", "-s", default=None, help="Optional catalog source hint for ID lookup")
    inspect_p.add_argument("--json", action="store_true", help="Output JSON metadata (always JSON)")

    # categories command
    cat_p = subparsers.add_parser("categories", help="List available categories and counts")
    cat_p.add_argument("--source", "-s", default="all", help="Source(s) to summarize (default: all)")
    cat_p.add_argument("--json", action="store_true", help="Output JSON category summary")

    # sources command
    src_p = subparsers.add_parser("sources", help="List all catalog sources, file counts, and CLI managers")
    src_p.add_argument("--json", action="store_true", help="Output JSON source status")

    args = parser.parse_args()

    try:
        if args.command == "index":
            run_index_sources(source=args.source, as_json=args.json)

        elif args.command == "search":
            payload = search_unified(
                args.query,
                source=args.source,
                category=args.category,
                ext=args.ext,
                library=args.library,
                limit=args.limit,
            )
            if args.json:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_search_plain(payload)

        elif args.command == "inspect":
            info = inspect_asset(args.path, source=args.source)
            print(json.dumps(info, indent=2, ensure_ascii=False))

        elif args.command == "categories":
            cat_data = collect_categories(source=args.source)
            if args.json:
                print(json.dumps(cat_data, indent=2, ensure_ascii=False))
            else:
                _print_categories_plain(cat_data)

        elif args.command == "sources":
            statuses = collect_sources_status()
            if args.json:
                print(json.dumps({"total_sources": len(statuses), "sources": statuses}, indent=2, ensure_ascii=False))
            else:
                print(f"Workspace Asset Catalog Sources ({len(statuses)}):")
                for s in statuses:
                    state = "READY" if s["exists"] else "MISSING"
                    print(f"- [{state}] {s['source']:10s} ({s['dimension']:8s}) : {s['item_count']:>7,} items | {s['catalog_file']} | {s['manager_tool']}")

        else:
            parser.print_help()
    except ValueError as e:
        parser.error(str(e))


if __name__ == "__main__":
    main()
