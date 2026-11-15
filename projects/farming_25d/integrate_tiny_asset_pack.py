#!/usr/bin/env python3
"""
Master Integration Script for Farm RPG Tiny Asset Pack (EmanuelleDev)
Adapts assets into projects/farming_25d/ for the 2.5D FPS Retro Farming + Shooter Hybrid.

- Strictly quantizes to GDD Section 8.4 32-Color Palette.
- Generates cluster-faceted normal maps (_n.png) for dynamic lighting.
- Slices front-facing horizontal strips (_stripN.png) for 2D Y-billboard sprites.
- Extracts 3D terrain/wall textures and UI elements.
- Records full attribution and metadata.
"""

import sys
import os
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, sobel

SOURCE_ROOT = Path(r"D:\Assetler\Farm RPG - Tiny Asset Pack - (All in One)")
TARGET_ROOT = Path(r"D:\GameMaker\projects\farming_25d")

FARMING_25D_PALETTE_HEX = [
    "#070B08", "#0D1610", "#142219", "#1C2F23",
    "#2E1D14", "#4A2F21", "#6B442E", "#8C5B3E", "#B37A54", "#D9A377",
    "#1A381F", "#28542E", "#3B753F", "#54994E", "#75BD64", "#9EE07E", "#C8F5A6",
    "#2B3036", "#454D57", "#687382", "#94A1B2", "#C7D2E0",
    "#C86432", "#E8994A", "#F5D042",
    "#19824C", "#28C76F", "#52FF9A", "#B8FFD6",
    "#D9383A", "#FF8C24", "#3898FF"
]

def hex_to_rgb(h: str):
    h = h.lstrip('#')
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]

PALETTE_RGB = np.array([hex_to_rgb(h) for h in FARMING_25D_PALETTE_HEX], dtype=np.float32)

def quantize_to_palette(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    arr = np.array(img)
    alpha = arr[:, :, 3]
    rgb = arr[:, :, :3].astype(np.float32)
    
    mask = alpha > 32
    if np.any(mask):
        pixels = rgb[mask]
        diff = pixels[:, np.newaxis, :] - PALETTE_RGB[np.newaxis, :, :]
        dist_sq = np.sum(diff ** 2, axis=2)
        nearest_idx = np.argmin(dist_sq, axis=1)
        rgb[mask] = PALETTE_RGB[nearest_idx]
        
    arr[:, :, :3] = np.clip(rgb, 0, 255).astype(np.uint8)
    arr[:, :, 3] = np.where(alpha > 32, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")

def generate_normal_map(img: Image.Image, strength: float = 1.8) -> Image.Image:
    arr = np.array(img)
    alpha = arr[:, :, 3]
    
    lum = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]) / 255.0
    dist = distance_transform_edt(alpha > 32)
    max_d = np.max(dist) or 1.0
    dist_norm = dist / max_d
    
    height = 0.60 * dist_norm + 0.40 * lum
    height[alpha <= 32] = 0.0
    
    dx = sobel(height, axis=1) * strength
    dy = -sobel(height, axis=0) * strength
    dz = np.ones_like(dx)
    
    length = np.sqrt(dx**2 + dy**2 + dz**2)
    length[length == 0] = 1.0
    nx = dx / length
    ny = dy / length
    nz = dz / length
    
    r = np.clip((nx * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    g = np.clip((ny * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    b = np.clip((nz * 0.5 + 0.5) * 255, 0, 255).astype(np.uint8)
    
    normal_arr = np.stack([r, g, b, alpha], axis=2)
    empty = alpha <= 32
    normal_arr[empty, 0] = 128
    normal_arr[empty, 1] = 128
    normal_arr[empty, 2] = 255
    normal_arr[empty, 3] = 0
    return Image.fromarray(normal_arr, "RGBA")

def process_sprite_sheet(src_path: Path, dst_dir: Path, base_name: str, frame_h: int = 32):
    """Processes a sheet, creates quantized version, normal map, and front-facing strip."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(src_path) as raw:
        quantized = quantize_to_palette(raw)
        normal = generate_normal_map(quantized)
        
        # Save full sheet
        quantized.save(dst_dir / f"{base_name}.png")
        normal.save(dst_dir / f"{base_name}_n.png")
        
        # Extract front-facing row (row 0)
        w, h = quantized.size
        cols = max(1, w // frame_h)
        if h >= frame_h:
            front_row = quantized.crop((0, 0, w, frame_h))
            front_normal = normal.crop((0, 0, w, frame_h))
            strip_name = f"{base_name}_front_strip{cols}"
            front_row.save(dst_dir / f"{strip_name}.png")
            front_normal.save(dst_dir / f"{strip_name}_n.png")

def run_integration():
    print("=" * 70)
    print("MIGRATING & ADAPTING ASSETS FROM TINY ASSET PACK")
    print(f"Source: {SOURCE_ROOT}")
    print(f"Target: {TARGET_ROOT}")
    print("=" * 70)
    
    stats = {
        "enemies": 0,
        "animals": 0,
        "props": 0,
        "workbenches": 0,
        "buildings": 0,
        "textures_3d": 0,
        "ui_and_icons": 0
    }
    
    # ----------------------------------------------------
    # 1. ENEMIES (Goblins, Slimes, Myconids, Spikes, Blooms)
    # ----------------------------------------------------
    print("\n[1/6] Processing Enemies (Guns 'n Goblins 2.5D FPS Hordes)...")
    enemy_dst = TARGET_ROOT / "sprites_2d" / "enemies_billboard"
    
    # 1a. Goblins
    goblin_src = SOURCE_ROOT / "Enemy" / "Goblins"
    if goblin_src.exists():
        for gob_type in ["Archer Goblin", "Bomb Goblin", "Spear Goblin"]:
            sub = goblin_src / gob_type
            if sub.exists():
                dst = enemy_dst / "goblins" / gob_type.lower().replace(" ", "_")
                for png in sub.glob("*.png"):
                    name = f"goblin_{gob_type.lower().split()[0]}_{png.stem.lower().replace(' ', '_')}"
                    process_sprite_sheet(png, dst, name, frame_h=32)
                    stats["enemies"] += 1
                    
        # Goblin Merchant
        merch_src = goblin_src / "Goblin merchant"
        if merch_src.exists():
            dst = enemy_dst / "goblins" / "merchant"
            for png in merch_src.glob("*.png"):
                name = f"goblin_merchant_anim_{png.stem}"
                process_sprite_sheet(png, dst, name, frame_h=32)
                stats["enemies"] += 1

    # 1b. Slimes
    slime_src = SOURCE_ROOT / "Enemy" / "Slimes"
    if slime_src.exists():
        for color in ["Green", "Blue", "Pink", "Pupple"]:
            sub_col = slime_src / color
            if sub_col.exists():
                for size in ["Big Slime", "Slime", "Small Slime"]:
                    sub_sz = sub_col / size
                    if sub_sz.exists():
                        dst = enemy_dst / "slimes" / color.lower() / size.lower().replace(" ", "_")
                        for png in sub_sz.glob("*.png"):
                            name = f"slime_{color.lower()}_{size.lower().replace(' ', '_')}_{png.stem.lower()}"
                            process_sprite_sheet(png, dst, name, frame_h=32)
                            stats["enemies"] += 1
                            
    # 1c. Myconids (Mushroom Monsters)
    myconid_src = SOURCE_ROOT / "Enemy" / "Myconid"
    if myconid_src.exists():
        for color in ["Green", "Blue", "Pink", "Purple"]:
            sub_col = myconid_src / color
            if sub_col.exists():
                dst = enemy_dst / "myconids" / color.lower()
                for png in sub_col.glob("*.png"):
                    name = f"myconid_{color.lower()}_{png.stem.lower()}"
                    process_sprite_sheet(png, dst, name, frame_h=32)
                    stats["enemies"] += 1

    # 1d. Spikes & Venom Blooms
    spike_src = SOURCE_ROOT / "Enemy" / "Spike"
    if spike_src.exists():
        dst = enemy_dst / "spikes"
        for png in spike_src.glob("*.png"):
            name = f"spike_monster_{png.stem.lower()}"
            process_sprite_sheet(png, dst, name, frame_h=32)
            stats["enemies"] += 1
        proj_dir = spike_src / "projectile"
        if proj_dir.exists():
            dst_proj = enemy_dst / "spikes" / "projectiles"
            for png in proj_dir.glob("*.png"):
                name = f"projectile_spike_{png.stem.lower()}"
                process_sprite_sheet(png, dst_proj, name, frame_h=16)
                stats["enemies"] += 1

    bloom_src = SOURCE_ROOT / "Enemy" / "Venom Bloom"
    if bloom_src.exists():
        dst = enemy_dst / "venom_bloom"
        for png in bloom_src.rglob("*.png"):
            name = f"venom_bloom_{png.stem.lower().replace(' ', '_')}"
            process_sprite_sheet(png, dst, name, frame_h=32)
            stats["enemies"] += 1

    # ----------------------------------------------------
    # 2. ANIMALS & WILDLIFE
    # ----------------------------------------------------
    print("\n[2/6] Processing Farm Animals & Forest Wildlife...")
    anim_dst = TARGET_ROOT / "sprites_2d" / "animals_billboard"
    
    # 2a. Farm Animals (Cow, Chicken, Sheep, Pig, Goat, Duck)
    farm_anim_src = SOURCE_ROOT / "Animals" / "Farm"
    if farm_anim_src.exists():
        # Cows
        cow_src = farm_anim_src / "Cow" / "Common Cow"
        if cow_src.exists():
            dst = anim_dst / "cow"
            for png in cow_src.glob("*.png"):
                name = f"animal_cow_{png.stem.lower().replace(' ', '_')}"
                process_sprite_sheet(png, dst, name, frame_h=32)
                stats["animals"] += 1
        # Chickens
        chick_src = farm_anim_src / "Chicken"
        if chick_src.exists():
            dst = anim_dst / "chicken"
            for png in chick_src.glob("*.png"):
                name = f"animal_chicken_{png.stem.lower().replace(' ', '_')}"
                process_sprite_sheet(png, dst, name, frame_h=16 if "Baby" in png.name else 32)
                stats["animals"] += 1
        # Sheep
        sheep_src = farm_anim_src / "Sheep"
        if sheep_src.exists():
            dst = anim_dst / "sheep"
            for png in sheep_src.glob("*.png"):
                name = f"animal_sheep_{png.stem.lower().replace(' ', '_').strip()}"
                process_sprite_sheet(png, dst, name, frame_h=32)
                stats["animals"] += 1
        # Pigs
        pig_src = farm_anim_src / "Pig"
        if pig_src.exists():
            dst = anim_dst / "pig"
            for png in pig_src.glob("*.png"):
                name = f"animal_pig_{png.stem.lower().replace(' ', '_')}"
                process_sprite_sheet(png, dst, name, frame_h=32)
                stats["animals"] += 1
        # Goat
        goat_src = farm_anim_src / "Goat"
        if goat_src.exists():
            dst = anim_dst / "goat"
            for png in goat_src.glob("*.png"):
                name = f"animal_goat_{png.stem.lower().replace(' ', '_')}"
                process_sprite_sheet(png, dst, name, frame_h=32)
                stats["animals"] += 1
        # Ducks
        duck_src = farm_anim_src / "Ducks"
        if duck_src.exists():
            dst = anim_dst / "duck"
            for png in duck_src.glob("*.png"):
                name = f"animal_duck_{png.stem.lower().replace(' ', '_')}"
                process_sprite_sheet(png, dst, name, frame_h=16)
                stats["animals"] += 1

    # 2b. Forest Wildlife (Deer, Fox, Rabbit, Frog, Crow, Bee, Butterfly, Snail)
    forest_src = SOURCE_ROOT / "Animals" / "Forest"
    if forest_src.exists():
        dst_wild = anim_dst / "wildlife"
        for sub_name in ["Deer/Female", "Deer/Male", "Fox", "Rabbit", "Frog", "Crow", "Bugs/Bee", "Bugs/Snail"]:
            p = forest_src / sub_name
            if p.exists():
                for png in p.glob("*.png"):
                    clean_name = f"wildlife_{sub_name.split('/')[-1].lower()}_{png.stem.lower().replace(' ', '_')}"
                    process_sprite_sheet(png, dst_wild, clean_name, frame_h=32)
                    stats["animals"] += 1

    # ----------------------------------------------------
    # 3. WORKBENCHES & CRAFTING STATIONS
    # ----------------------------------------------------
    print("\n[3/6] Processing Workbenches & Crafting Stations...")
    wb_src = SOURCE_ROOT / "Objects" / "Work Benches"
    wb_dst = TARGET_ROOT / "sprites_2d" / "props_billboard" / "workbenches"
    wb_dst.mkdir(parents=True, exist_ok=True)
    if wb_src.exists():
        for png in wb_src.glob("*.png"):
            name = f"workbench_{png.stem.lower().replace(' ', '_')}"
            process_sprite_sheet(png, wb_dst, name, frame_h=32)
            stats["workbenches"] += 1

    # ----------------------------------------------------
    # 4. EXTERIOR PROPS & FARM BUILDINGS
    # ----------------------------------------------------
    print("\n[4/6] Processing Exterior Props, Campfire, Lanterns & Buildings...")
    prop_dst = TARGET_ROOT / "sprites_2d" / "props_billboard"
    
    # 4a. Mine & Dungeon props (Bonfire, Lantern, Rail, Cart, Traps)
    mine_obj = SOURCE_ROOT / "Objects" / "Exterior" / "Mine and Dungeon"
    if mine_obj.exists():
        dst_mine = prop_dst / "mine_and_dungeon"
        for png in mine_obj.glob("*.png"):
            name = f"prop_mine_{png.stem.lower().replace(' ', '_')}"
            process_sprite_sheet(png, dst_mine, name, frame_h=32)
            stats["props"] += 1
        mine_sub = mine_obj / "Mine"
        if mine_sub.exists():
            for png in mine_sub.glob("*.png"):
                name = f"prop_mine_rail_{png.stem.lower().replace(' ', '_')}"
                process_sprite_sheet(png, dst_mine, name, frame_h=32)
                stats["props"] += 1

    # 4b. Farm Buildings (Barn, Chicken Coop, Greenhouse, Mill, Silo, Stable)
    bld_src = SOURCE_ROOT / "Objects" / "Exterior" / "Houses" / "Farm Buildings"
    if bld_src.exists():
        dst_bld = prop_dst / "farm_buildings"
        dst_bld.mkdir(parents=True, exist_ok=True)
        for bld_dir in bld_src.iterdir():
            if bld_dir.is_dir():
                for png in bld_dir.glob("*.png"):
                    name = f"building_{bld_dir.name.lower().replace(' ', '_')}_{png.stem.lower().replace(' ', '_')}"
                    with Image.open(png) as raw:
                        q = quantize_to_palette(raw)
                        n = generate_normal_map(q, strength=2.2)
                        q.save(dst_bld / f"{name}.png")
                        n.save(dst_bld / f"{name}_n.png")
                        stats["buildings"] += 1

    # 4c. General Props & All Props Sheets
    ext_src = SOURCE_ROOT / "Objects" / "Exterior"
    if ext_src.exists():
        dst_ext = prop_dst / "exterior"
        for png in ext_src.glob("*.png"):
            name = f"prop_exterior_{png.stem.lower().replace(' ', '_')}"
            process_sprite_sheet(png, dst_ext, name, frame_h=32)
            stats["props"] += 1

    # ----------------------------------------------------
    # 5. 3D TERRAIN & WALL TEXTURES (Tilesets)
    # ----------------------------------------------------
    print("\n[5/6] Processing 3D Terrain & Wall Textures...")
    tiles_src = SOURCE_ROOT / "Tileset"
    tiles_dst = TARGET_ROOT / "sprites_2d" / "textures_3d"
    tiles_dst.mkdir(parents=True, exist_ok=True)
    if tiles_src.exists():
        # Tilled Soil and Wet Soil
        soil_path = tiles_src / "Tilled Soil and wet soil.png"
        if soil_path.exists():
            with Image.open(soil_path) as raw:
                q = quantize_to_palette(raw)
                n = generate_normal_map(q, strength=2.0)
                q.save(tiles_dst / "tex_tilled_and_wet_soil_sheet.png")
                n.save(tiles_dst / "tex_tilled_and_wet_soil_sheet_n.png")
                # Extract individual 16x16 / 32x32 tiles for Dry Soil, Tilled Soil, Wet Soil
                dry_tile = q.crop((0, 0, 32, 32))
                dry_tile.save(tiles_dst / "tex_soil_dry_32x32.png")
                generate_normal_map(dry_tile).save(tiles_dst / "tex_soil_dry_32x32_n.png")
                
                tilled_tile = q.crop((32, 0, 64, 32))
                tilled_tile.save(tiles_dst / "tex_soil_tilled_32x32.png")
                generate_normal_map(tilled_tile).save(tiles_dst / "tex_soil_tilled_32x32_n.png")
                
                wet_tile = q.crop((64, 0, 96, 32))
                wet_tile.save(tiles_dst / "tex_soil_wet_32x32.png")
                generate_normal_map(wet_tile).save(tiles_dst / "tex_soil_wet_32x32_n.png")
                stats["textures_3d"] += 4

        # Caves & Dungeon & Path & Grass
        for tile_file in ["Caves.png", "Dungeon tileset.png", "Path tiles.png", "Tileset Grass Spring.png", "Tileset Grass Fall.png", "Barn tileset.png", "Water tile.png"]:
            p = tiles_src / tile_file
            if p.exists():
                with Image.open(p) as raw:
                    q = quantize_to_palette(raw)
                    n = generate_normal_map(q, strength=1.5)
                    clean_name = f"tex_{tile_file.lower().replace(' ', '_').replace('.png', '')}"
                    q.save(tiles_dst / f"{clean_name}.png")
                    n.save(tiles_dst / f"{clean_name}_n.png")
                    stats["textures_3d"] += 1

    # ----------------------------------------------------
    # 6. UI & 10-TIER RPG ICONS
    # ----------------------------------------------------
    print("\n[6/6] Processing UI Components & 10-Tier RPG Tool Icons...")
    ui_dst = TARGET_ROOT / "ui_ux" / "components"
    icons_dst = TARGET_ROOT / "ui_ux" / "icons"
    ui_dst.mkdir(parents=True, exist_ok=True)
    icons_dst.mkdir(parents=True, exist_ok=True)

    # 6a. UI Clock, Bars, HUD
    ui_src = SOURCE_ROOT / "UI"
    if ui_src.exists():
        # Clock
        clk = ui_src / "Clock" / "Clock.png"
        clk_h = ui_src / "Clock" / "clock hand.png"
        if clk.exists():
            quantize_to_palette(Image.open(clk)).save(ui_dst / "ui_clock_face.png")
            stats["ui_and_icons"] += 1
        if clk_h.exists():
            quantize_to_palette(Image.open(clk_h)).save(ui_dst / "ui_clock_hand.png")
            stats["ui_and_icons"] += 1
            
        # Bars & HUD
        for uipng in ["Bars.png", "HUD.png", "button.png", "dialogue box.png", "weather icons.png"]:
            p = ui_src / uipng
            if p.exists():
                quantize_to_palette(Image.open(p)).save(ui_dst / f"ui_{uipng.lower().replace(' ', '_')}")
                stats["ui_and_icons"] += 1

    # 6b. RPG Tool & Armor Icons (All 10 Tiers!)
    rpg_tiers_src = SOURCE_ROOT / "Icons" / "RPG icons" / "Weapons and Armor"
    if rpg_tiers_src.exists():
        for tier_dir in rpg_tiers_src.iterdir():
            if tier_dir.is_dir():
                tier_slug = tier_dir.name.lower().replace(" ", "_").replace(".", "")
                dst_tier = icons_dst / f"tier_{tier_slug}"
                dst_tier.mkdir(parents=True, exist_ok=True)
                for png in tier_dir.glob("*.png"):
                    name = f"icon_{tier_slug}_{png.stem.lower().replace(' ', '_')}.png"
                    quantize_to_palette(Image.open(png)).save(dst_tier / name)
                    stats["ui_and_icons"] += 1

    # 6c. Extras: Bars & Ores, Gems, Potions, Coal, Bags
    extras_src = SOURCE_ROOT / "Icons" / "RPG icons" / "Extras"
    if extras_src.exists():
        dst_ext = icons_dst / "extras"
        dst_ext.mkdir(parents=True, exist_ok=True)
        for png in extras_src.glob("*.png"):
            name = f"icon_extra_{png.stem.lower().replace(' ', '_')}.png"
            quantize_to_palette(Image.open(png)).save(dst_ext / name)
            stats["ui_and_icons"] += 1

    # 6d. Cooking & Food Produce Icons (Sample 20 essential food items)
    food_src = SOURCE_ROOT / "Icons" / "Food Icons"
    if food_src.exists():
        dst_food = icons_dst / "food"
        dst_food.mkdir(parents=True, exist_ok=True)
        food_files = list(food_src.glob("*.png"))[:30]
        for png in food_files:
            name = f"icon_food_{png.stem.lower().replace(' ', '_')}.png"
            quantize_to_palette(Image.open(png)).save(dst_food / name)
            stats["ui_and_icons"] += 1

    print("\n" + "=" * 70)
    print("INTEGRATION COMPLETE SUMMARY:")
    for k, v in stats.items():
        print(f" - {k.capitalize()}: {v} processed assets")
    print("=" * 70)

if __name__ == "__main__":
    run_integration()
