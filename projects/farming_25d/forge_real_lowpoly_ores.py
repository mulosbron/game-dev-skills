"""
Forges AAA-quality low-poly 3D Ore Veins with sharp chiseled rock boulders
and bold, prominent, gleaming prismatic crystal clusters in Blender 5.2.
Also builds a lush, stylized hybrid tree with roots and layered foliage.
"""

import bpy
import bmesh
import math
import mathutils
import os
import random

OUT_DIR = r"D:\GameMaker\projects\farming_25d\models_3d\custom_blender"
os.makedirs(OUT_DIR, exist_ok=True)


def hex_to_rgba(h, a=1.0):
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r ** 2.2, g ** 2.2, b ** 2.2, a)


def make_mat(name, hex_color, roughness=0.6, metallic=0.0, emission_hex=None, emission_strength=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = hex_to_rgba(hex_color)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission_hex and "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = hex_to_rgba(emission_hex)
            bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def add_chiseled_rock_base():
    """Builds a sharp, chiseled, multi-faceted low-poly rock boulder."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.55, location=(0, 0, 0.42))
    rock = bpy.context.active_object
    rock.name = "RockBase"
    rock.scale = (1.2, 0.95, 0.75)
    bpy.ops.object.transform_apply(scale=True)

    # Displace vertices to create angular planar facets
    bm = bmesh.new()
    bm.from_mesh(rock.data)
    rng = random.Random(42)
    for v in bm.verts:
        # Flatten bottom
        if v.co.z < 0.15:
            v.co.z = 0.02
        else:
            # Jitter slightly for natural cliff look
            v.co.x += rng.uniform(-0.06, 0.06)
            v.co.y += rng.uniform(-0.06, 0.06)
            v.co.z += rng.uniform(-0.04, 0.05)

    bm.to_mesh(rock.data)
    bm.free()

    # Apply flat shading
    for poly in rock.data.polygons:
        poly.use_smooth = False

    return rock


def add_crystal_cluster(crystal_mat, count=6, scale_range=(0.18, 0.32), height_mult=1.6):
    """Spawns prominent, sharp hexagonal/octagonal crystal obelisks jutting out."""
    crystals = []
    rng = random.Random(77)

    # Angles to sprout out
    angles = [
        (0.2, 0.15, 0.55, 0.35, -0.4, 0.6),
        (-0.25, 0.2, 0.5, -0.5, 0.3, -0.3),
        (0.1, -0.22, 0.48, 0.4, 0.5, -0.2),
        (-0.18, -0.15, 0.52, -0.3, -0.4, 0.5),
        (0.0, 0.0, 0.62, 0.05, 0.1, 0.1),
        (0.3, -0.05, 0.42, 0.6, -0.2, 0.4),
        (-0.32, 0.0, 0.38, -0.6, 0.1, -0.5),
    ]

    for i in range(min(count, len(angles))):
        pos_x, pos_y, pos_z, rot_x, rot_y, rot_z = angles[i]
        r = rng.uniform(scale_range[0], scale_range[1])
        h = r * height_mult * rng.uniform(1.3, 1.8)

        # Cylinder with 5 or 6 sides for hexagonal prism crystal
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=6,
            radius=r * 0.55,
            depth=h,
            location=(pos_x, pos_y, pos_z),
            rotation=(rot_x, rot_y, rot_z)
        )
        c = bpy.context.active_object
        c.name = f"Crystal_{i}"
        c.data.materials.append(crystal_mat)

        # Sharpen tip into a pointed pyramid
        bm = bmesh.new()
        bm.from_mesh(c.data)
        top_verts = [v for v in bm.verts if v.co.z > h * 0.35]
        if top_verts:
            # Merge or point top vertices
            center_top = mathutils.Vector((0, 0, h * 0.65))
            for v in top_verts:
                v.co = center_top
        bm.to_mesh(c.data)
        bm.free()

        for poly in c.data.polygons:
            poly.use_smooth = False
        crystals.append(c)

    return crystals


def build_ore_vein(slug, rock_hex, crystal_hex, metallic=0.0, roughness=0.5, emission_hex=None, emission_strength=0.0):
    clear_scene()
    mat_rock = make_mat(f"Mat_Rock_{slug}", rock_hex, roughness=0.85, metallic=0.05)
    mat_crystal = make_mat(
        f"Mat_Crystal_{slug}",
        crystal_hex,
        roughness=roughness,
        metallic=metallic,
        emission_hex=emission_hex,
        emission_strength=emission_strength
    )

    rock = add_chiseled_rock_base()
    rock.data.materials.append(mat_rock)

    add_crystal_cluster(
        mat_crystal,
        count=7 if "Fosforit" in slug or "Altin" in slug else 5,
        scale_range=(0.20, 0.36) if "Fosforit" in slug else (0.16, 0.28),
        height_mult=2.2 if "Fosforit" in slug else 1.6
    )

    # Join into single object
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = rock
    bpy.ops.object.join()
    rock.name = slug

    # Export GLB
    glb_path = os.path.join(OUT_DIR, f"{slug}.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        use_selection=True,
        export_apply=True
    )
    print(f"[OK] Exported {slug}.glb")


def build_hybrid_tree():
    clear_scene()
    mat_bark = make_mat("Mat_Bark", "#633E26", roughness=0.85)
    mat_leaves = make_mat("Mat_Leaves", "#3F7C49", roughness=0.7)
    mat_leaves_hi = make_mat("Mat_LeavesHi", "#75C782", roughness=0.6)

    # 1. Trunk with roots
    bpy.ops.mesh.primitive_cylinder_add(vertices=7, radius=0.26, depth=1.8, location=(0, 0, 0.9))
    trunk = bpy.context.active_object
    trunk.name = "Trunk"
    trunk.data.materials.append(mat_bark)

    # Roots flare
    bm = bmesh.new()
    bm.from_mesh(trunk.data)
    for v in bm.verts:
        if v.co.z < -0.6:
            v.co.x *= 1.6
            v.co.y *= 1.6
            v.co.z = -0.89  # snap to ground Z=0
    bm.to_mesh(trunk.data)
    bm.free()

    # 2. Layered foliage crowns (3 tiered fluffy polygonal domes)
    tiers = [
        (1.8, 1.15, 0.9, mat_leaves),
        (2.4, 0.92, 0.8, mat_leaves_hi),
        (2.9, 0.65, 0.65, mat_leaves),
    ]
    for z_pos, r_rad, h_depth, l_mat in tiers:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=r_rad, location=(0, 0, z_pos))
        crown = bpy.context.active_object
        crown.scale = (1.0, 1.0, h_depth)
        crown.data.materials.append(l_mat)
        for poly in crown.data.polygons:
            poly.use_smooth = False

    # Join
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.view_layer.objects.active = trunk
    bpy.ops.object.join()
    trunk.name = "SM_Hybrid_Tree_ShadowProxy"

    glb_path = os.path.join(OUT_DIR, "SM_Hybrid_Tree_ShadowProxy.glb")
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        use_selection=True,
        export_apply=True
    )
    print("[OK] Exported SM_Hybrid_Tree_ShadowProxy.glb")


if __name__ == "__main__":
    print("Building chiseled rocks and sparkling crystals...")
    # 1. Stone: Slate gray rock + quartz white-blue crystal facets
    build_ore_vein("SM_Ore_01_Tas", "#505E56", "#AFC0B7", metallic=0.1, roughness=0.4)

    # 2. Copper: Dark verdigris slate + fiery copper-orange crystals
    build_ore_vein("SM_Ore_02_Bakir", "#3A443E", "#FF8C24", metallic=0.8, roughness=0.3)

    # 3. Iron: Cold industrial granite + steel-blue magnetite slabs
    build_ore_vein("SM_Ore_03_Demir", "#26332D", "#8C99A6", metallic=0.7, roughness=0.35)

    # 4. Silver: Deep midnight rock + gleaming mirror silver prisms
    build_ore_vein("SM_Ore_04_Gumus", "#1E2420", "#D4E2D9", metallic=0.95, roughness=0.2)

    # 5. Gold: Rich dark basalt + heavy 24K pure gold clusters
    build_ore_vein("SM_Ore_05_Altin", "#142419", "#FFD541", metallic=0.9, roughness=0.25)

    # 6. Phosphorite: Jet black void stone + glowing alien neon-mint obelisks
    build_ore_vein("SM_Ore_06_Fosforit", "#0D1610", "#52FF9A", metallic=0.1, roughness=0.15, emission_hex="#52FF9A", emission_strength=4.0)

    # 7. Hybrid Tree
    build_hybrid_tree()
    print("All 3D crystalline ore veins and hybrid tree forged successfully!")
