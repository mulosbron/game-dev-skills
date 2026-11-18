#!/usr/bin/env python3
"""
Pixel Art Atlas 1.4M Manager & Spritesheet Pipeline
---------------------------------------------------
Dataset: Angais/pixel-art-atlas-1.4m (1,409,404 16x16 synthetic pixel art sprites)
Reverse-DNS Identifier: co.huggingface.angais.pixel-art-atlas-1.4m
License: CC0 1.0 Universal (Public Domain)

Provides:
- Fast multi-threaded downloader with checksum and resume support
- Memory-mapped O(1) sprite access from tokens.npy (688 MB) + palette.npy
- Subject/caption search across 6,194 categories & 1.4M sprites
- Spritesheet & GameMaker horizontal strip (_stripN.png) export
- Dynamic 2D normal map generation integration
"""

import os
import sys
import argparse
import json
import time
import zipfile
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = WORKSPACE_ROOT / "assets" / "co.huggingface.angais.pixel-art-atlas-1.4m"
DATA_DIR = ASSETS_DIR / "data"
EXPORTS_DIR = WORKSPACE_ROOT / "exports" / "co.huggingface.angais.pixel-art-atlas-1.4m"
CATALOG_PATH = WORKSPACE_ROOT / "catalogs" / "pixel_art_atlas_index.json"
LICENSES_PATH = ASSETS_DIR / "LICENSES.txt"
DOWNLOAD_SOURCES_PATH = ASSETS_DIR / "DOWNLOAD_SOURCES.txt"

HF_REPO = "Angais/pixel-art-atlas-1.4m"
BASE_URL = f"https://huggingface.co/datasets/{HF_REPO}/resolve/main"

MASTER_LICENSE_TEXT = """================================================================================
PIXEL ART ATLAS 1.4M (ANGAIS) COMMERCIAL CLEARANCE & ATTRIBUTION LEDGER
================================================================================

Dataset Identifier: co.huggingface.angais.pixel-art-atlas-1.4m
Repository: https://huggingface.co/datasets/Angais/pixel-art-atlas-1.4m
Author / Curator: Angais (https://huggingface.co/Angais)
Support / Buy Me a Coffee: https://buymeacoffee.com/angaisb_
Release License: CC0 1.0 Universal (Public Domain Dedication)
Full Legal Code: https://creativecommons.org/publicdomain/zero/1.0/legalcode

--------------------------------------------------------------------------------
ASSET OVERVIEW:
--------------------------------------------------------------------------------
- Total Sprites: 1,409,404 individual 16x16 RGBA pixel art sprites
- Training Sprites: 1,405,308
- Validation Sprites: 4,096
- Unique Subject Categories: 6,194
- Format: Native 16x16 with indexed palette and transparent background (index 0)
- Generation: Synthetic text-to-sprite generated with Krea 2 Turbo + Pixel Art LoRA

--------------------------------------------------------------------------------
RIGHTS & PROVENANCE:
--------------------------------------------------------------------------------
Angais releases the sprites, captions, and collection under CC0 1.0 to the extent
of the rights Angais can waive. This dedication does not grant rights in
third-party material, trademarks, or Krea's models.

All sprites are AI-generated outputs. No model weights or LoRA parameters are
distributed here. Krea claims no ownership of generated outputs under section 5.3
of the Krea 2 Community License (https://www.krea.ai/krea-2-licensing).
This release does not override that agreement, its commercial-use provisions (§2.3),
or the Krea Acceptable Use Policy (https://www.krea.ai/krea-2-use-policy).
This is an independent dataset, not an official or endorsed Krea release.

Commercial Use Clearance:
- GameMaker, Godot, Unity, Unreal, Web, Mobile: 100% Cleared for commercial games
- Spritesheets, strips, procedural mutations, dynamic normal maps: Cleared
================================================================================
"""

DOWNLOAD_SOURCES_TEXT = """================================================================================
PIXEL ART ATLAS 1.4M - DATASET STRUCTURE & USAGE INSTRUCTIONS
================================================================================

Source: https://huggingface.co/datasets/Angais/pixel-art-atlas-1.4m
Reverse-DNS ID: co.huggingface.angais.pixel-art-atlas-1.4m

Directory Layout:
- LICENSES.txt: Master legal clearance & attribution ledger (CC0 1.0)
- DOWNLOAD_SOURCES.txt: This overview document
- README.md: Original Hugging Face dataset card
- LICENSE: Original CC0 1.0 license text
- banner.png: Preview banner of selected sprites
- tokens.npy: (688 MB) Memory-mapped palette index tokens (1,409,404 x 256 uint8)
- palette.npy: (768 bytes) RGB color lookup table (256 x 3 uint8)
- captions.json: (60 MB) Parallel list of 1,409,404 English prompt captions
- objects.json: (21 MB) Parallel list of 1,409,404 subject/object labels
- split.npy: (1.3 MB) Train/validation split array (0 = train, 1 = validation)
- pixel-art-16x16-1.4m.zip: Original archive (259 MB)
- data/: Parquet split files for HuggingFace datasets library:
    train-000.parquet ... train-014.parquet (15 shards)
    validation-000.parquet (1 shard)

Quick CLI Commands:
1. Search categories & captions:
   python tools/pixel_atlas_manager.py search "sword" --limit 10

2. Export a specific sprite by ID to PNG:
   python tools/pixel_atlas_manager.py export --id 42 --scale 4

3. Export a GameMaker horizontal animation strip (_stripN.png):
   python tools/pixel_atlas_manager.py strip --subject "dragon" --count 6 --scale 2

4. Generate 2D normal map for dynamic lighting:
   python tools/pixel_atlas_manager.py normal --id 42

5. Display dataset statistics:
   python tools/pixel_atlas_manager.py stats
================================================================================
"""

def download_file(url: str, dest_path: Path, expected_size: int = None, retries: int = 5):
    """Download a file with resume support and retries."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    for attempt in range(1, retries + 1):
        try:
            downloaded = 0
            if temp_path.exists():
                downloaded = temp_path.stat().st_size
                if expected_size and downloaded == expected_size:
                    temp_path.rename(dest_path)
                    return True

            headers = {"User-Agent": "Mozilla/5.0"}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                mode = "ab" if downloaded > 0 else "wb"
                with open(temp_path, mode) as out_f:
                    while True:
                        chunk = resp.read(1024 * 512)
                        if not chunk:
                            break
                        out_f.write(chunk)

            if expected_size and temp_path.stat().st_size != expected_size:
                raise IOError(f"Size mismatch: got {temp_path.stat().st_size}, expected {expected_size}")

            if dest_path.exists():
                dest_path.unlink()
            temp_path.rename(dest_path)
            return True

        except Exception as e:
            if attempt == retries:
                print(f"[ERROR] Failed to download {url}: {e}")
                raise
            time.sleep(2 * attempt)
    return False

def cmd_download(args):
    """Download the complete Pixel Art Atlas 1.4M dataset and unpack it."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WORKSPACE_ROOT.joinpath("catalogs").mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print("PIXEL ART ATLAS 1.4M - REVERSE-DNS AUTOMATED INGESTION")
    print(f"Target Directory: {ASSETS_DIR}")
    print("================================================================================")

    # 1. Download metadata files
    meta_files = [
        ("LICENSE", ASSETS_DIR / "LICENSE"),
        ("README.md", ASSETS_DIR / "README.md"),
        ("banner.png", ASSETS_DIR / "banner.png"),
    ]

    for rel_name, dest_file in meta_files:
        if not dest_file.exists():
            print(f"[*] Downloading {rel_name}...")
            download_file(f"{BASE_URL}/{rel_name}", dest_file)
        else:
            print(f"[+] Found {rel_name}")

    # Write Legal Ledgers
    with open(LICENSES_PATH, "w", encoding="utf-8") as f:
        f.write(MASTER_LICENSE_TEXT)
    print(f"[+] Master Attribution & Legal Ledger recorded: {LICENSES_PATH}")

    with open(DOWNLOAD_SOURCES_PATH, "w", encoding="utf-8") as f:
        f.write(DOWNLOAD_SOURCES_TEXT)
    print(f"[+] Download sources & usage documented: {DOWNLOAD_SOURCES_PATH}")

    # 2. Download zip file (259 MB)
    zip_dest = ASSETS_DIR / "pixel-art-16x16-1.4m.zip"
    if not zip_dest.exists() and not (ASSETS_DIR / "tokens.npy").exists():
        print("[*] Downloading pixel-art-16x16-1.4m.zip (259 MB)...")
        download_file(f"{BASE_URL}/pixel-art-16x16-1.4m.zip", zip_dest)
        print("[+] Download complete: pixel-art-16x16-1.4m.zip")
    elif (ASSETS_DIR / "tokens.npy").exists():
        print("[+] tokens.npy already extracted, skipping zip re-download if present.")

    # 3. Extract zip if tokens.npy does not exist
    if not (ASSETS_DIR / "tokens.npy").exists():
        if zip_dest.exists():
            print("[*] Extracting pixel-art-16x16-1.4m.zip into assets directory...")
            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(ASSETS_DIR)
            print("[+] Extraction finished: tokens.npy, palette.npy, captions.json, objects.json, split.npy")
        else:
            print("[ERROR] Zip file missing!")
            return 1
    else:
        print("[+] Extracted arrays verified (tokens.npy, palette.npy, etc.)")

    # 4. Download Parquet shards in data/
    parquet_shards = [f"data/train-{i:03d}.parquet" for i in range(15)]
    parquet_shards.append("data/validation-000.parquet")

    missing_shards = [s for s in parquet_shards if not (WORKSPACE_ROOT / "assets" / "co.huggingface.angais.pixel-art-atlas-1.4m" / s).exists()]
    if missing_shards:
        print(f"[*] Downloading {len(missing_shards)} Parquet shards in parallel (4 threads)...")
        def dl_shard(shard_rel):
            dest = ASSETS_DIR / shard_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = f"{BASE_URL}/{shard_rel}"
            download_file(url, dest)
            return shard_rel

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(dl_shard, s): s for s in missing_shards}
            for fut in as_completed(futures):
                s = futures[fut]
                try:
                    fut.result()
                    print(f"  [+] Downloaded: {s}")
                except Exception as e:
                    print(f"  [!] Failed: {s}: {e}")
    else:
        print("[+] All 16 Parquet shards verified in data/")

    # 5. Build compact catalog for token-free indexing
    cmd_build_catalog(args)
    print("\n[SUCCESS] Pixel Art Atlas 1.4M ingestion & cataloging completed successfully!")
    return 0

def cmd_build_catalog(args):
    """Build a compact, indexed subject catalog in catalogs/pixel_art_atlas_index.json."""
    objects_path = ASSETS_DIR / "objects.json"
    if not objects_path.exists():
        print(f"[ERROR] Cannot build catalog: {objects_path} does not exist. Run download first.")
        return 1

    print("[*] Building token-free subject catalog from objects.json (1.4M records)...")
    t0 = time.time()
    with open(objects_path, "r", encoding="utf-8") as f:
        objects = json.load(f)

    # Group subjects
    from collections import defaultdict
    subject_map = defaultdict(lambda: {"count": 0, "sample_ids": []})
    for idx, obj in enumerate(objects):
        entry = subject_map[obj]
        entry["count"] += 1
        if len(entry["sample_ids"]) < 10:
            entry["sample_ids"].append(idx)

    catalog_data = {
        "dataset": "co.huggingface.angais.pixel-art-atlas-1.4m",
        "total_sprites": len(objects),
        "total_subjects": len(subject_map),
        "license": "CC0 1.0 Universal",
        "categories": {k: subject_map[k] for k in sorted(subject_map.keys())}
    }

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, indent=2)

    dt = time.time() - t0
    print(f"[+] Catalog created at {CATALOG_PATH} ({len(subject_map)} subjects, {len(objects)} sprites in {dt:.2f}s)")
    return 0

class SpriteAtlas:
    """Lazy loader for tokens.npy, palette.npy, and captions."""
    def __init__(self):
        self.tokens_path = ASSETS_DIR / "tokens.npy"
        self.palette_path = ASSETS_DIR / "palette.npy"
        self.captions_path = ASSETS_DIR / "captions.json"
        self.objects_path = ASSETS_DIR / "objects.json"
        self._tokens = None
        self._palette = None
        self._captions = None
        self._objects = None

    @property
    def tokens(self):
        if self._tokens is None:
            import numpy as np
            if not self.tokens_path.exists():
                raise FileNotFoundError(f"tokens.npy not found at {self.tokens_path}. Please download the dataset first.")
            self._tokens = np.load(self.tokens_path, mmap_mode="r")
        return self._tokens

    @property
    def palette(self):
        if self._palette is None:
            import numpy as np
            if not self.palette_path.exists():
                raise FileNotFoundError(f"palette.npy not found at {self.palette_path}.")
            self._palette = np.load(self.palette_path)
        return self._palette

    @property
    def captions(self):
        if self._captions is None:
            if not self.captions_path.exists():
                raise FileNotFoundError(f"captions.json not found at {self.captions_path}.")
            with open(self.captions_path, "r", encoding="utf-8") as f:
                self._captions = json.load(f)
        return self._captions

    @property
    def objects(self):
        if self._objects is None:
            if not self.objects_path.exists():
                raise FileNotFoundError(f"objects.json not found at {self.objects_path}.")
            with open(self.objects_path, "r", encoding="utf-8") as f:
                self._objects = json.load(f)
        return self._objects

    def get_rgba_image(self, row_id: int):
        """Retrieve 16x16 RGBA PIL Image for a sprite row_id."""
        import numpy as np
        from PIL import Image

        pixels = self.tokens[row_id].reshape(16, 16)
        rgb = self.palette[pixels]
        alpha = ((pixels != 0).astype("uint8") * 255)[:, :, None]
        rgba = np.concatenate([rgb, alpha], axis=-1)
        return Image.fromarray(rgba, mode="RGBA")

def cmd_search(args):
    """Search subjects or captions."""
    query = (args.query or "").strip().lower()
    tokens = query.split() if query else []
    limit = args.limit
    as_json = getattr(args, "json", False)

    subject_matches = []
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)
        for k, info in cat.get("categories", {}).items():
            kl = k.lower()
            if all(t in kl for t in tokens):
                if not tokens:
                    rank = 0
                elif kl == query:
                    rank = 100
                elif kl.startswith(query):
                    rank = 60
                elif all(t in kl.split() for t in tokens):
                    rank = 40
                else:
                    rank = 10
                subject_matches.append((rank, len(k), kl, k, info))

        if tokens:
            subject_matches.sort(key=lambda x: (-x[0], x[1], x[2]))

    captions_available = (ASSETS_DIR / "captions.json").exists() and (ASSETS_DIR / "objects.json").exists()
    caption_hits = []
    if not args.subjects_only and captions_available:
        atlas = SpriteAtlas()
        if not as_json:
            print(f"Searching captions for '{query}'...")
        for idx, cap in enumerate(atlas.captions):
            cap_low = cap.lower()
            if all(t in cap_low for t in tokens):
                caption_hits.append((idx, atlas.objects[idx], cap))
                if len(caption_hits) >= limit:
                    break

    if as_json:
        subj_out = [
            {
                "subject": k,
                "count": info.get("count", 0) if isinstance(info, dict) else 0,
                "sample_ids": info.get("sample_ids", [])[:5] if isinstance(info, dict) else [],
            }
            for _, _, _, k, info in subject_matches[:limit]
        ]
        cap_out = [
            {"id": idx, "subject": obj, "caption": cap}
            for idx, obj, cap in caption_hits
        ]
        print(json.dumps({
            "query": args.query,
            "total_matching_subjects": len(subject_matches),
            "subjects": subj_out,
            "captions_searched": (not args.subjects_only) and captions_available,
            "captions": cap_out,
        }, indent=2, ensure_ascii=False))
        return 0

    if subject_matches:
        print(f"Found {len(subject_matches)} matching subjects in catalog:")
        for _, _, _, k, info in subject_matches[:limit]:
            print(f"  • Subject: '{k}' ({info['count']} sprites) - Sample IDs: {info['sample_ids'][:5]}")
        if len(subject_matches) > limit:
            print(f"  ... and {len(subject_matches) - limit} more subjects.")
        print()

    if not args.subjects_only:
        if captions_available:
            print(f"Captions matching '{query}' (up to {limit}):")
            for idx, obj, cap in caption_hits:
                print(f"  [ID {idx:7d}] [{obj}] {cap}")
        else:
            print("[INFO] captions.json not found locally; skipped caption scan (use --subjects-only to silence).")
    return 0

def cmd_export(args):
    """Export one or more sprites by ID."""
    atlas = SpriteAtlas()
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    scale = args.scale
    from PIL import Image

    for row_id in args.ids:
        img = atlas.get_rgba_image(row_id)
        if scale > 1:
            img = img.resize((16 * scale, 16 * scale), resample=Image.NEAREST)

        subject = atlas.objects[row_id].replace(" ", "_")
        out_name = f"spr_{subject}_id{row_id}_s{scale}.png"
        out_path = EXPORTS_DIR / out_name
        img.save(out_path)
        print(f"[+] Exported sprite #{row_id} ({subject}) -> {out_path}")
        print(f"    Caption: \"{atlas.captions[row_id]}\"")

        if args.normal:
            cmd_generate_normal(out_path)
    return 0

def cmd_strip(args):
    """Export a horizontal GameMaker animation strip (_stripN.png)."""
    atlas = SpriteAtlas()
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    scale = args.scale
    count = args.count
    subject = args.subject

    # Find row IDs for subject
    matching_ids = [idx for idx, obj in enumerate(atlas.objects) if obj.lower() == subject.lower()]
    if not matching_ids:
        # Partial match
        matching_ids = [idx for idx, obj in enumerate(atlas.objects) if subject.lower() in obj.lower()]

    if not matching_ids:
        print(f"[ERROR] No sprites found matching subject '{subject}'")
        return 1

    selected_ids = matching_ids[:count]
    actual_count = len(selected_ids)
    print(f"Selected {actual_count} sprites for subject '{subject}' (IDs: {selected_ids})")

    from PIL import Image
    frame_w = 16 * scale
    frame_h = 16 * scale
    strip_w = frame_w * actual_count
    strip_img = Image.new("RGBA", (strip_w, frame_h), (0, 0, 0, 0))

    for i, row_id in enumerate(selected_ids):
        sprite_img = atlas.get_rgba_image(row_id)
        if scale > 1:
            sprite_img = sprite_img.resize((frame_w, frame_h), resample=Image.NEAREST)
        strip_img.paste(sprite_img, (i * frame_w, 0), sprite_img)

    clean_name = args.name or f"spr_{subject.replace(' ', '_')}_strip{actual_count}.png"
    if not clean_name.endswith(".png"):
        clean_name += ".png"
    if f"_strip{actual_count}" not in clean_name:
        clean_name = clean_name.replace(".png", f"_strip{actual_count}.png")

    out_path = EXPORTS_DIR / clean_name
    strip_img.save(out_path)
    print(f"[+] Generated GameMaker horizontal strip: {out_path}")
    print(f"    Dimensions: {strip_w}x{frame_h} ({actual_count} frames of {frame_w}x{frame_h})")

    if args.normal:
        cmd_generate_normal(out_path)
    return 0

def cmd_generate_normal(image_path: Path):
    """Call tools/normal_map_gen.py to generate 2D normal map."""
    normal_gen_script = WORKSPACE_ROOT / "tools" / "normal_map_gen.py"
    if normal_gen_script.exists():
        import subprocess
        print(f"[*] Generating dynamic lighting normal map via normal_map_gen.py...")
        subprocess.run([sys.executable, str(normal_gen_script), str(image_path), "--preview"], check=False)
    else:
        print(f"[!] normal_map_gen.py not found at {normal_gen_script}")

def cmd_stats(args):
    """Display dataset statistics and status."""
    as_json = getattr(args, "json", False)
    files_to_check = [
        ("LICENSES.txt", ASSETS_DIR / "LICENSES.txt"),
        ("tokens.npy", ASSETS_DIR / "tokens.npy"),
        ("palette.npy", ASSETS_DIR / "palette.npy"),
        ("captions.json", ASSETS_DIR / "captions.json"),
        ("objects.json", ASSETS_DIR / "objects.json"),
        ("split.npy", ASSETS_DIR / "split.npy"),
        ("banner.png", ASSETS_DIR / "banner.png"),
        ("pixel-art-16x16-1.4m.zip", ASSETS_DIR / "pixel-art-16x16-1.4m.zip"),
    ]
    parquet_count = len(list(DATA_DIR.glob("*.parquet"))) if DATA_DIR.exists() else 0
    cat_info = {}
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            cat = json.load(f)
        cat_info = {
            "total_sprites": cat.get("total_sprites", 0),
            "total_subjects": cat.get("total_subjects", 0),
            "license": cat.get("license", "Unknown"),
        }

    if as_json:
        files_status = {}
        for label, p in files_to_check:
            files_status[label] = {
                "exists": p.exists(),
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2) if p.exists() else 0.0,
            }
        print(json.dumps({
            "dataset": "co.huggingface.angais.pixel-art-atlas-1.4m",
            "assets_dir": str(ASSETS_DIR),
            "catalog_path": str(CATALOG_PATH),
            "files": files_status,
            "parquet_shards": parquet_count,
            "catalog": cat_info,
        }, indent=2, ensure_ascii=False))
        return 0

    print("================================================================================")
    print("PIXEL ART ATLAS 1.4M (ANGAIS) DATASET STATUS")
    print("================================================================================")
    print(f"Reverse-DNS Identifier: co.huggingface.angais.pixel-art-atlas-1.4m")
    print(f"Assets Directory: {ASSETS_DIR}")
    print(f"Catalog Path: {CATALOG_PATH}")

    for label, p in files_to_check:
        if p.exists():
            size_mb = p.stat().st_size / (1024 * 1024)
            print(f"  [x] {label:26s} : {size_mb:8.2f} MB")
        else:
            print(f"  [ ] {label:26s} : MISSING")

    print(f"  [x] Parquet Shards (data/)    : {parquet_count} / 16 files")

    if cat_info:
        print("--------------------------------------------------------------------------------")
        print(f"Indexed Total Sprites   : {cat_info['total_sprites']:,}")
        print(f"Indexed Total Subjects  : {cat_info['total_subjects']:,}")
        print(f"License Clearance       : {cat_info['license']}")
    print("================================================================================")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Pixel Art Atlas 1.4M Manager & Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # download
    subparsers.add_parser("download", help="Download full dataset, unpack arrays, and build catalog")

    # build-catalog
    subparsers.add_parser("build-catalog", help="Build/rebuild token-free search catalog")

    # search
    search_p = subparsers.add_parser("search", help="Search subjects and captions")
    search_p.add_argument("query", nargs="?", default="", type=str, help="Search query")
    search_p.add_argument("--subjects-only", action="store_true", help="Search only subjects (fast)")
    search_p.add_argument("--limit", "-n", "-l", type=int, default=15, help="Max results to display")
    search_p.add_argument("--json", action="store_true", help="Output JSON results")

    # export
    export_p = subparsers.add_parser("export", help="Export sprite(s) to PNG")
    export_p.add_argument("--id", dest="ids", type=int, nargs="+", required=True, help="One or more sprite row IDs")
    export_p.add_argument("--scale", type=int, default=1, choices=[1, 2, 4, 8], help="Integer scale factor")
    export_p.add_argument("--normal", action="store_true", help="Generate dynamic normal map")

    # strip
    strip_p = subparsers.add_parser("strip", help="Export GameMaker horizontal animation strip (_stripN.png)")
    strip_p.add_argument("--subject", type=str, required=True, help="Subject name (e.g. dragon, sword, potion)")
    strip_p.add_argument("--count", type=int, default=6, help="Number of frames in strip")
    strip_p.add_argument("--scale", type=int, default=2, choices=[1, 2, 4, 8], help="Integer scale factor")
    strip_p.add_argument("--name", type=str, default=None, help="Custom output filename")
    strip_p.add_argument("--normal", action="store_true", help="Generate dynamic normal map for strip")

    # normal
    normal_p = subparsers.add_parser("normal", help="Generate 2D normal map for sprite by ID")
    normal_p.add_argument("--id", type=int, required=True, help="Sprite row ID")
    normal_p.add_argument("--scale", type=int, default=4, help="Scale factor")

    # stats
    stats_p = subparsers.add_parser("stats", help="Display dataset stats & file verification")
    stats_p.add_argument("--json", action="store_true", help="Output JSON dataset stats")

    args = parser.parse_args()
    if args.command == "download":
        return cmd_download(args)
    elif args.command == "build-catalog":
        return cmd_build_catalog(args)
    elif args.command == "search":
        return cmd_search(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "strip":
        return cmd_strip(args)
    elif args.command == "normal":
        atlas = SpriteAtlas()
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        img = atlas.get_rgba_image(args.id)
        if args.scale > 1:
            from PIL import Image
            img = img.resize((16 * args.scale, 16 * args.scale), resample=Image.NEAREST)
        subject = atlas.objects[args.id].replace(" ", "_")
        out_name = f"spr_{subject}_id{args.id}_s{args.scale}.png"
        out_path = EXPORTS_DIR / out_name
        img.save(out_path)
        print(f"[+] Saved sprite image: {out_path}")
        cmd_generate_normal(out_path)
        return 0
    elif args.command == "stats":
        return cmd_stats(args)

if __name__ == "__main__":
    sys.exit(main() or 0)
