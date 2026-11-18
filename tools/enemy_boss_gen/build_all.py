"""
Master Build Pipeline for Enemy & Boss Sprites, Normal Maps, SpriteFrames, and .import Files.
"""

import os
import sys
import subprocess
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple
from PIL import Image

from .draw_utils import create_strip
from .common_enemies import (
    generate_shadow_imp_frame,
    generate_cultist_mage_frame,
    generate_crystal_spider_frame,
    generate_ash_crawler_frame,
    generate_swamp_slime_frame,
    generate_lava_hound_frame
)
from .biome_bosses import (
    generate_kok_devi_frame,
    generate_prizma_golemi_frame,
    generate_kul_kirpisi_frame,
    generate_camur_ana_frame,
    generate_cevher_krali_frame
)
from .elite_auras import generate_elite_aura_frame

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = WORKSPACE_ROOT / "projects" / "nos"
ENEMIES_DIR = PROJECT_DIR / "assets" / "enemies"
NORMALS_DIR = ENEMIES_DIR / "normals"
NORMAL_MAP_TOOL = WORKSPACE_ROOT / "tools" / "normal_map_gen.py"

def make_uid(text: str) -> str:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
    return f"uid://nos_{h}"

def generate_import_file(texture_path: Path):
    """Generates Godot 4 CompressedTexture2D .import file with Lossless & Nearest filter."""
    rel_path = texture_path.relative_to(PROJECT_DIR).as_posix()
    tex_name = texture_path.name
    tex_hash = hashlib.sha1(tex_name.encode("utf-8")).hexdigest()[:8]
    import_path = texture_path.with_name(texture_path.name + ".import")

    config = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="uid://tex_{tex_hash}"
path="res://.godot/imported/{tex_name}-{tex_hash}.ctex"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://{rel_path}"
dest_files=["res://.godot/imported/{tex_name}-{tex_hash}.ctex"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossless_compression_factor=0.7
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
"""
    import_path.write_text(config, encoding="utf-8")

def generate_sprite_frames_tres(
    entity_name: str,
    anim_configs: List[Dict[str, Any]], # [{"name": "idle", "strip_file": "...", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 8.0}]
    output_path: Path
):
    """Generates a Godot 4 SpriteFrames resource (.tres) file."""
    lines = []
    ext_resources = []
    sub_resources = []
    animations = []

    step_counter = 1
    for anim_idx, anim in enumerate(anim_configs):
        ext_id = f"{anim_idx + 1}_{anim['name']}"
        strip_name = anim["strip_file"]
        strip_path = f"res://assets/enemies/{strip_name}"
        ext_uid = make_uid(strip_path)
        ext_resources.append(f'[ext_resource type="Texture2D" uid="{ext_uid}" path="{strip_path}" id="{ext_id}"]')
        step_counter += 1

        frame_w = anim["frame_w"]
        frame_h = anim["frame_h"]
        frame_count = anim["frames"]

        anim_frame_entries = []
        for f in range(frame_count):
            sub_id = f"AtlasTexture_{anim['name']}_{f}"
            rx = f * frame_w
            sub_resources.append(
                f'[sub_resource type="AtlasTexture" id="{sub_id}"]\n'
                f'atlas = ExtResource("{ext_id}")\n'
                f'region = Rect2({rx}, 0, {frame_w}, {frame_h})\n'
            )
            step_counter += 1
            anim_frame_entries.append(
                f'{{\n"duration": 1.0,\n"texture": SubResource("{sub_id}")\n}}'
            )

        loop_str = "true" if anim.get("loop", True) else "false"
        speed_val = anim.get("fps", 8.0)
        frames_joined = ",\n".join(anim_frame_entries)

        animations.append(
            f'{{\n"frames": [\n{frames_joined}\n],\n"loop": {loop_str},\n"name": &"{anim["name"]}",\n"speed": {speed_val}\n}}'
        )

    tres_uid = make_uid(str(output_path))
    header = f'[gd_resource type="SpriteFrames" load_steps={step_counter} format=3 uid="{tres_uid}"]\n'
    
    anims_joined = ",\n".join(animations)
    resource_section = f'[resource]\nanimations = [\n{anims_joined}\n]\n'

    content = header + "\n" + "\n".join(ext_resources) + "\n\n" + "\n".join(sub_resources) + "\n" + resource_section
    output_path.write_text(content, encoding="utf-8")
    print(f"[SpriteFrames] Generated: {output_path.name}")

def main():
    print("=" * 70)
    print("  AESTRA: THE LAST WISH - ENEMY & BOSS SPRITE FACTORY")
    print("=" * 70)

    ENEMIES_DIR.mkdir(parents=True, exist_ok=True)
    NORMALS_DIR.mkdir(parents=True, exist_ok=True)

    # Dictionary of generated strips to run normal maps on:
    # key: filename, value: preset
    strips_to_generate: Dict[str, Tuple[Image.Image, str]] = {}

    # --------------------------------------------------------------------------
    # 1. SHADOW IMP
    # --------------------------------------------------------------------------
    print("\n[Generating] Shadow Imp...")
    imp_idle = create_strip([generate_shadow_imp_frame("idle", i) for i in range(4)])
    imp_walk = create_strip([generate_shadow_imp_frame("walk", i) for i in range(6)])
    imp_atk = create_strip([generate_shadow_imp_frame("attack", i) for i in range(4)])
    imp_dth = create_strip([generate_shadow_imp_frame("death", i) for i in range(4)])

    strips_to_generate["shadow_imp_idle_strip4.png"] = (imp_idle, "character")
    strips_to_generate["shadow_imp_walk_strip6.png"] = (imp_walk, "character")
    strips_to_generate["shadow_imp_attack_strip4.png"] = (imp_atk, "character")
    strips_to_generate["shadow_imp_death_strip4.png"] = (imp_dth, "character")

    # --------------------------------------------------------------------------
    # 2. CULTIST MAGES
    # --------------------------------------------------------------------------
    print("[Generating] Cultist Mages (Blue, Purple, Green)...")
    mage_blue = create_strip([generate_cultist_mage_frame("blue", i) for i in range(4)])
    mage_purple = create_strip([generate_cultist_mage_frame("purple", i) for i in range(4)])
    mage_green = create_strip([generate_cultist_mage_frame("green", i) for i in range(4)])

    strips_to_generate["cultist_mage_blue_strip4.png"] = (mage_blue, "character")
    strips_to_generate["cultist_mage_purple_strip4.png"] = (mage_purple, "character")
    strips_to_generate["cultist_mage_green_strip4.png"] = (mage_green, "character")

    # --------------------------------------------------------------------------
    # 3. CRYSTAL SPIDER
    # --------------------------------------------------------------------------
    print("[Generating] Crystal Spider...")
    spider_walk = create_strip([generate_crystal_spider_frame("walk", i) for i in range(6)])
    spider_atk = create_strip([generate_crystal_spider_frame("attack", i) for i in range(4)])

    strips_to_generate["crystal_spider_walk_strip6.png"] = (spider_walk, "character")
    strips_to_generate["crystal_spider_attack_strip4.png"] = (spider_atk, "character")

    # --------------------------------------------------------------------------
    # 4. ASH CRAWLER
    # --------------------------------------------------------------------------
    print("[Generating] Ash Crawler...")
    crawler_walk = create_strip([generate_ash_crawler_frame("walk", i) for i in range(6)])
    crawler_atk = create_strip([generate_ash_crawler_frame("attack", i) for i in range(4)])

    strips_to_generate["ash_crawler_walk_strip6.png"] = (crawler_walk, "character")
    strips_to_generate["ash_crawler_attack_strip4.png"] = (crawler_atk, "character")

    # --------------------------------------------------------------------------
    # 5. SWAMP SLIME
    # --------------------------------------------------------------------------
    print("[Generating] Swamp Slime...")
    slime_hop = create_strip([generate_swamp_slime_frame("hop", i) for i in range(6)])
    slime_splash = create_strip([generate_swamp_slime_frame("splash", i) for i in range(4)])

    strips_to_generate["swamp_slime_hop_strip6.png"] = (slime_hop, "character")
    strips_to_generate["swamp_slime_splash_strip4.png"] = (slime_splash, "character")

    # --------------------------------------------------------------------------
    # 6. LAVA HOUND
    # --------------------------------------------------------------------------
    print("[Generating] Lava Hound...")
    hound_run = create_strip([generate_lava_hound_frame("run", i) for i in range(6)])
    hound_bite = create_strip([generate_lava_hound_frame("bite", i) for i in range(4)])

    strips_to_generate["lava_hound_run_strip6.png"] = (hound_run, "character")
    strips_to_generate["lava_hound_bite_strip4.png"] = (hound_bite, "character")

    # --------------------------------------------------------------------------
    # 7. BOSS: ROOT GIANT (kok_devi)
    # --------------------------------------------------------------------------
    print("[Generating] Boss 1: Root Giant...")
    kok_idle = create_strip([generate_kok_devi_frame("idle", i) for i in range(4)])
    kok_slam = create_strip([generate_kok_devi_frame("slam", i) for i in range(6)])
    kok_stomp = create_strip([generate_kok_devi_frame("stomp", i) for i in range(6)])

    strips_to_generate["boss_kok_devi_idle_strip4.png"] = (kok_idle, "character")
    strips_to_generate["boss_kok_devi_slam_strip6.png"] = (kok_slam, "character")
    strips_to_generate["boss_kok_devi_stomp_strip6.png"] = (kok_stomp, "character")

    # --------------------------------------------------------------------------
    # 8. BOSS: PRISM GOLEM (prizma_golemi)
    # --------------------------------------------------------------------------
    print("[Generating] Boss 2: Prism Golem...")
    prizma_idle = create_strip([generate_prizma_golemi_frame("idle", i) for i in range(4)])
    prizma_beam = create_strip([generate_prizma_golemi_frame("beam", i) for i in range(6)])
    prizma_crush = create_strip([generate_prizma_golemi_frame("crush", i) for i in range(6)])

    strips_to_generate["boss_prizma_golemi_idle_strip4.png"] = (prizma_idle, "character")
    strips_to_generate["boss_prizma_golemi_beam_strip6.png"] = (prizma_beam, "character")
    strips_to_generate["boss_prizma_golemi_crush_strip6.png"] = (prizma_crush, "character")

    # --------------------------------------------------------------------------
    # 9. BOSS: SPIKY ASH BEAST (kul_kirpisi)
    # --------------------------------------------------------------------------
    print("[Generating] Boss 3: Spiky Ash Beast...")
    kul_idle = create_strip([generate_kul_kirpisi_frame("idle", i) for i in range(4)])
    kul_charge = create_strip([generate_kul_kirpisi_frame("charge", i) for i in range(6)])
    kul_spikes = create_strip([generate_kul_kirpisi_frame("spikes", i) for i in range(6)])

    strips_to_generate["boss_kul_kirpisi_idle_strip4.png"] = (kul_idle, "character")
    strips_to_generate["boss_kul_kirpisi_charge_strip6.png"] = (kul_charge, "character")
    strips_to_generate["boss_kul_kirpisi_spikes_strip6.png"] = (kul_spikes, "character")

    # --------------------------------------------------------------------------
    # 10. BOSS: MUD MOTHER (camur_ana)
    # --------------------------------------------------------------------------
    print("[Generating] Boss 4: Mud Mother...")
    camur_idle = create_strip([generate_camur_ana_frame("idle", i) for i in range(4)])
    camur_slam = create_strip([generate_camur_ana_frame("slam", i) for i in range(6)])
    camur_spit = create_strip([generate_camur_ana_frame("spit", i) for i in range(6)])

    strips_to_generate["boss_camur_ana_idle_strip4.png"] = (camur_idle, "character")
    strips_to_generate["boss_camur_ana_slam_strip6.png"] = (camur_slam, "character")
    strips_to_generate["boss_camur_ana_spit_strip6.png"] = (camur_spit, "character")

    # --------------------------------------------------------------------------
    # 11. BOSS: ORE KING (cevher_krali)
    # --------------------------------------------------------------------------
    print("[Generating] Boss 5: Ore King...")
    cevher_idle = create_strip([generate_cevher_krali_frame("idle", i) for i in range(4)])
    cevher_smash = create_strip([generate_cevher_krali_frame("smash", i) for i in range(6)])
    cevher_erup = create_strip([generate_cevher_krali_frame("eruption", i) for i in range(6)])

    strips_to_generate["boss_cevher_krali_idle_strip4.png"] = (cevher_idle, "character")
    strips_to_generate["boss_cevher_krali_smash_strip6.png"] = (cevher_smash, "character")
    strips_to_generate["boss_cevher_krali_eruption_strip6.png"] = (cevher_erup, "character")

    # --------------------------------------------------------------------------
    # 12. ALFA ELITE OVERLAYS
    # --------------------------------------------------------------------------
    print("[Generating] Alfa Elite Auras (Gold & Violet)...")
    aura_gold = create_strip([generate_elite_aura_frame("gold", i) for i in range(4)])
    aura_violet = create_strip([generate_elite_aura_frame("violet", i) for i in range(4)])

    strips_to_generate["elite_aura_gold_strip4.png"] = (aura_gold, "object")
    strips_to_generate["elite_aura_violet_strip4.png"] = (aura_violet, "object")

    # Save all diffuse strips and generate .import files
    print("\n" + "=" * 50)
    print("Saving 32 Animation Strips & Generating Normal Maps...")
    print("=" * 50)

    for filename, (img_strip, preset) in strips_to_generate.items():
        out_png = ENEMIES_DIR / filename
        img_strip.save(out_png, "PNG")
        generate_import_file(out_png)
        print(f"  -> Saved Strip: {filename} ({img_strip.width}x{img_strip.height})")

        # Generate Normal Map via normal_map_gen.py
        norm_filename = filename.replace(".png", "_n.png")
        out_norm_png = NORMALS_DIR / norm_filename
        
        cmd = [
            sys.executable,
            str(NORMAL_MAP_TOOL),
            str(out_png),
            "-o", str(out_norm_png),
            "--preset", preset,
            "-s", "1.5"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            generate_import_file(out_norm_png)
            print(f"     [OK Normal Map] {norm_filename}")
        else:
            print(f"     [Error Normal Map] {res.stderr.strip()}", file=sys.stderr)

    # --------------------------------------------------------------------------
    # 13. GENERATE GODOT 4 SPRITEFRAMES (.tres)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 50)
    print("Generating Godot 4 SpriteFrames (.tres)...")
    print("=" * 50)

    # 1. Shadow Imp
    generate_sprite_frames_tres(
        "shadow_imp",
        [
            {"name": "idle", "strip_file": "shadow_imp_idle_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 6.0},
            {"name": "walk", "strip_file": "shadow_imp_walk_strip6.png", "frames": 6, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 8.0},
            {"name": "attack", "strip_file": "shadow_imp_attack_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": False, "fps": 10.0},
            {"name": "death", "strip_file": "shadow_imp_death_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": False, "fps": 6.0}
        ],
        ENEMIES_DIR / "shadow_imp_frames.tres"
    )

    # 2. Cultist Mages
    for col in ["blue", "purple", "green"]:
        generate_sprite_frames_tres(
            f"cultist_mage_{col}",
            [
                {"name": "cast", "strip_file": f"cultist_mage_{col}_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 6.0}
            ],
            ENEMIES_DIR / f"cultist_mage_{col}_frames.tres"
        )

    # 3. Crystal Spider
    generate_sprite_frames_tres(
        "crystal_spider",
        [
            {"name": "walk", "strip_file": "crystal_spider_walk_strip6.png", "frames": 6, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 8.0},
            {"name": "attack", "strip_file": "crystal_spider_attack_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": False, "fps": 10.0}
        ],
        ENEMIES_DIR / "crystal_spider_frames.tres"
    )

    # 4. Ash Crawler
    generate_sprite_frames_tres(
        "ash_crawler",
        [
            {"name": "walk", "strip_file": "ash_crawler_walk_strip6.png", "frames": 6, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 8.0},
            {"name": "attack", "strip_file": "ash_crawler_attack_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": False, "fps": 10.0}
        ],
        ENEMIES_DIR / "ash_crawler_frames.tres"
    )

    # 5. Swamp Slime
    generate_sprite_frames_tres(
        "swamp_slime",
        [
            {"name": "hop", "strip_file": "swamp_slime_hop_strip6.png", "frames": 6, "frame_w": 32, "frame_h": 32, "loop": True, "fps": 8.0},
            {"name": "splash", "strip_file": "swamp_slime_splash_strip4.png", "frames": 4, "frame_w": 32, "frame_h": 32, "loop": False, "fps": 8.0}
        ],
        ENEMIES_DIR / "swamp_slime_frames.tres"
    )

    # 6. Lava Hound
    generate_sprite_frames_tres(
        "lava_hound",
        [
            {"name": "run", "strip_file": "lava_hound_run_strip6.png", "frames": 6, "frame_w": 40, "frame_h": 32, "loop": True, "fps": 10.0},
            {"name": "bite", "strip_file": "lava_hound_bite_strip4.png", "frames": 4, "frame_w": 40, "frame_h": 32, "loop": False, "fps": 10.0}
        ],
        ENEMIES_DIR / "lava_hound_frames.tres"
    )

    # 7. Boss: Kök Devi
    generate_sprite_frames_tres(
        "boss_kok_devi",
        [
            {"name": "idle", "strip_file": "boss_kok_devi_idle_strip4.png", "frames": 4, "frame_w": 64, "frame_h": 64, "loop": True, "fps": 6.0},
            {"name": "slam", "strip_file": "boss_kok_devi_slam_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0},
            {"name": "stomp", "strip_file": "boss_kok_devi_stomp_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0}
        ],
        ENEMIES_DIR / "boss_kok_devi_frames.tres"
    )

    # 8. Boss: Prizma Golemi
    generate_sprite_frames_tres(
        "boss_prizma_golemi",
        [
            {"name": "idle", "strip_file": "boss_prizma_golemi_idle_strip4.png", "frames": 4, "frame_w": 64, "frame_h": 64, "loop": True, "fps": 6.0},
            {"name": "beam", "strip_file": "boss_prizma_golemi_beam_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0},
            {"name": "crush", "strip_file": "boss_prizma_golemi_crush_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0}
        ],
        ENEMIES_DIR / "boss_prizma_golemi_frames.tres"
    )

    # 9. Boss: Kül Kirpisi
    generate_sprite_frames_tres(
        "boss_kul_kirpisi",
        [
            {"name": "idle", "strip_file": "boss_kul_kirpisi_idle_strip4.png", "frames": 4, "frame_w": 64, "frame_h": 64, "loop": True, "fps": 6.0},
            {"name": "charge", "strip_file": "boss_kul_kirpisi_charge_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 10.0},
            {"name": "spikes", "strip_file": "boss_kul_kirpisi_spikes_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0}
        ],
        ENEMIES_DIR / "boss_kul_kirpisi_frames.tres"
    )

    # 10. Boss: Çamur Ana
    generate_sprite_frames_tres(
        "boss_camur_ana",
        [
            {"name": "idle", "strip_file": "boss_camur_ana_idle_strip4.png", "frames": 4, "frame_w": 64, "frame_h": 64, "loop": True, "fps": 6.0},
            {"name": "slam", "strip_file": "boss_camur_ana_slam_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0},
            {"name": "spit", "strip_file": "boss_camur_ana_spit_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0}
        ],
        ENEMIES_DIR / "boss_camur_ana_frames.tres"
    )

    # 11. Boss: Ore King (cevher_krali)
    generate_sprite_frames_tres(
        "boss_cevher_krali",
        [
            {"name": "idle", "strip_file": "boss_cevher_krali_idle_strip4.png", "frames": 4, "frame_w": 64, "frame_h": 64, "loop": True, "fps": 6.0},
            {"name": "smash", "strip_file": "boss_cevher_krali_smash_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0},
            {"name": "eruption", "strip_file": "boss_cevher_krali_eruption_strip6.png", "frames": 6, "frame_w": 64, "frame_h": 64, "loop": False, "fps": 8.0}
        ],
        ENEMIES_DIR / "boss_cevher_krali_frames.tres"
    )

    # 12. Alfa Elite Overlays
    generate_sprite_frames_tres(
        "elite_aura_gold",
        [
            {"name": "aura", "strip_file": "elite_aura_gold_strip4.png", "frames": 4, "frame_w": 48, "frame_h": 48, "loop": True, "fps": 8.0}
        ],
        ENEMIES_DIR / "elite_aura_gold_frames.tres"
    )

    generate_sprite_frames_tres(
        "elite_aura_violet",
        [
            {"name": "aura", "strip_file": "elite_aura_violet_strip4.png", "frames": 4, "frame_w": 48, "frame_h": 48, "loop": True, "fps": 8.0}
        ],
        ENEMIES_DIR / "elite_aura_violet_frames.tres"
    )

    print("\n[Complete] All 32 strips, 32 normal maps, 15 SpriteFrames, and .import files successfully created!")

if __name__ == "__main__":
    main()
