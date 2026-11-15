"""
Renders bright 3-point studio preview PNGs for the rebuilt 3D low-poly ore veins
and hybrid tree in headless Blender 5.2.
"""

import bpy
import math
import mathutils
import os

CUSTOM_DIR = r"D:\GameMaker\projects\farming_25d\models_3d\custom_blender"
MODELS = [
    "SM_Ore_01_Tas",
    "SM_Ore_02_Bakir",
    "SM_Ore_03_Demir",
    "SM_Ore_04_Gumus",
    "SM_Ore_05_Altin",
    "SM_Ore_06_Fosforit",
    "SM_Hybrid_Tree_ShadowProxy",
]


def render_all_previews():
    for m_id in MODELS:
        glb_path = os.path.join(CUSTOM_DIR, f"{m_id}.glb")
        png_path = os.path.join(CUSTOM_DIR, f"{m_id}_preview.png")
        if not os.path.exists(glb_path):
            continue

        bpy.ops.wm.read_factory_settings(use_empty=True)

        # Import GLB
        bpy.ops.import_scene.gltf(filepath=glb_path)

        # Compute bounding box
        objs = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        if not objs:
            continue

        bbox_min = mathutils.Vector((float('inf'), float('inf'), float('inf')))
        bbox_max = mathutils.Vector((float('-inf'), float('-inf'), float('-inf')))
        for obj in objs:
            for v in obj.bound_box:
                world_co = obj.matrix_world @ mathutils.Vector(v)
                bbox_min.x = min(bbox_min.x, world_co.x)
                bbox_min.y = min(bbox_min.y, world_co.y)
                bbox_min.z = min(bbox_min.z, world_co.z)
                bbox_max.x = max(bbox_max.x, world_co.x)
                bbox_max.y = max(bbox_max.y, world_co.y)
                bbox_max.z = max(bbox_max.z, world_co.z)

        center = (bbox_min + bbox_max) * 0.5
        size = (bbox_max - bbox_min).length

        # Camera setup
        cam_data = bpy.data.cameras.new("Cam")
        cam_obj = bpy.data.objects.new("CamObj", cam_data)
        bpy.context.scene.collection.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj

        dist = max(size * 1.45, 1.2)
        cam_obj.location = (center.x + dist * 0.82, center.y - dist * 0.95, center.z + dist * 0.65)
        dir_to_center = center - cam_obj.location
        rot_quat = dir_to_center.to_track_quat('-Z', 'Y')
        cam_obj.rotation_euler = rot_quat.to_euler()

        # 3-Point Studio Lighting
        # 1. Key light (bright warm)
        key_data = bpy.data.lights.new(name="KeyLight", type='SUN')
        key_data.energy = 4.5
        key_data.color = (1.0, 0.96, 0.88)
        key_obj = bpy.data.objects.new(name="KeyLightObj", object_data=key_data)
        key_obj.rotation_euler = (math.radians(45), math.radians(25), math.radians(-35))
        bpy.context.scene.collection.objects.link(key_obj)

        # 2. Rim light (cool crisp cyan-white from behind)
        rim_data = bpy.data.lights.new(name="RimLight", type='SUN')
        rim_data.energy = 3.2
        rim_data.color = (0.75, 0.90, 1.0)
        rim_obj = bpy.data.objects.new(name="RimLightObj", object_data=rim_data)
        rim_obj.rotation_euler = (math.radians(-60), math.radians(-40), math.radians(140))
        bpy.context.scene.collection.objects.link(rim_obj)

        # 3. Fill light (soft green-slate bounce)
        fill_data = bpy.data.lights.new(name="FillLight", type='SUN')
        fill_data.energy = 1.8
        fill_data.color = (0.85, 0.95, 0.90)
        fill_obj = bpy.data.objects.new(name="FillLightObj", object_data=fill_data)
        fill_obj.rotation_euler = (math.radians(30), math.radians(-50), math.radians(-70))
        bpy.context.scene.collection.objects.link(fill_obj)

        # Render settings
        scene = bpy.context.scene
        scene.render.resolution_x = 512
        scene.render.resolution_y = 512
        scene.render.film_transparent = True
        scene.render.filepath = png_path
        bpy.ops.render.render(write_still=True)
        print(f"[OK] Rendered preview: {png_path}")


if __name__ == "__main__":
    render_all_previews()
