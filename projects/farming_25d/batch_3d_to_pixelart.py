#!/usr/bin/env python3
"""
Batch 3D-to-PixelArt Converter & Gallery Builder
Converts 32 curated 3D game models into 2.5D retro pixel art sprites using Image-to-Pixel 3.2.0
with the 'farming-25d' profile (32-Color Reference Palette, 8x8 Bayer Dither, Pixel Snapping,
and Tangent-Space Dynamic Lighting Normal Maps).
"""

import os
import sys
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
IMAGE_TO_PIXEL = WORKSPACE_ROOT / "tools" / "image_to_pixel.py"
THUMBS_DIR = WORKSPACE_ROOT / "assets" / "com.threejsassets" / "thumbs"
CUSTOM_DIR = WORKSPACE_ROOT / "projects" / "farming_25d" / "models_3d" / "custom_blender"
OUTPUT_DIR = WORKSPACE_ROOT / "projects" / "farming_25d" / "sprites_2d" / "pixelated_3d"
MASTER_SHEET_PATH = WORKSPACE_ROOT / "projects" / "farming_25d" / "06_3D_TO_PIXELART_GALLERY_SHEET.png"

# Curated 32 3D Assets (Category, Key, Display Name, Source Path)
ASSETS = [
    # Çiftlik Alanı (Farm)
    ("Farm", "stone-well", "Taş Su Kuyusu", THUMBS_DIR / "stone-well.png"),
    ("Farm", "village-well", "Çatılı Çiftlik Kuyusu", THUMBS_DIR / "village-well.png"),
    ("Farm", "autumn-wheelbarrow", "Hasat El Arabası", THUMBS_DIR / "autumn-wheelbarrow.png"),
    ("Farm", "autumn-hay-bale-round", "Saman Balyası", THUMBS_DIR / "autumn-hay-bale-round.png"),
    ("Farm", "autumn-scarecrow", "Tarla Korkuluğu", THUMBS_DIR / "autumn-scarecrow.png"),
    ("Farm", "apple-crate", "Meyve/Hasat Sandığı", THUMBS_DIR / "apple-crate.png"),
    ("Farm", "barrel", "Ahşap Su Fıçısı", THUMBS_DIR / "barrel.png"),
    ("Farm", "axe-chopping-stump", "Balta ve Odun Kütüğü", THUMBS_DIR / "axe-chopping-stump.png"),

    # Köy Meydanı (Village Market)
    ("Village", "bazaar-stall", "Pazar Tezgahı", THUMBS_DIR / "bazaar-stall.png"),
    ("Village", "boarded-store", "Köy Dükkanı Cephesi", THUMBS_DIR / "boarded-store.png"),
    ("Village", "boulangerie-01", "Fırın ve Ticarethane", THUMBS_DIR / "boulangerie-01.png"),
    ("Village", "birch-tree", "Beyaz Huş Ağacı", THUMBS_DIR / "birch-tree.png"),
    ("Village", "autumn-maple", "Kızıl Akçaağaç", THUMBS_DIR / "autumn-maple.png"),
    ("Village", "bush-round-01", "Köy Çiti Çalılığı", THUMBS_DIR / "bush-round-01.png"),

    # Maden & Zindan (Mine / Dungeon)
    ("Mine", "ammo-crate", "Dinamit ve Mühimmat Sandığı", THUMBS_DIR / "ammo-crate.png"),
    ("Mine", "arctic-storm-lantern", "K1 Galeri Feneri", THUMBS_DIR / "arctic-storm-lantern.png"),
    ("Mine", "boulder", "Bazalt Maden Kayası", THUMBS_DIR / "boulder.png"),
    ("Mine", "buffer-stop", "Maden Rayı Tamponu", THUMBS_DIR / "buffer-stop.png"),
    ("Mine", "mossy-boulder", "K3 Yosunlu Kaya Bloğu", THUMBS_DIR / "mossy-boulder.png"),
    ("Mine", "bats-01", "K2 Şaft Yarasaları", THUMBS_DIR / "bats-01.png"),

    # 6 Özel Blender 3B Cevher Damarı
    ("Ores", "SM_Ore_01_Tas", "1. Taş Damarı (Can: 3)", CUSTOM_DIR / "SM_Ore_01_Tas_preview.png"),
    ("Ores", "SM_Ore_02_Bakir", "2. Bakır Damarı (Can: 5)", CUSTOM_DIR / "SM_Ore_02_Bakir_preview.png"),
    ("Ores", "SM_Ore_03_Demir", "3. Demir Damarı (Can: 8)", CUSTOM_DIR / "SM_Ore_03_Demir_preview.png"),
    ("Ores", "SM_Ore_04_Gumus", "4. Gümüş Damarı (Can: 12)", CUSTOM_DIR / "SM_Ore_04_Gumus_preview.png"),
    ("Ores", "SM_Ore_05_Altin", "5. Altın Damarı (Can: 16)", CUSTOM_DIR / "SM_Ore_05_Altin_preview.png"),
    ("Ores", "SM_Ore_06_Fosforit", "6. Fosforit Damarı (Can: 22)", CUSTOM_DIR / "SM_Ore_06_Fosforit_preview.png"),

    # Özel Hibrit Ağaç (Gövde + Billboard Taç + Gölge Vekili)
    ("Hybrid", "SM_Hybrid_Tree_ShadowProxy", "Tablo 12 Hibrit Ağaç & Vekil", CUSTOM_DIR / "SM_Hybrid_Tree_ShadowProxy_preview.png"),

    # 5 FPS Viewmodel Alet ve Silahı
    ("Viewmodel", "VM_01_Kazma_Gold", "FPS Altın Kazma", CUSTOM_DIR / "VM_01_Kazma_Gold_preview.png"),
    ("Viewmodel", "VM_02_Capa_Gold", "FPS Altın Çapa (5x5)", CUSTOM_DIR / "VM_02_Capa_Gold_preview.png"),
    ("Viewmodel", "VM_03_SulamaKabi", "FPS Sulama Kabı (24)", CUSTOM_DIR / "VM_03_SulamaKabi_preview.png"),
    ("Viewmodel", "VM_04_Tirpan_Gold", "FPS Altın Tırpan (3x3)", CUSTOM_DIR / "VM_04_Tirpan_Gold_preview.png"),
    ("Viewmodel", "VM_05_Hitscan_Tabanca_ve_Fener", "FPS Madenci Tabanca & Fener", CUSTOM_DIR / "VM_05_Hitscan_Tabanca_ve_Fener_preview.png"),
]

def run_batch_pixelation():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    print("================================================================================")
    print("BATCH 3D-TO-PIXELART CONVERSION (32 ASSETS) - IMAGE-TO-PIXEL 3.2.0")
    print(f"Profile: farming-25d (32-color CRT palette, Bayer dither, tangent normal map)")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("================================================================================")

    for idx, (cat, key, name, src_path) in enumerate(ASSETS, 1):
        if not src_path.exists():
            print(f"[!] Warning: Missing {src_path}")
            continue

        print(f"[{idx:02d}/32] Converting '{key}' ({cat} - {name})...")
        cmd = [
            sys.executable,
            str(IMAGE_TO_PIXEL),
            "convert",
            str(src_path),
            "--profile", "farming-25d",
            "--width", "64",
            "--scale", "2",
            "--normal-map",
            "--out-dir", str(OUTPUT_DIR),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[ERROR] Failed {key}:\n{res.stderr}")
            continue

        # Look for expected output files
        stem = src_path.stem
        out_1x = OUTPUT_DIR / f"{stem}_farming-25d_64w_1x.png"
        out_2x = OUTPUT_DIR / f"{stem}_farming-25d_64w_2x.png"
        out_n = OUTPUT_DIR / f"{stem}_farming-25d_64w_1x_n.png"

        results.append({
            "category": cat,
            "key": key,
            "name": name,
            "source": src_path,
            "out_1x": out_1x,
            "out_2x": out_2x,
            "out_n": out_n,
        })
        print(f"   [+] Generated 1x Sprite, 2x Preview, and Normal Map.")

    print(f"\n[OK] Successfully converted {len(results)} / 32 assets!")
    build_master_gallery(results)

def build_master_gallery(results):
    print("\n[*] Assembling 06_3D_TO_PIXELART_GALLERY_SHEET.png Master Showcase...")
    cols = 4
    rows = (len(results) + cols - 1) // cols

    card_w = 420
    card_h = 240
    pad_x = 24
    pad_y = 24
    header_top = 160

    canvas_w = cols * (card_w + pad_x) + pad_x
    canvas_h = header_top + rows * (card_h + pad_y) + pad_y

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (12, 16, 22, 255))
    draw = ImageDraw.Draw(canvas)

    # Master Banner Header
    draw.rectangle([0, 0, canvas_w, 130], fill=(18, 24, 34, 255), outline=(40, 54, 76, 255))
    draw.text((30, 24), "3D-TO-PIXELART 2.5D ASSET FORGE — 32 CURATED GAME ASSETS", fill=(82, 255, 154, 255))
    draw.text((30, 56), "Image-to-Pixel 3.2.0 + GDD v1.0 32-Color Reference Palette + 8x8 Bayer Dither + Dynamic Tangent Normal Maps", fill=(170, 185, 205, 255))
    draw.text((30, 84), "Original 3D Model Render  ==>  1x/2x Retro Pixel Art Sprite (64x64)  ==>  Faceted Tangent Normal Map (_n.png)", fill=(255, 213, 65, 255))

    cat_colors = {
        "Farm": (100, 210, 110, 255),
        "Village": (100, 180, 255, 255),
        "Mine": (255, 170, 80, 255),
        "Ores": (255, 215, 65, 255),
        "Hybrid": (82, 255, 154, 255),
        "Viewmodel": (255, 110, 140, 255),
    }

    for idx, item in enumerate(results):
        r = idx // cols
        c = idx % cols
        x = pad_x + c * (card_w + pad_x)
        y = header_top + r * (card_h + pad_y)

        # Card Background
        cat = item["category"]
        c_col = cat_colors.get(cat, (180, 180, 180, 255))
        draw.rectangle([x, y, x + card_w, y + card_h], fill=(22, 28, 38, 255), outline=(48, 62, 86, 255), width=1)
        draw.rectangle([x, y, x + card_w, y + 28], fill=(30, 38, 52, 255))

        # Title
        draw.text((x + 10, y + 6), f"[{cat.upper()}] {item['name']}", fill=c_col)

        # 3 Thumbnail Slots (3D Source, Pixel Art 2x, Normal Map 2x)
        slot_size = 110
        sy = y + 42

        # 1. Source 3D Render
        sx1 = x + 16
        draw.rectangle([sx1, sy, sx1 + slot_size, sy + slot_size], fill=(14, 18, 24, 255), outline=(60, 75, 100, 255))
        if item["source"].exists():
            try:
                src_im = Image.open(item["source"]).convert("RGBA")
                src_im.thumbnail((slot_size - 8, slot_size - 8), Image.Resampling.LANCZOS)
                ox = sx1 + (slot_size - src_im.width) // 2
                oy = sy + (slot_size - src_im.height) // 2
                canvas.alpha_composite(src_im, (ox, oy))
            except Exception:
                pass
        draw.text((sx1 + 4, sy + slot_size + 6), "3D Model Render", fill=(140, 155, 175, 255))

        # Arrow
        draw.text((sx1 + slot_size + 8, sy + 45), "➔", fill=(82, 255, 154, 255))

        # 2. Pixel Art 2x Preview (128x128)
        sx2 = x + 150
        draw.rectangle([sx2, sy, sx2 + slot_size, sy + slot_size], fill=(14, 18, 24, 255), outline=(82, 255, 154, 255))
        if item["out_2x"].exists():
            try:
                px_im = Image.open(item["out_2x"]).convert("RGBA")
                px_im.thumbnail((slot_size - 6, slot_size - 6), Image.Resampling.NEAREST)
                ox = sx2 + (slot_size - px_im.width) // 2
                oy = sy + (slot_size - px_im.height) // 2
                canvas.alpha_composite(px_im, (ox, oy))
            except Exception:
                pass
        draw.text((sx2 + 4, sy + slot_size + 6), "Pixel Art 2.5D", fill=(82, 255, 154, 255))

        # Arrow
        draw.text((sx2 + slot_size + 8, sy + 45), "➔", fill=(255, 213, 65, 255))

        # 3. Dynamic Normal Map
        sx3 = x + 284
        draw.rectangle([sx3, sy, sx3 + slot_size, sy + slot_size], fill=(14, 18, 24, 255), outline=(100, 140, 255, 255))
        if item["out_n"].exists():
            try:
                n_im = Image.open(item["out_n"]).convert("RGBA")
                n_im = n_im.resize((slot_size - 6, slot_size - 6), Image.Resampling.NEAREST)
                ox = sx3 + (slot_size - n_im.width) // 2
                oy = sy + (slot_size - n_im.height) // 2
                canvas.alpha_composite(n_im, (ox, oy))
            except Exception:
                pass
        draw.text((sx3 + 4, sy + slot_size + 6), "Normal Map (_n)", fill=(100, 160, 255, 255))

        # Technical label
        draw.text((x + 10, y + card_h - 22), f"ID: {item['key']} | 64x64px Native | PPU: 32", fill=(110, 125, 145, 255))

    canvas.save(MASTER_SHEET_PATH)
    print(f"\n[SUCCESS] Master Gallery Sheet saved: {MASTER_SHEET_PATH} ({canvas_w}x{canvas_h})")

if __name__ == "__main__":
    run_batch_pixelation()
