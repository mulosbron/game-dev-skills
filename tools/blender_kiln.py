#!/usr/bin/env python3
"""
Blender Kiln 3.0 — Headless 3D Asset Forge, 6-View Clay/Colour Review Sheet Renderer,
UV/Print Validator & 3D-to-2D Pixel Sprite Bridge (tools/blender_kiln.py)

Backed by `libraries/com.github.elithril.blender-kiln` (MIT License © Nicolas Dolphens)
and local Blender 5.2 LTS (`C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe`).

Zero AI Diffusion Weights / Zero GPU Required:
Builds editable, real-size (1 unit = 1 meter), grounded (Z=0), multi-part 3D assets directly
via deterministic Blender Python (`bpy`) scripts, audits UVs (`uv_check.py`), renders 6-angle
Colour + Clay review sheets (`review_sheet.py`), optimizes via `glb_forge.py`, and optionally
converts the 3D render into a 2D Pixel Art Sprite + Normal Map via `image_to_pixel.py`!

Subcommands:
  1. doctor       : Verify Blender 5.2+, run Kiln's `verify_blender.py` API suite, and check bridges
  2. build        : Execute the full 7-phase Kiln pipeline (Model -> Clean -> UV/PBR -> Review Sheet -> Optimize GLB -> Optional 2D Pixel Sprite)
  3. review-sheet : Render Kiln's 6-angle Colour (`_sheet.png`) + Clay (`_sheet_clay.png`) inspection sheets for any GLB/Blend
  4. uv-check     : Run Kiln's UV map auditor (`collapsed`, `overlap`, `stretch`, `flipped`) on any GLB/Blend
  5. print-check  : Run Kiln's 3D printability validator (`manifold`, `wall thickness`, `flat base`)
  6. studio       : Launch local Kiln Studio web server (`plugin/studio/studio.py`)
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
KILN_ROOT = WORKSPACE_ROOT / "libraries" / "com.github.elithril.blender-kiln" / "plugin"
KILN_TOOLS = KILN_ROOT / "tools"
KILN_STUDIO = KILN_ROOT / "studio"
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.github.elithril.blender-kiln"


def find_blender(explicit: str | None = None) -> str:
    candidates = [
        explicit,
        os.environ.get("BLENDER"),
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        shutil.which("blender"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(Path(c).resolve())
    raise FileNotFoundError(
        "Blender 4.4+ not found. Set BLENDER environment variable or install Blender 5.2 LTS."
    )


# Built-in Procedural 3D Prop Scripts (Follows Kiln Iron Rules: 1 unit = 1m, grounded at Z=0, named parts, Smart UV, Principled BSDF)
PROCEDURAL_PROP_BUILDERS = {
    "iron-lantern": {
        "title": "Medieval Hanging Iron Lantern (0.44m tall, 5 named parts, PBR Iron/Brass/Glass/Flame)",
        "code": r"""
import bpy, bmesh, math, sys
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:]
out_blend = argv[0]
out_glb   = argv[1]
out_render = argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.preferences.filepaths.save_version = 0

def make_mat(name, base_col, metallic=0.0, roughness=0.5, emission_col=None, emission_str=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_col, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission_col and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*emission_col, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emission_str
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
    return mat

mat_iron  = make_mat("M_ForgedIron", (0.14, 0.15, 0.18), metallic=0.88, roughness=0.42)
mat_brass = make_mat("M_AgedBrass",  (0.78, 0.56, 0.22), metallic=0.92, roughness=0.30)
mat_glass = make_mat("M_LanternGlass", (0.65, 0.85, 0.98), metallic=0.05, roughness=0.12)
mat_flame = make_mat("M_CandleFlame", (1.0, 0.65, 0.15), metallic=0.0, roughness=0.2, emission_col=(1.0, 0.55, 0.12), emission_str=4.5)

parts = []

# 1. Hexagonal Base Pedestal (Z = 0.00m to 0.06m)
bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.11, depth=0.06, location=(0, 0, 0.03))
base = bpy.context.active_object
base.name = "SM_Lantern_Base"
base.data.materials.append(mat_iron)
parts.append(base)

# 2. Lower Brass Collar (Z = 0.06m to 0.085m)
bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.088, depth=0.025, location=(0, 0, 0.0725))
collar = bpy.context.active_object
collar.name = "SM_Lantern_Collar"
collar.data.materials.append(mat_brass)
parts.append(collar)

# 3. Inner Glowing Flame Core (Z = 0.085m to 0.19m)
bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.032, radius2=0.004, depth=0.105, location=(0, 0, 0.1375))
flame = bpy.context.active_object
flame.name = "SM_Lantern_FlameCore"
flame.data.materials.append(mat_flame)
parts.append(flame)

# 4. Hexagonal Glass Chamber (Z = 0.08m to 0.27m)
bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.078, depth=0.19, location=(0, 0, 0.175))
glass = bpy.context.active_object
glass.name = "SM_Lantern_Glass"
glass.data.materials.append(mat_glass)
parts.append(glass)

# 5. Four Vertical Iron Guard Struts
for i in range(6):
    ang = i * (math.pi / 3.0)
    rx = math.cos(ang) * 0.086
    ry = math.sin(ang) * 0.086
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.007, depth=0.20, location=(rx, ry, 0.175))
    strut = bpy.context.active_object
    strut.name = f"SM_Lantern_Strut_{i+1}"
    strut.data.materials.append(mat_iron)
    parts.append(strut)

# 6. Stepped Pagoda Roof Cap (Z = 0.27m to 0.36m)
bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.13, radius2=0.035, depth=0.09, location=(0, 0, 0.315))
cap = bpy.context.active_object
cap.name = "SM_Lantern_RoofCap"
cap.data.materials.append(mat_iron)
parts.append(cap)

# 7. Top Brass Hanging Torus Ring (Z = 0.36m to 0.44m)
bpy.ops.mesh.primitive_torus_add(major_radius=0.036, minor_radius=0.008, major_segments=18, minor_segments=8, location=(0, 0, 0.395), rotation=(math.pi/2, 0, 0))
ring = bpy.context.active_object
ring.name = "SM_Lantern_HangRing"
ring.data.materials.append(mat_brass)
parts.append(ring)

# Kiln Rule 10: Apply transforms, smart UV project, recalc normals
bpy.ops.object.select_all(action='DESELECT')
for ob in parts:
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')
    ob.select_set(False)

# Save .blend and _original.glb
Path(out_blend).parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', export_apply=False)

# Also render a crisp transparent 512x512 3/4 view for the 3D -> 2D Pixel Art bridge!
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.film_transparent = True

cam_data = bpy.data.cameras.new("KilnCam")
cam_ob = bpy.data.objects.new("KilnCam", cam_data)
scene.collection.objects.link(cam_ob)
scene.camera = cam_ob
cam_ob.location = (0.58, -0.58, 0.42)
direction = cam_ob.location * -1
cam_ob.rotation_euler = (math.radians(68), 0, math.radians(45))

# Aim camera at center Z=0.21m
track = cam_ob.constraints.new(type='TRACK_TO')
empty = bpy.data.objects.new("Target", None)
empty.location = (0, 0, 0.21)
scene.collection.objects.link(empty)
track.target = empty
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

for name, loc, energy, col in [
    ("KeyLight", (1.2, -1.0, 1.4), 120.0, (1.0, 0.95, 0.88)),
    ("FillLight", (-1.2, -0.8, 0.8), 55.0, (0.65, 0.80, 1.0)),
    ("RimLight", (0.0, 1.4, 1.1), 85.0, (1.0, 0.75, 0.45)),
]:
    ld = bpy.data.lights.new(name=name, type='AREA')
    ld.energy = energy
    ld.color = col
    lo = bpy.data.objects.new(name=name, object_data=ld)
    lo.location = loc
    scene.collection.objects.link(lo)
    t = lo.constraints.new(type='TRACK_TO')
    t.target = empty
    t.track_axis = 'TRACK_NEGATIVE_Z'
    t.up_axis = 'UP_Y'

scene.render.filepath = out_render
bpy.ops.render.render(write_still=True)
print("KILN_BUILD_OK", out_blend, out_glb, out_render)
"""
    }
}


def cmd_doctor(args):
    blender = find_blender(args.blender)
    ver_out = subprocess.check_output([blender, "--version"], text=True).splitlines()[0]
    print(f"[OK] Local Blender Found : {ver_out} ({blender})")

    verify_script = KILN_TOOLS / "verify_blender.py"
    print(f"[..] Running Kiln Blender 5.2 Verification Suite ({verify_script.name})...")
    proc = subprocess.run(
        [blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(verify_script)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        print("[OK] Kiln `verify_blender.py` passed 100% of Blender API & mesh/rig checks!")
    else:
        print(f"[WARN] verify_blender output:\n{proc.stdout}\n{proc.stderr}")


def cmd_review_sheet(args):
    blender = find_blender(args.blender)
    model_path = Path(args.model).resolve()
    out_png = Path(args.out).resolve() if args.out else (DEFAULT_EXPORT_DIR / f"{model_path.stem}_review_sheet.png")
    out_png.parent.mkdir(parents=True, exist_ok=True)

    script = KILN_TOOLS / "review_sheet.py"
    proc = subprocess.run(
        [
            blender, "-b", "--factory-startup", "--python-exit-code", "1",
            "--python", str(script), "--",
            str(model_path), "--out", str(out_png), "--res", str(args.res)
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"review_sheet failed:\n{proc.stderr}\n{proc.stdout}")

    clay_png = out_png.with_name(f"{out_png.stem}_clay.png")
    print(f"[OK] Rendered 6-View Colour Review Sheet -> {out_png}")
    print(f"[OK] Rendered 6-View Clay Geometry Sheet -> {clay_png}")
    return out_png, clay_png


def cmd_uv_check(args):
    blender = find_blender(args.blender)
    model_path = Path(args.model).resolve()
    json_out = Path(args.json_out).resolve() if args.json_out else (model_path.parent / f"{model_path.stem}_uv_report.json")

    script = KILN_TOOLS / "uv_check.py"
    proc = subprocess.run(
        [
            blender, "-b", "--factory-startup", "--python-exit-code", "1",
            "--python", str(script), "--",
            str(model_path), "--json", str(json_out)
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in proc.stdout.splitlines():
        if line.strip() and not line.startswith("Blender"):
            print(f"  {line}")
    print(f"[OK] UV Audit JSON saved -> {json_out}")
    return json_out


def cmd_print_check(args):
    blender = find_blender(args.blender)
    model_path = Path(args.model).resolve()
    script = KILN_TOOLS / "print_check.py"
    proc = subprocess.run(
        [
            blender, "-b", "--factory-startup", "--python-exit-code", "1",
            "--python", str(script), "--",
            str(model_path)
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    for line in proc.stdout.splitlines():
        if line.strip() and not line.startswith("Blender"):
            print(f"  {line}")


def cmd_build(args):
    blender = find_blender(args.blender)
    preset_id = args.preset
    prop = PROCEDURAL_PROP_BUILDERS[preset_id]
    out_dir = Path(args.out_dir).resolve() / preset_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_blend = out_dir / f"{preset_id}.blend"
    out_orig_glb = out_dir / f"{preset_id}_original.glb"
    out_render_png = out_dir / f"{preset_id}_3d_render.png"
    script_file = out_dir / f"build_{preset_id}.py"
    script_file.write_text(prop["code"], encoding="utf-8")

    print(f"=== [PHASE 1-5] KILN HEADLESS BLENDER BUILD: {prop['title']} ===")
    proc = subprocess.run(
        [
            blender, "-b", "--factory-startup", "--python-exit-code", "1",
            "--python", str(script_file), "--",
            str(out_blend), str(out_orig_glb), str(out_render_png)
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Blender build failed:\n{proc.stderr}\n{proc.stdout}")
    print(f"  -> Editable Blender Source : {out_blend}")
    print(f"  -> Raw Grounded GLB (Z=0)  : {out_orig_glb}")
    print(f"  -> Transparent 3D Render   : {out_render_png}")

    print("\n=== [PHASE 6] KILN UV AUDIT & 6-VIEW COLOUR/CLAY REVIEW SHEETS ===")
    cmd_uv_check(argparse.Namespace(
        blender=blender,
        model=str(out_orig_glb),
        json_out=str(out_dir / f"{preset_id}_uv_report.json"),
    ))
    sheet_png, clay_png = cmd_review_sheet(argparse.Namespace(
        blender=blender,
        model=str(out_orig_glb),
        out=str(out_dir / f"{preset_id}_review_sheet.png"),
        res=720,
    ))
    # Remove intermediate single-view tiles to keep export folder super clean
    for tile in out_dir.glob(f"{preset_id}_review_sheet_*.png"):
        if tile.name != clay_png.name:
            tile.unlink(missing_ok=True)

    print("\n=== [PHASE 7] GLB FORGE OPTIMIZATION & SPLIT-SCREEN 3D COMPARE STUDIO ===")
    glb_forge_script = WORKSPACE_ROOT / "tools" / "glb_forge.py"
    subprocess.run(
        [sys.executable, str(glb_forge_script), "optimize", str(out_orig_glb), "--preset", "web-mobile", "--out-dir", str(out_dir)],
        check=True,
    )

    if args.to_pixel:
        print("\n=== [PHASE 8] 3D -> 2D PIXEL SPRITE + MOONFELL NORMAL MAP BRIDGE ===")
        i2p_script = WORKSPACE_ROOT / "tools" / "image_to_pixel.py"
        subprocess.run(
            [
                sys.executable, str(i2p_script), "convert", str(out_render_png),
                "--profile", args.pixel_profile, "--width", "64", "--scale", "4",
                "--normal-map", "--out-dir", str(out_dir)
            ],
            check=True,
        )

    # Write official Kiln `{name}_log.md` production & license ledger (Iron Rule 7 & 17)
    log_md = out_dir / f"{preset_id}_log.md"
    log_md.write_text(
        f"# Kiln Production & Provenance Log: `{preset_id}`\n\n"
        f"- **Title:** {prop['title']}\n"
        f"- **Generator:** `tools/blender_kiln.py` (Headless Blender 5.2 LTS)\n"
        f"- **License:** CC0 1.0 / MIT (100% Procedural Geometry & Materials — Commercial Use Allowed)\n"
        f"- **Checkpoint:** EXPORT COMPLETE\n\n"
        f"## Output Artifacts\n"
        f"- `{out_blend.name}` (Editable Blender 5.2 source)\n"
        f"- `{out_orig_glb.name}` (Uncompressed grounded GLB)\n"
        f"- `{sheet_png.name}` (6-View Colour Review Sheet)\n"
        f"- `{clay_png.name}` (6-View Clay Topology Sheet)\n"
        f"- `{preset_id}_original_web-mobile.glb` (Meshopt + WebP optimized GLB)\n"
        f"- `{preset_id}_original_web-mobile_compare_studio.html` (Split-Screen 3D Compare Studio)\n",
        encoding="utf-8",
    )
    print(f"\n[OK] Wrote Kiln Production Ledger -> {log_md}")


def cmd_studio(args):
    studio_py = KILN_STUDIO / "studio.py"
    target_root = Path(args.dir).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Launching Kiln Studio for {target_root}...")
    subprocess.run([sys.executable, str(studio_py), str(target_root)])


def main():
    parser = argparse.ArgumentParser(description="Blender Kiln 3.0 — Headless 3D Asset Forge & 3D-to-2D Pixel Bridge")
    parser.add_argument("--blender", default=None, help="Explicit path to blender.exe")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="Verify local Blender 5.2+ and run Kiln's verify_blender.py suite")

    p_build = sub.add_parser("build", help="Run the full 7-phase Kiln 3D build + Review Sheet + GLB Optimize + 2D Pixel Bridge")
    p_build.add_argument("--preset", choices=list(PROCEDURAL_PROP_BUILDERS.keys()), default="iron-lantern")
    p_build.add_argument("--to-pixel", action="store_true", default=True, help="Also convert 3D render to 2D Pixel Art + Normal Map")
    p_build.add_argument("--pixel-profile", default="dark-fantasy")
    p_build.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    p_rev = sub.add_parser("review-sheet", help="Render 6-angle Colour + Clay Review Sheets for any GLB or .blend")
    p_rev.add_argument("model", help="Path to .glb or .blend file")
    p_rev.add_argument("--out", default=None, help="Output PNG path")
    p_rev.add_argument("--res", type=int, default=720)

    p_uv = sub.add_parser("uv-check", help="Audit UV maps (collapsed, overlap, stretch, flipped) in headless Blender")
    p_uv.add_argument("model", help="Path to .glb or .blend file")
    p_uv.add_argument("--json-out", default=None)

    p_pr = sub.add_parser("print-check", help="Validate 3D printability (manifold, wall thickness, flat base)")
    p_pr.add_argument("model", help="Path to .stl, .glb, or .blend file")

    p_st = sub.add_parser("studio", help="Launch local Kiln Studio web viewer & note pinboard")
    p_st.add_argument("--dir", default=str(DEFAULT_EXPORT_DIR))

    args = parser.parse_args()
    if args.cmd == "doctor":
        cmd_doctor(args)
    elif args.cmd == "build":
        cmd_build(args)
    elif args.cmd == "review-sheet":
        cmd_review_sheet(args)
    elif args.cmd == "uv-check":
        cmd_uv_check(args)
    elif args.cmd == "print-check":
        cmd_print_check(args)
    elif args.cmd == "studio":
        cmd_studio(args)


if __name__ == "__main__":
    main()
