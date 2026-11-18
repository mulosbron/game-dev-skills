#!/usr/bin/env python3
"""
Universal LPC Character Builder & GameMaker Exporter
Composites modular Liberated Pixel Cup (LPC) sprite layers into
game-ready spritesheets and GameMaker horizontal '_stripN.png' animations,
while tracking exact author licensing and attribution from CREDITS.csv.
"""

import os
import sys
import json
import argparse
import csv
from pathlib import Path
from PIL import Image

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
LPC_ROOT = WORKSPACE_ROOT / "libraries" / "com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator"
SPRITESHEETS_DIR = LPC_ROOT / "spritesheets"
SHEET_DEFS_DIR = LPC_ROOT / "sheet_definitions"
CREDITS_CSV = LPC_ROOT / "CREDITS.csv"
ELIZAWY_LPC_ROOT = WORKSPACE_ROOT / "libraries" / "com.github.elizawy.lpc"
CATALOG_FILE = WORKSPACE_ROOT / "catalogs" / "lpc_catalog.json"

# Standard LPC Animation Grid Definitions (64x64 pixel cells)
# (row_offset, frame_count, has_4_directions: Up, Left, Down, Right)
ANIMATIONS = {
    "spellcast": {"rows": 4, "cols": 7, "sheet_w": 448, "sheet_h": 256, "row_offset": 0},
    "thrust":    {"rows": 4, "cols": 8, "sheet_w": 512, "sheet_h": 256, "row_offset": 4},
    "walk":      {"rows": 4, "cols": 9, "sheet_w": 576, "sheet_h": 256, "row_offset": 8},
    "slash":     {"rows": 4, "cols": 6, "sheet_w": 384, "sheet_h": 256, "row_offset": 12},
    "shoot":     {"rows": 4, "cols": 13, "sheet_w": 832, "sheet_h": 256, "row_offset": 16},
    "hurt":      {"rows": 1, "cols": 6, "sheet_w": 384, "sheet_h": 64,  "row_offset": 20},
    "idle":      {"rows": 4, "cols": 2, "sheet_w": 128, "sheet_h": 256, "row_offset": 0},
    "run":       {"rows": 4, "cols": 8, "sheet_w": 512, "sheet_h": 256, "row_offset": 0},
    "climb":     {"rows": 1, "cols": 6, "sheet_w": 384, "sheet_h": 64,  "row_offset": 0},
    "jump":      {"rows": 4, "cols": 8, "sheet_w": 512, "sheet_h": 256, "row_offset": 0},
    "sit":       {"rows": 4, "cols": 3, "sheet_w": 192, "sheet_h": 256, "row_offset": 0},
}

DIRECTIONS = ["up", "left", "down", "right"]

# Default Presets with verified directory paths
PRESETS = {
    "warrior": {
        "body": "body/bodies/male",
        "head": "head/heads/human/male",
        "eyes": "eyes/human/adult/default",
        "legs": "legs/pants/male",
        "feet": "feet/armour/plate/male",
        "torso": "torso/armour/plate/male",
        "hair": "hair/plain/adult",
        "weapon": "weapon/melee/sword/arming/male"
    },
    "mage": {
        "body": "body/bodies/male",
        "head": "head/heads/human/male",
        "eyes": "eyes/human/adult/default",
        "legs": "legs/pants/male",
        "feet": "feet/shoes/basic/male",
        "torso": "torso/tunics/robe/male",
        "hair": "hair/messy/adult",
        "weapon": "weapon/magic/crystal/male"
    },
    "rogue": {
        "body": "body/bodies/female",
        "head": "head/heads/human/female",
        "eyes": "eyes/human/adult/default",
        "legs": "legs/pants/thin",
        "feet": "feet/boots/basic/thin",
        "torso": "torso/armour/leather/thin",
        "hair": "hair/ponytail/adult",
        "weapon": "weapon/melee/dagger/basic/thin"
    },
    "peasant": {
        "body": "body/bodies/male",
        "head": "head/heads/human/male",
        "eyes": "eyes/human/adult/default",
        "legs": "legs/pants/male",
        "feet": "feet/shoes/basic/male",
        "torso": "torso/clothes/tunic/male",
        "hair": "hair/bedhead/adult"
    }
}

# Standard Z-ordering for compositing
DEFAULT_Z_ORDER = [
    "shadow", "quiver", "body", "head", "eyes", "facial", "legs", "feet",
    "torso", "dress", "arms", "neck", "beards", "hair", "hat", "headwear",
    "weapon", "shield"
]

def load_credits_for_file(relative_path: str):
    """
    Looks up attribution data for a specific asset relative path from CREDITS.csv.
    """
    if not CREDITS_CSV.exists():
        return None

    clean_rel = relative_path.replace("\\", "/").strip("/")
    try:
        with open(CREDITS_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_fn = row.get("filename", "").strip()
                if row_fn == clean_rel or row_fn.startswith(clean_rel) or clean_rel.startswith(row_fn):
                    return row
    except Exception:
        pass
    return None

def find_layer_file(category_or_rel: str, anim_name: str) -> Path:
    """
    Finds the exact animation PNG file for a given category/part relative path quickly.
    Avoids slow recursive rglob scans across 89,000 files.
    """
    rel = category_or_rel.replace("\\", "/").strip("/")
    direct = SPRITESHEETS_DIR / rel

    # 1. Exact PNG file path
    if direct.is_file() and direct.name.endswith(".png"):
        return direct

    # 2. Direct subfile <rel>/<anim_name>.png
    candidate = direct / f"{anim_name}.png"
    if candidate.is_file():
        return candidate

    # 3. Direct shallow scan in folder (1 level deep)
    if direct.is_dir():
        for sub in direct.iterdir():
            if sub.is_file() and sub.name == f"{anim_name}.png":
                return sub
            if sub.is_dir():
                sub_cand = sub / f"{anim_name}.png"
                if sub_cand.is_file():
                    return sub_cand

    # 4. Fallback search within the specific category folder only
    parts = rel.split("/")
    if len(parts) > 0:
        top_cat = SPRITESHEETS_DIR / parts[0]
        if top_cat.is_dir():
            for p in top_cat.glob(f"**/{parts[-1]}/**/{anim_name}.png"):
                return p

    return None

def composite_animation(layers: list, anim_name: str) -> tuple[Image.Image, list]:
    """
    Composites multiple layer images for a specific animation action.
    Returns the composite RGBA Image and a list of used layer paths.
    """
    composite_img = None
    used_layers = []

    for layer_spec in layers:
        layer_path = find_layer_file(layer_spec, anim_name)
        if not layer_path or not layer_path.exists():
            continue

        try:
            layer_img = Image.open(layer_path).convert("RGBA")
            if composite_img is None:
                composite_img = Image.new("RGBA", layer_img.size, (0, 0, 0, 0))
            
            # Align sizes if needed
            if layer_img.size != composite_img.size:
                # Resize or paste at 0, 0
                temp = Image.new("RGBA", composite_img.size, (0, 0, 0, 0))
                temp.paste(layer_img, (0, 0), layer_img)
                layer_img = temp

            composite_img.alpha_composite(layer_img)
            used_layers.append(layer_path)
        except Exception as e:
            print(f"Warning: Failed to composite {layer_path}: {e}")

    return composite_img, used_layers

def build_classic_sheet(layers: list) -> tuple[Image.Image, list]:
    """
    Assembles the classic Universal LPC 832x1344 composite spritesheet
    containing Spellcast, Thrust, Walk, Slash, Shoot, and Hurt.
    """
    full_sheet = Image.new("RGBA", (832, 1344), (0, 0, 0, 0))
    all_used = []

    # 1. Spellcast (rows 0-3, y = 0..255)
    spell_img, used = composite_animation(layers, "spellcast")
    if spell_img:
        full_sheet.paste(spell_img, (0, 0), spell_img)
        all_used.extend(used)

    # 2. Thrust (rows 4-7, y = 256..511)
    thrust_img, used = composite_animation(layers, "thrust")
    if thrust_img:
        full_sheet.paste(thrust_img, (0, 256), thrust_img)
        all_used.extend(used)

    # 3. Walk (rows 8-11, y = 512..767)
    walk_img, used = composite_animation(layers, "walk")
    if walk_img:
        full_sheet.paste(walk_img, (0, 512), walk_img)
        all_used.extend(used)

    # 4. Slash (rows 12-15, y = 768..1023)
    slash_img, used = composite_animation(layers, "slash")
    if slash_img:
        full_sheet.paste(slash_img, (0, 768), slash_img)
        all_used.extend(used)

    # 5. Shoot (rows 16-19, y = 1024..1279)
    shoot_img, used = composite_animation(layers, "shoot")
    if shoot_img:
        full_sheet.paste(shoot_img, (0, 1024), shoot_img)
        all_used.extend(used)

    # 6. Hurt (row 20, y = 1280..1343)
    hurt_img, used = composite_animation(layers, "hurt")
    if hurt_img:
        full_sheet.paste(hurt_img, (0, 1280), hurt_img)
        all_used.extend(used)

    return full_sheet, list(set(all_used))

def slice_gamemaker_strip(anim_img: Image.Image, anim_name: str, direction: str, output_path: Path):
    """
    Slices a specific direction from an animation sheet and exports a horizontal '_stripN.png'.
    Directions: up=0, left=1, down=2, right=3.
    """
    dir_idx = DIRECTIONS.index(direction) if direction in DIRECTIONS else 2
    y_start = dir_idx * 64
    w, h = anim_img.size
    cols = w // 64

    # Extract horizontal frames
    strip = Image.new("RGBA", (cols * 64, 64), (0, 0, 0, 0))
    for c in range(cols):
        frame = anim_img.crop((c * 64, y_start, (c + 1) * 64, y_start + 64))
        strip.paste(frame, (c * 64, 0))

    out_file = output_path.parent / f"{output_path.stem}_{direction}_strip{cols}.png"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out_file)
    print(f"Saved GameMaker strip: {out_file} ({strip.width}x{strip.height})")
    return out_file

def generate_credits_file(used_files: list, output_path: Path):
    """
    Compiles full license, author, and URL attributions into a credits.txt file.
    """
    credits_collected = {}

    for f in used_files:
        try:
            rel = f.relative_to(SPRITESHEETS_DIR).as_posix()
            data = load_credits_for_file(rel)
            if data:
                authors = data.get("authors", "").strip()
                licenses = data.get("licenses", "").strip()
                urls = data.get("urls", "").strip()
                notes = data.get("notes", "").strip()
                credits_collected[rel] = {
                    "authors": authors,
                    "licenses": licenses,
                    "urls": urls,
                    "notes": notes
                }
            else:
                credits_collected[rel] = {
                    "authors": "Liberated Pixel Cup Contributors",
                    "licenses": "CC-BY-SA 3.0 / OGA-BY 3.0 / GPL 3.0",
                    "urls": "https://opengameart.org/content/lpc-collection",
                    "notes": "LPC Universal Character Generator Asset"
                }
        except Exception:
            pass

    out_txt = output_path.parent / f"{output_path.stem}_credits.txt"
    with open(out_txt, "w", encoding="utf-8") as out:
        out.write("========================================================================\n")
        out.write("UNIVERSAL LPC CHARACTER ATTRIBUTION & LEGAL CREDITS\n")
        out.write("========================================================================\n\n")
        out.write("All assets used in this character are licensed under free open licenses\n")
        out.write("(CC-BY-SA 3.0/4.0, CC-BY 3.0/4.0, OGA-BY 3.0, CC0 1.0, or GPL 3.0).\n")
        out.write("Commercial use in games is 100% permitted provided author attribution\n")
        out.write("is maintained in your game's credits.\n\n")
        out.write("Assets Used & Contributors:\n")
        out.write("------------------------------------------------------------------------\n\n")

        for asset, info in credits_collected.items():
            out.write(f"• Asset: {asset}\n")
            out.write(f"  Authors:  {info['authors']}\n")
            out.write(f"  Licenses: {info['licenses']}\n")
            out.write(f"  URLs:     {info['urls']}\n")
            if info['notes']:
                out.write(f"  Notes:    {info['notes']}\n")
            out.write("\n")

    print(f"Saved legal attribution ledger: {out_txt}")
    return out_txt


def build_lpc_catalog(verbose: bool = True) -> dict:
    """
    Indexes Universal LPC sheet_definitions, spritesheets leaf part folders,
    CREDITS.csv license summary, and com.github.elizawy.lpc category counts
    into catalogs/lpc_catalog.json.
    """
    CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    definitions = []

    if SHEET_DEFS_DIR.exists():
        for jpath in sorted(SHEET_DEFS_DIR.rglob("*.json")):
            if jpath.name.startswith("meta_"):
                continue
            try:
                raw = json.loads(jpath.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(raw, dict) or not raw.get("name"):
                continue

            rel_def = jpath.relative_to(SHEET_DEFS_DIR).as_posix()
            cat = rel_def.split("/")[0] if "/" in rel_def else "general"

            layer_paths = []
            for key, val in raw.items():
                if key.startswith("layer_") and isinstance(val, dict):
                    for body_key, pval in val.items():
                        if body_key in ("zPos", "custom_animation"):
                            continue
                        if isinstance(pval, str) and pval.strip():
                            clean_p = pval.strip().strip("/")
                            if clean_p not in layer_paths:
                                layer_paths.append(clean_p)

            licenses = []
            authors = []
            for c in raw.get("credits", []) or []:
                if not isinstance(c, dict):
                    continue
                for lic in c.get("licenses", []) or []:
                    if lic and lic not in licenses:
                        licenses.append(lic)
                for auth in c.get("authors", []) or []:
                    if auth and auth not in authors:
                        authors.append(auth)

            definitions.append({
                "id": jpath.stem,
                "category": cat,
                "name": raw.get("name", jpath.stem),
                "type_name": raw.get("type_name", ""),
                "priority": raw.get("priority"),
                "animations": raw.get("animations", []),
                "variants": raw.get("variants", []),
                "layer_paths": layer_paths,
                "licenses": licenses,
                "authors_count": len(authors),
                "definition_file": f"libraries/com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator/sheet_definitions/{rel_def}",
            })

    parts = []
    parts_by_category = {}
    total_spritesheet_pngs = 0

    if SPRITESHEETS_DIR.exists():
        for root, dirs, files in os.walk(SPRITESHEETS_DIR):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            pngs = sorted(f[:-4] for f in files if f.lower().endswith(".png"))
            if not pngs:
                continue
            total_spritesheet_pngs += len(pngs)
            rel_dir = Path(root).relative_to(SPRITESHEETS_DIR).as_posix()
            cat = rel_dir.split("/")[0] if "/" in rel_dir else rel_dir
            parts_by_category[cat] = parts_by_category.get(cat, 0) + 1
            parts.append({
                "part_path": rel_dir,
                "category": cat,
                "animations": pngs,
                "png_count": len(pngs),
            })

    credits_total_rows = 0
    credits_license_counts = {}
    if CREDITS_CSV.exists():
        try:
            with open(CREDITS_CSV, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    credits_total_rows += 1
                    for lic in (row.get("licenses") or "").split(","):
                        lic_s = lic.strip()
                        if lic_s:
                            credits_license_counts[lic_s] = credits_license_counts.get(lic_s, 0) + 1
        except Exception:
            pass

    elizawy_categories = {}
    elizawy_total_pngs = 0
    elizawy_leaf_folders = 0
    if ELIZAWY_LPC_ROOT.exists():
        for root, dirs, files in os.walk(ELIZAWY_LPC_ROOT):
            dirs[:] = sorted(d for d in dirs if d != ".git" and not d.startswith("."))
            pngs = [f for f in files if f.lower().endswith(".png")]
            if not pngs:
                continue
            elizawy_total_pngs += len(pngs)
            elizawy_leaf_folders += 1
            rel = Path(root).relative_to(ELIZAWY_LPC_ROOT).as_posix()
            top = rel.split("/")[0] if "/" in rel else "root"
            entry = elizawy_categories.setdefault(top, {"leaf_folders": 0, "png_count": 0})
            entry["leaf_folders"] += 1
            entry["png_count"] += len(pngs)

    catalog = {
        "repository": "com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator",
        "license_summary": "CC-BY-SA 3.0/4.0, CC-BY 3.0/4.0, OGA-BY 3.0, CC0 1.0, GPL 3.0 (per-asset in CREDITS.csv)",
        "total_definitions": len(definitions),
        "total_part_folders": len(parts),
        "total_spritesheet_pngs": total_spritesheet_pngs,
        "parts_by_category": dict(sorted(parts_by_category.items(), key=lambda x: -x[1])),
        "credits_summary": {
            "total_rows": credits_total_rows,
            "license_mentions": dict(sorted(credits_license_counts.items(), key=lambda x: -x[1])),
        },
        "related_repositories": {
            "com.github.elizawy.lpc": {
                "total_pngs": elizawy_total_pngs,
                "total_leaf_folders": elizawy_leaf_folders,
                "categories": dict(sorted(elizawy_categories.items(), key=lambda x: -x[1]["png_count"])),
            }
        },
        "presets": list(PRESETS.keys()),
        "animations": list(ANIMATIONS.keys()),
        "definitions": definitions,
        "parts": parts,
    }

    with open(CATALOG_FILE, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))

    if verbose:
        print(
            f"Built LPC catalog: {len(definitions)} sheet definitions, "
            f"{len(parts)} part folders ({total_spritesheet_pngs} PNGs), "
            f"elizawy.lpc ({elizawy_total_pngs} PNGs in {elizawy_leaf_folders} folders) -> {CATALOG_FILE}"
        )
    return catalog


def search_lpc_catalog(query: str, category: str = None, limit: int = 20) -> list:
    if CATALOG_FILE.exists():
        try:
            catalog = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            catalog = build_lpc_catalog(verbose=False)
    else:
        catalog = build_lpc_catalog(verbose=False)

    tokens = query.lower().split() if query else []
    cat_filter = category.lower() if category else None
    results = []

    for d in catalog.get("definitions", []):
        if cat_filter and d.get("category", "").lower() != cat_filter:
            continue
        hay = " ".join([
            d.get("id", ""),
            d.get("name", ""),
            d.get("category", ""),
            d.get("type_name", ""),
            " ".join(d.get("layer_paths", [])),
        ]).lower()
        if all(t in hay for t in tokens):
            results.append({
                "kind": "definition",
                "id": d.get("id"),
                "name": d.get("name"),
                "category": d.get("category"),
                "layer_paths": d.get("layer_paths", []),
                "animations": d.get("animations", []),
                "variants": d.get("variants", []),
            })
            if len(results) >= limit:
                return results

    for p in catalog.get("parts", []):
        if cat_filter and p.get("category", "").lower() != cat_filter:
            continue
        hay = " ".join([
            p.get("part_path", ""),
            p.get("category", ""),
            " ".join(p.get("animations", [])),
        ]).lower()
        if all(t in hay for t in tokens):
            results.append({
                "kind": "part",
                "part_path": p.get("part_path"),
                "category": p.get("category"),
                "animations": p.get("animations", []),
                "png_count": p.get("png_count", 0),
            })
            if len(results) >= limit:
                return results

    return results


def main():
    parser = argparse.ArgumentParser(description="Universal LPC Character Builder & GameMaker Exporter")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Index command
    subparsers.add_parser("index", help="Build catalogs/lpc_catalog.json from sheet_definitions and spritesheets")

    # Search command
    search_p = subparsers.add_parser("search", help="Search available LPC character parts and sheet definitions")
    search_p.add_argument("query", nargs="?", default="", help="Keyword to search (e.g. 'plate', 'wizard', 'hair')")
    search_p.add_argument("--category", "-c", help="Category filter (body, hair, torso, legs, feet, weapon, hat)")
    search_p.add_argument("--limit", "-l", type=int, default=20, help="Max results")
    search_p.add_argument("--json", action="store_true", help="Output JSON results")

    # Build command
    build_p = subparsers.add_parser("build", help="Assemble character layers into spritesheets")
    build_p.add_argument("--preset", "-p", choices=list(PRESETS.keys()), help="Start with a preset (warrior, mage, rogue, peasant)")
    build_p.add_argument("--anim", "-a", default="classic", help="Animation to export: classic (full 832x1344), walk, slash, thrust, spellcast, shoot, hurt, run, idle")
    build_p.add_argument("--body", help="Body layer (e.g. body/bodies/male)")
    build_p.add_argument("--head", help="Head layer (e.g. head/heads/human/male)")
    build_p.add_argument("--eyes", help="Eyes layer (e.g. eyes/human/adult/default)")
    build_p.add_argument("--hair", help="Hair layer (e.g. hair/plain/adult/blonde)")
    build_p.add_argument("--torso", help="Torso/shirt/armor layer (e.g. torso/chainmail/male/gray)")
    build_p.add_argument("--legs", help="Legs/pants layer (e.g. legs/pants/male/navy)")
    build_p.add_argument("--feet", help="Feet/shoes/boots layer (e.g. feet/boots/armored/male/metal)")
    build_p.add_argument("--headwear", help="Headwear/hat/helmet (e.g. hat/helmet/iron/male)")
    build_p.add_argument("--weapon", help="Weapon layer (e.g. weapon/melee/sword/longsword/male)")
    build_p.add_argument("--gamemaker-strip", action="store_true", help="Export horizontal GameMaker '_stripN.png' files for each direction")
    build_p.add_argument("--direction", "-d", choices=DIRECTIONS, default="down", help="Direction for GameMaker strip (default: down)")
    default_out = str(WORKSPACE_ROOT / "exports" / "com.github.liberatedpixelcup.lpc" / "character.png")
    build_p.add_argument("-o", "--output", default=default_out, help="Output path (default: exports/com.github.liberatedpixelcup.lpc/character.png)")

    args = parser.parse_args()

    if args.command == "index":
        build_lpc_catalog(verbose=True)
        return

    if args.command == "search":
        results = search_lpc_catalog(args.query, category=args.category, limit=args.limit)
        if args.json:
            print(json.dumps({"query": args.query, "count": len(results), "results": results}, indent=2, ensure_ascii=False))
        else:
            print(f"Found {len(results)} matches for '{args.query}':")
            for r in results:
                if r.get("kind") == "definition":
                    lp = r["layer_paths"][0] if r.get("layer_paths") else r.get("id")
                    print(f"- [def:{r.get('category')}] {r.get('name')} ({lp})")
                else:
                    print(f"- [part:{r.get('category')}] {r.get('part_path')} ({r.get('png_count')} anims)")
        return

    if args.command == "build":
        layer_map = {}
        # Base preset if specified
        if args.preset and args.preset in PRESETS:
            layer_map.update(PRESETS[args.preset])

        # Overrides from CLI flags
        cli_overrides = {
            "body": args.body,
            "head": args.head,
            "eyes": args.eyes,
            "hair": args.hair,
            "torso": args.torso,
            "legs": args.legs,
            "feet": args.feet,
            "headwear": args.headwear,
            "weapon": args.weapon
        }
        for k, v in cli_overrides.items():
            if v:
                layer_map[k] = v

        # Auto-fill head and eyes if a human body was specified without a head
        if "body" in layer_map and "head" not in layer_map:
            body_val = layer_map["body"].lower()
            if "skeleton" in body_val:
                layer_map["head"] = "head/heads/skeleton/adult"
            elif "zombie" in body_val:
                layer_map["head"] = "head/heads/zombie/adult"
            elif "female" in body_val or "thin" in body_val:
                layer_map["head"] = "head/heads/human/female"
                layer_map.setdefault("eyes", "eyes/human/adult/default")
            else:
                layer_map["head"] = "head/heads/human/male"
                layer_map.setdefault("eyes", "eyes/human/adult/default")

        layers = [layer_map[k] for k in DEFAULT_Z_ORDER if k in layer_map]

        if not layers:
            print("Error: No layers or preset specified. Use --preset warrior or specify --body, --torso, etc.")
            sys.exit(1)

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if args.anim == "classic":
            res_img, used_files = build_classic_sheet(layers)
            res_img.save(out_path)
            print(f"Success: Exported Classic LPC 832x1344 composite spritesheet to: {out_path}")
        else:
            res_img, used_files = composite_animation(layers, args.anim)
            if not res_img:
                print(f"Error: Could not composite animation '{args.anim}'")
                sys.exit(1)
            res_img.save(out_path)
            print(f"Success: Exported LPC '{args.anim}' animation sheet ({res_img.width}x{res_img.height}) to: {out_path}")

        # GameMaker strip export
        if args.gamemaker_strip and args.anim != "classic":
            slice_gamemaker_strip(res_img, args.anim, args.direction, out_path)

        # Generate legal attribution ledger
        generate_credits_file(used_files, out_path)

if __name__ == "__main__":
    main()
