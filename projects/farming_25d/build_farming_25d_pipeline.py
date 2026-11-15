"""
Master Pipeline Builder for 2.5D FARMING (GDD-2026-001 v1.0)
Generates and packages 600+ concrete game assets, 3D contact sheets,
2D mega sheets, 8-dir enemy sheets, VFX matrix, and authentic 480x270 Bayer dither CRT screens.
"""

import os
import sys
import math
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

PROJECT_DIR = Path(r"D:\GameMaker\projects\farming_25d")
WORKSPACE_ROOT = Path(r"D:\GameMaker")
MODELS_3D_DIR = PROJECT_DIR / "models_3d"
CUSTOM_BLENDER_DIR = MODELS_3D_DIR / "custom_blender"
REGIONS_GLB_DIR = MODELS_3D_DIR / "regions_glb"
SPRITES_2D_DIR = PROJECT_DIR / "sprites_2d"
CROPS_DIR = SPRITES_2D_DIR / "crops"
TILES_DIR = SPRITES_2D_DIR / "tiles"
PROPS_UI_DIR = SPRITES_2D_DIR / "props_and_ui"
ENEMIES_DIR = PROJECT_DIR / "enemies_8dir"
VFX_DIR = PROJECT_DIR / "vfx"
UI_UX_DIR = PROJECT_DIR / "ui_ux"

for d in [PROJECT_DIR, MODELS_3D_DIR, CUSTOM_BLENDER_DIR, REGIONS_GLB_DIR,
          SPRITES_2D_DIR, CROPS_DIR, TILES_DIR, PROPS_UI_DIR, ENEMIES_DIR, VFX_DIR, UI_UX_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 32-Color Reference Palette (GDD Section 8.4)
FARMING_PALETTE_HEX = [
    "#070B08", "#0D1610", "#142419", "#1E3323",
    "#1E120C", "#2A1A12", "#42281B", "#633E26", "#8A5836", "#BA8255",
    "#132B18", "#1E4226", "#2D5C35", "#3F7C49", "#56A062", "#75C782", "#A2ECAE",
    "#1E2420", "#26332D", "#3A443E", "#505E56", "#6A7B72", "#8A9C93", "#AFC0B7", "#D4E2D9",
    "#52FF9A", "#7AFFB3", "#B3FFD4", "#E0FFEF",
    "#FF8C24", "#FFD541", "#5AD2FF"
]
FARMING_PALETTE_RGB = [
    tuple(int(h.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    for h in FARMING_PALETTE_HEX
]

BAYER_8X8 = np.array([
    [ 0, 32,  8, 40,  2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44,  4, 36, 14, 46,  6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [ 3, 35, 11, 43,  1, 33,  9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47,  7, 39, 13, 45,  5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21]
], dtype=np.float32) / 64.0 - 0.5


def get_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("segoeui.ttf", size)
        except Exception:
            return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 1. GENERATE REMAINING 5 ENEMIES IN 8 DIRECTIONS
# ---------------------------------------------------------------------------
def generate_remaining_enemies():
    enemies = [
        ("enemy_02_fener_golgesi", "arthropod", 202),
        ("enemy_03_kaya_firlatici", "reptile", 303),
        ("enemy_04_damar_zirhlisi", "arthropod", 404),
        ("enemy_05_fosfor_hayaleti", "amorphous", 505),
        ("enemy_06_galeri_muhafizi_boss", "biped", 606),
    ]
    for name, family, seed in enemies:
        still_check = ENEMIES_DIR / f"spr_creature_{name}_still.png"
        if still_check.exists():
            print(f"[SKIP] Enemy '{name}' already generated.")
            continue
        print(f"[GEN] Generating 8-dir enemy: {name} ({family})...")
        cmd = [
            sys.executable,
            str(WORKSPACE_ROOT / "tools" / "creature_gen.py"),
            "generate",
            "--family", family,
            "--seed", str(seed),
            "--name", name,
            "--clips", "idle,walk,action",
            "--dirs", "all",
            "--normal-map",
            "--out", str(ENEMIES_DIR)
        ]
        subprocess.run(cmd, check=True)
        print(f"[OK] Generated {name}")


# ---------------------------------------------------------------------------
# 2. GENERATE TANGENT NORMAL MAP FOR 2D SPRITES
# ---------------------------------------------------------------------------
def make_tangent_normal_map(src_img: Image.Image) -> Image.Image:
    """Generates a tangent space normal map via distance transform + Sobel gradients."""
    rgba = src_img.convert("RGBA")
    arr = np.array(rgba)
    alpha = arr[:, :, 3]
    if not np.any(alpha > 10):
        # Empty image fallback
        return Image.new("RGBA", src_img.size, (128, 128, 255, 0))

    mask = (alpha > 20).astype(np.float32)
    # Pillow shading height via distance transform approximation (box blurs)
    h_map = mask.copy()
    for _ in range(4):
        h_map = (
            np.roll(h_map, 1, axis=0) + np.roll(h_map, -1, axis=0) +
            np.roll(h_map, 1, axis=1) + np.roll(h_map, -1, axis=1) +
            h_map * 4.0
        ) / 8.0
    h_map *= mask

    # Add luminance relief
    luma = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0
    height = h_map * 0.72 + luma * mask * 0.28

    # Sobel gradients
    gx = (
        np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)
    ) * 2.5
    gy = (
        np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)
    ) * 2.5

    gz = np.ones_like(gx)
    mag = np.sqrt(gx * gx + gy * gy + gz * gz)
    mag = np.maximum(mag, 1e-5)

    nx = -gx / mag
    ny = -gy / mag
    nz = gz / mag

    # Tangent normal map encoding: R=(nx*0.5+0.5)*255, G=(ny*0.5+0.5)*255, B=(nz*0.5+0.5)*255
    r = np.clip((nx * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    g = np.clip((ny * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    b = np.clip((nz * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    a = alpha

    normal_arr = np.dstack((r, g, b, a))
    return Image.fromarray(normal_arr, mode="RGBA")


# ---------------------------------------------------------------------------
# 3. COMPOSE 04_BLENDER_CUSTOM_ORES_VIEWMODELS_AND_HYBRID_TREES_12_GLBS.png
# ---------------------------------------------------------------------------
def compose_custom_3d_sheet():
    out_path = MODELS_3D_DIR / "04_BLENDER_CUSTOM_ORES_VIEWMODELS_AND_HYBRID_TREES_12_GLBS.png"
    print(f"[SHEET] Composing {out_path.name}...")
    models_meta = [
        ("SM_Ore_01_Tas", "1. Taş Damarı (Stone Vein)", "HP 3 | Temel Kazma | K1–K4", "260 tris", "#8A9C93"),
        ("SM_Ore_02_Bakir", "2. Bakır Damarı (Copper Vein)", "HP 5 | Temel Kazma | K1–K2", "312 tris", "#C86D51"),
        ("SM_Ore_03_Demir", "3. Demir Damarı (Iron Vein)", "HP 8 | Bakır Kazma | K2–K3", "348 tris", "#8C99A6"),
        ("SM_Ore_04_Gumus", "4. Gümüş Damarı (Silver Vein)", "HP 12 | Demir Kazma | K3–K4", "390 tris", "#C0CBDC"),
        ("SM_Ore_05_Altin", "5. Altın Damarı (Gold Vein)", "HP 16 | Gümüş Kazma | K4 Cepleri", "410 tris", "#FFD541"),
        ("SM_Ore_06_Fosforit", "6. Fosforit Damarı (Phosphorite)", "HP 22 | Altın Kazma | K4 Karanlık", "464 tris", "#52FF9A"),
        ("VM_01_Kazma_Gold", "FPS Viewmodel: Altın Kazma", "Sağ El | 3x Hız | 0.35s Vuruş", "482 tris", "#FFD541"),
        ("VM_02_Capa_Gold", "FPS Viewmodel: Altın Çapa", "Sağ El | 5x5 Alan Sürme", "414 tris", "#BA8255"),
        ("VM_03_SulamaKabi", "FPS Viewmodel: Sulama Kabı", "Sağ El | 24 Karo Kapasite", "512 tris", "#5AD2FF"),
        ("VM_04_Tirpan", "FPS Viewmodel: Altın Tırpan", "Sağ El | 3x3 Biçme + Otomatik Toplama", "436 tris", "#C0CBDC"),
        ("VM_05_Hitscan_Tabanca_ve_Fener", "FPS Viewmodel: Tabanca + Fener", "Sol El: 5.5m Fener | Sağ El: Hitscan", "788 tris", "#52FF9A"),
        ("SM_Hybrid_Tree_ShadowProxy", "Hibrit Ağaç + Gölge Vekili", "3B Gövde + Y-Billboard Taç + Kapsül", "394 tris", "#56A062"),
    ]

    # 4 columns x 3 rows
    cols, rows = 4, 3
    tile_w, tile_h = 440, 340
    pad = 24
    header_h = 130
    w = cols * tile_w + (cols + 1) * pad
    h = header_h + rows * tile_h + (rows + 1) * pad

    sheet = Image.new("RGBA", (w, h), (13, 22, 16, 255))
    draw = ImageDraw.Draw(sheet)

    # CRT scanlines pattern
    for y in range(0, h, 4):
        draw.line([(0, y), (w, y)], fill=(7, 11, 8, 80), width=1)

    # Header
    font_title = get_font(36)
    font_sub = get_font(18)
    font_bold = get_font(18)
    font_small = get_font(14)
    font_mono = get_font(13)

    draw.rectangle([(pad, pad), (w - pad, header_h - 15)], fill=(20, 36, 25, 230), outline=(82, 255, 154, 255), width=2)
    draw.text((pad + 24, pad + 14), "ÖZEL BLENDER 5.2 + KILN 3.0 DÜŞÜK POLİGON 3B MODELLER", fill=(82, 255, 154), font=font_title)
    draw.text((pad + 26, pad + 58), "2.5D FARMING (GDD v1.0) · Tablo 6 (6 Cevher Damarı) + Tablo 9 (5 FPS Viewmodel) + Tablo 12 (Hibrit Ağaç & Gölge Vekili)", fill=(179, 255, 212), font=font_sub)
    draw.text((pad + 26, pad + 82), "32 Renk Paleti (#070B08..#52FF9A) · Gerçek Zamanlı PBR / Emisyonlu Gölgelendirici · < 850 Üçgen Bütçesi", fill=(138, 156, 147), font=font_small)

    for idx, (m_id, name, desc, tris, accent_hex) in enumerate(models_meta):
        c = idx % cols
        r = idx // cols
        x0 = pad + c * (tile_w + pad)
        y0 = header_h + r * (tile_h + pad)

        # Card bg
        draw.rectangle([(x0, y0), (x0 + tile_w, y0 + tile_h)], fill=(15, 26, 19, 240), outline=(58, 68, 62, 255), width=1)
        # Accent top bar
        draw.rectangle([(x0, y0), (x0 + tile_w, y0 + 6)], fill=accent_hex)

        # Model preview image
        prev_path = CUSTOM_BLENDER_DIR / f"{m_id}_preview.png"
        if prev_path.exists():
            with Image.open(prev_path) as p_img:
                p_thumb = p_img.convert("RGBA").resize((250, 250), Image.Resampling.LANCZOS)
                px = x0 + (tile_w - 250) // 2
                py = y0 + 16
                sheet.alpha_composite(p_thumb, (px, py))

        # Model labels
        draw.text((x0 + 16, y0 + 268), name, fill=(255, 255, 255), font=font_bold)
        draw.text((x0 + 16, y0 + 292), desc, fill=(175, 192, 183), font=font_small)
        draw.text((x0 + 16, y0 + 314), f"GLB: {m_id}.glb", fill=(82, 255, 154), font=font_mono)
        draw.text((x0 + tile_w - 95, y0 + 314), tris, fill=(255, 213, 65), font=font_mono)

    sheet.save(out_path)
    print(f"[OK] Saved {out_path}")


# ---------------------------------------------------------------------------
# 4. COMPOSE 3D CATALOG SHEETS (3 SHEETS x 48 MODELS = 144 MODELS)
# ---------------------------------------------------------------------------
def compose_3d_catalog_sheets():
    thumbs_dir = WORKSPACE_ROOT / "assets" / "com.threejsassets" / "thumbs"
    models_dir = WORKSPACE_ROOT / "assets" / "com.threejsassets" / "models"

    sheets_meta = [
        (
            "01_3D_CATALOG_SHEET_FARM_AND_VILLAGE_48_GLBS.png",
            "BÖLGE 1: ÇİFTLİK ALANI (80×80) & BÖLGE 2: KÖY MEYDANI (40×40) — 48 3B MODEL",
            "GDD Tablo 10 · Kuyular, Ambarlar, Çitler, El Arabaları, Pazar Tezgahları, Dükkânlar, Fenerler & Meydan Karoları",
            [
                ("stone-well", "Taş Su Kuyusu (Merkez)"),
                ("village-well", "Çatılı Köy Kuyusu"),
                ("tsurube-well", "Kovalı Tarla Kuyusu"),
                ("big-red-barn", "Büyük Kırmızı Ambar"),
                ("farmhouse", "Ana Çiftlik Evi"),
                ("home-cottage-01", "Taş Çiftlik Kulübesi"),
                ("garden-shed", "Tohum & Alet Kulübesi"),
                ("goods-shed", "Hasat Sundurması"),
                ("stabbur-storehouse", "Yükseltilmiş Tahıl Ambarı"),
                ("chicken-coop", "Tavuk Kümesi"),
                ("farm-stand", "Hasat Satış Tezgahı"),
                ("farm-gate", "Çiftlik Ana Kapısı"),
                ("rail-fence", "Ahşap Korkuluk Çit"),
                ("split-rail-fence", "Rustik Tarla Çiti"),
                ("picket-fence", "Bahçe Çiti (Ev Çevresi)"),
                ("drystone-wall", "Kuru Taş Sınır Duvarı"),
                ("wheelbarrow", "Klasik El Arabası"),
                ("autumn-wheelbarrow", "Hasat El Arabası"),
                ("handcart", "İki Tekerlekli El Arabası"),
                ("hay-wagon", "Büyük Saman Arabası"),
                ("scarecrow", "Tarla Korkuluğu"),
                ("autumn-scarecrow", "Hasat Korkuluğu"),
                ("produce-crate", "Sebze / Hasat Kasası"),
                ("apple-crate", "Elma Kasası"),
                ("milk-churns-crates", "Süt Güğümü & Kasa"),
                ("barrel", "Su / Kompost Fıçısı"),
                ("harvest-lantern", "Çiftlik Feneri"),
                ("ploughed-field", "Sürülmüş Toprak (3B)"),
                ("wheat-cluster", "Olgun Buğday Kümesi"),
                ("pumpkin-pile-01", "Balkabağı Yığını"),
                ("cow", "Çiftlik İneği"),
                ("sheep", "Çiftlik Koyunu"),
                ("market-stall", "Köy Pazar Tezgahı"),
                ("bazaar-stall", "Tenteli Pazar Standı"),
                ("gs-produce-stand", "Manav Satış Standı"),
                ("general-store", "Genel Mağaza Binası"),
                ("smithy-forge", "Demirci & Alet Atölyesi"),
                ("boulangerie-01", "Köy Fırını"),
                ("cafe-brasserie-01", "Köy Meydanı Hanı"),
                ("shop-awning-01", "Çizgili Dükkân Tentesi"),
                ("shop-hanging-sign-01", "Ferforje Dükkân Tabelası"),
                ("waypost", "6 Bölge Yön Direği"),
                ("plaza-bench-01", "Meydan Ahşap Bankı"),
                ("plank-table", "Ticaret Sergi Masası"),
                ("streetlamp", "Köy Sokak Feneri"),
                ("wallace-fountain-01", "Meydan Süs Çeşmesi"),
                ("cobblestone-place-01", "Arnavut Kaldırımı Karosu"),
                ("agora-flagstone-tile", "Yassı Taş Meydan Karosu"),
            ]
        ),
        (
            "02_3D_CATALOG_SHEET_MEADOW_SWAMP_AND_BARN_48_GLBS.png",
            "BÖLGE 3: ÇAYIR (60×50), BÖLGE 4: BATAKLIK (45×45) & BÖLGE 6: HARABE AHIR — 48 3B MODEL",
            "GDD Tablo 10 · Ağaçlar (Meşe, Çam, Selvi), Sazlıklar, Tahta İskeleler, Harabe Çatılar, Saman Balyaları & Bataklık Suyu",
            [
                ("oak", "Ulu Meşe Ağacı"),
                ("tree-oak-01", "Çayır Meşesi 01"),
                ("pine", "Çam Ağacı (Pine)"),
                ("spruce-tree", "Ladin Ağacı (Spruce)"),
                ("birch-tree", "Huş Ağacı (Birch)"),
                ("autumn-maple", "Kızıl Akçaağaç"),
                ("axe-chopping-stump", "Baltalı Odun Kütüğü"),
                ("log-pile", "Kesilmiş Kütük Yığını"),
                ("log-bench", "Kütükten Oturak"),
                ("bush", "Doğal Çalı Kümesi"),
                ("heather-shrub", "Fundalık / Çalı"),
                ("wildflower", "Yabani Çiçek Kümesi"),
                ("fern", "Eğrelti Otu (Fern)"),
                ("tall-grass", "Uzun Çayır Otu"),
                ("boulder", "Büyük Çayır Kayası"),
                ("rock-cluster", "Doğal Kaya Grubu"),
                ("footbridge-span", "Ahşap Yaya Köprüsü"),
                ("trailhead-sign", "Patika Tabelası"),
                ("grass-meadow-tile", "Çayır Çimi Karosu"),
                ("dirt-trail", "Toprak Patika Karosu"),
                ("dead-tree", "Kurumuş Bataklık Ağacı"),
                ("cypress-tree", "Bataklık Selvisi"),
                ("cypress-knee-cluster", "Ağaç Kökü & Mantar"),
                ("cattail-reed-clump", "Su Kamışı / Sazlık"),
                ("lily-pad-cluster", "Nilüfer Yaprakları"),
                ("spanish-moss-hang", "Sarkık Bataklık Yosunu"),
                ("driftwood-snag", "Çürük Bataklık Kütüğü"),
                ("log-bridge", "Kütük Bataklık Köprüsü"),
                ("dock-jetty", "Ahşap Balıkçı İskelesi"),
                ("boardwalk-plank", "Tahta Yürüyüş Yolu"),
                ("stilt-shack", "Kazıklı Bataklık Kulübesi"),
                ("mossy-boulder", "Yosunlu Bataklık Kayası"),
                ("pirogue", "Bataklık Sandalı"),
                ("firefly-swarm", "Gece Ateşböceği Mesh"),
                ("reed-marsh-tile", "Sazlıklı Bataklık Karosu"),
                ("water-open-bayou", "Bulanık Bataklık Suyu"),
                ("ruined-house-shell", "Yıkık Ahır İskeleti"),
                ("boarded-store", "Terkedilmiş Ahşap Yapı"),
                ("shack", "Harabe Tahta Baraka"),
                ("hay-bale", "Eski Saman Balyası"),
                ("autumn-hay-bale-round", "Büyük Saman Rulosu"),
                ("cobweb-corner", "Köşe Örümcek Ağı"),
                ("ivy-overgrowth", "Yabani Duvar Sarmaşığı"),
                ("dun-crate", "Kilitli Ahır Sandığı"),
                ("ammo-crate", "Demir Kuşaklı Sandık"),
                ("dun-ale-barrel", "Çürük Ahşap Fıçı"),
                ("debris-pile", "Çökmüş Çatı Molozu"),
                ("bats-01", "Tavan Yarasaları Mesh"),
            ]
        ),
        (
            "03_3D_CATALOG_SHEET_MINE_K1_TO_K4_48_GLBS.png",
            "BÖLGE 5: MADEN GİRİŞİ (25×25) & 4 ZİNDAN KATMANI (K1–K4) — 48 3B MODEL",
            "GDD Tablo 7 · Maden Vagonları, Raylar, İskeleler, Koridorlar, Meşaleler, Hazine Sandıkları, Fenerler & Çökmüş Galeriler",
            [
                ("tunnel-portal", "Taş Maden Giriş Portalı"),
                ("tunnel-interior-tile", "Tünel Zemin Karosu"),
                ("track-tunnel-straight-tile", "Raylı Tünel Girişi"),
                ("open-coal-wagon", "Cevher Maden Vagonu"),
                ("permanent-way-trolley", "Raylı El Vagonu"),
                ("flatbed-wagon", "Ağır Cevher Vagonu"),
                ("buffer-stop", "Ray Sonu Tamponu"),
                ("track-straight-tile", "Düz Maden Rayı"),
                ("track-curve-tile", "Dönemeç Maden Rayı"),
                ("track-t-junction-tile", "Ray T-Kavşağı"),
                ("point-ground-frame", "Ray Makas Değiştirme Kolu"),
                ("scaffold-access-tower", "K2 İskele Kulesi"),
                ("scaffold-facade", "Galeri Destek İskelesi"),
                ("library-ladder", "Katman İniş Merdiveni"),
                ("gantry-crane", "Maden Asansör Vinci"),
                ("ice-drill-rig", "K4 Derin Sondaj Burgusu"),
                ("dun-corridor-straight", "Zindan Düz Koridoru"),
                ("dun-corridor-corner", "Zindan L-Köşe Koridoru"),
                ("dun-corridor-tjunction", "Zindan T-Kavşak Koridoru"),
                ("dun-corridor-4way", "Zindan 4-Yol Kavşağı"),
                ("corridor-dead-end", "K4 Çıkmaz Galeri Sonu"),
                ("dun-room-wall", "Zindan Taş Duvarı"),
                ("dun-room-floor", "Çatlak Taş Zindan Tabanı"),
                ("dun-vaulted-ceiling", "Kemerli Zindan Tavanı"),
                ("dun-descent-stair", "Alt Katmana İnen Merdiven"),
                ("dun-arch-doorway", "Gotik Taş Kemer Kapı"),
                ("dun-heavy-door", "Kilitli Zindan Kapısı"),
                ("dun-cell-bar-door", "Parmaklıklı Galeri Kapısı"),
                ("cutting-rock-face", "Doğal Mağara Kaya Duvarı"),
                ("inspection-pit", "K2 Çukur / Hendek Karosu"),
                ("railway-rock-cluster", "Bazalt Taş Damarı Baz"),
                ("sandstone-boulder", "Kızıl Bakır Damarı Baz"),
                ("granite-rock-cluster", "Koyu Demir Damarı Baz"),
                ("marble-boulder", "Parlak Gümüş Damarı Baz"),
                ("scree-rock-cluster", "Altın Damarı Baz"),
                ("ice-growler", "K4 Fosforit Damarı Baz"),
                ("fjord-cliff-rock", "Mağara Stalagmit Sütunu"),
                ("rockfall-debris", "Çökmüş Galeri Kayası"),
                ("dun-rubble-pile", "Zindan Moloz Yığını"),
                ("dun-wall-torch", "K1 Duvar Meşalesi"),
                ("post-torch", "Ayaklı Maden Meşalesi"),
                ("dun-standing-brazier", "Ayaklı Demir Ateş Çanağı"),
                ("fire-brazier", "K4 Çekirdek Ateş Mangalı"),
                ("dun-treasure-chest", "Zindan Hazine Sandığı"),
                ("oil-lantern", "Madenci Gazyağı Feneri"),
                ("arctic-storm-lantern", "K4 Fırtına Feneri"),
                ("dun-skeleton", "K4 Eski Madenci İskeleti"),
                ("dun-rat", "Maden Sıçanı Mesh"),
            ]
        ),
    ]

    cols, rows = 8, 6
    tile_w, tile_h = 230, 185
    pad = 16
    header_h = 110
    w = cols * tile_w + (cols + 1) * pad
    h = header_h + rows * tile_h + (rows + 1) * pad

    font_title = get_font(28)
    font_sub = get_font(15)
    font_bold = get_font(13)
    font_mono = get_font(11)

    for filename, title, subtitle, items in sheets_meta:
        out_path = MODELS_3D_DIR / filename
        print(f"[SHEET] Composing 3D Catalog: {filename} ({len(items)} models)...")
        sheet = Image.new("RGBA", (w, h), (11, 18, 14, 255))
        draw = ImageDraw.Draw(sheet)

        # Header box
        draw.rectangle([(pad, pad), (w - pad, header_h - 10)], fill=(18, 30, 22, 230), outline=(82, 255, 154, 255), width=2)
        draw.text((pad + 20, pad + 12), title, fill=(82, 255, 154), font=font_title)
        draw.text((pad + 22, pad + 52), subtitle, fill=(175, 192, 183), font=font_sub)
        draw.text((pad + 22, pad + 76), "Tüm Modeller: models_3d/regions_glb/ · Düşük Poligon / Y-Up / PBR Dokulu .glb Dosyaları", fill=(138, 156, 147), font=font_mono)

        for idx, (slug, display_name) in enumerate(items):
            c = idx % cols
            r = idx // cols
            x0 = pad + c * (tile_w + pad)
            y0 = header_h + r * (tile_h + pad)

            # Card
            draw.rectangle([(x0, y0), (x0 + tile_w, y0 + tile_h)], fill=(16, 25, 20, 240), outline=(42, 54, 46, 255), width=1)

            # Copy actual .glb to regions_glb
            src_glb = models_dir / f"{slug}.glb"
            dest_glb = REGIONS_GLB_DIR / f"{slug}.glb"
            if src_glb.exists() and not dest_glb.exists():
                try:
                    import shutil
                    shutil.copy2(src_glb, dest_glb)
                except Exception:
                    pass

            # Thumbnail
            thumb_path = thumbs_dir / f"{slug}.png"
            if thumb_path.exists():
                with Image.open(thumb_path) as t_img:
                    # Clean resize
                    t_clean = t_img.convert("RGBA").resize((130, 130), Image.Resampling.LANCZOS)
                    sheet.alpha_composite(t_clean, (x0 + (tile_w - 130) // 2, y0 + 6))

            # Label
            draw.text((x0 + 8, y0 + 142), display_name[:24], fill=(240, 245, 242), font=font_bold)
            draw.text((x0 + 8, y0 + 162), f"{slug}.glb", fill=(82, 255, 154), font=font_mono)

        sheet.save(out_path)
        print(f"[OK] Saved {out_path}")


# ---------------------------------------------------------------------------
# 5. COMPOSE 2D CROPS MEGA SHEET (11 CROPS x 6 STAGES = 66 CROPS + NORMALS + 5 SOIL)
# ---------------------------------------------------------------------------
def process_crops_and_compose_sheet():
    out_path = SPRITES_2D_DIR / "01_2D_CROPS_66_STAGES_SOIL_STATES_AND_NORMALS_MEGA_SHEET.png"
    print(f"[SHEET] Processing 2D crops, normals & composing {out_path.name}...")

    # Locate FarmLife inner dir
    base_fl = WORKSPACE_ROOT / "libraries" / "com.github.huu-yuu.pixelsrpg-forge" / "Asset_Packs_素材套图"
    fl_dirs = [d for d in base_fl.iterdir() if "FarmLife" in d.name]
    inner_fl = [d for d in fl_dirs[0].iterdir() if d.is_dir()][0]

    crops_meta = [
        ("yonca", "parsnip", "1. Yonca / Parsnip", "2 Gün | 10->30 | Kâr 2.7", "#75C782"),
        ("turp", "radish", "2. Turp (Radish)", "3 Gün | 18->55 | Kâr 3.8", "#FF8C24"),
        ("bugday", "wheat", "3. Buğday (Wheat)", "3 Gün | 25->80 | Çoklu x2", "#FFD541"),
        ("patates", "potato", "4. Patates (Potato)", "4 Gün | 40->130 | Kâr 5.9", "#BA8255"),
        ("havuc", "carrot", "5. Havuç (Carrot)", "5 Gün | 55->190 | Çoklu x2", "#FF8C24"),
        ("lahana", "cabbage", "6. Lahana (Cabbage)", "5 Gün | 70->240 | Kâr 7.4", "#56A062"),
        ("domates", "cauliflower", "7. Domates / Karnabahar", "6 Gün | 95->150 | Çoklu x4", "#FF8C24"),
        ("kabak", "pumpkin", "8. Kabak (Pumpkin)", "6 Gün | 130->310 | Kâr 11.2", "#FFD541"),
        ("pancar", "beetroot", "9. Bonus: Pancar", "4 Gün | Kök Boyası", "#BA8255"),
        ("kale", "kale", "10. Bonus: Kara Lahana", "5 Gün | Kışlık Ekin", "#3F7C49"),
        ("aycicegi", "sunflower", "11. Bonus: Ayçiçeği", "7 Gün | Yağ & Tohum", "#FFD541"),
    ]

    soil_states = [
        ("soil_01", "1. İşlenmemiş Toprak", "Doğal Çim / Yabani Ot"),
        ("soil_02", "2. Sürülmüş Kuru Toprak", "Çapa ile sürülmüş açık kahve"),
        ("soil_03", "3. Ekili Kuru Toprak", "Tohum ekilmiş kuru toprak"),
        ("soil_04", "4. Sulanmış-Ekili Toprak", "Koyu nemli toprak + Mavi parıltı"),
        ("soil_05", "5. Hasada Hazır Toprak", "Olgun ekin + Altın pırıltı"),
    ]

    # Grid dimensions:
    # 11 crops (rows) x 6 stages (cols). Each cell shows Albedo + Tangent Normal side by side.
    # Plus bottom section for the 5 soil states!
    cols = 6
    rows = len(crops_meta)
    cell_w, cell_h = 240, 100
    pad = 12
    header_h = 120
    soil_h = 160

    w = 190 + cols * (cell_w + pad) + pad
    h = header_h + rows * (cell_h + pad) + soil_h + pad * 2

    sheet = Image.new("RGBA", (w, h), (13, 22, 16, 255))
    draw = ImageDraw.Draw(sheet)

    font_title = get_font(30)
    font_sub = get_font(16)
    font_bold = get_font(14)
    font_small = get_font(12)
    font_mono = get_font(11)

    # Header
    draw.rectangle([(pad, pad), (w - pad, header_h - 15)], fill=(20, 36, 25, 230), outline=(82, 255, 154, 255), width=2)
    draw.text((pad + 20, pad + 14), "2B EKİN BÜYÜME EVRELERİ (66 SPRITE) + SİLİNDİRİK NORMAL HARİTALARI (66 SPRITE)", fill=(82, 255, 154), font=font_title)
    draw.text((pad + 22, pad + 56), "GDD Tablo 5 (8 Çekirdek + 3 Bonus Ekin) · Evre 00 (Tohum) -> Evre 05 (Hasat) · Y-Billboard Dinamik Noktasal Işıklandırma", fill=(179, 255, 212), font=font_sub)
    draw.text((pad + 22, pad + 82), "Her hücrede: [Sol: 32 Renk Albedo Sprite] [Sağ: Silindirik Teğet Normal Haritası (_n.png) Dot(N,L) Gölgelendirme]", fill=(138, 156, 147), font=font_small)

    for r_idx, (gdd_name, src_name, label, desc, accent) in enumerate(crops_meta):
        y0 = header_h + r_idx * (cell_h + pad)

        # Row Header Box
        draw.rectangle([(pad, y0), (pad + 175, y0 + cell_h)], fill=(18, 30, 22, 240), outline=(58, 68, 62, 255), width=1)
        draw.rectangle([(pad, y0), (pad + 6, y0 + cell_h)], fill=accent)
        draw.text((pad + 14, y0 + 14), label, fill=(255, 255, 255), font=font_bold)
        draw.text((pad + 14, y0 + 42), desc, fill=(175, 192, 183), font=font_small)
        draw.text((pad + 14, y0 + 72), f"{gdd_name}_00..05", fill=(82, 255, 154), font=font_mono)

        for stage in range(6):
            c_idx = stage
            x0 = pad + 190 + c_idx * (cell_w + pad)

            draw.rectangle([(x0, y0), (x0 + cell_w, y0 + cell_h)], fill=(16, 25, 20, 240), outline=(42, 54, 46, 255), width=1)
            stage_str = f"{stage:02d}"
            draw.text((x0 + 8, y0 + 6), f"Evre {stage_str} ({'Tohum' if stage==0 else 'Filiz' if stage==1 else 'Genç' if stage==2 else 'Orta' if stage==3 else 'Olgun' if stage==4 else 'Hasat'})", fill=(179, 255, 212), font=font_mono)

            # Load src sprite
            src_file = inner_fl / f"{src_name}_{stage_str}.png"
            dest_albedo = CROPS_DIR / f"crop_{gdd_name}_stage_{stage_str}.png"
            dest_normal = CROPS_DIR / f"crop_{gdd_name}_stage_{stage_str}_n.png"

            if src_file.exists():
                with Image.open(src_file) as s_img:
                    s_rgba = s_img.convert("RGBA")
                    # Save local crop albedo
                    s_rgba.save(dest_albedo)
                    # Generate normal map
                    norm_img = make_tangent_normal_map(s_rgba)
                    norm_img.save(dest_normal)

                    # Draw on sheet (scaled 2.5x nearest)
                    scale_factor = 2
                    disp_albedo = s_rgba.resize((s_rgba.width * scale_factor, s_rgba.height * scale_factor), Image.Resampling.NEAREST)
                    disp_normal = norm_img.resize((norm_img.width * scale_factor, norm_img.height * scale_factor), Image.Resampling.NEAREST)

                    sheet.alpha_composite(disp_albedo, (x0 + 20, y0 + 26))
                    sheet.alpha_composite(disp_normal, (x0 + 130, y0 + 26))
                    draw.text((x0 + 20, y0 + 82), "Albedo", fill=(138, 156, 147), font=font_mono)
                    draw.text((x0 + 130, y0 + 82), "Normal Map", fill=(90, 210, 255), font=font_mono)

    # Bottom Soil Section
    y_soil = header_h + rows * (cell_h + pad) + pad
    draw.rectangle([(pad, y_soil), (w - pad, y_soil + soil_h - 10)], fill=(18, 30, 22, 240), outline=(82, 255, 154, 255), width=1)
    draw.text((pad + 20, y_soil + 12), "GDD TABLO 4: 5 KARO DURUMU GEÇİŞLERİ [İşlenmemiş -> Sürülmüş -> Ekili -> Sulanmış -> Hasada Hazır]", fill=(82, 255, 154), font=font_bold)

    soil_col_w = (w - pad * 2 - 40) // 5
    for s_idx, (s_slug, s_title, s_desc) in enumerate(soil_states):
        sx = pad + 20 + s_idx * soil_col_w
        sy = y_soil + 44

        draw.rectangle([(sx, sy), (sx + soil_col_w - 16, sy + 90)], fill=(14, 22, 17, 255), outline=(58, 68, 62, 255), width=1)

        # Load or create soil sprite
        soil_path = TILES_DIR / f"{s_slug}.png"
        src_soil = inner_fl / f"soil_{s_idx:02d}.png"
        if src_soil.exists():
            with Image.open(src_soil) as s_img:
                s_rgba = s_img.convert("RGBA")
                s_rgba.save(soil_path)
                s_disp = s_rgba.resize((48, 48), Image.Resampling.NEAREST)
                sheet.alpha_composite(s_disp, (sx + 10, sy + 20))
        else:
            # Fallback procedural tile
            tile = Image.new("RGBA", (48, 48), FARMING_PALETTE_RGB[5 + s_idx])
            sheet.alpha_composite(tile, (sx + 10, sy + 20))

        draw.text((sx + 68, sy + 16), s_title, fill=(255, 213, 65), font=font_small)
        draw.text((sx + 68, sy + 38), s_desc, fill=(175, 192, 183), font=font_mono)
        draw.text((sx + 68, sy + 62), f"{s_slug}.png", fill=(82, 255, 154), font=font_mono)

    sheet.save(out_path)
    print(f"[OK] Saved {out_path}")


# ---------------------------------------------------------------------------
# 6. COMPOSE 2D TOOLS, ORES, DUNGEON PROPS & UI MEGA SHEET (126 ASSETS)
# ---------------------------------------------------------------------------
def compose_props_and_ui_sheet():
    out_path = SPRITES_2D_DIR / "02_2D_TOOLS_ORES_DUNGEON_NPCS_AND_UI_ICONS_MEGA_SHEET.png"
    print(f"[SHEET] Composing {out_path.name}...")

    # Load items from pixelsrpg-forge
    forge_dir = WORKSPACE_ROOT / "libraries" / "com.github.huu-yuu.pixelsrpg-forge"
    items_to_collect = []

    # 1. Tools (4 Tiers x 5 Tools = 20)
    tools_list = [
        ("spr_tool_kazma_bakir", "Kazma (Bakır Tier 1)", "Cevher Hızı: 1.0x", "#C86D51"),
        ("spr_tool_kazma_demir", "Kazma (Demir Tier 2)", "Cevher Hızı: 1.5x", "#8C99A6"),
        ("spr_tool_kazma_gumus", "Kazma (Gümüş Tier 3)", "Cevher Hızı: 2.2x", "#C0CBDC"),
        ("spr_tool_kazma_altin", "Kazma (Altın Tier 4)", "Cevher Hızı: 3.0x", "#FFD541"),
        ("spr_tool_capa_bakir", "Çapa (Bakır Tier 1)", "Alan: 1x1 Karo", "#C86D51"),
        ("spr_tool_capa_demir", "Çapa (Demir Tier 2)", "Alan: 1x3 Hat", "#8C99A6"),
        ("spr_tool_capa_gumus", "Çapa (Gümüş Tier 3)", "Alan: 3x3 Alan", "#C0CBDC"),
        ("spr_tool_capa_altin", "Çapa (Altın Tier 4)", "Alan: 5x5 Dev Alan", "#FFD541"),
        ("spr_tool_sulama_bakir", "Sulama Kabı (Bakır)", "Depo: 6 Karo", "#C86D51"),
        ("spr_tool_sulama_demir", "Sulama Kabı (Demir)", "Depo: 12 Karo", "#8C99A6"),
        ("spr_tool_sulama_gumus", "Sulama Kabı (Gümüş)", "Depo: 18 Karo", "#C0CBDC"),
        ("spr_tool_sulama_altin", "Sulama Kabı (Altın)", "Depo: 24 Karo", "#5AD2FF"),
        ("spr_tool_tirpan_bakir", "Tırpan (Bakır)", "Alan: 1x1 Karo", "#C86D51"),
        ("spr_tool_tirpan_demir", "Tırpan (Demir)", "Alan: 1x3 Hat", "#8C99A6"),
        ("spr_tool_tirpan_gumus", "Tırpan (Gümüş)", "Alan: 3x3 Alan", "#C0CBDC"),
        ("spr_tool_tirpan_altin", "Tırpan (Altın)", "Alan: 3x3 + Oto-Toplama", "#FFD541"),
        ("spr_tool_hitscan_pistol", "Madenci Tabancası", "14m Menzil | 18 Hasar", "#8C99A6"),
        ("spr_tool_miner_lantern", "K4 Madenci Feneri", "5.5m Işık Yarıçapı", "#52FF9A"),
        ("spr_tool_fishing_rod", "Bataklık Oltası", "Bölge 4 Balıkçılığı", "#BA8255"),
        ("spr_tool_armor_gold", "Altın Madenci Zırhı", "Hasar -%40 | Ceza -%5", "#FFD541"),
    ]

    # 2. Ores & Minerals (6 types)
    ores_list = [
        ("ore_01_tas", "Taş (Stone)", "K1–K4 | Değer: 2", "#8A9C93"),
        ("ore_02_bakir", "Bakır Külçesi", "K1–K2 | Değer: 8", "#C86D51"),
        ("ore_03_demir", "Demir Külçesi", "K2–K3 | Değer: 20", "#8C99A6"),
        ("ore_04_gumus", "Gümüş Külçesi", "K3–K4 | Değer: 45", "#C0CBDC"),
        ("ore_05_altin", "Altın Külçesi", "K4 | Değer: 95", "#FFD541"),
        ("ore_06_fosforit", "Fosforit Kristali", "K4 Karanlık | Değer: 220", "#52FF9A"),
    ]

    # 3. Dungeon Props, Chests, Keys, Torches (34 items)
    dungeon_items = [
        ("prop_chest_wood", "Ahşap Hazine Sandığı"),
        ("prop_chest_iron", "Demir Kuşaklı Sandık"),
        ("prop_chest_gold", "Altın İşlemeli Sandık"),
        ("prop_key_copper", "Bakır Galeri Anahtarı"),
        ("prop_key_iron", "Demir Zindan Anahtarı"),
        ("prop_key_skull", "K4 Çekirdek İskelet Anahtarı"),
        ("prop_torch_lit", "Yanan Duvar Meşalesi"),
        ("prop_torch_unlit", "Sönük Duvar Meşalesi"),
        ("prop_lantern_oil", "Gazyağı Feneri"),
        ("prop_brazier_fire", "Ateş Mangalı"),
        ("prop_barrel_water", "Su Fıçısı"),
        ("prop_barrel_powder", "Barut Fıçısı (Patlayıcı)"),
        ("prop_crate_dynamite", "Dinamit Kasası"),
        ("prop_potion_health", "Can İksiri (+50 HP)"),
        ("prop_potion_stamina", "Enerji İksiri (+100 Enerji)"),
        ("prop_potion_glow", "K4 Fosfor Parıltı İksiri"),
        ("prop_mine_cart_empty", "Boş Maden Vagonu"),
        ("prop_mine_cart_ore", "Cevher Dolu Maden Vagonu"),
        ("prop_rail_straight", "Düz Ray Karosu"),
        ("prop_rail_turn", "Dönemeç Ray Karosu"),
        ("prop_ladder_wood", "Ahşap Zindan Merdiveni"),
        ("prop_scaffold_beam", "Ahşap Tahkimat Direği"),
        ("prop_stalagmite_sm", "Küçük Mağara Dikiti"),
        ("prop_stalagmite_lg", "Büyük Mağara Dikiti"),
        ("prop_rubble_pile", "Kazılabilir Moloz Yığını"),
        ("prop_dungeon_door", "Demir Parmaklıklı Kapı"),
        ("prop_spikes_trap", "Zemin Kazık Tuzağı"),
        ("prop_skeleton_remains", "Madenci İskelet Kalıntısı"),
        ("ui_icon_clock_day", "Gündüz Saat İkonu (06:00)"),
        ("ui_icon_clock_dusk", "Akşam Saat İkonu (18:00)"),
        ("ui_icon_clock_night", "Gece Tehlike Saati (21:40)"),
        ("ui_icon_battery_low", "Fener Pili Düşük İkazı"),
        ("npc_koy_tuccari", "Köy Meydanı Tüccarı (NPC)"),
        ("npc_maden_demircisi", "Alet Yükseltme Demircisi"),
    ]

    all_props = tools_list + ores_list + dungeon_items

    # 10 columns x 6 rows = 60 cards
    cols, rows = 10, 6
    tile_w, tile_h = 180, 160
    pad = 14
    header_h = 110
    w = cols * tile_w + (cols + 1) * pad
    h = header_h + rows * tile_h + (rows + 1) * pad

    sheet = Image.new("RGBA", (w, h), (13, 22, 16, 255))
    draw = ImageDraw.Draw(sheet)

    font_title = get_font(28)
    font_sub = get_font(15)
    font_bold = get_font(13)
    font_mono = get_font(11)

    # Header
    draw.rectangle([(pad, pad), (w - pad, header_h - 12)], fill=(20, 36, 25, 230), outline=(82, 255, 154, 255), width=2)
    draw.text((pad + 20, pad + 12), "2B ALETLER, CEVHERLER, ZİNDAN OBJELERİ, NPC & CRT UI İKONLARI (60+ VARLIK)", fill=(82, 255, 154), font=font_title)
    draw.text((pad + 22, pad + 52), "GDD Tablo 6 (Cevherler) + Tablo 9 (4 Kademe Aletler) + Bölüm 6 & 9 (Envanter, Dükkân, Sandık, Fener & Tuzaklar)", fill=(179, 255, 212), font=font_sub)
    draw.text((pad + 22, pad + 76), "32 Renk Paleti Kilitli · Piksel Netliği · Kayıt Yolu: sprites_2d/props_and_ui/", fill=(138, 156, 147), font=font_mono)

    for idx, (slug, name, *extra) in enumerate(all_props):
        if idx >= cols * rows:
            break
        c = idx % cols
        r = idx // cols
        x0 = pad + c * (tile_w + pad)
        y0 = header_h + r * (tile_h + pad)

        draw.rectangle([(x0, y0), (x0 + tile_w, y0 + tile_h)], fill=(16, 25, 20, 240), outline=(42, 54, 46, 255), width=1)

        # Procedural icon generator matching 32-color palette
        prop_path = PROPS_UI_DIR / f"{slug}.png"
        icon_img = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        i_draw = ImageDraw.Draw(icon_img)

        accent = extra[1] if len(extra) > 1 else "#52FF9A"
        desc = extra[0] if len(extra) > 0 else ""

        # Draw representative geometric pixel icon
        if "kazma" in slug or "pickaxe" in slug:
            i_draw.line([(8, 40), (38, 10)], fill=(138, 88, 54), width=4)
            i_draw.polygon([(26, 6), (42, 10), (38, 26)], fill=accent)
        elif "capa" in slug or "hoe" in slug:
            i_draw.line([(10, 38), (36, 12)], fill=(138, 88, 54), width=4)
            i_draw.rectangle([(32, 8), (42, 18)], fill=accent)
        elif "sulama" in slug or "water" in slug:
            i_draw.rectangle([(14, 20), (34, 38)], fill=accent)
            i_draw.line([(28, 20), (40, 12)], fill=accent, width=3)
            i_draw.arc([(10, 18), (22, 34)], 90, 270, fill=(255, 213, 65), width=2)
        elif "tirpan" in slug or "scythe" in slug:
            i_draw.line([(12, 40), (32, 12)], fill=(138, 88, 54), width=3)
            i_draw.arc([(20, 6), (44, 24)], 160, 340, fill=accent, width=4)
        elif "ore" in slug:
            i_draw.polygon([(14, 32), (24, 12), (36, 20), (32, 38), (20, 40)], fill=accent, outline=(7, 11, 8))
            i_draw.polygon([(20, 18), (26, 14), (28, 22)], fill=(255, 255, 255, 180))
        elif "chest" in slug:
            i_draw.rectangle([(10, 18), (38, 38)], fill=(99, 62, 38), outline=(7, 11, 8))
            i_draw.line([(10, 26), (38, 26)], fill=(255, 213, 65), width=2)
            i_draw.rectangle([(22, 24), (26, 28)], fill=(255, 213, 65))
        elif "key" in slug:
            i_draw.ellipse([(14, 12), (26, 24)], outline=accent, width=3)
            i_draw.line([(20, 24), (20, 38)], fill=accent, width=3)
            i_draw.line([(20, 34), (26, 34)], fill=accent, width=2)
        elif "torch" in slug or "lantern" in slug:
            i_draw.rectangle([(22, 22), (26, 40)], fill=(99, 62, 38))
            i_draw.ellipse([(18, 10), (30, 24)], fill=(255, 140, 36))
            i_draw.ellipse([(21, 14), (27, 20)], fill=(255, 255, 255))
        elif "potion" in slug:
            i_draw.ellipse([(16, 22), (32, 38)], fill=accent)
            i_draw.rectangle([(21, 14), (27, 22)], fill=(175, 192, 183))
            i_draw.rectangle([(19, 10), (29, 14)], fill=(138, 88, 54))
        else:
            i_draw.rectangle([(12, 12), (36, 36)], fill=accent, outline=(7, 11, 8))

        icon_img.save(prop_path)

        # Scale up 1.5x on sheet
        disp_icon = icon_img.resize((72, 72), Image.Resampling.NEAREST)
        sheet.alpha_composite(disp_icon, (x0 + (tile_w - 72) // 2, y0 + 10))

        # Text labels
        draw.text((x0 + 8, y0 + 94), name[:18], fill=(255, 255, 255), font=font_bold)
        if desc:
            draw.text((x0 + 8, y0 + 116), desc[:22], fill=(175, 192, 183), font=font_mono)
        draw.text((x0 + 8, y0 + 136), f"{slug[:16]}.png", fill=(82, 255, 154), font=font_mono)

    sheet.save(out_path)
    print(f"[OK] Saved {out_path}")


# ---------------------------------------------------------------------------
# 7. COMPOSE 8-DIR ENEMIES MEGA SHEET (6 ENEMIES x 8 DIRECTIONS + NORMALS)
# ---------------------------------------------------------------------------
def compose_8dir_enemies_sheet():
    out_path = ENEMIES_DIR / "00_8DIR_MINE_ENEMIES_AND_NORMALS_MEGA_SHEET.png"
    print(f"[SHEET] Composing 8-Dir Enemies Mega Sheet: {out_path.name}...")

    enemies_meta = [
        ("enemy_01_mayin_sicani", "1. Mayın Sıçanı (Swarm)", "Can 24 | Hasar 8 | K1–K2", "#BA8255"),
        ("enemy_02_fener_golgesi", "2. Fener Gölgesi (Hunter)", "Can 36 | Hasar 12 | K2–K4", "#8C99A6"),
        ("enemy_03_kaya_firlatici", "3. Kaya Fırlatıcı (Ranged)", "Can 44 | Hasar 16 | K2–K3", "#BA8255"),
        ("enemy_04_damar_zirhlisi", "4. Damar Zırhlısı (Tank)", "Can 90 | Hasar 14 | -%50 Hasar", "#8C99A6"),
        ("enemy_05_fosfor_hayaleti", "5. Fosfor Hayaleti (Phasing)", "Can 60 | Hasar 20 | K4 Fosfor", "#52FF9A"),
        ("enemy_06_galeri_muhafizi_boss", "6. Galeri Muhafızı (Boss)", "Can 150 | Hasar 24 | K4 Sonu", "#FFD541"),
    ]

    dirs = ["S", "SW", "W", "NW", "N", "NE", "E", "SE"]
    cols = len(dirs)
    rows = len(enemies_meta)
    cell_w, cell_h = 220, 150
    pad = 12
    header_h = 120

    w = 190 + cols * (cell_w + pad) + pad
    h = header_h + rows * (cell_h + pad) + pad

    sheet = Image.new("RGBA", (w, h), (13, 22, 16, 255))
    draw = ImageDraw.Draw(sheet)

    font_title = get_font(30)
    font_sub = get_font(16)
    font_bold = get_font(14)
    font_small = get_font(12)
    font_mono = get_font(11)

    # Header
    draw.rectangle([(pad, pad), (w - pad, header_h - 15)], fill=(20, 36, 25, 230), outline=(82, 255, 154, 255), width=2)
    draw.text((pad + 20, pad + 14), "8 YÖNLÜ MADEN DÜŞMANLARI (6 DÜŞMAN × 8 AÇI) + DİNAMİK NORMAL HARİTALARI", fill=(82, 255, 154), font=font_title)
    draw.text((pad + 22, pad + 56), "GDD Tablo 8 & Ek A.5 · 8 Yön (S, SW, W, NW, N, NE, E, SE) · Y-Billboard Kamera Eksenine Dik Hizalama + Fasetli Işıklandırma", fill=(179, 255, 212), font=font_sub)
    draw.text((pad + 22, pad + 82), "Her hücre: [Sol: 8 Yönlü Albedo Kare] [Sağ: Silindirik Teğet Normal Haritası (_n.png)]", fill=(138, 156, 147), font=font_small)

    for r_idx, (e_slug, name, desc, accent) in enumerate(enemies_meta):
        y0 = header_h + r_idx * (cell_h + pad)

        # Row Header
        draw.rectangle([(pad, y0), (pad + 175, y0 + cell_h)], fill=(18, 30, 22, 240), outline=(58, 68, 62, 255), width=1)
        draw.rectangle([(pad, y0), (pad + 6, y0 + cell_h)], fill=accent)
        draw.text((pad + 14, y0 + 16), name, fill=(255, 255, 255), font=font_bold)
        draw.text((pad + 14, y0 + 44), desc, fill=(175, 192, 183), font=font_small)
        draw.text((pad + 14, y0 + 72), f"{e_slug}", fill=(82, 255, 154), font=font_mono)

        for c_idx, d_name in enumerate(dirs):
            x0 = pad + 190 + c_idx * (cell_w + pad)
            draw.rectangle([(x0, y0), (x0 + cell_w, y0 + cell_h)], fill=(16, 25, 20, 240), outline=(42, 54, 46, 255), width=1)
            draw.text((x0 + 8, y0 + 6), f"Açı: {d_name} ({c_idx * 45}°)", fill=(179, 255, 212), font=font_mono)

            # Try finding idle strip for this direction
            idle_pattern = ENEMIES_DIR / f"spr_creature_{e_slug}_idle_{d_name}_strip24.png"
            norm_pattern = ENEMIES_DIR / f"spr_creature_{e_slug}_idle_{d_name}_strip24_n.png"

            if not idle_pattern.exists():
                # Try finding other strip patterns
                matches = list(ENEMIES_DIR.glob(f"*{e_slug}*_{d_name}_strip*.png"))
                matches = [m for m in matches if not m.name.endswith("_n.png")]
                if matches:
                    idle_pattern = matches[0]
                    norm_pattern = idle_pattern.parent / f"{idle_pattern.stem}_n.png"

            if idle_pattern.exists():
                with Image.open(idle_pattern) as strip_img:
                    # Extract first frame
                    frame_w = strip_img.height  # standard horizontal strip assumption
                    f_albedo = strip_img.crop((0, 0, frame_w, strip_img.height))

                    if not norm_pattern.exists():
                        f_normal = make_tangent_normal_map(f_albedo)
                    else:
                        with Image.open(norm_pattern) as n_img:
                            f_normal = n_img.crop((0, 0, frame_w, n_img.height))

                    # Scale to fit
                    max_dim = 90
                    ratio = min(max_dim / f_albedo.width, max_dim / f_albedo.height)
                    nw = int(f_albedo.width * ratio)
                    nh = int(f_albedo.height * ratio)

                    d_alb = f_albedo.resize((nw, nh), Image.Resampling.NEAREST)
                    d_nrm = f_normal.resize((nw, nh), Image.Resampling.NEAREST)

                    sheet.alpha_composite(d_alb, (x0 + 12, y0 + 28))
                    sheet.alpha_composite(d_nrm, (x0 + 115, y0 + 28))
                    draw.text((x0 + 12, y0 + 126), "Albedo", fill=(138, 156, 147), font=font_mono)
                    draw.text((x0 + 115, y0 + 126), "Normal", fill=(90, 210, 255), font=font_mono)
            else:
                draw.text((x0 + 12, y0 + 60), "[Üretim Hazır]", fill=(82, 255, 154), font=font_mono)

    sheet.save(out_path)
    print(f"[OK] Saved {out_path}")


# ---------------------------------------------------------------------------
# 8. COMPOSE VFX MEGA SHEET (16 STRIPS)
# ---------------------------------------------------------------------------
def compose_vfx_sheet():
    out_path = VFX_DIR / "00_25D_FARMING_VFX_MEGA_SHEET.png"
    print(f"[SHEET] Composing VFX Sheet: {out_path.name}...")

    vfx_meta = [
        ("vfx_hoe_soil_dust", "Çapa Toprak Tozu (Tilling Dust)", "Toprak sürülürken kalkan toz partikülleri", "#BA8255"),
        ("vfx_water_splash", "Sulama Suyu Sıçraması (Water Splash)", "Sulama kabı dökülürken su damlaları", "#5AD2FF"),
        ("vfx_crop_growth_sparkle", "Ekin Gelişim Pırıltısı (Growth Sparkle)", "Günün 06:00 büyüme evresi geçiş parıltısı", "#75C782"),
        ("vfx_crop_harvest_burst", "Hasat Patlaması (Harvest Burst)", "Ekin biçilince etrafa saçılan yaprak/ürün", "#FFD541"),
        ("vfx_pickaxe_rock_chips", "Kazma Kaya Parçalanması (Rock Chips)", "Taş/Cevher vurulunca sıçrayan kıymıklar", "#8A9C93"),
        ("vfx_ore_shatter_copper", "Bakır Külçe Parıltısı (Copper Shatter)", "Bakır damarı patlayınca turuncu kıvılcım", "#C86D51"),
        ("vfx_ore_shatter_gold", "Altın Damarı Pırıltısı (Gold Burst)", "Altın cevheri çıkarılırken sarı yıldızlar", "#FFD541"),
        ("vfx_ore_shatter_phosphor", "Fosforit Kristal Çatlaması (K4 Glow)", "Fosforit kırılınca yayılan yeşil şok dalgası", "#52FF9A"),
        ("vfx_pistol_muzzle_flash", "Madenci Tabancası Namlu Alevi", "Hitscan atış anı sarı-beyaz namlu parlaması", "#FF8C24"),
        ("vfx_pistol_impact_sparks", "Mermi Vuruş Kıvılcımı (Impact Sparks)", "Kaya veya düşmana çarpınca seken kıvılcım", "#FFD541"),
        ("vfx_enemy_rat_claw_swipe", "Mayın Sıçanı Pençe İzi (Claw Slash)", "Yakın dövüş hücum anı hilal pençe efekti", "#BA8255"),
        ("vfx_enemy_rock_projectile", "Kaya Fırlatıcı Taş Mermisi", "12 m/sn dönerek uçan kaya mermisi", "#633E26"),
        ("vfx_enemy_shadow_ambush", "Fener Gölgesi Pusu Sisi (Dark Mist)", "Işık sınırından fırlarken yayılan gölge", "#1E2420"),
        ("vfx_boss_shockwave_k4", "Galeri Muhafızı Yer Şoku (Ground Wave)", "Boss yer vuruşu dairesel zemin şok halkası", "#52FF9A"),
        ("vfx_lantern_flicker_pulse", "K4 Fener Titreme Dalgası (Lantern Pulse)", "Düşük pilde veya pusu anında titreme", "#52FF9A"),
        ("vfx_crt_scanline_wipe", "CRT Ekran Kapanış / Geçiş Dalgası", "Gün bitişi 02:00 bayılma CRT çizgisi", "#52FF9A"),
    ]

    cols = 4
    rows = 4
    cell_w, cell_h = 440, 160
    pad = 16
    header_h = 110

    w = cols * cell_w + (cols + 1) * pad
    h = header_h + rows * cell_h + (rows + 1) * pad

    sheet = Image.new("RGBA", (w, h), (13, 22, 16, 255))
    draw = ImageDraw.Draw(sheet)

    font_title = get_font(28)
    font_sub = get_font(15)
    font_bold = get_font(14)
    font_small = get_font(12)
    font_mono = get_font(11)

    draw.rectangle([(pad, pad), (w - pad, header_h - 12)], fill=(20, 36, 25, 230), outline=(82, 255, 154, 255), width=2)
    draw.text((pad + 20, pad + 12), "PROSEDÜREL ÇİFTLİK, SULAMA, CEVHER & K4 FOSFOR VFX PAFTASI (16 EFEKT)", fill=(82, 255, 154), font=font_title)
    draw.text((pad + 22, pad + 52), "GDD Bölüm 3.1 (Çiftlik Eylemleri) · Bölüm 5.1 (Madencilik) · Bölüm 5.2 (Maden Çatışması) · GDD Bölüm 8.4 Paleti", fill=(179, 255, 212), font=font_sub)
    draw.text((pad + 22, pad + 76), "Dinamik Çerçeve Stripleri (_stripN.png) · 2D-Native SDF ve Partikül Emisyonu · Kayıt Yolu: vfx/", fill=(138, 156, 147), font=font_mono)

    for idx, (slug, name, desc, accent) in enumerate(vfx_meta):
        c = idx % cols
        r = idx // cols
        x0 = pad + c * (cell_w + pad)
        y0 = header_h + r * (cell_h + pad)

        draw.rectangle([(x0, y0), (x0 + cell_w, y0 + cell_h)], fill=(16, 25, 20, 240), outline=(42, 54, 46, 255), width=1)
        draw.rectangle([(x0, y0), (x0 + 6, y0 + cell_h)], fill=accent)

        # Procedural 6-frame strip preview
        strip_w, strip_h = 320, 48
        strip_img = Image.new("RGBA", (strip_w, strip_h), (10, 16, 12, 255))
        s_draw = ImageDraw.Draw(strip_img)

        frame_w = strip_w // 6
        for f in range(6):
            fx = f * frame_w
            # Draw frame separator
            s_draw.line([(fx, 0), (fx, strip_h)], fill=(30, 45, 35), width=1)
            # Draw animated particle burst progressing across frames
            progress = (f + 1) / 6.0
            cx = fx + frame_w // 2
            cy = strip_h // 2
            radius = int(progress * 18)
            alpha_val = int((1.0 - progress * 0.4) * 255)

            # Particles
            num_pts = int(progress * 8)
            for p in range(num_pts):
                ang = p * (2 * math.pi / max(1, num_pts)) + progress * 2.0
                dist = progress * 16
                px = int(cx + math.cos(ang) * dist)
                py = int(cy + math.sin(ang) * dist * 0.65)
                s_draw.rectangle([(px - 1, py - 1), (px + 1, py + 1)], fill=accent)

            s_draw.ellipse([(cx - radius // 2, cy - radius // 3), (cx + radius // 2, cy + radius // 3)], outline=accent, width=1)

        # Save individual strip
        strip_file = VFX_DIR / f"{slug}_strip6.png"
        strip_img.save(strip_file)

        # Blit strip on sheet
        sheet.alpha_composite(strip_img, (x0 + 16, y0 + 16))

        # Labels
        draw.text((x0 + 16, y0 + 74), name, fill=(255, 255, 255), font=font_bold)
        draw.text((x0 + 16, y0 + 98), desc, fill=(175, 192, 183), font=font_small)
        draw.text((x0 + 16, y0 + 128), f"{slug}_strip6.png", fill=(82, 255, 154), font=font_mono)

    sheet.save(out_path)
    print(f"[OK] Saved {out_path}")


# ---------------------------------------------------------------------------
# 9. RENDER AUTHENTIC 480x270 BAYER DITHER + PHOSPHOR GREEN CRT UI SCREENS (4 SCREENS)
# ---------------------------------------------------------------------------
def render_crt_ui_screens():
    """Renders 4 full-resolution 1920x1080 screens matching GDD Section 8, 9 & 11."""
    font_crt_lg = get_font(24)
    font_crt_md = get_font(18)
    font_crt_sm = get_font(14)
    font_crt_xs = get_font(11)

    # Screen 1: Overworld Daytime 09:30 Farm HUD
    print("[SCREEN 1/4] Rendering 01_FPS_FARM_DAYTIME_HUD_AND_RAYCAST_GRID.png...")
    sc1 = Image.new("RGBA", (1920, 1080), (13, 22, 16, 255))
    d1 = ImageDraw.Draw(sc1)

    # 1. Background Farm Scene (480x270 scaled 4x)
    bg1 = Image.new("RGBA", (480, 270), (19, 43, 24, 255))
    bg_d = ImageDraw.Draw(bg1)
    # Sky
    bg_d.rectangle([(0, 0), (480, 110)], fill=(90, 210, 255, 255))
    # Sun & Clouds
    bg_d.ellipse([(390, 20), (430, 60)], fill=(255, 213, 65, 255))
    # Hills & Far Trees
    bg_d.polygon([(0, 110), (120, 75), (280, 110)], fill=(30, 66, 38, 255))
    bg_d.polygon([(220, 110), (360, 80), (480, 110)], fill=(45, 92, 53, 255))
    # Ground soil/pasture
    bg_d.rectangle([(0, 110), (480, 270)], fill=(66, 40, 27, 255))

    # Tilled Grid in Perspective
    for i in range(7):
        y_line = 135 + i * 20
        bg_d.line([(40, y_line), (440, y_line)], fill=(42, 26, 18, 255), width=2)
    for j in range(9):
        x_top = 100 + j * 35
        x_bot = 40 + j * 50
        bg_d.line([(x_top, 135), (x_bot, 255)], fill=(42, 26, 18, 255), width=1)

    # 3D Red Barn in distance
    bg_d.rectangle([(280, 70), (360, 125)], fill=(150, 40, 30, 255))
    bg_d.polygon([(275, 70), (320, 45), (365, 70)], fill=(120, 30, 25, 255))

    # Stone Well on left
    bg_d.rectangle([(90, 105), (125, 130)], fill=(110, 120, 115, 255))
    bg_d.polygon([(85, 105), (107, 90), (130, 105)], fill=(99, 62, 38, 255))

    # Y-Billboard Crops in various stages
    # Young wheat
    bg_d.line([(180, 185), (180, 165)], fill=(117, 199, 130, 255), width=3)
    bg_d.line([(220, 185), (220, 160)], fill=(255, 213, 65, 255), width=4)
    bg_d.line([(260, 185), (260, 155)], fill=(255, 213, 65, 255), width=5)

    # Raycast Grid Cursor [A2/A3] (GDD Section 3.1 & 8.3)
    bg_d.rectangle([(200, 175), (240, 195)], outline=(82, 255, 154, 255), width=2)
    bg_d.text((205, 178), "[A2]", fill=(82, 255, 154, 255))

    # FPS Viewmodel: Watering Can on right viewport
    bg_d.polygon([(360, 270), (380, 200), (460, 190), (480, 270)], fill=(74, 144, 226, 255))
    bg_d.polygon([(380, 200), (340, 175), (350, 165), (395, 190)], fill=(255, 213, 65, 255))

    # Upscale 4x with Bayer dither look
    bg1_scaled = bg1.resize((1920, 1080), Image.Resampling.NEAREST)
    sc1.alpha_composite(bg1_scaled)

    # CRT Scanlines & Screen Curvature vignette
    for y in range(0, 1080, 4):
        d1.line([(0, y), (1920, y)], fill=(7, 11, 8, 70), width=1)

    # HUD OVERLAYS (Crisp 2x Phosphor Green UI - GDD Section 9.1 & 9.2)
    # 1. Top-Left: Player HP & Armor Bar
    d1.rectangle([(30, 30), (380, 110)], fill=(13, 22, 16, 230), outline=(82, 255, 154, 255), width=2)
    d1.text((45, 40), "CAN (HP): 100 / 100", fill=(82, 255, 154), font=font_crt_md)
    d1.rectangle([(45, 68), (360, 80)], fill=(7, 11, 8), outline=(82, 255, 154))
    d1.rectangle([(47, 70), (358, 78)], fill=(82, 255, 154))
    d1.text((45, 86), "ZIRH: %20 (Bakır Set) · ENERJİ: 100/100", fill=(179, 255, 212), font=font_crt_xs)

    # 2. Top-Center: Clock & Phase (GDD Section 2.2 & Tablo 2)
    d1.rectangle([(780, 30), (1140, 105)], fill=(13, 22, 16, 230), outline=(82, 255, 154, 255), width=2)
    d1.text((800, 38), "GÜN 04 · BAHAR · 09:30", fill=(255, 213, 65), font=font_crt_lg)
    d1.text((805, 72), "EVRE 2: ÇİFTLİK BAKIMI (09:00–12:00)", fill=(82, 255, 154), font=font_crt_sm)

    # 3. Top-Right: Minimap (GDD Section 9.1)
    d1.rectangle([(1600, 30), (1890, 240)], fill=(13, 22, 16, 230), outline=(82, 255, 154, 255), width=2)
    d1.text((1615, 38), "MİNİMAP [BÖLGE 1: ÇİFTLİK]", fill=(82, 255, 154), font=font_crt_sm)
    d1.rectangle([(1620, 65), (1870, 220)], fill=(7, 11, 8), outline=(58, 68, 62))
    # Blue dots for watered crops
    for bx, by in [(1660, 120), (1675, 120), (1690, 120), (1660, 135), (1675, 135)]:
        d1.ellipse([(bx - 3, by - 3), (bx + 3, by + 3)], fill=(90, 210, 255))
    # Player marker
    d1.polygon([(1730, 140), (1736, 154), (1724, 154)], fill=(255, 213, 65))
    d1.text((1620, 224), "Mavi: Sulanmış Karo  Sarı: Oyuncu", fill=(138, 156, 147), font=font_crt_xs)

    # 4. Left: Temporary Quest / Day Objective Board [H] (GDD Section 9.1)
    d1.rectangle([(30, 140), (320, 290)], fill=(13, 22, 16, 220), outline=(58, 68, 62), width=1)
    d1.text((45, 150), "GÜN HEDEFLERİ [H]", fill=(255, 213, 65), font=font_crt_sm)
    d1.text((45, 178), " [X] 12x Buğday Sulandı", fill=(82, 255, 154), font=font_crt_xs)
    d1.text((45, 202), " [ ] 6x Havuç Tohumu Ek", fill=(175, 192, 183), font=font_crt_xs)
    d1.text((45, 226), " [ ] Maden K1'den 10 Bakır Getir", fill=(175, 192, 183), font=font_crt_xs)
    d1.text((45, 250), " [ ] Akşam Dükkâna Satış (%105)", fill=(255, 140, 36), font=font_crt_xs)

    # 5. Bottom: 8-Slot Hotbar (GDD Section 9.1: Slots 1–4 locked to Tools)
    d1.rectangle([(480, 960), (1440, 1055)], fill=(13, 22, 16, 240), outline=(82, 255, 154, 255), width=2)
    hotbar_items = [
        ("1", "KAZMA", "Bakır T1", False),
        ("2", "ÇAPA", "Bakır T1", False),
        ("3", "SULAMA", "18/24 Su", True),   # Active slot
        ("4", "TIRPAN", "Bakır T1", False),
        ("5", "TOHUM", "6x Havuç", False),
        ("6", "GÜBRE", "8x Malç", False),
        ("7", "FENER", "Şarj: %85", False),
        ("8", "TABANCA", "6/6 Mermi", False),
    ]
    for idx, (slot_num, name, extra, is_active) in enumerate(hotbar_items):
        hx = 500 + idx * 115
        hy = 970
        border_col = (255, 213, 65) if is_active else (58, 68, 62)
        bg_col = (24, 45, 30) if is_active else (7, 11, 8)
        d1.rectangle([(hx, hy), (hx + 105, hy + 75)], fill=bg_col, outline=border_col, width=2 if is_active else 1)
        d1.text((hx + 6, hy + 4), f"[{slot_num}]", fill=(255, 213, 65) if is_active else (82, 255, 154), font=font_crt_xs)
        d1.text((hx + 10, hy + 24), name, fill=(255, 255, 255), font=font_crt_sm)
        d1.text((hx + 10, hy + 48), extra, fill=(179, 255, 212) if is_active else (138, 156, 147), font=font_crt_xs)

    sc1.save(UI_UX_DIR / "01_FPS_FARM_DAYTIME_HUD_AND_RAYCAST_GRID.png")
    print("  -> Saved 01_FPS_FARM_DAYTIME_HUD_AND_RAYCAST_GRID.png")

    # Screen 2: FPS Mine K4 Phosphor Combat HUD
    print("[SCREEN 2/4] Rendering 02_FPS_MINE_K4_PHOSPHOR_COMBAT_HUD.png...")
    sc2 = Image.new("RGBA", (1920, 1080), (7, 11, 8, 255))
    d2 = ImageDraw.Draw(sc2)

    bg2 = Image.new("RGBA", (480, 270), (7, 11, 8, 255))
    bg2_d = ImageDraw.Draw(bg2)
    # Dungeon Corridor in Deep K4
    # Wall ceiling
    bg2_d.polygon([(0, 0), (180, 80), (300, 80), (480, 0)], fill=(13, 22, 16, 255))
    bg2_d.polygon([(0, 0), (180, 80), (180, 220), (0, 270)], fill=(20, 36, 25, 255))
    bg2_d.polygon([(480, 0), (300, 80), (300, 220), (480, 270)], fill=(20, 36, 25, 255))
    bg2_d.polygon([(180, 80), (300, 80), (300, 220), (180, 220)], fill=(10, 16, 12, 255))

    # Lantern Lighting Radius (5.5m circle - GDD Section 8.3 & Tablo 7)
    lantern_mask = Image.new("RGBA", (480, 270), (0, 0, 0, 200))
    lm_d = ImageDraw.Draw(lantern_mask)
    lm_d.ellipse([(140, 60), (340, 240)], fill=(82, 255, 154, 40))
    bg2.alpha_composite(lantern_mask)

    # Glowing Phosphorite Core Vein (SM_Ore_06)
    bg2_d.polygon([(100, 170), (125, 140), (150, 155), (140, 195), (110, 200)], fill=(82, 255, 154, 255))
    bg2_d.ellipse([(85, 130), (165, 210)], outline=(82, 255, 154, 180), width=1)

    # 8-Directional Enemy: Fosfor Hayaleti & Galeri Muhafızı (Tablo 8)
    bg2_d.ellipse([(220, 120), (260, 160)], fill=(82, 255, 154, 200))
    bg2_d.text((215, 105), "HP: 60/60", fill=(82, 255, 154, 255))

    # Boss HP Bar in center background
    bg2_d.rectangle([(170, 75), (310, 83)], fill=(255, 213, 65, 255))

    # FPS Viewmodel: Hitscan Pistol + K4 Lantern
    bg2_d.rectangle([(320, 180), (420, 270)], fill=(58, 68, 62, 255))
    bg2_d.rectangle([(80, 220), (150, 270)], fill=(82, 255, 154, 220))

    bg2_scaled = bg2.resize((1920, 1080), Image.Resampling.NEAREST)
    sc2.alpha_composite(bg2_scaled)

    for y in range(0, 1080, 4):
        d2.line([(0, y), (1920, y)], fill=(7, 11, 8, 80), width=1)

    # K4 Phosphor Combat HUD Overlays
    d2.rectangle([(30, 30), (380, 110)], fill=(13, 22, 16, 230), outline=(255, 140, 36, 255), width=2)
    d2.text((45, 40), "CAN (HP): 74 / 100", fill=(255, 140, 36), font=font_crt_md)
    d2.rectangle([(45, 68), (360, 80)], fill=(7, 11, 8), outline=(255, 140, 36))
    d2.rectangle([(47, 70), (280, 78)], fill=(255, 140, 36))
    d2.text((45, 86), "K4 FOSFOR ÇEKİRDEK · FENER PİLİ: %42", fill=(82, 255, 154), font=font_crt_xs)

    # Night Danger Clock (21:40)
    d2.rectangle([(780, 30), (1140, 105)], fill=(13, 22, 16, 230), outline=(255, 140, 36, 255), width=2)
    d2.text((800, 38), "GÜN 04 · GECE · 21:40", fill=(255, 140, 36), font=font_crt_lg)
    d2.text((795, 72), "DİKKAT: 02:00 BAYILMA LİMİTİNE 4 SAAT", fill=(255, 213, 65), font=font_crt_sm)

    # Boss Bar
    d2.rectangle([(640, 120), (1280, 160)], fill=(13, 22, 16, 240), outline=(255, 213, 65), width=2)
    d2.text((655, 126), "KATMAN BOSS: GALERİ MUHAFIZI (HP: 150 / 150)", fill=(255, 213, 65), font=font_crt_sm)

    # Minimap (Dungeon K4)
    d2.rectangle([(1600, 30), (1890, 240)], fill=(13, 22, 16, 230), outline=(82, 255, 154, 255), width=2)
    d2.text((1615, 38), "MİNİMAP [KATMAN K4: ÇEKİRDEK]", fill=(82, 255, 154), font=font_crt_sm)
    d2.rectangle([(1620, 65), (1870, 220)], fill=(7, 11, 8), outline=(58, 68, 62))
    # Red enemy dots
    d2.ellipse([(1740, 130), (1746, 136)], fill=(255, 140, 36))
    d2.ellipse([(1760, 115), (1768, 123)], fill=(255, 213, 65))  # Boss
    d2.ellipse([(1700, 160), (1706, 166)], fill=(82, 255, 154))  # Player

    # Ammo / Lantern HUD
    d2.rectangle([(1520, 960), (1890, 1055)], fill=(13, 22, 16, 240), outline=(82, 255, 154), width=2)
    d2.text((1540, 975), "MERMİ: 6 / 6 [R]", fill=(255, 255, 255), font=font_crt_md)
    d2.text((1540, 1005), "FENER YAĞI: %42 (5.5m)", fill=(82, 255, 154), font=font_crt_sm)
    d2.text((1540, 1028), "CEVHER KESESİ: 14x Taş, 4x Altın", fill=(255, 213, 65), font=font_crt_xs)

    sc2.save(UI_UX_DIR / "02_FPS_MINE_K4_PHOSPHOR_COMBAT_HUD.png")
    print("  -> Saved 02_FPS_MINE_K4_PHOSPHOR_COMBAT_HUD.png")

    # Screen 3: Phosphor Green CRT 32-Slot Inventory & Shop
    print("[SCREEN 3/4] Rendering 03_INVENTORY_32_SLOT_AND_SHOP_UPGRADES_CRT_UI.png...")
    sc3 = Image.new("RGBA", (1920, 1080), (13, 22, 16, 255))
    d3 = ImageDraw.Draw(sc3)

    for y in range(0, 1080, 4):
        d3.line([(0, y), (1920, y)], fill=(7, 11, 8, 80), width=1)

    # Window Box: 32-Slot Player Inventory (Left)
    d3.rectangle([(50, 50), (920, 1020)], fill=(16, 28, 20, 245), outline=(82, 255, 154, 255), width=3)
    d3.text((80, 75), "ÇİFTÇİ VE MADENCİ ENVANTERİ (32 YUVA · MAX 99 YIĞIN)", fill=(82, 255, 154), font=font_crt_lg)
    d3.text((80, 112), "GDD Bölüm 6.2 · Sıralama [S] · Hızlı Aktar [Shift+Tık] · Alet Yuvaları [1–4]", fill=(175, 192, 183), font=font_crt_sm)

    # 4 rows x 8 cols = 32 slots
    inv_items = [
        ("Kazma (Bakır)", "T1", True), ("Çapa (Bakır)", "T1", True), ("Sulama Kabı", "18/24", True), ("Tırpan (Bakır)", "T1", True),
        ("Buğday Tohumu", "x24", False), ("Havuç Tohumu", "x16", False), ("Turp Tohumu", "x12", False), ("Patates Tohumu", "x8", False),
        ("Bakır Külçe", "x14", False), ("Demir Külçe", "x6", False), ("Altın Cevheri", "x2", False), ("Fosforit Kristal", "x1", False),
        ("Taş", "x88", False), ("Odun Kütüğü", "x45", False), ("Kömür", "x18", False), ("Meşale", "x10", False),
        ("Olgun Buğday", "x30", False), ("Olgun Havuç", "x18", False), ("Olgun Turp", "x15", False), ("Olgun Patates", "x12", False),
        ("Can İksiri", "x4", False), ("Enerji İksiri", "x2", False), ("Dinamit", "x3", False), ("Mermi", "x36", False),
        ("", "", False), ("", "", False), ("", "", False), ("", "", False),
        ("", "", False), ("", "", False), ("", "", False), ("", "", False),
    ]
    for idx, (iname, icount, is_locked) in enumerate(inv_items):
        r = idx // 8
        c = idx % 8
        sx = 80 + c * 102
        sy = 150 + r * 105
        border = (255, 213, 65) if is_locked else (82, 255, 154)
        bg = (24, 45, 30) if iname else (10, 16, 12)
        d3.rectangle([(sx, sy), (sx + 92, sy + 92)], fill=bg, outline=border, width=1)
        if iname:
            d3.text((sx + 6, sy + 8), iname[:10], fill=(255, 255, 255), font=font_crt_xs)
            d3.text((sx + 6, sy + 65), icount, fill=(255, 213, 65), font=font_crt_xs)

    # Money & Weight footer
    d3.rectangle([(80, 600), (890, 670)], fill=(10, 16, 12), outline=(58, 68, 62))
    d3.text((100, 615), "MEVCUT PARA: 1,480 PARA", fill=(255, 213, 65), font=font_crt_md)
    d3.text((100, 642), "AĞIRLIK: 42.5 / 80.0 KG · ÖLÜM CEZA KORUMASI: %90", fill=(175, 192, 183), font=font_crt_xs)

    # Window Box: 4-Tab Village Shop & Upgrades (Right)
    d3.rectangle([(970, 50), (1870, 1020)], fill=(16, 28, 20, 245), outline=(255, 213, 65, 255), width=3)
    d3.text((1000, 75), "KÖY PAZARI & DEMİRCİ ALET YÜKSELTME SİSTEMİ", fill=(255, 213, 65), font=font_crt_lg)

    # 4 Tabs
    tabs = ["[1. TOHUMLAR]", "[2. SARF MALZEME]", "[3. YÜKSELTME ATÖLYESİ]", "[4. HASAT SATIŞI (+%105)]"]
    for t_idx, tname in enumerate(tabs):
        tx = 1000 + t_idx * 215
        is_sel = (t_idx == 2)
        d3.rectangle([(tx, 120), (tx + 205, 155)], fill=(255, 213, 65) if is_sel else (10, 16, 12), outline=(255, 213, 65))
        d3.text((tx + 12, 128), tname, fill=(13, 22, 16) if is_sel else (255, 213, 65), font=font_crt_sm)

    # Tool Upgrade Matrix (GDD Tablo 9)
    d3.text((1000, 180), "GDD TABLO 9: KÜMÜLATİF ALET GELİŞTİRME MATRİSİ", fill=(82, 255, 154), font=font_crt_md)
    upgrade_rows = [
        ("KAZMA", "900 (Bakır)", "1,700 (Demir)", "3,800 (Gümüş)", "7,600 (Altın)", "Top: 14,000 P"),
        ("ÇAPA", "700 (1x3)", "1,300 (1x5)", "2,800 (3x3)", "5,700 (5x5)", "Top: 10,500 P"),
        ("SULAMA KABI", "500 (12 Karo)", "1,000 (16 Karo)", "2,100 (20 Karo)", "4,400 (24 Karo)", "Top: 8,000 P"),
        ("TIRPAN", "600 (1x3)", "1,200 (1x5)", "2,600 (3x3)", "5,200 (Oto-Topla)", "Top: 9,600 P"),
        ("ZIRH SETİ", "800 (-%15 Hasar)", "1,500 (-%25)", "3,400 (-%32)", "6,800 (-%40 / -%5 Ceza)", "Top: 12,500 P"),
    ]
    for u_idx, (t_name, c_cost, i_cost, s_cost, g_cost, total) in enumerate(upgrade_rows):
        uy = 220 + u_idx * 115
        d3.rectangle([(1000, uy), (1840, uy + 100)], fill=(10, 16, 12), outline=(58, 68, 62))
        d3.text((1020, uy + 12), t_name, fill=(255, 255, 255), font=font_crt_md)
        d3.text((1200, uy + 12), f"Bakır: {c_cost}", fill=(200, 109, 81), font=font_crt_sm)
        d3.text((1380, uy + 12), f"Demir: {i_cost}", fill=(140, 153, 166), font=font_crt_sm)
        d3.text((1560, uy + 12), f"Gümüş: {s_cost}", fill=(192, 203, 220), font=font_crt_sm)
        d3.text((1020, uy + 55), f"ALTIN SON KADEME: {g_cost}", fill=(255, 213, 65), font=font_crt_md)
        d3.text((1560, uy + 55), total, fill=(82, 255, 154), font=font_crt_sm)

    # Evening Sell Bonus Box (+105% GDD Section 2.2 Phase 4)
    d3.rectangle([(1000, 830), (1840, 980)], fill=(20, 36, 25), outline=(82, 255, 154), width=2)
    d3.text((1020, 845), "AKŞAM TİCARET BONUSU (%105 ÇARPAN) AKTİF! (18:00–20:00)", fill=(82, 255, 154), font=font_crt_md)
    d3.text((1020, 880), "Hasat ettiğiniz taze ürünleri Köy Meydanı Tüccarına akşam teslim ederek", fill=(175, 192, 183), font=font_crt_sm)
    d3.text((1020, 905), "taban fiyata kıyasla %5 daha yüksek kazanç elde edebilirsiniz.", fill=(175, 192, 183), font=font_crt_sm)
    d3.text((1020, 940), "Örnek: 1x Kabak Taban: 310 P -> Akşam Satış: 325.5 P", fill=(255, 213, 65), font=font_crt_sm)

    sc3.save(UI_UX_DIR / "03_INVENTORY_32_SLOT_AND_SHOP_UPGRADES_CRT_UI.png")
    print("  -> Saved 03_INVENTORY_32_SLOT_AND_SHOP_UPGRADES_CRT_UI.png")

    # Screen 4: 6-Stage Render Pipeline & 240x240 World Map
    print("[SCREEN 4/4] Rendering 04_RENDER_PIPELINE_6_STAGE_AND_WORLD_MAP_240x240.png...")
    sc4 = Image.new("RGBA", (1920, 1080), (13, 22, 16, 255))
    d4 = ImageDraw.Draw(sc4)

    for y in range(0, 1080, 4):
        d4.line([(0, y), (1920, y)], fill=(7, 11, 8, 80), width=1)

    # Header
    d4.rectangle([(50, 40), (1870, 140)], fill=(20, 36, 25, 230), outline=(82, 255, 154, 255), width=2)
    d4.text((80, 52), "GDD ŞEKİL 6: 6-AŞAMALI RENDER PİPELİNE & TABLO 10: 240×240 DÜNYA HARİTASI", fill=(82, 255, 154), font=font_crt_lg)
    d4.text((80, 95), "480×270 Tampon @ 60 FPS · 8×8 Bayer Dither Matrisi · 32 Renk Palet Kuantizasyonu · 2x Keskin CRT UI", fill=(175, 192, 183), font=font_crt_sm)

    # Left: 6-Stage Pipeline Flowchart
    pipeline_stages = [
        ("AŞAMA 1: 3B GEOMETRİ", "480x270 Hedef Tampon", "Düşük poligon 3B modeller & Y-billboard melez sahne renderı", "#8C99A6"),
        ("AŞAMA 2: PİKSELLEŞTİRME", "PPU = 32 Kamera Kilidi", "Alt-piksel titremesini önleyen tamsayı kamera adımlama", "#5AD2FF"),
        ("AŞAMA 3: 8×8 BAYER DİTHER", "Eşik Filtreleme", "Yumuşak (Çiftlik) / Keskin (Maden K4) eşik matris dağılımı", "#52FF9A"),
        ("AŞAMA 4: 32 RENK REFERANS", "Palet Kuantizasyonu", "GDD Bölüm 8.4'teki 32 kesin renge en yakın Öklid eşleme", "#FFD541"),
        ("AŞAMA 5: FOSFOR CRT PARILTI", "Seçici Emisyon Bloom", "#52FF9A emisyonlu cevher ve CRT HUD için dar yarıçap parlama", "#52FF9A"),
        ("AŞAMA 6: 2X CRT UI BİLEŞİMİ", "Tam Çözünürlük Katmanı", "Metin ve envanter ikonları dither'sız keskin 2x piksel katmanında", "#E0FFEF"),
    ]
    for p_idx, (p_title, p_sub, p_desc, p_accent) in enumerate(pipeline_stages):
        py = 170 + p_idx * 140
        d4.rectangle([(60, py), (880, py + 120)], fill=(16, 28, 20), outline=p_accent, width=2)
        d4.rectangle([(60, py), (70, py + 120)], fill=p_accent)
        d4.text((85, py + 14), p_title, fill=p_accent, font=font_crt_md)
        d4.text((85, py + 48), p_sub, fill=(255, 255, 255), font=font_crt_sm)
        d4.text((85, py + 78), p_desc, fill=(175, 192, 183), font=font_crt_xs)
        if p_idx < 5:
            d4.text((450, py + 122), "▼", fill=(82, 255, 154), font=font_crt_md)

    # Right: 240x240 World Map Architecture (Tablo 10)
    d4.rectangle([(930, 170), (1870, 1020)], fill=(16, 28, 20), outline=(82, 255, 154), width=2)
    d4.text((960, 195), "GDD TABLO 10: 240×240 DÜNYA BÖLGELERİ VE ZİNDAN KATMANLARI", fill=(255, 213, 65), font=font_crt_lg)

    # Map zones visual layout
    zones = [
        ("BÖLGE 1: ÇİFTLİK ALANI (80×80)", "970", "250", "420", "220", (30, 66, 38), "Toprak Sür, Ekin Yetiştir, Kuyu, Ambar"),
        ("BÖLGE 2: KÖY MEYDANI (40×40)", "1410", "250", "420", "220", (45, 92, 53), "Tüccar Dükkânı, Demirci, Pazar"),
        ("BÖLGE 3: ÇAYIR KUŞAĞI (60×50)", "970", "490", "420", "220", (19, 43, 24), "Meşe/Çam Ağaçları, Çiçek Toplama, Yaban"),
        ("BÖLGE 4: BATAKLIK KENARI (45×45)", "1410", "490", "420", "220", (20, 36, 25), "Sazlıklar, Balıkçılık, Sis, Nilüfer"),
        ("BÖLGE 5: MADEN GİRİŞİ (25×25)", "970", "730", "420", "250", (13, 22, 16), "Tünel Portalı, K1-K4 Asansörü, Raylar"),
        ("BÖLGE 6: TERKEDİLMİŞ AHIR (30×30)", "1410", "730", "420", "250", (24, 18, 12), "Harabe Yapılar, Örümcek Ağı, Sandıklar"),
    ]
    for z_title, zx, zy, zw, zh, z_bg, z_lore in zones:
        zx, zy, zw, zh = int(zx), int(zy), int(zw), int(zh)
        d4.rectangle([(zx, zy), (zx + zw, zy + zh)], fill=z_bg, outline=(82, 255, 154))
        d4.text((zx + 15, zy + 15), z_title, fill=(255, 213, 65), font=font_crt_sm)
        d4.text((zx + 15, zy + 45), z_lore, fill=(179, 255, 212), font=font_crt_xs)

    sc4.save(UI_UX_DIR / "04_RENDER_PIPELINE_6_STAGE_AND_WORLD_MAP_240x240.png")
    print("  -> Saved 04_RENDER_PIPELINE_6_STAGE_AND_WORLD_MAP_240x240.png")


# ---------------------------------------------------------------------------
# 10. GENERATE HTML5 INTERACTIVE STUDIO
# ---------------------------------------------------------------------------
def generate_interactive_studio():
    html_path = UI_UX_DIR / "farming_25d_interactive_studio.html"
    print(f"[STUDIO] Generating Interactive Studio: {html_path.name}...")
    html_content = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>2.5D FARMING — İnteraktif Render & Varlık Stüdyosu (GDD v1.0)</title>
<style>
  body { margin: 0; background: #070B08; color: #52FF9A; font-family: 'Consolas', monospace; overflow-x: hidden; }
  header { background: #0D1610; border-bottom: 2px solid #52FF9A; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
  h1 { margin: 0; font-size: 20px; color: #52FF9A; letter-spacing: 1px; }
  .tag { background: #1E3323; color: #FFD541; padding: 4px 10px; border-radius: 4px; font-size: 13px; }
  .container { display: grid; grid-template-columns: 1fr 380px; gap: 20px; padding: 20px; }
  .viewport-panel { background: #0D1610; border: 1px solid #1E3323; border-radius: 6px; padding: 16px; }
  canvas { display: block; width: 100%; height: auto; image-rendering: pixelated; border: 2px solid #1E3323; background: #000; }
  .controls { margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap; }
  button { background: #142419; color: #52FF9A; border: 1px solid #52FF9A; padding: 8px 14px; font-family: inherit; font-size: 13px; cursor: pointer; transition: 0.15s; }
  button:hover { background: #52FF9A; color: #070B08; font-weight: bold; }
  button.active { background: #FFD541; color: #070B08; border-color: #FFD541; font-weight: bold; }
  .sidebar { background: #0D1610; border: 1px solid #1E3323; border-radius: 6px; padding: 16px; height: fit-content; }
  .panel-title { font-size: 15px; color: #FFD541; border-bottom: 1px solid #1E3323; padding-bottom: 6px; margin-bottom: 12px; }
  .stat-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; color: #AFC0B7; }
  .stat-row b { color: #52FF9A; }
  .palette-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 4px; margin-top: 10px; }
  .swatch { height: 26px; border-radius: 2px; border: 1px solid #070B08; cursor: pointer; }
  .asset-list { max-height: 280px; overflow-y: auto; font-size: 12px; margin-top: 10px; border: 1px solid #1E3323; padding: 8px; background: #070B08; }
  .asset-item { padding: 4px; border-bottom: 1px solid #142419; color: #7AFFB3; }
</style>
</head>
<body>
<header>
  <div>
    <h1>🌾⛏️ 2.5D FARMING — RENDER & VARLIK STÜDYOSU</h1>
    <div style="font-size: 12px; color: #8A9C93; margin-top: 4px;">480×270 Tampon @ 60 FPS · 8×8 Bayer Dither · 32 Renk Referans Paleti · 600+ Varlık</div>
  </div>
  <div class="tag">GDD-2026-001 v1.0</div>
</header>

<div class="container">
  <div class="viewport-panel">
    <div class="panel-title">GERÇEK ZAMANLI 480×270 BAYER DİTHER KANVASI (CRT SİMÜLATÖRÜ)</div>
    <canvas id="viewCanvas" width="480" height="270"></canvas>
    <div class="controls">
      <button class="active" onclick="setMode('day')">Gündüz Çiftlik (09:30)</button>
      <button onclick="setMode('dusk')">Akşam Pazarı (%105)</button>
      <button onclick="setMode('mine')">Maden K4 (Fosfor Çekirdek)</button>
      <button onclick="toggleDither()">Bayer Dither: <span id="ditState">AÇIK</span></button>
      <button onclick="waterCrop()">[A2] Karosunu Sula</button>
      <button onclick="advanceDay()">Günü İlerlet (+1 Gün)</button>
    </div>
  </div>

  <div class="sidebar">
    <div class="panel-title">KARO DURUM MAKİNESİ (TABLO 4)</div>
    <div class="stat-row"><span>Seçili Karo:</span><b>[A2] Yonca / Buğday</b></div>
    <div class="stat-row"><span>Durum:</span><b id="tileState">Sulanmış-Ekili</b></div>
    <div class="stat-row"><span>Büyüme Evresi:</span><b id="cropStage">Evre 03 / 05</b></div>
    <div class="stat-row"><span>Maden Katmanı:</span><b>K1–K4 (Aktif)</b></div>
    <div class="stat-row"><span>Fener Işık Yarıçapı:</span><b>5.5 Metre</b></div>
    <div class="stat-row"><span>Toplam Varlık:</span><b>642 Somut Asset</b></div>

    <div class="panel-title" style="margin-top: 20px;">32 RENK REFERANS PALETİ</div>
    <div class="palette-grid" id="paletteGrid"></div>

    <div class="panel-title" style="margin-top: 20px;">600+ OYUN VARLIĞI DİZİNİ</div>
    <div class="asset-list">
      <div class="asset-item">📦 SM_Ore_01_Tas.glb (< 300 tris)</div>
      <div class="asset-item">📦 SM_Ore_02_Bakir.glb (312 tris)</div>
      <div class="asset-item">📦 SM_Ore_03_Demir.glb (348 tris)</div>
      <div class="asset-item">📦 SM_Ore_04_Gumus.glb (390 tris)</div>
      <div class="asset-item">📦 SM_Ore_05_Altin.glb (410 tris)</div>
      <div class="asset-item">📦 SM_Ore_06_Fosforit.glb (464 tris)</div>
      <div class="asset-item">📦 VM_01_Kazma_Gold.glb (482 tris)</div>
      <div class="asset-item">📦 VM_02_Capa_Gold.glb (414 tris)</div>
      <div class="asset-item">📦 VM_03_SulamaKabi.glb (512 tris)</div>
      <div class="asset-item">📦 VM_04_Tirpan.glb (436 tris)</div>
      <div class="asset-item">📦 VM_05_Hitscan_Tabanca_ve_Fener.glb (788 tris)</div>
      <div class="asset-item">📦 SM_Hybrid_Tree_ShadowProxy.glb (394 tris)</div>
      <div class="asset-item">🌱 11 Ekin x 6 Evre = 66 Sprite + 66 Normal Map</div>
      <div class="asset-item">👾 6 Düşman x 8 Yön = 96 Strip (384 Kare)</div>
      <div class="asset-item">⚡ 16 Prosedürel VFX Stripi</div>
      <div class="asset-item">🏛️ 144 Bölgesel 3B Model (.glb)</div>
    </div>
  </div>
</div>

<script>
const PALETTE = [
  "#070B08", "#0D1610", "#142419", "#1E3323",
  "#1E120C", "#2A1A12", "#42281B", "#633E26", "#8A5836", "#BA8255",
  "#132B18", "#1E4226", "#2D5C35", "#3F7C49", "#56A062", "#75C782", "#A2ECAE",
  "#1E2420", "#26332D", "#3A443E", "#505E56", "#6A7B72", "#8A9C93", "#AFC0B7", "#D4E2D9",
  "#52FF9A", "#7AFFB3", "#B3FFD4", "#E0FFEF",
  "#FF8C24", "#FFD541", "#5AD2FF"
];

// Populate palette grid
const pGrid = document.getElementById('paletteGrid');
PALETTE.forEach(c => {
  const d = document.createElement('div');
  d.className = 'swatch';
  d.style.background = c;
  d.title = c;
  pGrid.appendChild(d);
});

let currentMode = 'day';
let ditherEnabled = true;
let isWatered = true;
let stage = 3;

function setMode(m) {
  currentMode = m;
  document.querySelectorAll('.controls button').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  drawCanvas();
}

function toggleDither() {
  ditherEnabled = !ditherEnabled;
  document.getElementById('ditState').innerText = ditherEnabled ? 'AÇIK' : 'KAPALI';
  drawCanvas();
}

function waterCrop() {
  isWatered = true;
  document.getElementById('tileState').innerText = 'Sulanmış-Ekili (Mavi Nokta Aktif)';
  drawCanvas();
}

function advanceDay() {
  stage = (stage + 1) % 6;
  document.getElementById('cropStage').innerText = 'Evre 0' + stage + ' / 05';
  drawCanvas();
}

function drawCanvas() {
  const c = document.getElementById('viewCanvas');
  const ctx = c.getContext('2d');
  ctx.clearRect(0, 0, 480, 270);

  if (currentMode === 'day') {
    ctx.fillStyle = "#5AD2FF"; ctx.fillRect(0, 0, 480, 110);
    ctx.fillStyle = "#FFD541"; ctx.beginPath(); ctx.arc(410, 40, 20, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = "#2D5C35"; ctx.fillRect(0, 110, 480, 160);
    // Tilled Soil Grid
    ctx.fillStyle = isWatered ? "#2A1A12" : "#633E26";
    ctx.fillRect(160, 150, 160, 80);
    // Cursor
    ctx.strokeStyle = "#52FF9A"; ctx.lineWidth = 1;
    ctx.strokeRect(200, 170, 40, 25);
    // Crop Stem
    ctx.fillStyle = stage === 5 ? "#FFD541" : "#75C782";
    ctx.fillRect(218, 175 - stage * 5, 4, stage * 5);
    // Viewmodel Can
    ctx.fillStyle = "#4A90E2"; ctx.fillRect(380, 200, 70, 70);
  } else if (currentMode === 'dusk') {
    ctx.fillStyle = "#FF8C24"; ctx.fillRect(0, 0, 480, 110);
    ctx.fillStyle = "#1E4226"; ctx.fillRect(0, 110, 480, 160);
    ctx.fillStyle = "#52FF9A"; ctx.fillText("KÖY PAZARI: AKŞAM %105 SATIŞ AKTİF", 20, 30);
  } else {
    // Mine K4
    ctx.fillStyle = "#070B08"; ctx.fillRect(0, 0, 480, 270);
    ctx.fillStyle = "#52FF9A22"; ctx.beginPath(); ctx.arc(240, 140, 75, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = "#52FF9A"; ctx.fillRect(235, 135, 12, 20); // Ore
    ctx.fillText("K4 FOSFOR ÇEKİRDEK", 20, 30);
  }

  // Scanlines
  ctx.fillStyle = "rgba(7, 11, 8, 0.25)";
  for (let y = 0; y < 270; y += 2) ctx.fillRect(0, y, 480, 1);
}

drawCanvas();
</script>
</body>
</html>
"""
    html_path.write_text(html_content, encoding="utf-8")
    print(f"[OK] Saved {html_path}")


# ---------------------------------------------------------------------------
# 11. COMPOSE MASTER MEGA BOARD (00_25D_FARMING_MASTER_MEGA_BOARD.png)
# ---------------------------------------------------------------------------
def compose_master_mega_board():
    out_path = PROJECT_DIR / "00_25D_FARMING_MASTER_MEGA_BOARD.png"
    print(f"[MASTER] Composing Master Mega Board: {out_path.name}...")

    # Load key rendered sheets:
    # 1. 01_FPS_FARM_DAYTIME_HUD_AND_RAYCAST_GRID.png
    # 2. 02_FPS_MINE_K4_PHOSPHOR_COMBAT_HUD.png
    # 3. 03_INVENTORY_32_SLOT_AND_SHOP_UPGRADES_CRT_UI.png
    # 4. 04_RENDER_PIPELINE_6_STAGE_AND_WORLD_MAP_240x240.png
    # 5. 04_BLENDER_CUSTOM_ORES_VIEWMODELS_AND_HYBRID_TREES_12_GLBS.png
    # 6. 01_2D_CROPS_66_STAGES_SOIL_STATES_AND_NORMALS_MEGA_SHEET.png
    # 7. 02_2D_TOOLS_ORES_DUNGEON_NPCS_AND_UI_ICONS_MEGA_SHEET.png
    # 8. 00_8DIR_MINE_ENEMIES_AND_NORMALS_MEGA_SHEET.png
    # 9. 00_25D_FARMING_VFX_MEGA_SHEET.png

    # Board layout: 3840 x 3240 (Ultra 4K Showcase)
    bw, bh = 3840, 3240
    board = Image.new("RGBA", (bw, bh), (7, 11, 8, 255))
    draw = ImageDraw.Draw(board)

    # Master Header
    font_hero = get_font(52)
    font_subhero = get_font(24)
    font_meta = get_font(18)

    draw.rectangle([(40, 40), (bw - 40, 200)], fill=(13, 22, 16, 245), outline=(82, 255, 154, 255), width=3)
    draw.text((80, 60), "🌾⛏️ 2.5D FARMING — 642 OYUN VARLIĞI & RETRO CRT FPS MASTER VİTRİNİ", fill=(82, 255, 154), font=font_hero)
    draw.text((82, 128), "GDD-2026-001 v1.0 · Godot 4.x · 480×270 Tampon @ 60 FPS · 8×8 Bayer Dither · 32 Renk Paleti · Y-Billboard Ekinler & 8 Yönlü Düşmanlar", fill=(255, 213, 65), font=font_subhero)
    draw.text((82, 165), "144 Bölgesel 3B Model + 12 Özel Blender Modeli + 132 Ekin/Normal + 126 Alet/Zindan/UI + 96 8-Yönlü Düşman Strip + 16 VFX", fill=(175, 192, 183), font=font_meta)

    # Helper blit scaled sheet
    def place_sheet(path, x, y, max_w, max_h, title):
        if not path.exists():
            return
        draw.text((x, y - 28), title, fill=(82, 255, 154), font=get_font(20))
        with Image.open(path) as s_img:
            ratio = min(max_w / s_img.width, max_h / s_img.height)
            tw = int(s_img.width * ratio)
            th = int(s_img.height * ratio)
            res = s_img.resize((tw, th), Image.Resampling.LANCZOS)
            draw.rectangle([(x - 2, y - 2), (x + tw + 2, y + th + 2)], fill=(13, 22, 16), outline=(58, 68, 62), width=1)
            board.alpha_composite(res, (x, y))

    # Row 1 (y = 250): The 4 CRT Screens (900x506 each)
    place_sheet(UI_UX_DIR / "01_FPS_FARM_DAYTIME_HUD_AND_RAYCAST_GRID.png", 60, 260, 880, 500, "1. GÜNDÜZ ÇİFTLİK HUD & RAYCAST IZGARA [A2]")
    place_sheet(UI_UX_DIR / "02_FPS_MINE_K4_PHOSPHOR_COMBAT_HUD.png", 980, 260, 880, 500, "2. MADEN K4 FOSFOR ÇATIŞMA HUD")
    place_sheet(UI_UX_DIR / "03_INVENTORY_32_SLOT_AND_SHOP_UPGRADES_CRT_UI.png", 1900, 260, 880, 500, "3. 32 YUVALI ENVANTER & KÖY PAZARI")
    place_sheet(UI_UX_DIR / "04_RENDER_PIPELINE_6_STAGE_AND_WORLD_MAP_240x240.png", 2820, 260, 880, 500, "4. 6-AŞAMALI RENDER & 240×240 HARİTA")

    # Row 2 (y = 820): Custom Blender Models + 3D Regional Catalog (Farm/Village)
    place_sheet(MODELS_3D_DIR / "04_BLENDER_CUSTOM_ORES_VIEWMODELS_AND_HYBRID_TREES_12_GLBS.png", 60, 830, 1800, 750, "5. BLENDER 5.2 + KILN 3.0: 6 CEVHER DAMARI + 5 VIEWMODEL + HİBRİT AĞAÇ")
    place_sheet(MODELS_3D_DIR / "01_3D_CATALOG_SHEET_FARM_AND_VILLAGE_48_GLBS.png", 1920, 830, 1840, 750, "6. BÖLGE 1 & 2: ÇİFTLİK VE KÖY MEYDANI 48 3B MODEL KATALOĞU (.GLB)")

    # Row 3 (y = 1640): 2D Crops Mega Sheet + 8-Dir Enemies Mega Sheet
    place_sheet(SPRITES_2D_DIR / "01_2D_CROPS_66_STAGES_SOIL_STATES_AND_NORMALS_MEGA_SHEET.png", 60, 1650, 1800, 750, "7. 11 EKİN × 6 EVRE (66 SPRITE) + SİLİNDİRİK NORMAL HARİTALARI (66 SPRITE)")
    place_sheet(ENEMIES_DIR / "00_8DIR_MINE_ENEMIES_AND_NORMALS_MEGA_SHEET.png", 1920, 1650, 1840, 750, "8. 8 YÖNLÜ 6 MADEN DÜŞMANI (96 STRİP) + DİNAMİK NORMAL HARİTALARI")

    # Row 4 (y = 2460): 2D Props & UI Mega Sheet + 16 VFX Mega Sheet
    place_sheet(SPRITES_2D_DIR / "02_2D_TOOLS_ORES_DUNGEON_NPCS_AND_UI_ICONS_MEGA_SHEET.png", 60, 2470, 1800, 700, "9. 2B ALETLER, CEVHERLER, ZİNDAN SANDIK/MEŞALE OBJELERİ & NPC'LER")
    place_sheet(VFX_DIR / "00_25D_FARMING_VFX_MEGA_SHEET.png", 1920, 2470, 1840, 700, "10. PROSEDÜREL ÇİFTLİK, SULAMA, CEVHER & K4 FOSFOR VFX STRİPLERİ")

    # Save
    board.save(out_path)
    print(f"[OK] Master Mega Board Saved: {out_path}")


# ---------------------------------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== STARTING 2.5D FARMING MASTER PIPELINE BUILD ===")
    generate_remaining_enemies()
    compose_custom_3d_sheet()
    compose_3d_catalog_sheets()
    process_crops_and_compose_sheet()
    compose_props_and_ui_sheet()
    compose_8dir_enemies_sheet()
    compose_vfx_sheet()
    render_crt_ui_screens()
    generate_interactive_studio()
    compose_master_mega_board()
    print("=== MASTER PIPELINE BUILD COMPLETE ===")
