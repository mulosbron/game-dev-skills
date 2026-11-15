#!/usr/bin/env python3
"""
Master Real Asset Harvester for 'Aestra: The Last Wish'
Extracts genuine handcrafted pixel art from:
  1. LPC (Liberated Pixel Cup Universal Character Generator)
  2. Redshrike Classic Monsters (Goblins, Golems, Imps, Spiders, Wolves)
  3. CharlesGabriel Classic Monsters (Bats, Slimes, Ghosts, Snakes, Worms, Plants)
  4. PixelSRPG-Forge (Boars, Treants, Rhinos, Mushrooms, MapleStory Weapons & Skills)
Organizes them into standard horizontal strips, generates normal maps, .import files, and SpriteFrames (.tres).
"""

import os
import sys
import shutil
from pathlib import Path
from PIL import Image
import numpy as np

WORKSPACE = Path(__file__).resolve().parent.parent
TARGET_ROOT = WORKSPACE / "projects" / "nos" / "assets"
ENEMIES_ROOT = TARGET_ROOT / "enemies"
ICONS_ROOT = TARGET_ROOT / "ui" / "icons"

LPC_GEN = WORKSPACE / "libraries" / "com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator" / "spritesheets"
REDSHRIKE = WORKSPACE / "libraries" / "org.opengameart.liberatedpixelcup" / "sprite" / "original" / "Redshrike"
CHARLES = WORKSPACE / "libraries" / "org.opengameart.liberatedpixelcup" / "sprite" / "original" / "CharlesGabriel" / "PNG"
PIXELSRPG_MONSTERS = WORKSPACE / "libraries" / "com.github.huu-yuu.pixelsrpg-forge" / "Characters_角色人物" / "monster" / "monster"
PIXELSRPG_WEAPONS = WORKSPACE / "libraries" / "com.github.huu-yuu.pixelsrpg-forge" / "Weapons_武器装备" / "weapons-MapleStory" / "武器装备-冒险岛"
PIXELSRPG_SKILLS = WORKSPACE / "libraries" / "com.github.huu-yuu.pixelsrpg-forge" / "Skill_Icons_技能图标" / "Skill_Icons-MapleStory" / "技能图标"

def make_normal_map(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    arr = np.array(rgba)
    alpha = arr[:, :, 3] > 20
    if not np.any(alpha):
        return Image.new("RGBA", img.size, (128, 128, 255, 0))

    try:
        from scipy.ndimage import distance_transform_edt
        dist = distance_transform_edt(alpha)
    except Exception:
        from PIL import ImageFilter
        mask = Image.fromarray((alpha * 255).astype(np.uint8))
        dist = np.array(mask.filter(ImageFilter.GaussianBlur(radius=2)), dtype=float)

    if dist.max() > 0:
        dist = dist / dist.max()

    lum = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114) / 255.0
    height = dist * 0.7 + lum * 0.3

    gy, gx = np.gradient(height)
    strength = 3.5
    nx = -gx * strength
    ny = -gy * strength
    nz = np.ones_like(nx)
    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    norm[norm == 0] = 1.0
    nx /= norm
    ny /= norm
    nz /= norm

    r = ((nx * 0.5 + 0.5) * 255).astype(np.uint8)
    g = (((-ny) * 0.5 + 0.5) * 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255).astype(np.uint8)
    a = arr[:, :, 3]

    norm_arr = np.dstack([r, g, b, a])
    return Image.fromarray(norm_arr, "RGBA")

def create_import_file(target_png: Path):
    imp_path = target_png.with_suffix(target_png.suffix + ".import")
    rel_path = f"res://assets/{target_png.relative_to(TARGET_ROOT).as_posix()}"
    h = abs(hash(str(target_png)))
    content = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="uid://{h % 1000000000000}"
path="res://.godot/imported/{target_png.name}-{h % 10000000}.ctex"
metadata={{
"vram_texture": false
}}

[deps]

source_file="{rel_path}"
dest_files=["res://.godot/imported/{target_png.name}-{h % 10000000}.ctex"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossless_quality=0.7
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=false
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
svg/scale=1.0
editor/scale_with_editor_scale=false
editor/convert_colors_with_editor_theme=false
"""
    imp_path.write_text(content, encoding="utf-8")

def save_strip_and_normal(strip_img: Image.Image, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    strip_img.save(out_path)
    create_import_file(out_path)
    
    # Normal map in 'normals/' subfolder
    normals_dir = out_path.parent / "normals"
    normals_dir.mkdir(parents=True, exist_ok=True)
    norm_path = normals_dir / f"{out_path.stem}_n.png"
    norm_img = make_normal_map(strip_img)
    norm_img.save(norm_path)
    create_import_file(norm_path)

def slice_horizontal_row(sheet: Image.Image, frame_w: int, frame_h: int, row_idx: int, num_cols: int) -> Image.Image:
    strip = Image.new("RGBA", (num_cols * frame_w, frame_h), (0, 0, 0, 0))
    for c in range(num_cols):
        f = sheet.crop((c * frame_w, row_idx * frame_h, (c + 1) * frame_w, (row_idx + 1) * frame_h))
        strip.paste(f, (c * frame_w, 0))
    return strip

def create_spriteframes_for_strips(tres_path: Path, anims_dict: dict):
    """
    anims_dict: { anim_name: { 'strip_file': Path, 'cols': int, 'frame_w': int, 'frame_h': int, 'fps': int, 'loop': bool } }
    """
    tres_path.parent.mkdir(parents=True, exist_ok=True)
    subres_lines = []
    anim_blocks = []
    ext_res_lines = []
    
    res_counter = 1
    ext_idx = 1
    
    for anim_name, info in anims_dict.items():
        s_file = info['strip_file']
        rel_tex = f"res://assets/{s_file.relative_to(TARGET_ROOT).as_posix()}"
        tex_id = f"ext_{ext_idx}"
        ext_res_lines.append(f'[ext_resource type="Texture2D" path="{rel_tex}" id="{tex_id}"]')
        ext_idx += 1
        
        cols = info['cols']
        fw = info['frame_w']
        fh = info['frame_h']
        
        frame_refs = []
        for c in range(cols):
            sub_id = f"AtlasTexture_{res_counter}"
            res_counter += 1
            subres_lines.append(f"""[sub_resource type="AtlasTexture" id="{sub_id}"]
atlas = ExtResource("{tex_id}")
region = Rect2({c * fw}, 0, {fw}, {fh})
""")
            frame_refs.append(f"""{{
"duration": 1.0,
"texture": SubResource("{sub_id}")
}}""")
            
        anim_blocks.append(f"""{{
"frames": [
{",\n".join(frame_refs)}
],
"loop": {str(info.get('loop', True)).lower()},
"name": &"{anim_name}",
"speed": {info.get('fps', 10.0)}
}}""")

    content = f"""[gd_resource type="SpriteFrames" load_steps={res_counter + ext_idx} format=3]

{"\n".join(ext_res_lines)}

{"\n".join(subres_lines)}
[resource]
animations = [{",\n".join(anim_blocks)}]
"""
    tres_path.write_text(content, encoding="utf-8")

# ==============================================================================
# 1. HARVEST BEASTS & WILD MONSTERS (Redshrike, CharlesGabriel, PixelSRPG)
# ==============================================================================
def harvest_beasts():
    beasts_dir = ENEMIES_ROOT / "beasts"
    print("\n--- Harvesting Beasts & Wildlife ---")

    # A) Dire Wolf (Redshrike) - 64x64 frames
    wolf1 = REDSHRIKE / "wolf" / "wolfsheet1.png" # walk (cols=5, row 2=down)
    wolf3 = REDSHRIKE / "wolf" / "wolfsheet3.png" # run (cols=5, row 2=down)
    wolfhowl = REDSHRIKE / "wolf" / "howl.png"    # howl (cols=4, row 2=down)
    wolf5 = REDSHRIKE / "wolf" / "wolfsheet5.png" # attack (cols=5, row 2=down)

    wolf_anims = {}
    if wolf1.exists():
        im = Image.open(wolf1).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 5)
        p = beasts_dir / "dire_wolf_walk_strip5.png"
        save_strip_and_normal(strip, p)
        wolf_anims['walk'] = {'strip_file': p, 'cols': 5, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': True}

    if wolf3.exists():
        im = Image.open(wolf3).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 5)
        p = beasts_dir / "dire_wolf_run_strip5.png"
        save_strip_and_normal(strip, p)
        wolf_anims['run'] = {'strip_file': p, 'cols': 5, 'frame_w': 64, 'frame_h': 64, 'fps': 12, 'loop': True}

    if wolf5.exists():
        im = Image.open(wolf5).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 5)
        p = beasts_dir / "dire_wolf_attack_strip5.png"
        save_strip_and_normal(strip, p)
        wolf_anims['attack'] = {'strip_file': p, 'cols': 5, 'frame_w': 64, 'frame_h': 64, 'fps': 10, 'loop': False}

    if wolfhowl.exists():
        im = Image.open(wolfhowl).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 4)
        p = beasts_dir / "dire_wolf_howl_strip4.png"
        save_strip_and_normal(strip, p)
        wolf_anims['howl'] = {'strip_file': p, 'cols': 4, 'frame_w': 64, 'frame_h': 64, 'fps': 6, 'loop': False}

    if wolf_anims:
        create_spriteframes_for_strips(beasts_dir / "dire_wolf_frames.tres", wolf_anims)
        print("  [x] Harvested Dire Wolf (walk, run, attack, howl)")

    # B) Giant Spider (Redshrike) - 64x64 frames
    spider_sheet = REDSHRIKE / "spider" / "PNG" / "spider01.png"
    if spider_sheet.exists():
        im = Image.open(spider_sheet).convert("RGBA")
        # 10 cols, row 2=down
        walk_strip = slice_horizontal_row(im, 64, 64, 2, 5)
        atk_strip = slice_horizontal_row(im, 64, 64, 2, 10)
        p_walk = beasts_dir / "giant_spider_walk_strip5.png"
        p_atk = beasts_dir / "giant_spider_attack_strip10.png"
        save_strip_and_normal(walk_strip, p_walk)
        save_strip_and_normal(atk_strip, p_atk)
        create_spriteframes_for_strips(beasts_dir / "giant_spider_frames.tres", {
            'walk': {'strip_file': p_walk, 'cols': 5, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': True},
            'attack': {'strip_file': p_atk, 'cols': 10, 'frame_w': 64, 'frame_h': 64, 'fps': 12, 'loop': False}
        })
        print("  [x] Harvested Giant Spider (walk, attack)")

    # C) CharlesGabriel Standard 96x128 4-Direction Sprites (32x32 frames, row 2 = Down)
    charles_mobs = [
        ("bat.png", "cave_bat", "fly"),
        ("slime.png", "green_slime", "hop"),
        ("snake.png", "giant_snake", "slither"),
        ("small_worm.png", "cave_worm", "crawl"),
        ("bee.png", "killer_bee", "hover")
    ]
    for filename, mob_id, anim_name in charles_mobs:
        src = CHARLES / filename
        if src.exists():
            im = Image.open(src).convert("RGBA")
            strip = slice_horizontal_row(im, 32, 32, 2, 3)
            p = beasts_dir / f"{mob_id}_{anim_name}_strip3.png"
            save_strip_and_normal(strip, p)
            create_spriteframes_for_strips(beasts_dir / f"{mob_id}_frames.tres", {
                anim_name: {'strip_file': p, 'cols': 3, 'frame_w': 32, 'frame_h': 32, 'fps': 8, 'loop': True}
            })
            print(f"  [x] Harvested {mob_id} ({anim_name})")

    # D) PixelSRPG Monsters (AngryPig, Trunk, Plant, Rino, Mushroom)
    ps_mobs = [
        ("AngryPig", "wild_boar", [("Idle (36x30).png", "idle", 36, 30, 9), ("Run (36x30).png", "run", 36, 30, 12), ("Hit 1 (36x30).png", "hit", 36, 30, 5)]),
        ("Trunk", "ancient_treant", [("Idle (64x32).png", "idle", 64, 32, 18), ("Run (64x32).png", "run", 64, 32, 14), ("Attack (64x32).png", "attack", 64, 32, 11)]),
        ("Plant", "man_eater_plant", [("Idle (44x42).png", "idle", 44, 42, 11), ("Attack (44x42).png", "attack", 44, 42, 8), ("Hit (44x42).png", "hit", 44, 42, 5)]),
        ("Rino", "horned_rhino", [("Idle (52x34).png", "idle", 52, 34, 11), ("Run (52x34).png", "run", 52, 34, 6), ("Hit (52x34).png", "hit", 52, 34, 5)]),
        ("Mushroom", "spore_mushroom", [("Idle (32x32).png", "idle", 32, 32, 14), ("Run (32x32).png", "run", 32, 32, 16), ("Hit.png", "hit", 32, 32, 5)])
    ]
    for folder, mob_id, anim_list in ps_mobs:
        mob_anims = {}
        for src_file, a_name, fw, fh, expected_cols in anim_list:
            sp = PIXELSRPG_MONSTERS / folder / src_file
            if sp.exists():
                im = Image.open(sp).convert("RGBA")
                cols = im.width // fw
                strip = im.crop((0, 0, cols * fw, fh))
                p = beasts_dir / f"{mob_id}_{a_name}_strip{cols}.png"
                save_strip_and_normal(strip, p)
                mob_anims[a_name] = {'strip_file': p, 'cols': cols, 'frame_w': fw, 'frame_h': fh, 'fps': 10, 'loop': (a_name != 'hit' and a_name != 'attack')}
        if mob_anims:
            create_spriteframes_for_strips(beasts_dir / f"{mob_id}_frames.tres", mob_anims)
            print(f"  [x] Harvested {mob_id} ({list(mob_anims.keys())})")

# ==============================================================================
# 2. HARVEST GOLEMS & IMPS (Redshrike)
# ==============================================================================
def harvest_golems_and_imps():
    golems_dir = ENEMIES_ROOT / "golems"
    imps_dir = ENEMIES_ROOT / "imps_and_demons"
    print("\n--- Harvesting Golems & Imps ---")

    # A) Stone Golem (Redshrike Golem: 448x256, 7 cols x 4 rows @ 64x64)
    g_walk = REDSHRIKE / "golem" / "PNG" / "golem-walk.png"
    g_atk = REDSHRIKE / "golem" / "PNG" / "golem-atk.png"
    g_die = REDSHRIKE / "golem" / "PNG" / "golem-die.png"
    golem_anims = {}

    if g_walk.exists():
        im = Image.open(g_walk).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 7)
        p = golems_dir / "stone_golem_walk_strip7.png"
        save_strip_and_normal(strip, p)
        golem_anims['walk'] = {'strip_file': p, 'cols': 7, 'frame_w': 64, 'frame_h': 64, 'fps': 7, 'loop': True}

    if g_atk.exists():
        im = Image.open(g_atk).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 7)
        p = golems_dir / "stone_golem_attack_strip7.png"
        save_strip_and_normal(strip, p)
        golem_anims['attack'] = {'strip_file': p, 'cols': 7, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': False}

    if g_die.exists():
        im = Image.open(g_die).convert("RGBA")
        strip = slice_horizontal_row(im, 64, 64, 2, 7)
        p = golems_dir / "stone_golem_death_strip7.png"
        save_strip_and_normal(strip, p)
        golem_anims['death'] = {'strip_file': p, 'cols': 7, 'frame_w': 64, 'frame_h': 64, 'fps': 7, 'loop': False}

    if golem_anims:
        create_spriteframes_for_strips(golems_dir / "stone_golem_frames.tres", golem_anims)
        print("  [x] Harvested Stone Golem (walk, attack, death)")

    # B) Red, Blue, Green Imps (Redshrike) - 64x64 frames, 4 cols x 4 rows
    imp_colors = ["red", "blue", "green"]
    for color in imp_colors:
        imp_dir = REDSHRIKE / "imp" / "PNG" / color
        if not imp_dir.exists():
            continue
        
        walk_f = imp_dir / "walk - sword.png" if (imp_dir / "walk - sword.png").exists() else imp_dir / "walk - vanilla.png"
        atk_f = imp_dir / "attack - sword.png" if (imp_dir / "attack - sword.png").exists() else imp_dir / "attack - vanilla.png"
        die_f = imp_dir / "imp death.png"

        anims = {}
        if walk_f.exists():
            im = Image.open(walk_f).convert("RGBA")
            strip = slice_horizontal_row(im, 64, 64, 2, 4)
            p = imps_dir / f"{color}_imp_walk_strip4.png"
            save_strip_and_normal(strip, p)
            anims['walk'] = {'strip_file': p, 'cols': 4, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': True}

        if atk_f.exists():
            im = Image.open(atk_f).convert("RGBA")
            strip = slice_horizontal_row(im, 64, 64, 2, 4)
            p = imps_dir / f"{color}_imp_attack_strip4.png"
            save_strip_and_normal(strip, p)
            anims['attack'] = {'strip_file': p, 'cols': 4, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': False}

        if die_f.exists():
            im = Image.open(die_f).convert("RGBA")
            strip = slice_horizontal_row(im, 64, 64, 0, 5) if im.width >= 320 else slice_horizontal_row(im, 64, 64, 0, im.width // 64)
            p = imps_dir / f"{color}_imp_death_strip{strip.width//64}.png"
            save_strip_and_normal(strip, p)
            anims['death'] = {'strip_file': p, 'cols': strip.width//64, 'frame_w': 64, 'frame_h': 64, 'fps': 6, 'loop': False}

        if anims:
            create_spriteframes_for_strips(imps_dir / f"{color}_imp_frames.tres", anims)
            print(f"  [x] Harvested {color.capitalize()} Imp ({list(anims.keys())})")

# ==============================================================================
# 3. HARVEST HUMANOIDS & UNDEAD (LPC Modular Compositing)
# ==============================================================================
def composite_lpc_strip(layers: list, action: str, direction_row: int = 2) -> Image.Image:
    """
    Composites multiple LPC spritesheet layers for an action (walk, slash, shoot, spellcast, hurt)
    and extracts the Downward facing horizontal strip.
    """
    comp_sheet = None
    for l_rel in layers:
        lp = LPC_GEN / f"{l_rel}/{action}.png"
        if not lp.exists():
            # Try alternate path
            lp = LPC_GEN / f"{l_rel}.png"
        if not lp.exists():
            continue
            
        layer_img = Image.open(lp).convert("RGBA")
        if comp_sheet is None:
            comp_sheet = Image.new("RGBA", layer_img.size, (0, 0, 0, 0))
        if layer_img.size != comp_sheet.size:
            temp = Image.new("RGBA", comp_sheet.size, (0, 0, 0, 0))
            temp.paste(layer_img, (0, 0), layer_img)
            layer_img = temp
        comp_sheet.alpha_composite(layer_img)

    if comp_sheet is None:
        return None

    # Number of columns
    cols = comp_sheet.width // 64
    row = direction_row if (direction_row + 1) * 64 <= comp_sheet.height else 0
    return slice_horizontal_row(comp_sheet, 64, 64, row, cols)

def harvest_humanoids_and_undead():
    humanoids_dir = ENEMIES_ROOT / "humanoids"
    undead_dir = ENEMIES_ROOT / "undead"
    print("\n--- Harvesting Humanoids & Undead (LPC) ---")

    # A) UNDEAD: Skeleton Warrior, Skeleton Archer, Skeleton Mage, Zombie
    undead_defs = [
        ("skeleton_warrior", undead_dir, [
            ("walk", ["body/bodies/skeleton", "legs/pants/male/torn/walk", "weapon/sword/arming/universal/fg"]),
            ("slash", ["body/bodies/skeleton", "weapon/sword/arming/attack_slash/fg"]),
            ("hurt", ["body/bodies/skeleton"])
        ]),
        ("skeleton_archer", undead_dir, [
            ("walk", ["body/bodies/skeleton", "quiver/quiver"]),
            ("shoot", ["body/bodies/skeleton", "quiver/quiver"]),
            ("hurt", ["body/bodies/skeleton"])
        ]),
        ("skeleton_mage", undead_dir, [
            ("walk", ["body/bodies/skeleton", "torso/tunics/robe/male", "weapon/magic/simple/foreground"]),
            ("spellcast", ["body/bodies/skeleton", "torso/tunics/robe/male", "weapon/magic/simple/foreground"]),
            ("hurt", ["body/bodies/skeleton"])
        ]),
        ("zombie_walker", undead_dir, [
            ("walk", ["body/bodies/zombie", "legs/pants/male/torn/walk", "torso/clothes/tunic/male"]),
            ("hurt", ["body/bodies/zombie"])
        ])
    ]
    for mob_id, out_folder, actions in undead_defs:
        anims = {}
        for act, layers in actions:
            strip = composite_lpc_strip(layers, act, direction_row=2)
            if strip:
                cols = strip.width // 64
                p = out_folder / f"{mob_id}_{act}_strip{cols}.png"
                save_strip_and_normal(strip, p)
                anims[act] = {'strip_file': p, 'cols': cols, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': (act == 'walk')}
        if anims:
            create_spriteframes_for_strips(out_folder / f"{mob_id}_frames.tres", anims)
            print(f"  [x] Harvested Undead: {mob_id} ({list(anims.keys())})")

    # B) HUMANOIDS: Bandits, Corrupted Knights, Spearmen, Cultists, Orcs, Goblins
    humanoid_defs = [
        ("bandit_thug", [
            ("walk", ["body/bodies/muscular", "legs/pants/male", "torso/armour/leather/male", "head/heads/human/male", "hair/messy/adult", "weapon/blunt/club"]),
            ("slash", ["body/bodies/muscular", "legs/pants/male", "torso/armour/leather/male", "head/heads/human/male", "hair/messy/adult", "weapon/blunt/club/attack_slash"]),
            ("hurt", ["body/bodies/muscular", "legs/pants/male", "torso/armour/leather/male", "head/heads/human/male"])
        ]),
        ("bandit_archer", [
            ("walk", ["body/bodies/male", "legs/pants/male", "torso/armour/leather/male", "head/heads/human/male", "quiver/quiver"]),
            ("shoot", ["body/bodies/male", "legs/pants/male", "torso/armour/leather/male", "head/heads/human/male", "quiver/quiver"]),
            ("hurt", ["body/bodies/male", "legs/pants/male", "torso/armour/leather/male", "head/heads/human/male"])
        ]),
        ("bandit_assassin", [
            ("walk", ["body/bodies/female", "legs/pants/thin", "torso/armour/leather/thin", "head/heads/human/female", "weapon/sword/dagger/walk"]),
            ("slash", ["body/bodies/female", "legs/pants/thin", "torso/armour/leather/thin", "head/heads/human/female", "weapon/sword/dagger/slash"]),
            ("hurt", ["body/bodies/female", "legs/pants/thin", "torso/armour/leather/thin", "head/heads/human/female"])
        ]),
        ("corrupted_knight", [
            ("walk", ["body/bodies/male", "legs/armour/plate/male", "torso/armour/plate/male", "feet/armour/plate/male", "head/heads/human/male", "hat/helmet/plate/male"]),
            ("slash", ["body/bodies/male", "legs/armour/plate/male", "torso/armour/plate/male", "feet/armour/plate/male", "head/heads/human/male", "hat/helmet/plate/male"]),
            ("hurt", ["body/bodies/male", "legs/armour/plate/male", "torso/armour/plate/male", "feet/armour/plate/male"])
        ]),
        ("royal_spearman", [
            ("walk", ["body/bodies/male", "legs/pants/male", "torso/chainmail/male", "head/heads/human/male", "weapon/polearm/spear/male/walk"]),
            ("thrust", ["body/bodies/male", "legs/pants/male", "torso/chainmail/male", "head/heads/human/male", "weapon/polearm/spear/male/thrust"]),
            ("hurt", ["body/bodies/male", "legs/pants/male", "torso/chainmail/male", "head/heads/human/male"])
        ]),
        ("dark_cultist", [
            ("walk", ["body/bodies/male", "legs/pants/male", "torso/tunics/robe/male", "head/heads/human/male"]),
            ("spellcast", ["body/bodies/male", "legs/pants/male", "torso/tunics/robe/male", "head/heads/human/male"]),
            ("hurt", ["body/bodies/male", "legs/pants/male", "torso/tunics/robe/male", "head/heads/human/male"])
        ]),
        ("orc_berserker", [
            ("walk", ["body/bodies/muscular", "head/heads/orc/male", "legs/pants/male", "weapon/blunt/waraxe/walk"]),
            ("slash", ["body/bodies/muscular", "head/heads/orc/male", "legs/pants/male", "weapon/blunt/waraxe/attack_slash"]),
            ("hurt", ["body/bodies/muscular", "head/heads/orc/male", "legs/pants/male"])
        ]),
        ("lizardman_hunter", [
            ("walk", ["body/bodies/male", "head/heads/lizard/male", "legs/pants/male", "weapon/polearm/spear/male/walk"]),
            ("thrust", ["body/bodies/male", "head/heads/lizard/male", "legs/pants/male", "weapon/polearm/spear/male/thrust"]),
            ("hurt", ["body/bodies/male", "head/heads/lizard/male", "legs/pants/male"])
        ])
    ]
    for mob_id, actions in humanoid_defs:
        anims = {}
        for act, layers in actions:
            strip = composite_lpc_strip(layers, act, direction_row=2)
            if strip:
                cols = strip.width // 64
                p = humanoids_dir / f"{mob_id}_{act}_strip{cols}.png"
                save_strip_and_normal(strip, p)
                anims[act] = {'strip_file': p, 'cols': cols, 'frame_w': 64, 'frame_h': 64, 'fps': 8, 'loop': (act == 'walk')}
        if anims:
            create_spriteframes_for_strips(humanoids_dir / f"{mob_id}_frames.tres", anims)
            print(f"  [x] Harvested Humanoid: {mob_id} ({list(anims.keys())})")

# ==============================================================================
# 4. HARVEST MAPLESTORY ICONS (Weapons & Skills from PixelSRPG)
# ==============================================================================
def harvest_icons():
    print("\n--- Harvesting Genuine RPG Icons from PixelSRPG-Forge ---")
    w_out = ICONS_ROOT / "weapons_handcrafted"
    s_out = ICONS_ROOT / "skills_handcrafted"
    w_out.mkdir(parents=True, exist_ok=True)
    s_out.mkdir(parents=True, exist_ok=True)

    # Harvest 40 high quality weapons
    if PIXELSRPG_WEAPONS.exists():
        w_files = sorted(list(PIXELSRPG_WEAPONS.glob("*.png")))[:40]
        for idx, wf in enumerate(w_files, 1):
            dest = w_out / f"rpg_weapon_{idx:02d}.png"
            shutil.copy2(wf, dest)
            create_import_file(dest)
        print(f"  [x] Copied and imported {len(w_files)} authentic weapons into icons/weapons_handcrafted/")

    # Harvest 40 high quality skill icons
    if PIXELSRPG_SKILLS.exists():
        s_files = sorted(list(PIXELSRPG_SKILLS.glob("*.png")))[:40]
        for idx, sf in enumerate(s_files, 1):
            dest = s_out / f"rpg_skill_{idx:02d}.png"
            shutil.copy2(sf, dest)
            create_import_file(dest)
        print(f"  [x] Copied and imported {len(s_files)} authentic skill icons into icons/skills_handcrafted/")

if __name__ == "__main__":
    print("================================================================================")
    print("MASTER ASSET FORGE HARVESTER: BUILDING COMPREHENSIVE READY-MADE ASSET ROSTER")
    print("================================================================================")
    harvest_beasts()
    harvest_golems_and_imps()
    harvest_humanoids_and_undead()
    harvest_icons()
    print("\n================================================================================")
    print("HARVESTING COMPLETE! ALL READY ASSETS SLICED, NORMAL-MAPPED & IMPORTED.")
    print("================================================================================")
