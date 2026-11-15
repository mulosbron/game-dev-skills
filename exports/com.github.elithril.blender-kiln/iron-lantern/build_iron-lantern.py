
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
