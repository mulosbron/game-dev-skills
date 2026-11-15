#!/usr/bin/env python3
"""
Godot Pixel Texture Pipeline Tool (godot_pixel_tool.py)
Automates pixel-perfect configuration, texture import presets, batch quantization,
audit verification, and shader/script generation for Godot 4.x projects.

Covers 2D, 3D Low-Poly, 2.5D FPS (Doom-style), and 2.5D Top-Down (HD-2D / Y-Sort).
Reference: docs/godot-pixel-texture-rehberi.md
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

# Common retro pixel palettes
PALETTES = {
    "pico8": [
        "#000000", "#1D2B53", "#7E2553", "#008751", "#AB5236", "#5F574F", "#C2C3C7", "#FFF1E8",
        "#FF004D", "#FFA300", "#FFEC27", "#00E436", "#29ADFF", "#83769C", "#FF77A8", "#FFCCAA"
    ],
    "db16": [
        "#140c1c", "#442434", "#30346d", "#4e4a4e", "#854c30", "#346524", "#d04648", "#757161",
        "#597dce", "#d27d2c", "#8595a1", "#6daa2c", "#d2aa99", "#6dc2ca", "#dad45e", "#deeed6"
    ],
    "sweetie16": [
        "#1a1c2c", "#5d275d", "#b13e53", "#ef7d57", "#ffcd75", "#a7f070", "#38b764", "#257179",
        "#29366f", "#3b5dc9", "#41a6f6", "#73eff7", "#f4f4f4", "#94b0c2", "#566c86", "#333c57"
    ],
    "gameboy": [
        "#0f380f", "#306230", "#8bac0f", "#9bbc0f"
    ]
}

PSX_RETRO_SHADER = """// psx_retro.gdshader - PS1 Era Spatial Shader
// Features: Vertex snapping, Affine texture mapping, Color posterization.
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, shadows_disabled;

uniform sampler2D base_tex : source_color, filter_nearest, repeat_enable;
uniform float vertex_snap_res : hint_range(120.0, 1080.0) = 240.0; // Virtual vertical resolution
uniform bool affine_mapping = true;
uniform float color_levels : hint_range(2.0, 256.0) = 32.0;

varying vec2 uv_affine;
varying float clip_w;

void vertex() {
    vec4 clip = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
    if (clip.w > 0.0001) {
        // Vertex snapping in NDC space
        vec3 ndc = clip.xyz / clip.w;
        float half_res = vertex_snap_res * 0.5;
        ndc.xy = floor(ndc.xy * half_res + 0.5) / half_res;
        clip.xyz = ndc * clip.w;
    }
    POSITION = clip;
    uv_affine = UV * clip.w;
    clip_w = max(clip.w, 0.0001);
}

void fragment() {
    vec2 uv = affine_mapping ? uv_affine / clip_w : UV;
    vec3 col = texture(base_tex, uv).rgb * COLOR.rgb;
    col = floor(col * color_levels + 0.5) / color_levels; // Posterize
    ALBEDO = col;
}
"""

POSTERIZE_DITHER_SHADER = """// posterize_dither.gdshader - CanvasItem 4x4 Bayer Dither & Posterize
shader_type canvas_item;

uniform float levels : hint_range(2.0, 64.0) = 8.0;          // Quantization steps per channel
uniform float dither_strength : hint_range(0.0, 1.0) = 1.0;  // 0 = flat posterize, 1 = full Bayer dither

// 4x4 Bayer matrix
const mat4 BAYER = mat4(
    vec4(0.000, 0.500, 0.125, 0.625),
    vec4(0.750, 0.250, 0.875, 0.375),
    vec4(0.188, 0.688, 0.062, 0.562),
    vec4(0.812, 0.312, 0.938, 0.438)
);

void fragment() {
    vec4 c = COLOR;
    ivec2 px = ivec2(FRAGCOORD.xy) % 4;
    float d = (BAYER[px.x][px.y] - 0.5) * dither_strength;
    c.rgb = floor((c.rgb + d / levels) * levels + 0.5) / levels;
    COLOR = c;
}
"""

PIXEL_CAMERA_2D_GD = """# pixel_camera_2d.gd - Pixel-perfect Camera2D with integer scaling and floor snapping
class_name PixelCamera2D
extends Camera2D

@export var pixel_scale: int = 4  # PPU zoom multiplier

func _ready() -> void:
	zoom = Vector2(pixel_scale, pixel_scale)

func _physics_process(_delta: float) -> void:
	# Lock camera coordinates to integer pixel boundaries to eliminate subpixel jitter
	global_position = global_position.floor()
"""

WEAPON_SPRITE_GD = """# weapon_sprite.gd - Retro 2.5D FPS HUD Weapon Viewmodel Anchor
extends Sprite2D

@export var scale_factor: int = 4

func _ready() -> void:
	scale = Vector2(scale_factor, scale_factor)

func _process(_delta: float) -> void:
	if texture:
		var vp := get_viewport_rect().size
		var half := texture.get_size() * float(scale_factor) / 2.0
		position = Vector2(vp.x / 2.0 - half.x, vp.y - texture.get_size().y * float(scale_factor))
"""

SET_NEAREST_MATERIALS_GD = """# set_nearest_materials.gd - EditorScript to batch set all materials to Nearest filter
@tool
extends EditorScript

const ROOT := "res://"

func _run() -> void:
	_scan(ROOT)
	print("Godot Pixel Tool: All BaseMaterial3D resources updated to Nearest filter.")

func _scan(path: String) -> void:
	var dir := DirAccess.open(path)
	if dir == null:
		return
	dir.list_dir_begin()
	var fname := dir.get_next()
	while fname != "":
		var full := path.path_join(fname)
		if dir.current_is_dir() and not fname.begins_with(".") and fname != ".godot":
			_scan(full)
		elif fname.ends_with(".tres") or fname.ends_with(".material"):
			var res := load(full)
			if res is BaseMaterial3D:
				res.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
				ResourceSaver.save(res, full)
				print("[ok] Nearest filter applied: ", full)
		fname = dir.get_next()
"""

AUTO_NEAREST_RUNTIME_GD = """# auto_nearest.gd - Runtime node that forces Nearest filter across all MeshInstance3D nodes
extends Node

func _ready() -> void:
	_apply(get_tree().current_scene)

func _apply(node: Node) -> void:
	if node is MeshInstance3D:
		var mi := node as MeshInstance3D
		for i in mi.get_surface_override_material_count():
			var m := mi.get_surface_override_material(i)
			if m is BaseMaterial3D:
				m.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
		if mi.mesh:
			for i in mi.mesh.get_surface_count():
				var m2 := mi.mesh.surface_get_material(i)
				if m2 is BaseMaterial3D:
					m2.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
	for c in node.get_children():
		_apply(c)
"""

def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def update_godot_config(project_file: Path, mode: str = "fps") -> List[str]:
    """Updates or injects pixel-perfect settings into project.godot."""
    if not project_file.exists():
        raise FileNotFoundError(f"project.godot not found at {project_file}")

    content = project_file.read_text(encoding="utf-8")
    changes = []

    # Target settings dictionary
    settings = {
        "display": {
            "window/stretch/aspect": '"keep"',
            "window/stretch/scale_mode": '"integer"'
        },
        "rendering": {
            "textures/canvas_textures/default_texture_filter": "0",  # Nearest
            "2d/snap/snap_2d_transforms_to_pixel": "true",
            "anti_aliasing/quality/msaa_3d": "0",
            "anti_aliasing/quality/screen_space_aa": "0",
            "textures/canvas_textures/default_texture_repeat": "1"  # Disabled
        }
    }

    if mode in ("2d", "topdown"):
        settings["display"]["window/stretch/mode"] = '"canvas_items"'
    else:  # fps, 3d
        settings["display"]["window/stretch/mode"] = '"viewport"'

    lines = content.splitlines()
    sections: Dict[str, List[str]] = {}
    current_sec = "header"
    sections[current_sec] = []

    for line in lines:
        match = re.match(r"^\[(.*)\]$", line.strip())
        if match:
            current_sec = match.group(1).strip()
            sections.setdefault(current_sec, [])
        else:
            sections[current_sec].append(line)

    for sec_name, sec_dict in settings.items():
        if sec_name not in sections:
            sections[sec_name] = []
        for key, val in sec_dict.items():
            pattern = re.compile(rf"^{re.escape(key)}\s*=")
            found = False
            for idx, line in enumerate(sections[sec_name]):
                if pattern.match(line.strip()):
                    found = True
                    if line.strip() != f"{key}={val}":
                        sections[sec_name][idx] = f"{key}={val}"
                        changes.append(f"[{sec_name}] {key} = {val} (updated)")
                    break
            if not found:
                sections[sec_name].append(f"{key}={val}")
                changes.append(f"[{sec_name}] {key} = {val} (added)")

    # Reconstruct project.godot
    out_lines = []
    if "header" in sections:
        out_lines.extend(sections["header"])
        del sections["header"]

    for sec_name, s_lines in sections.items():
        out_lines.append(f"\n[{sec_name}]")
        for line in s_lines:
            out_lines.append(line)

    new_content = "\n".join(out_lines).strip() + "\n"
    project_file.write_text(new_content, encoding="utf-8")
    return changes


def generate_import_file(texture_path: Path) -> Path:
    """Generates a pixel-perfect .import file for Godot 4 CompressedTexture2D."""
    import_path = texture_path.with_name(texture_path.name + ".import")
    
    config = f"""[remap]

importer="texture"
type="CompressedTexture2D"
uid="uid://{texture_path.stem}_{hash(texture_path.name) & 0xFFFFFFF:x}"
path="res://.godot/imported/{texture_path.name}-{hash(texture_path.name) & 0xFFFFFFF:x}.ctex"
metadata={{
"vram_texture": false
}}

[deps]

source_file="res://{texture_path.as_posix()}"
dest_files=["res://.godot/imported/{texture_path.name}-{hash(texture_path.name) & 0xFFFFFFF:x}.ctex"]

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
    return import_path


def process_image(img: Image.Image, size=None, scale=None, colors=None,
                  palette=None, alpha_threshold: int = 128) -> Image.Image:
    img = img.convert("RGBA")

    # 1. Nearest Neighbor resize
    if scale and scale != 1:
        size = (int(img.width * scale), int(img.height * scale))
    if size and size != img.size:
        img = img.resize(size, Image.NEAREST)

    # 2. Hard alpha cut (threshold at 128)
    alpha = img.getchannel("A").point(lambda a: 255 if a >= alpha_threshold else 0)

    # 3. Palette quantization
    if palette:
        if isinstance(palette, str) and palette in PALETTES:
            # Build palette image
            pal_colors = [hex_to_rgb(h) for h in PALETTES[palette]]
            pal_img = Image.new("P", (1, 1))
            flat_pal = [c for rgb in pal_colors for c in rgb] + [0] * (768 - len(pal_colors) * 3)
            pal_img.putpalette(flat_pal)
            rgb = img.convert("RGB").quantize(palette=pal_img, dither=Image.Dither.NONE)
        elif isinstance(palette, (str, Path)) and Path(palette).exists():
            pal_img = Image.open(palette).convert("P")
            rgb = img.convert("RGB").quantize(palette=pal_img, dither=Image.Dither.NONE)
        else:
            rgb = img.convert("RGB")
        img = rgb.convert("RGBA")
        img.putalpha(alpha)
    elif colors:
        rgb = img.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        img = rgb.convert("RGBA")
        img.putalpha(alpha)
    else:
        img.putalpha(alpha)

    return img


def cmd_apply_settings(args: argparse.Namespace) -> None:
    p_file = Path(args.project).resolve()
    if p_file.is_dir():
        p_file = p_file / "project.godot"
    changes = update_godot_config(p_file, mode=args.mode)
    print(f"\n[Godot Pixel Tool] Applied pixel-perfect settings to {p_file}:")
    if changes:
        for c in changes:
            print(f"  * {c}")
    else:
        print("  * All pixel-perfect settings are already active and up-to-date!")
    print()


def cmd_batch_import(args: argparse.Namespace) -> None:
    folder = Path(args.folder).resolve()
    if not folder.exists():
        print(f"Error: Folder {folder} does not exist.", file=sys.stderr)
        sys.exit(1)

    count = 0
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith((".png", ".webp")):
                t_path = Path(root) / f
                generate_import_file(t_path)
                count += 1
    print(f"\n[Godot Pixel Tool] Generated/patched {count} .import files with Lossless + Mipmaps=Off + Detect3D=Off.")
    print()


def cmd_batch_process(args: argparse.Namespace) -> None:
    src = Path(args.src).resolve()
    dst = Path(args.dst).resolve()
    if not src.exists():
        print(f"Error: Source directory {src} does not exist.", file=sys.stderr)
        sys.exit(1)

    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(src.rglob("*")):
        if path.suffix.lower() in {".png", ".bmp", ".jpg", ".jpeg", ".webp"}:
            rel = path.relative_to(src)
            out_file = (dst / rel).with_suffix(".png")
            out_file.parent.mkdir(parents=True, exist_ok=True)

            img = Image.open(path)
            processed = process_image(
                img,
                size=tuple(args.size) if args.size else None,
                scale=args.scale,
                colors=args.colors,
                palette=args.palette,
                alpha_threshold=args.alpha
            )
            processed.save(out_file, format="PNG")
            if args.create_imports:
                generate_import_file(out_file)
            count += 1

    print(f"\n[Godot Pixel Tool] Batch processed {count} pixel textures from {src} -> {dst}.")
    print()


def cmd_export_shaders(args: argparse.Namespace) -> None:
    target_dir = Path(args.target).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    psx_file = target_dir / "psx_retro.gdshader"
    psx_file.write_text(PSX_RETRO_SHADER, encoding="utf-8")
    print(f"  * Emitted PSX Spatial Shader: {psx_file}")

    dither_file = target_dir / "posterize_dither.gdshader"
    dither_file.write_text(POSTERIZE_DITHER_SHADER, encoding="utf-8")
    print(f"  * Emitted 2D Posterize/Dither Shader: {dither_file}")
    print()


def cmd_export_scripts(args: argparse.Namespace) -> None:
    target_dir = Path(args.target).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    cam_file = target_dir / "pixel_camera_2d.gd"
    cam_file.write_text(PIXEL_CAMERA_2D_GD, encoding="utf-8")
    print(f"  * Emitted Pixel Camera 2D: {cam_file}")

    wep_file = target_dir / "weapon_sprite.gd"
    wep_file.write_text(WEAPON_SPRITE_GD, encoding="utf-8")
    print(f"  * Emitted Weapon Sprite Anchor: {wep_file}")

    near_file = target_dir / "set_nearest_materials.gd"
    near_file.write_text(SET_NEAREST_MATERIALS_GD, encoding="utf-8")
    print(f"  * Emitted Set Nearest Materials EditorScript: {near_file}")

    auto_file = target_dir / "auto_nearest.gd"
    auto_file.write_text(AUTO_NEAREST_RUNTIME_GD, encoding="utf-8")
    print(f"  * Emitted Auto Nearest Runtime Node: {auto_file}")
    print()


def cmd_check_integrity(args: argparse.Namespace) -> None:
    root = Path(args.project).resolve()
    if root.is_file() and root.name == "project.godot":
        root = root.parent

    print(f"\n================================================================================")
    print(f"GODOT 4.x PIXEL TEXTURE INTEGRITY AUDIT: {root.name}")
    print(f"================================================================================\n")

    p_file = root / "project.godot"
    checks_passed = 0
    checks_warn = 0
    checks_failed = 0

    if not p_file.exists():
        print(f"[FAIL] project.godot not found at {root}")
        sys.exit(1)

    p_text = p_file.read_text(encoding="utf-8")

    def test_setting(label: str, pattern: str, expected: str):
        nonlocal checks_passed, checks_warn, checks_failed
        match = re.search(pattern, p_text, re.MULTILINE)
        if match:
            val = match.group(1).strip()
            if val == expected:
                print(f"  [PASS] {label}: {val}")
                checks_passed += 1
            else:
                print(f"  [FAIL] {label}: Found {val}, Expected {expected}")
                checks_failed += 1
        else:
            print(f"  [WARN] {label}: Setting not specified (using Godot default)")
            checks_warn += 1

    print("1. Project Settings Audit (§1.4):")
    test_setting("Default Texture Filter (Nearest)", r"default_texture_filter\s*=\s*(.*)", "0")
    test_setting("Stretch Aspect (Keep)", r"stretch/aspect\s*=\s*(.*)", '"keep"')
    test_setting("Stretch Scale Mode (Integer)", r"stretch/scale_mode\s*=\s*(.*)", '"integer"')
    test_setting("Snap 2D Transforms to Pixel", r"snap_2d_transforms_to_pixel\s*=\s*(.*)", "true")
    test_setting("MSAA 3D (Disabled)", r"msaa_3d\s*=\s*(.*)", "0")
    test_setting("Screen Space AA (Disabled)", r"screen_space_aa\s*=\s*(.*)", "0")

    print("\n2. Raw Asset Folders (.gdignore) Audit (§1.6):")
    raw_found = False
    for r, dirs, _ in os.walk(root):
        if "raw" in dirs or "raw_assets" in dirs:
            raw_found = True
            raw_path = Path(r) / ("raw" if "raw" in dirs else "raw_assets")
            gdignore = raw_path / ".gdignore"
            if gdignore.exists():
                print(f"  [PASS] Found .gdignore in: {raw_path.relative_to(root)}")
                checks_passed += 1
            else:
                print(f"  [WARN] Missing .gdignore in: {raw_path.relative_to(root)} (Godot may import raw Aseprite/PSD files!)")
                checks_warn += 1
    if not raw_found:
        print("  [INFO] No dedicated 'raw/' directory detected.")

    print("\n3. Texture Import Settings Audit (§1.5):")
    bad_imports = []
    total_imports = 0
    for r, _, files in os.walk(root):
        for f in files:
            if f.endswith(".import"):
                total_imports += 1
                imp_text = (Path(r) / f).read_text(encoding="utf-8", errors="ignore")
                if "compress/mode=0" not in imp_text or "mipmaps/generate=false" not in imp_text:
                    bad_imports.append(f)

    if total_imports == 0:
        print("  [INFO] No .import files generated yet (clean project or unimported).")
    elif not bad_imports:
        print(f"  [PASS] All {total_imports} texture .import files enforce Lossless & Mipmaps=Off.")
        checks_passed += 1
    else:
        print(f"  [WARN] {len(bad_imports)} of {total_imports} .import files are not enforcing Lossless/Mipmaps=Off!")
        checks_warn += 1

    print(f"\nAudit Summary: {checks_passed} Passed, {checks_warn} Warnings, {checks_failed} Failures.\n")


def main():
    parser = argparse.ArgumentParser(description="Godot 4.x Pixel Texture Pipeline CLI Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # apply-settings
    p_apply = subparsers.add_parser("apply-settings", help="Apply pixel-perfect settings to project.godot")
    p_apply.add_argument("project", nargs="?", default=".", help="Path to Godot project directory or project.godot")
    p_apply.add_argument("--mode", choices=["2d", "3d", "fps", "topdown"], default="fps", help="Game genre preset")

    # batch-import
    p_bimp = subparsers.add_parser("batch-import", help="Generate/patch .import files with Lossless/No-Mipmaps")
    p_bimp.add_argument("folder", help="Folder containing textures")

    # batch-process
    p_bproc = subparsers.add_parser("batch-process", help="Nearest resize, alpha threshold, and palette quantize")
    p_bproc.add_argument("--src", required=True, help="Source folder")
    p_bproc.add_argument("--dst", required=True, help="Destination folder")
    p_bproc.add_argument("--scale", type=int, default=1, help="Integer scale multiplier")
    p_bproc.add_argument("--size", nargs=2, type=int, metavar=("W", "H"), help="Target width and height")
    p_bproc.add_argument("--colors", type=int, help="Color count for median-cut")
    p_bproc.add_argument("--palette", help="Palette name (pico8, db16, sweetie16, gameboy) or path to palette PNG")
    p_bproc.add_argument("--alpha", type=int, default=128, help="Alpha cut threshold (0-255)")
    p_bproc.add_argument("--create-imports", action="store_true", help="Automatically generate .import files")

    # export-shaders
    p_eshader = subparsers.add_parser("export-shaders", help="Export PSX retro & 2D Bayer dither shaders")
    p_eshader.add_argument("target", help="Target shaders folder (e.g. res://shaders)")

    # export-scripts
    p_escript = subparsers.add_parser("export-scripts", help="Export pixel camera & editor helper scripts")
    p_escript.add_argument("target", help="Target scripts folder (e.g. res://scripts)")

    # check-integrity
    p_check = subparsers.add_parser("check-integrity", help="Audit project settings, imports, and materials")
    p_check.add_argument("project", nargs="?", default=".", help="Project directory")

    args = parser.parse_args()
    if args.command == "apply-settings":
        cmd_apply_settings(args)
    elif args.command == "batch-import":
        cmd_batch_import(args)
    elif args.command == "batch-process":
        cmd_batch_process(args)
    elif args.command == "export-shaders":
        cmd_export_shaders(args)
    elif args.command == "export-scripts":
        cmd_export_scripts(args)
    elif args.command == "check-integrity":
        cmd_check_integrity(args)


if __name__ == "__main__":
    main()
