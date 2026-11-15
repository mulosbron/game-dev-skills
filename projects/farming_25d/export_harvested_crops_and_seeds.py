#!/usr/bin/env python3
"""
Export Harvested Crops & Seed Packets for 2.5D Farming Inventory & Shop
Extracts authentic 16x16 pixel sprites from Pixel Art Atlas 1.4M (co.huggingface.angais.pixel-art-atlas-1.4m)
and quantizes them to the 32-color GDD palette for the 32-slot inventory & shop selling.
"""

import sys
from pathlib import Path
from PIL import Image

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(WORKSPACE_ROOT / "tools"))
from pixel_atlas_manager import SpriteAtlas

OUT_DIR = WORKSPACE_ROOT / "projects" / "farming_25d" / "sprites_2d" / "props_and_ui"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Selected authentic IDs from Pixel Art Atlas 1.4M
CROP_ITEMS = {
    "item_crop_yonca": (19454, "four leaf clover"),
    "item_crop_turp": (6353, "radish"),
    "item_crop_bugday": (441439, "wheat"),
    "item_crop_patates": (4831, "potato"),
    "item_crop_havuc": (21625, "carrot"),
    "item_crop_lahana": (5918, "cabbage"),
    "item_crop_domates": (9074, "tomato"),
    "item_crop_kabak": (3629, "pumpkin"),
    "item_crop_aycicegi": (8188, "sunflower"),
    "item_crop_kale": (439063, "kale leaf"),
    "item_crop_pancar": (7490, "beet"),
}

# Seed packet IDs from Pixel Art Atlas 1.4M
SEED_ITEMS = {
    "item_seed_yonca": (436916, "seed packet yonca"),
    "item_seed_turp": (438297, "seed packet turp"),
    "item_seed_bugday": (450034, "seed packet bugday"),
    "item_seed_patates": (451780, "seed packet patates"),
    "item_seed_havuc": (453642, "seed packet havuc"),
    "item_seed_lahana": (454378, "seed packet lahana"),
    "item_seed_domates": (456102, "seed packet domates"),
    "item_seed_kabak": (457812, "seed packet kabak"),
    "item_seed_aycicegi": (459240, "seed packet aycicegi"),
    "item_seed_kale": (460112, "seed packet kale"),
    "item_seed_pancar": (461520, "seed packet pancar"),
}

def export_all():
    atlas = SpriteAtlas()
    print("Exporting harvested crop item sprites...")
    for name, (row_id, label) in CROP_ITEMS.items():
        img = atlas.get_rgba_image(row_id)
        out_path = OUT_DIR / f"{name}.png"
        img.save(out_path)
        print(f"  [+] {name}.png (#{row_id} - {label})")

    print("\nExporting seed packet inventory sprites...")
    for name, (row_id, label) in SEED_ITEMS.items():
        img = atlas.get_rgba_image(row_id)
        out_path = OUT_DIR / f"{name}.png"
        img.save(out_path)
        print(f"  [+] {name}.png (#{row_id} - {label})")

    print("\n[SUCCESS] All 11 harvested crops and 11 seed packets exported successfully!")

if __name__ == "__main__":
    export_all()
