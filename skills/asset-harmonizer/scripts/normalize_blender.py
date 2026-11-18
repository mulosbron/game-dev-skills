"""Stage 2 - geometric normalization (blender -b -P normalize_blender.py -- --root R --style S --src DIR --out DIR).

Fixed order (never reorder): import -> fix negative scale -> apply transform -> unit scale to real size
-> base-center pivot -> cleanup -> auto-smooth -> decimate(apply) -> export GLB (no embedded textures).
Failures are logged to pipeline/normalize_errors.txt; the batch never aborts on one file.
Optional pivot exceptions: pipeline/pivot_overrides.json {"file.glb": [x,y,z]} (world offset of origin).
The style's `engine` (godot/unity/unreal) remaps the forward axis so meshes line up in-engine before export.
"""
import bpy, os, sys, json, math, traceback
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from _common import args, style, asset_class
import mathutils

A = args(); ROOT = Path(A["root"]); ST = style(A["style"])
SRC = ROOT / A["src"]; OUT = ROOT / A["out"]; OUT.mkdir(parents=True, exist_ok=True)
EXC_P = ROOT / "pipeline" / "pivot_overrides.json"
EXC = json.load(open(EXC_P)) if EXC_P.exists() else {}
ERR = ROOT / "pipeline" / "normalize_errors.txt"

# engine forward axis in Blender (+X default): -Z (Godot), +Z (Unity), +X (Unreal)
AXIS = {"godot": (2, -1), "unity": (1, 1), "unreal": (0, 1)}.get(ST.get("engine", "godot"), (0, 1))
AX, SIGN = AXIS


def do_import(p):
    e = p.suffix.lower()
    if e == ".fbx": bpy.ops.import_scene.fbx(filepath=str(p))
    elif e == ".obj": bpy.ops.wm.obj_import(filepath=str(p))
    elif e in (".glb", ".gltf"): bpy.ops.import_scene.gltf(filepath=str(p))
    else: return False
    return True


def meshes(): return [o for o in bpy.data.objects if o.type == "MESH"]


def world_bounds(objs):
    mn = mathutils.Vector((1e9,) * 3); mx = mathutils.Vector((-1e9,) * 3)
    for o in objs:
        for v in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(v)
            for i in range(3): mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    return mn, mx


def process(p):
    bpy.ops.wm.read_homefile(use_empty=True)
    if not do_import(p): return
    for o in list(bpy.data.objects):  # drop cameras/lights/empties leaking in
        if o.type not in ("MESH",) : bpy.data.objects.remove(o, do_unlink=True)
    ms = meshes()
    for o in ms: o.parent = None
    bpy.ops.object.select_all(action="DESELECT")
    for o in ms:
        if any(s < 0 for s in o.scale):  # fix negative scale BEFORE apply
            o.select_set(True); bpy.context.view_layer.objects.active = o
            o.scale = [abs(s) for s in o.scale]; bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.flip_normals(); bpy.ops.object.mode_set(mode="OBJECT"); o.select_set(False)
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = ms[0]
    if len(ms) > 1: bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    # real-world scale from style dimension_ranges_m when file name carries the keyword
    for key, (lo, hi) in ST.get("dimension_ranges_m", {}).items():
        if key in p.stem.lower():
            h = obj.dimensions.z or 1.0; tgt = (lo + hi) / 2
            if not (lo <= h <= hi):
                f = tgt / h; obj.scale = (f, f, f); bpy.ops.object.transform_apply(scale=True)
    mn, mx = world_bounds([obj])
    if p.name in EXC: off = mathutils.Vector(EXC[p.name])
    else: off = mathutils.Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))  # base-center
    bpy.context.scene.cursor.location = off
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")
    obj.location = (0, 0, 0); bpy.ops.object.transform_apply(location=True)
    bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.mesh.dissolve_degenerate()
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    try: bpy.ops.object.shade_auto_smooth(angle=math.radians(ST.get("auto_smooth_deg", 40)))
    except Exception: pass
    tri = sum(len(q.vertices) - 2 for q in obj.data.polygons)
    cap = ST["poly_cap"].get(asset_class(p.name), 2000)
    if tri > cap:
        m = obj.modifiers.new("dec", "DECIMATE"); m.ratio = max(cap / tri, 0.05)
        bpy.ops.object.modifier_apply(modifier="dec")
    if AX != 0 and SIGN < 0:  # remap forward axis to engine convention
        m = obj.modifiers.new("ax", "ARMATURE"); obj.modifiers.remove(m)
        rot = mathutils.Quaternion((math.sqrt(0.5), 0, math.sqrt(0.5), 0)) if AX == 1 else mathutils.Quaternion((math.sqrt(0.5), 0, -math.sqrt(0.5), 0))
        obj.rotation_quaternion = rot
        bpy.ops.object.transform_apply(rotation=True)
    obj.name = p.stem
    dst = OUT / (p.stem.lower().replace(" ", "_").replace("-", "_") + ".glb")
    bpy.ops.export_scene.gltf(filepath=str(dst), export_format="GLB", use_selection=False,
                              export_image_format="NONE", export_yup=True, export_apply=True)
    print(f"OK {p.name}: {tri}->{sum(len(q.vertices)-2 for q in obj.data.polygons)} tris -> {dst.name}")


errs = []
for p in sorted(SRC.rglob("*")):
    try: process(p)
    except Exception:
        errs.append(f"{p.name}\n{traceback.format_exc()}"); print("FAIL", p.name)
if errs: ERR.write_text("\n".join(errs), encoding="utf-8")
