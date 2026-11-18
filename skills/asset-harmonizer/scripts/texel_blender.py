"""Stage 3 - texel density normalization WITHOUT any add-on (blender -b -P texel_blender.py -- --root R --style S --dir DIR [--tex 1024]).

Measures px/cm = tex_px * sqrt(UVarea/3Darea) / 100 (3D in metres) and uniformly scales the UV set around its
centroid to hit the class target. Missing UV -> xatlas-style fallback: Smart UV Project. Writes pipeline/texel_report.csv.
Note: scaling UVs above 1.0 tiles/overflows; if the scaled islands exceed 0-1 the file is flagged 'overflow' (raise tex size or atlas).
"""
import bpy, bmesh, os, sys, csv
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))
from _common import args, style, asset_class

A = args(); ROOT = Path(A["root"]); ST = style(A["style"]); TEX = int(A.get("tex", 1024))
D = ROOT / A["dir"]; rows = []
for p in sorted(D.glob("*.glb")):
    bpy.ops.wm.read_homefile(use_empty=True); bpy.ops.import_scene.gltf(filepath=str(p))
    ms = [o for o in bpy.data.objects if o.type == "MESH"]
    if not ms: continue
    o = ms[0]; bpy.context.view_layer.objects.active = o; o.select_set(True)
    if not o.data.uv_layers:
        bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.01); bpy.ops.object.mode_set(mode="OBJECT")
    bm = bmesh.new(); bm.from_mesh(o.data); uvl = bm.loops.layers.uv.active
    a3 = sum(f.calc_area() for f in bm.faces)
    def uva():
        t = 0.0
        for f in bm.faces:
            pts = [l[uvl].uv for l in f.loops]
            t += abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y for i in range(len(pts)))) / 2
        return t
    au = uva(); cls = asset_class(p.name); tgt = ST["texel_density_px_cm"].get(cls, ST["texel_density_px_cm"]["prop"])
    cur = TEX * (au / a3) ** 0.5 / 100 if a3 and au else 0
    over = False
    if cur > 0:
        k = tgt / cur; cx = cy = 0; n = 0
        for f in bm.faces:
            for l in f.loops: cx += l[uvl].uv.x; cy += l[uvl].uv.y; n += 1
        cx /= n; cy /= n
        for f in bm.faces:
            for l in f.loops:
                u = l[uvl].uv; u.x = cx + (u.x - cx) * k; u.y = cy + (u.y - cy) * k
        over = any(not (0 <= l[uvl].uv.x <= 1 and 0 <= l[uvl].uv.y <= 1) for f in bm.faces for l in f.loops)
        bm.to_mesh(o.data)
    bm.free()
    bpy.ops.export_scene.gltf(filepath=str(p), export_format="GLB", export_image_format="NONE")
    rows.append([p.name, cls, round(cur, 3), tgt, "overflow" if over else "ok"]); print(rows[-1])
out = ROOT / "pipeline" / "texel_report.csv"
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["file", "class", "before_px_cm", "target_px_cm", "status"]); w.writerows(rows)
