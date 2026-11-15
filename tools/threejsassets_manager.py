#!/usr/bin/env python3
"""
ThreeJS Assets Manager & Bulk Downloader
Manages, searches, and downloads 1,040+ free web-ready low-poly 3D models
from https://threejsassets.com/ with complete provenance and Free Commercial License tracking.
"""

import sys
import argparse
import json
import time
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = WORKSPACE_ROOT / "assets" / "com.threejsassets"
MODELS_DIR = ASSETS_DIR / "models"
THUMBS_DIR = ASSETS_DIR / "thumbs"
CATALOG_PATH = WORKSPACE_ROOT / "catalogs" / "threejsassets_catalog.json"
LICENSES_PATH = ASSETS_DIR / "LICENSES.txt"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

LICENSE_TEXT = """================================================================================
THREEJSASSETS.COM FREE ASSET COMMERCIAL LICENSE & PROVENANCE LEDGER
================================================================================

Source: https://threejsassets.com/
License Reference: https://threejsassets.com/license#free-asset-license
Reverse Domain Identifier: com.threejsassets
Asset Format: Web-ready low-poly glTF Binary (.glb) with embedded PBR textures.

--------------------------------------------------------------------------------
TERMS OF USE (Free Asset License v1):
--------------------------------------------------------------------------------
• Public label: Free Commercial License.
• Scope of use: Free assets can be used in personal, open-source, educational,
  client, commercial, game, app, website, video, and shipped product work.
• Modification: You may modify, transform, combine, and embed them in your projects.
• Royalties: 100% royalty-free, no trial, no watermark.
• Restriction: Do not resell, mirror, share, repackage, or redistribute raw
  asset files or download access as a competing stock/asset pack.

================================================================================
CATALOG OVERVIEW:
All models listed in 'catalogs/threejsassets_catalog.json' are covered under this
Free Commercial License.
================================================================================
"""

def ensure_dirs():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LICENSES_PATH.exists():
        LICENSES_PATH.write_text(LICENSE_TEXT, encoding="utf-8")

def fetch_catalog(force: bool = False):
    """
    Scrapes the full 1,040+ free model catalog from https://threejsassets.com/assets/free
    """
    ensure_dirs()
    if CATALOG_PATH.exists() and not force:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog = json.load(f)
            print(f"Loaded existing catalog: {len(catalog)} items.")
            return catalog

    print("Fetching free catalog from https://threejsassets.com/assets/free ...", flush=True)
    r = requests.get("https://threejsassets.com/assets/free", headers={"User-Agent": USER_AGENT}, timeout=25)
    r.raise_for_status()
    html = r.text

    pattern = r'href="/assets/([a-zA-Z0-9_\-]+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*alt="([^"]*)"'
    matches = re.findall(pattern, html, re.DOTALL)

    catalog = []
    seen = set()
    non_assets = {'free', 'buildings', 'nature', 'vehicles', 'roads-streets', 'props-interiors', 'sky-terrain-water'}

    for slug, thumb, alt in matches:
        if slug in non_assets or slug in seen:
            continue
        seen.add(slug)
        clean_name = alt.replace(" thumbnail", "").replace("Low-poly ", "").strip()
        catalog.append({
            "slug": slug,
            "name": clean_name or slug.replace("-", " ").title(),
            "thumbnail": thumb,
            "model_url": f"https://threejsassets.com/models/{slug}.glb",
            "page_url": f"https://threejsassets.com/assets/{slug}",
            "file_name": f"{slug}.glb",
            "license": "Free Commercial License"
        })

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2)

    print(f"Catalog fetched and saved: {len(catalog)} free 3D models -> {CATALOG_PATH}")
    return catalog

def download_single_model(item: dict, delay: float = 0.1) -> tuple[str, bool, str]:
    slug = item["slug"]
    out_file = MODELS_DIR / f"{slug}.glb"
    if out_file.exists() and out_file.stat().st_size > 1024:
        return slug, True, "cached"

    url = item["model_url"]
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": item["page_url"],
        "Accept": "*/*"
    }

    max_attempts = 6
    for attempt in range(max_attempts):
        try:
            r = requests.get(url, headers=headers, timeout=25)
            if r.status_code == 200 and r.content[:4] == b"glTF":
                out_file.write_bytes(r.content)
                if delay > 0:
                    time.sleep(delay)
                return slug, True, "downloaded"
            elif r.status_code == 429:
                wait_time = 3.0 + attempt * 2.5
                time.sleep(wait_time)
            elif r.status_code == 404:
                return slug, False, "HTTP 404 Not Found"
            else:
                time.sleep(1.0)
        except Exception as e:
            time.sleep(1.5)
            if attempt == max_attempts - 1:
                return slug, False, str(e)
    return slug, False, "failed after max retries"

def download_single_thumb(item: dict, delay: float = 0.05) -> tuple[str, bool]:
    slug = item["slug"]
    out_file = THUMBS_DIR / f"{slug}.png"
    if out_file.exists() and out_file.stat().st_size > 100:
        return slug, True

    thumb_url = item.get("thumbnail")
    if not thumb_url:
        return slug, False

    for attempt in range(3):
        try:
            r = requests.get(thumb_url, headers={"User-Agent": USER_AGENT}, timeout=15)
            if r.status_code == 200:
                out_file.write_bytes(r.content)
                if delay > 0:
                    time.sleep(delay)
                return slug, True
            elif r.status_code == 429:
                time.sleep(3.0)
        except Exception:
            time.sleep(1.0)
    return slug, False

def bulk_download(max_workers: int = 3, download_thumbs: bool = True):
    """
    Downloads all 1,040+ models concurrently with progress tracking.
    """
    catalog = fetch_catalog()
    ensure_dirs()

    print(f"Starting bulk download of {len(catalog)} free 3D models into {MODELS_DIR} (threads: {max_workers})...", flush=True)

    success_count = 0
    cached_count = 0
    fail_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_single_model, item, 0.12): item for item in catalog}
        for i, future in enumerate(as_completed(futures), 1):
            slug, ok, status = future.result()
            if ok:
                if status == "cached":
                    cached_count += 1
                else:
                    success_count += 1
            else:
                fail_count += 1
                print(f"[!] Failed {slug}: {status}", flush=True)

            if i % 25 == 0 or i == len(catalog):
                elapsed = time.time() - start_time
                print(f"Progress: [{i}/{len(catalog)}] ({i*100//len(catalog)}%) | Downloaded: {success_count} | Cached: {cached_count} | Failed: {fail_count} | Elapsed: {elapsed:.1f}s", flush=True)

    if download_thumbs:
        print("\nDownloading preview thumbnails...", flush=True)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_single_thumb, item, 0.05): item for item in catalog}
            for _ in as_completed(futures):
                pass
        print(f"Thumbnails saved to {THUMBS_DIR}")

    total_time = time.time() - start_time
    print(f"\nBulk download complete in {total_time:.1f}s!")
    print(f"Total downloaded: {success_count}, Cached: {cached_count}, Failed: {fail_count}")

def search_catalog(query: str, limit: int = 20):
    catalog = fetch_catalog()
    q = query.lower()
    matches = [item for item in catalog if q in item["name"].lower() or q in item["slug"].lower()]
    print(f"Found {len(matches)} matching models for '{query}':")
    for m in matches[:limit]:
        local_file = MODELS_DIR / f"{m['slug']}.glb"
        status = "INSTALLED" if local_file.exists() else "AVAILABLE"
        print(f"- [{status}] {m['name']} ({m['slug']}.glb)")

def main():
    parser = argparse.ArgumentParser(description="ThreeJS Assets Manager & Bulk Downloader")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Catalog command
    subparsers.add_parser("catalog", help="Fetch or update catalog JSON")

    # Download command
    dl_p = subparsers.add_parser("download", help="Bulk download all free 3D models")
    dl_p.add_argument("--workers", "-w", type=int, default=3, help="Concurrent download threads (default: 3)")
    dl_p.add_argument("--no-thumbs", action="store_true", help="Skip downloading thumbnails")

    # Search command
    s_p = subparsers.add_parser("search", help="Search free 3D models by keyword")
    s_p.add_argument("query", help="Keyword to search")
    s_p.add_argument("--limit", "-l", type=int, default=20, help="Max results")

    args = parser.parse_args()

    if args.command == "catalog":
        fetch_catalog(force=True)
    elif args.command == "download":
        bulk_download(max_workers=args.workers, download_thumbs=not args.no_thumbs)
    elif args.command == "search":
        search_catalog(args.query, limit=args.limit)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
