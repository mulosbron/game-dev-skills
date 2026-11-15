#!/usr/bin/env python3
"""
Generates the Master Visual Showcase Board for 2.5D FARMING & RETRO FPS HYBRID.
Displays:
1. Header & Technical Specifications (480x270 Viewport, Guns 'n Goblins 2.5D FPS Style).
2. FPS Viewmodels (Gold Tools + Chrome Guns).
3. Guns 'n Goblins Horde Enemies (Archer Goblin, Bomb Goblin, Spear Goblin, Slimes, Myconids).
4. Farm Livestock & Wildlife (Cow, Sheep, Chicken, Pig, Goat, Deer).
5. 11 Farming Crops (Growth Stages 0 to 5 + Harvested Items + Seeds).
6. Workbenches & Campfire Props (Furnace, Anvil, Workbench, Bonfire, Lanterns).
7. 10-Tier RPG Tool Progression (Wood -> Obsidian).
"""

import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(r"D:\GameMaker\projects\farming_25d")
OUTPUT_PATH = BASE_DIR / "00_25D_FARMING_MASTER_MEGA_BOARD.png"

def load_or_placeholder(path: Path, size=(32, 32)) -> Image.Image:
    if path.exists():
        img = Image.open(path).convert("RGBA")
        if img.size != size:
            img = img.resize(size, Image.NEAREST)
        return img
    img = Image.new("RGBA", size, (40, 45, 55, 255))
    return img

def create_master_board():
    board_w = 1920
    board_h = 1080
    board = Image.new("RGBA", (board_w, board_h), (7, 11, 8, 255)) # GDD CRT Void #070B08
    draw = ImageDraw.Draw(board)
    
    # 1. Header Banner
    draw.rectangle([0, 0, board_w, 70], fill=(20, 34, 25, 255))
    draw.rectangle([0, 68, board_w, 70], fill=(40, 199, 111, 255)) # CRT Green accent
    
    # Title
    draw.text((30, 15), "2.5D FARMING & RETRO FPS HYBRID — MASTER ASSET ATLAS", fill=(82, 255, 154, 255))
    draw.text((30, 40), "Target: Godot 4.x | Viewport: 480x270 @ 60 FPS | Perspective: First-Person 2.5D (Guns 'n Goblins Style)", fill=(184, 255, 214, 255))
    draw.text((1500, 25), "TOTAL ASSETS: 2,000+ FILES", fill=(245, 208, 66, 255))
    
    # Section 1: FPS First-Person Viewmodels (Hands, Tools & Guns)
    draw.rectangle([30, 85, 930, 320], fill=(13, 22, 16, 255), outline=(43, 48, 54, 255))
    draw.text((45, 95), "1. FIRST-PERSON VIEWMODELS (Tools & Firearm Viewmodels)", fill=(245, 208, 66, 255))
    vm_dir = BASE_DIR / "sprites_2d" / "viewmodels"
    vm_samples = [
        ("VM_01_Kazma_Gold_frame0.png", "Gold Kazma"),
        ("VM_02_Capa_Gold_frame0.png", "Gold Çapa"),
        ("VM_03_Sulama_Gold_frame0.png", "Gold Sulama"),
        ("VM_04_Tirpan_Gold_frame0.png", "Gold Tırpan"),
        ("VM_05_Tabanca_Chrome_frame0.png", "Chrome Tabanca"),
        ("VM_05_Tabanca_Chrome_frame1.png", "Muzzle Flash Shot")
    ]
    vx = 55
    for file_name, label in vm_samples:
        p = vm_dir / file_name
        img = load_or_placeholder(p, (128, 128))
        board.paste(img, (vx, 125), img)
        draw.text((vx, 260), label, fill=(200, 210, 224, 255))
        vx += 145

    # Section 2: Guns 'n Goblins Horde Enemies (2D Billboard Sprites)
    draw.rectangle([950, 85, 1890, 320], fill=(13, 22, 16, 255), outline=(43, 48, 54, 255))
    draw.text((965, 95), "2. GUNS 'N GOBLINS HORDE ENEMIES (2D Y-Billboard Sprites)", fill=(217, 56, 58, 255))
    
    enemy_samples = [
        (BASE_DIR / "sprites_2d/enemies_billboard/goblins/archer_goblin/goblin_archer_idle_front_strip4.png", "Archer Goblin (Strip4)", (128, 32)),
        (BASE_DIR / "sprites_2d/enemies_billboard/goblins/bomb_goblin/goblin_bomb_idle_front_strip4.png", "Bomb Goblin (Strip4)", (128, 32)),
        (BASE_DIR / "sprites_2d/enemies_billboard/goblins/spear_goblin/goblin_spear_idle_front_strip4.png", "Spear Goblin (Strip4)", (128, 32)),
        (BASE_DIR / "sprites_2d/enemies_billboard/slimes/green/slime/slime_green_slime_idle_front_strip4.png", "Green Slime (Strip4)", (128, 32)),
        (BASE_DIR / "sprites_2d/enemies_billboard/slimes/blue/slime/slime_blue_slime_idle_front_strip4.png", "Blue Slime (Strip4)", (128, 32)),
        (BASE_DIR / "sprites_2d/enemies_billboard/myconids/green/myconid_green_idle_front_strip4.png", "Myconid Shroom (Strip4)", (128, 32)),
        (BASE_DIR / "sprites_2d/enemies_billboard/spikes/spike_monster_idle_front_strip4.png", "Spike Monster (Strip4)", (128, 32))
    ]
    ey = 125
    for p, label, sz in enemy_samples[:4]:
        if p.exists():
            im = Image.open(p).convert("RGBA").resize((sz[0] * 2, sz[1] * 2), Image.NEAREST)
            board.paste(im, (965, ey), im)
            draw.text((1240, ey + 20), label, fill=(200, 210, 224, 255))
        ey += 45

    # Section 3: Farm Livestock & Forest Wildlife (2D Billboard Sprites)
    draw.rectangle([30, 335, 930, 570], fill=(13, 22, 16, 255), outline=(43, 48, 54, 255))
    draw.text((45, 345), "3. FARM LIVESTOCK & FOREST WILDLIFE (2D Y-Billboard Sprites)", fill=(117, 189, 100, 255))
    anim_samples = [
        (BASE_DIR / "sprites_2d/animals_billboard/cow/animal_cow_female_cow_black_front_strip4.png", "Dairy Cow"),
        (BASE_DIR / "sprites_2d/animals_billboard/cow/animal_cow_female_cow_brown_front_strip4.png", "Brown Cow"),
        (BASE_DIR / "sprites_2d/animals_billboard/sheep/animal_sheep_sheep_female_front_strip4.png", "Wool Sheep"),
        (BASE_DIR / "sprites_2d/animals_billboard/pig/animal_pig_pig_pink_front_strip4.png", "Farm Pig"),
        (BASE_DIR / "sprites_2d/animals_billboard/chicken/animal_chicken_chicken_white_front_strip4.png", "Hen White"),
        (BASE_DIR / "sprites_2d/animals_billboard/duck/animal_duck_baby_duck_brown_front_strip4.png", "Duckling")
    ]
    ax = 50
    for p, label in anim_samples:
        if p.exists():
            im = Image.open(p).convert("RGBA").crop((0, 0, 32, 32)).resize((64, 64), Image.NEAREST)
            board.paste(im, (ax, 380), im)
            draw.text((ax, 455), label, fill=(200, 210, 224, 255))
        ax += 145

    # Section 4: Workbenches, Campfire & Props
    draw.rectangle([950, 335, 1890, 570], fill=(13, 22, 16, 255), outline=(43, 48, 54, 255))
    draw.text((965, 345), "4. WORKBENCHES, CAMPFIRE & MINE PROPS (2D Billboard / 3D Textures)", fill=(232, 153, 74, 255))
    prop_samples = [
        (BASE_DIR / "sprites_2d/props_billboard/mine_and_dungeon/prop_mine_bonfire.png", "Campfire"),
        (BASE_DIR / "sprites_2d/props_billboard/mine_and_dungeon/prop_mine_lamp_.png", "Lantern"),
        (BASE_DIR / "sprites_2d/props_billboard/workbenches/workbench_furnace.png", "Furnace"),
        (BASE_DIR / "sprites_2d/props_billboard/workbenches/workbench_anvil.png", "Anvil"),
        (BASE_DIR / "sprites_2d/props_billboard/workbenches/workbench_workbench.png", "Crafting Table"),
        (BASE_DIR / "sprites_2d/props_billboard/workbenches/workbench_alchemy_table.png", "Alchemy Table"),
        (BASE_DIR / "sprites_2d/props_billboard/mine_and_dungeon/prop_mine_minecart.png", "Mine Cart")
    ]
    px = 965
    for p, label in prop_samples:
        if p.exists():
            im = Image.open(p).convert("RGBA")
            im = im.crop((0, 0, min(im.width, 32), min(im.height, 32))).resize((64, 64), Image.NEAREST)
            board.paste(im, (px, 380), im)
            draw.text((px, 455), label, fill=(200, 210, 224, 255))
        px += 130

    # Section 5: 11 Farming Crops Progression (Stages 0 to 5)
    draw.rectangle([30, 585, 1890, 810], fill=(13, 22, 16, 255), outline=(43, 48, 54, 255))
    draw.text((45, 595), "5. 11 CROPS GROWTH PIPELINE (Stage 0: Tohum -> Stage 1: Filiz -> Stage 5: Hasat + Ürün & Tohum İkonları)", fill=(158, 224, 126, 255))
    
    crops_to_show = ["bugday", "domates", "havuc", "kabak", "lahana", "aycicegi"]
    cy = 630
    for crop in crops_to_show:
        draw.text((45, cy + 8), crop.capitalize(), fill=(245, 208, 66, 255))
        cx = 150
        # Show stages 0, 1, 3, 5
        for stg in [0, 1, 3, 5]:
            p = BASE_DIR / f"sprites_2d/crops/crop_{crop}_stage_0{stg}.png"
            if p.exists():
                im = Image.open(p).convert("RGBA").resize((32, 32), Image.NEAREST)
                board.paste(im, (cx, cy), im)
            cx += 45
        # Show harvested item & seed
        item_p = BASE_DIR / f"sprites_2d/props_and_ui/item_crop_{crop}.png"
        seed_p = BASE_DIR / f"sprites_2d/props_and_ui/item_seed_{crop}.png"
        if item_p.exists():
            im = Image.open(item_p).convert("RGBA").resize((32, 32), Image.NEAREST)
            board.paste(im, (cx + 20, cy), im)
        if seed_p.exists():
            im = Image.open(seed_p).convert("RGBA").resize((32, 32), Image.NEAREST)
            board.paste(im, (cx + 65, cy), im)
        cy += 40

    # Section 6: 10-Tier RPG Tool Progression & UI
    draw.rectangle([30, 825, 1890, 1050], fill=(13, 22, 16, 255), outline=(43, 48, 54, 255))
    draw.text((45, 835), "6. 10-TIER RPG EQUIPMENT PROGRESSION & CRT RETRO UI (Wood -> Cooper -> Iron -> Gold -> Platinum -> Obsidian)", fill=(56, 152, 255, 255))
    
    tiers = [
        ("tier_1_wood", "1. Wood"),
        ("tier_2_cooper", "2. Copper"),
        ("tier_3_iron", "3. Iron"),
        ("tier_4_gold", "4. Gold"),
        ("tier_5_platinum", "5. Platinum"),
        ("tier_6_crimson", "6. Crimson"),
        ("tier_7_frost", "7. Frost"),
        ("tier_8_shadow", "8. Shadow"),
        ("tier_9_obsidian", "9. Obsidian")
    ]
    tx = 50
    for tier_folder, label in tiers:
        p_hoe = BASE_DIR / f"ui_ux/icons/{tier_folder}/icon_{tier_folder.replace('tier_', '')}_hoe.png"
        p_axe = BASE_DIR / f"ui_ux/icons/{tier_folder}/icon_{tier_folder.replace('tier_', '')}_axe.png"
        p_sword = BASE_DIR / f"ui_ux/icons/{tier_folder}/icon_{tier_folder.replace('tier_', '')}_sword.png"
        draw.text((tx, 865), label, fill=(200, 210, 224, 255))
        
        ix = tx
        for icon_path in [p_hoe, p_axe, p_sword]:
            if icon_path.exists():
                im = Image.open(icon_path).convert("RGBA").resize((36, 36), Image.NEAREST)
                board.paste(im, (ix, 895), im)
            ix += 42
        tx += 190

    # UI Clock & Bars preview on right
    clk_p = BASE_DIR / "ui_ux/components/ui_clock_face.png"
    if clk_p.exists():
        im = Image.open(clk_p).convert("RGBA").resize((64, 64), Image.NEAREST)
        board.paste(im, (1780, 865), im)
        draw.text((1770, 935), "Day/Night Clock", fill=(245, 208, 66, 255))
        
    board.save(OUTPUT_PATH)
    print(f"Master Showcase Mega-Board successfully generated: {OUTPUT_PATH} ({board_w}x{board_h})")

if __name__ == "__main__":
    create_master_board()
