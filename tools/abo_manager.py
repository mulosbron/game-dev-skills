#!/usr/bin/env python3
"""
Amazon Berkeley Objects (ABO) 3D Model Manager
Manages, searches, and downloads 7,953 real-world 3D products (GLB + Collision + LODs)
repackaged by An Xuan (CodePawl) under CC-BY-4.0 from Amazon Berkeley Objects.
Guarantees 100% Commercial Use compliance with preserved attribution.
"""

import os
import sys
import json
import urllib.request
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
ABO_DIR = WORKSPACE_ROOT / "assets" / "com.amazon.berkeley.abo"
CATALOG_FILE = ABO_DIR / "catalog.jsonl"
MODELS_DIR = ABO_DIR / "models"
COLLISION_DIR = ABO_DIR / "collision"
THUMBS_DIR = ABO_DIR / "thumbs"
LICENSES_FILE = ABO_DIR / "LICENSES.txt"

HF_BASE_URL = "https://huggingface.co/datasets/codepawl/abo-glb/resolve/main"

MASTER_LICENSE_HEADER = """================================================================================
AMAZON BERKELEY OBJECTS (ABO) - 3D COLLECTION COMMERCIAL LICENSE DECLARATION
================================================================================

1. LEGAL STATUS & COMMERCIAL RIGHTS
--------------------------------------------------------------------------------
All 3D assets in this collection originate from Amazon Berkeley Objects (ABO)
and are distributed under the Creative Commons Attribution 4.0 International
License (CC-BY-4.0).

COMMERCIAL USE IS 100% PERMITTED:
- You are free to use, adapt, and bundle these 3D models into commercial games,
  interactive web applications, architectural scenes, and simulations.
- Zero non-commercial (NC) restrictions.
- Zero copyleft (SA) restrictions.

2. MANDATORY ATTRIBUTION NOTICE (CC-BY-4.0)
--------------------------------------------------------------------------------
When using these assets in your game or project, provide attribution in your
game's credits or documentation:

  "3D models from Amazon Berkeley Objects (ABO) by Amazon (https://amazon-berkeley-objects.s3.amazonaws.com/index.html),
   licensed under CC BY 4.0. Repackaged with WebP PBR textures, convex collision hulls,
   and real-world meter scaling by An Xuan Nguyen (CodePawl)."

3. ASSET PROVENANCE LEDGER
--------------------------------------------------------------------------------
"""

def ensure_catalog():
    if not CATALOG_FILE.exists():
        ABO_DIR.mkdir(parents=True, exist_ok=True)
        url = f"{HF_BASE_URL}/thumbs/metadata.jsonl"
        print(f"Downloading master catalog from {url}...", flush=True)
        urllib.request.urlretrieve(url, CATALOG_FILE)
        print(f"Master catalog saved to {CATALOG_FILE}")

def load_catalog() -> List[Dict[str, Any]]:
    ensure_catalog()
    items = []
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items

def search_catalog(query: str = "", category: Optional[str] = None, limit: int = 20):
    catalog = load_catalog()
    tokens = query.lower().split() if query else []
    results = []

    for item in catalog:
        if category and item.get("product_type", "").lower() != category.lower():
            continue

        item_text = (item.get("name", "") + " " + item.get("id", "") + " " + item.get("product_type", "") + " " + item.get("brand", "")).lower()
        if all(token in item_text for token in tokens):
            results.append(item)
            if len(results) >= limit:
                break

    print(f"Found {len(results)} ABO products matching '{query}':")
    for r in results:
        downloaded = (MODELS_DIR / f"{r['id']}.glb").exists()
        status_tag = "[DOWNLOADED]" if downloaded else "[AVAILABLE]"
        print(f"- {status_tag} [{r.get('product_type')}] {r.get('id')}: {r.get('name')} ({r.get('size_cm', 'N/A')})")

def download_model(item_id: str, with_collision: bool = True) -> bool:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    COLLISION_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    catalog = load_catalog()
    meta = next((item for item in catalog if item["id"] == item_id), None)
    if not meta:
        print(f"Error: Model ID '{item_id}' not found in catalog.")
        return False

    headers = {"User-Agent": "Mozilla/5.0"}

    # 1. Download GLB
    glb_dest = MODELS_DIR / f"{item_id}.glb"
    if not glb_dest.exists():
        glb_url = f"{HF_BASE_URL}/objects/{item_id}/{item_id}.glb"
        print(f"Downloading GLB: {item_id}...", end=" ", flush=True)
        try:
            req = urllib.request.Request(glb_url, headers=headers)
            with urllib.request.urlopen(req) as resp, open(glb_dest, "wb") as f:
                f.write(resp.read())
            print(f"Done ({round(glb_dest.stat().st_size / 1024, 1)} KB).")
        except Exception as e:
            print(f"Failed: {e}")
            return False
    else:
        print(f"GLB already downloaded: {glb_dest.name}")

    # 2. Download Collision Hull if requested
    if with_collision:
        col_dest = COLLISION_DIR / f"{item_id}_collision.glb"
        if not col_dest.exists():
            col_url = f"{HF_BASE_URL}/collision/{item_id}/{item_id}_collision.glb"
            try:
                req = urllib.request.Request(col_url, headers=headers)
                with urllib.request.urlopen(req) as resp, open(col_dest, "wb") as f:
                    f.write(resp.read())
                print(f"Downloaded convex collision hull: {col_dest.name}")
            except Exception:
                pass

    # 3. Download Thumbnail
    thumb_dest = THUMBS_DIR / f"{item_id}.webp"
    if not thumb_dest.exists():
        thumb_url = f"{HF_BASE_URL}/thumbs/{item_id}.webp"
        try:
            req = urllib.request.Request(thumb_url, headers=headers)
            with urllib.request.urlopen(req) as resp, open(thumb_dest, "wb") as f:
                f.write(resp.read())
        except Exception:
            pass

    # 4. Save individual metadata.json alongside model
    item_meta_file = MODELS_DIR / f"{item_id}_metadata.json"
    meta_info = {
        **meta,
        "license": "CC-BY-4.0",
        "author": "Amazon / Amazon Berkeley Objects",
        "repackaged_by": "An Xuan Nguyen (CodePawl)",
        "features": {
            "pbr_textures": "WebP (diffuse, normal, metallic, roughness)",
            "scale": "Real size in meters (Y-up, standing on Y=0)",
            "collision_hull": with_collision
        },
        "commercial_use_cleared": True
    }
    with open(item_meta_file, "w", encoding="utf-8") as f:
        json.dump(meta_info, f, indent=2, ensure_ascii=False)

    # 5. Update master LICENSES.txt
    record_entry = f"- [{meta.get('product_type')}] {item_id}: {meta.get('name')} | License: CC-BY-4.0 | Attribution: Amazon Berkeley Objects, repackaged by CodePawl"
    update_license_ledger(record_entry)
    return True

def update_license_ledger(entry: str):
    ABO_DIR.mkdir(parents=True, exist_ok=True)
    existing = ""
    if LICENSES_FILE.exists():
        existing = LICENSES_FILE.read_text(encoding="utf-8")

    with open(LICENSES_FILE, "a", encoding="utf-8") as f:
        if not LICENSES_FILE.exists() or os.path.getsize(LICENSES_FILE) == 0:
            f.write(MASTER_LICENSE_HEADER)
        if entry not in existing:
            f.write(f"\n{entry}\n")

def download_batch(category: str, limit: int = 5):
    catalog = load_catalog()
    matching = [item for item in catalog if item.get("product_type", "").lower() == category.lower()]
    print(f"Found {len(matching)} items in category '{category}'. Downloading {min(limit, len(matching))} items...")

    success = 0
    for item in matching[:limit]:
        if download_model(item["id"]):
            success += 1
    print(f"Downloaded {success}/{limit} items in '{category}'.")

def list_categories():
    catalog = load_catalog()
    counts = {}
    for item in catalog:
        cat = item.get("product_type", "other")
        counts[cat] = counts.get(cat, 0) + 1

    print(f"ABO Catalog Breakdown ({len(catalog)} total models):")
    for cat, c in sorted(counts.items(), key=lambda x: -x[1])[:25]:
        print(f"  {cat:28s}: {c} models")

def main():
    parser = argparse.ArgumentParser(description="Amazon Berkeley Objects (ABO) 3D Model Manager")
    subparsers = parser.add_subparsers(dest="command")

    # search
    s_p = subparsers.add_parser("search", help="Search 7,953 products by keyword")
    s_p.add_argument("query", nargs="?", default="", help="Keyword (chair, table, desk, lamp)")
    s_p.add_argument("--category", "-c", help="Filter by product_type")
    s_p.add_argument("--limit", "-n", type=int, default=20, help="Max results")

    # download
    dl_p = subparsers.add_parser("download", help="Download a specific 3D model by ID")
    dl_p.add_argument("id", help="Product ID (e.g. B002CM3J2A)")
    dl_p.add_argument("--no-collision", action="store_true", help="Skip collision hull")

    # batch download
    b_p = subparsers.add_parser("download-batch", help="Download a batch of models in a category")
    b_p.add_argument("--category", "-c", required=True, help="Category name (e.g. chair, table, lamp)")
    b_p.add_argument("--limit", "-n", type=int, default=5, help="Number of items to download")

    # categories
    subparsers.add_parser("categories", help="List all 3D product categories")

    args = parser.parse_args()

    if args.command == "search":
        search_catalog(args.query, category=args.category, limit=args.limit)
    elif args.command == "download":
        download_model(args.id, with_collision=not args.no_collision)
    elif args.command == "download-batch":
        download_batch(args.category, limit=args.limit)
    elif args.command == "categories":
        list_categories()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
