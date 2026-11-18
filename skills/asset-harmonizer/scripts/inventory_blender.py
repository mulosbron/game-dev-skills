"""Stage 1 (FBX-capable) inventory: blender -b -P inventory_blender.py -- --root R --style S [--src assets_source/meshes]
Writes pipeline/inventory_blender.csv. For GLB/OBJ-only stocks `tools/asset_harmonizer.py inventory` needs no Blender."""
import bpy, os, sys, csv, mathutils
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from _common import args, style, asset_class
A = args(); ROOT = Path(A["root"]); ST = style(A["style"]); SRC = ROOT / A.get("src", "assets_source/meshes")
rows = []
for p in sorted(SRC.rglob("*")):
    e = p.suffix.lower()
    if e not in (".fbx", ".obj", ".glb", ".gltf"): continue
    try:
        bpy.ops.wm.read_homefile(use_empty=True)
        if e == ".fbx": bpy.ops.import_scene.fbx(filepath=str(p))
        elif e == ".obj": bpy.ops.wm.obj_import(filepath=str(p))
        else: bpy.ops.import_scene.gltf(filepath=str(p))
        ms = [o for o in bpy.data.objects if o.type == "MESH"]
        tri = sum(len(q.vertices) - 2 for o in ms for q in o.data.polygons)
        mn = [1e9] * 3; mx = [-1e9] * 3
        for o in ms:
            for v in o.bound_box:
                w = o.matrix_world @ mathutils.Vector(v)
                for i in range(3): mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
        neg = any(s < 0 for o in ms for s in o.scale); odd = any(abs(s - 1) > 1e-6 for o in ms for s in o.scale)
        uv = all(o.data.uv_layers for o in ms); cap = ST["poly_cap"].get(asset_class(p.name), 2000)
        verdict = "keep" if (tri <= cap and uv and not odd) else ("repair_uv" if not uv else "repair")
        rows.append([p.name, len(bpy.data.materials), tri, cap, "x".join(str(round(mx[i] - mn[i], 3)) for i in range(3)), uv, odd, neg, verdict])
    except Exception as ex:
        rows.append([p.name, "", "", "", "", "", "", "", f"error:{ex}"])
out = ROOT / "pipeline" / "inventory_blender.csv"; out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["file", "materials", "tris", "cap", "dims_m", "uv", "nonunit_scale", "negative_scale", "triage"]); w.writerows(rows)
print("wrote", out)
