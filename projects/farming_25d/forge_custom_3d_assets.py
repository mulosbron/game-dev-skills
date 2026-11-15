"""
Custom Blender 5.2 3D Asset Builder for 2.5D FARMING (GDD-2026-001 v1.0)
Builds 12 custom low-poly 3D models (< 500–850 tris) locked to the 32-Color Reference Palette:
  1. SM_Ore_01_Tas.glb            (Stone Vein - HP 3, Base Pickaxe)
  2. SM_Ore_02_Bakir.glb          (Copper Vein - HP 5, Base Pickaxe)
  3. SM_Ore_03_Demir.glb          (Iron Vein - HP 8, Copper Pickaxe)
  4. SM_Ore_04_Gumus.glb          (Silver Vein - HP 12, Iron Pickaxe)
  5. SM_Ore_05_Altin.glb          (Gold Vein - HP 16, Silver Pickaxe)
  6. SM_Ore_06_Fosforit.glb       (Phosphorite Core Vein - HP 22, Gold Pickaxe, Emissive #52FF9A)
  7. VM_01_Kazma_Gold.glb         (FPS Viewmodel: Gold Tier Pickaxe)
  8. VM_02_Capa_Gold.glb          (FPS Viewmodel: Gold Tier Hoe - 5x5 Area)
  9. VM_03_SulamaKabi.glb         (FPS Viewmodel: Upgraded Watering Can - 24 Tiles)
 10. VM_04_Tirpan.glb             (FPS Viewmodel: Gold Tier Scythe - 3x3 Harvest)
 11. VM_05_Hitscan_Tabanca_ve_Fener.glb (FPS Viewmodel: Miner Hitscan Pistol + K4 Lantern)
 12. SM_Hybrid_Tree_ShadowProxy.glb (Tablo 12 Hybrid 3D Trunk + Cross-Billboard Crown + Shadow Proxy)
"""

import bpy
import bmesh
import math
import os
import random

OUT_DIR = r"D:\GameMaker\projects\farming_25d\models_3d\custom_blender"
os.makedirs(OUT_DIR, exist_ok=True)


def hex_to_rgba(h, a=1.0):
    h = h.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    # sRGB to linear approximation
    return (r ** 2.2, g ** 2.2, b ** 2.2, a)


def make_mat(name, hex_color, roughness=0.75, metallic=0.0, emission_hex=None, emission_strength=0.0):
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


def add_lowpoly_rock_base(seed_val, rock_mat):
    rng = random.Random(seed_val)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.46, location=(0, 0, 0.34))
    rock = bpy.context.active_object
    rock.name = "RockBase"
    rock.scale = (1.1, 1.0, 0.78)
    bpy.ops.object.transform_apply(scale=True)
    mesh = rock.data
    for v in mesh.vertices:
        if v.co.z < 0.06:
            v.co.z = 0.0
        else:
            v.co.x += rng.uniform(-0.06, 0.06)
            v.co.y += rng.uniform(-0.06, 0.06)
            v.co.z += rng.uniform(-0.04, 0.05)
    mesh.materials.append(rock_mat)
    return rock


def build_ore_vein(filename, seed_val, rock_hex, crystal_hex, metallic, roughness, emission_hex=None, crystal_count=7):
    clear_scene()
    rock_mat = make_mat(f"Mat_Rock_{filename}", rock_hex, roughness=0.88, metallic=0.05)
    crys_mat = make_mat(
        f"Mat_Ore_{filename}",
        crystal_hex,
        roughness=roughness,
        metallic=metallic,
        emission_hex=emission_hex,
        emission_strength=2.8 if emission_hex else 0.0,
    )
    base = add_lowpoly_rock_base(seed_val, rock_mat)
    rng = random.Random(seed_val + 100)
    objs = [base]
    for i in range(crystal_count):
        angle = (i / crystal_count) * math.pi * 2.0 + rng.uniform(-0.25, 0.25)
        dist = rng.uniform(0.14, 0.34)
        cx = math.cos(angle) * dist
        cy = math.sin(angle) * dist
        cz = rng.uniform(0.22, 0.48)
        rad1 = rng.uniform(0.08, 0.14)
        depth = rng.uniform(0.24, 0.42)
        bpy.ops.mesh.primitive_cone_add(
            vertices=5,
            radius1=rad1,
            radius2=rad1 * 0.25,
            depth=depth,
            location=(cx, cy, cz),
            rotation=(
                rng.uniform(-0.55, 0.55),
                rng.uniform(-0.55, 0.55),
                angle,
            ),
        )
        c = bpy.context.active_object
        c.data.materials.append(crys_mat)
        objs.append(c)

    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    base.name = filename.replace(".glb", "")
    export_asset(base.name)


def build_vm_pickaxe():
    clear_scene()
    wood_mat = make_mat("Mat_Wood", "#8A5836", roughness=0.8)
    gold_mat = make_mat("Mat_GoldHead", "#FFD541", roughness=0.25, metallic=0.85)
    grip_mat = make_mat("Mat_Grip", "#3A443E", roughness=0.6, metallic=0.4)

    # Handle
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.032, depth=0.82, location=(0, 0, 0.41))
    handle = bpy.context.active_object
    handle.data.materials.append(wood_mat)

    # Grip collar
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.042, depth=0.16, location=(0, 0, 0.74))
    collar = bpy.context.active_object
    collar.data.materials.append(grip_mat)

    # Curved pick head (left + right spikes)
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.065, radius2=0.01, depth=0.36, location=(0.18, 0, 0.74), rotation=(0, math.radians(102), 0))
    spike_r = bpy.context.active_object
    spike_r.data.materials.append(gold_mat)

    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.065, radius2=0.01, depth=0.36, location=(-0.18, 0, 0.74), rotation=(0, math.radians(-102), 0))
    spike_l = bpy.context.active_object
    spike_l.data.materials.append(gold_mat)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = handle
    bpy.ops.object.join()
    handle.name = "VM_01_Kazma_Gold"
    export_asset(handle.name)


def build_vm_hoe():
    clear_scene()
    wood_mat = make_mat("Mat_Wood_Hoe", "#8A5836", roughness=0.8)
    gold_mat = make_mat("Mat_Gold_Hoe", "#FFD541", roughness=0.28, metallic=0.85)
    steel_mat = make_mat("Mat_Steel_Hoe", "#8C99A6", roughness=0.4, metallic=0.7)

    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.03, depth=0.88, location=(0, 0, 0.44))
    handle = bpy.context.active_object
    handle.data.materials.append(wood_mat)

    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.04, depth=0.12, location=(0, 0, 0.82))
    neck = bpy.context.active_object
    neck.data.materials.append(steel_mat)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.14, 0, 0.79), rotation=(0, math.radians(22), 0))
    blade = bpy.context.active_object
    blade.scale = (0.14, 0.22, 0.025)
    bpy.ops.object.transform_apply(scale=True)
    blade.data.materials.append(gold_mat)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = handle
    bpy.ops.object.join()
    handle.name = "VM_02_Capa_Gold"
    export_asset(handle.name)


def build_vm_watering_can():
    clear_scene()
    can_mat = make_mat("Mat_Can_Body", "#4A90E2", roughness=0.35, metallic=0.55)
    brass_mat = make_mat("Mat_Can_Rosette", "#FFD541", roughness=0.3, metallic=0.85)
    water_mat = make_mat("Mat_Can_Water", "#5AD2FF", roughness=0.15, metallic=0.1, emission_hex="#5AD2FF", emission_strength=1.2)

    # Tank body
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.18, depth=0.34, location=(0, 0, 0.17))
    tank = bpy.context.active_object
    tank.data.materials.append(can_mat)

    # Top water rim
    bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=0.13, depth=0.02, location=(0, 0, 0.345))
    water = bpy.context.active_object
    water.data.materials.append(water_mat)

    # Spout
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.032, depth=0.34, location=(0.24, 0, 0.23), rotation=(0, math.radians(52), 0))
    spout = bpy.context.active_object
    spout.data.materials.append(can_mat)

    # Rosette sprinkler head
    bpy.ops.mesh.primitive_cone_add(vertices=10, radius1=0.075, radius2=0.032, depth=0.06, location=(0.37, 0, 0.33), rotation=(0, math.radians(-128), 0))
    rosette = bpy.context.active_object
    rosette.data.materials.append(brass_mat)

    # Handle arch
    bpy.ops.mesh.primitive_torus_add(major_radius=0.14, minor_radius=0.022, major_segments=12, minor_segments=6, location=(-0.08, 0, 0.28), rotation=(math.radians(90), 0, 0))
    arch = bpy.context.active_object
    arch.data.materials.append(brass_mat)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = tank
    bpy.ops.object.join()
    tank.name = "VM_03_SulamaKabi"
    export_asset(tank.name)


def build_vm_scythe():
    clear_scene()
    wood_mat = make_mat("Mat_Wood_Scythe", "#633E26", roughness=0.8)
    blade_mat = make_mat("Mat_Blade_Scythe", "#C0CBDC", roughness=0.22, metallic=0.9)
    gold_mat = make_mat("Mat_Gold_Scythe", "#FFD541", roughness=0.3, metallic=0.85)

    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.026, depth=1.05, location=(0, 0, 0.525))
    snath = bpy.context.active_object
    snath.data.materials.append(wood_mat)

    # Side grip
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.02, depth=0.16, location=(0.08, 0, 0.52), rotation=(0, math.radians(90), 0))
    grip = bpy.context.active_object
    grip.data.materials.append(gold_mat)

    # Crescent scythe blade
    bpy.ops.mesh.primitive_cone_add(vertices=6, radius1=0.07, radius2=0.008, depth=0.52, location=(0.24, 0, 0.98), rotation=(0, math.radians(98), math.radians(12)))
    blade = bpy.context.active_object
    blade.scale = (0.35, 1.0, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    blade.data.materials.append(blade_mat)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = snath
    bpy.ops.object.join()
    snath.name = "VM_04_Tirpan"
    export_asset(snath.name)


def build_vm_pistol_and_lantern():
    clear_scene()
    steel_mat = make_mat("Mat_GunSteel", "#3A443E", roughness=0.35, metallic=0.85)
    brass_mat = make_mat("Mat_GunBrass", "#C86D51", roughness=0.35, metallic=0.8)
    phos_mat = make_mat("Mat_PhosphorGlow", "#52FF9A", roughness=0.1, metallic=0.0, emission_hex="#52FF9A", emission_strength=3.5)
    wood_mat = make_mat("Mat_GunGrip", "#633E26", roughness=0.75)

    # Right-hand Hitscan Revolver/Carbine
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.18, 0.0, 0.28))
    barrel = bpy.context.active_object
    barrel.scale = (0.05, 0.34, 0.065)
    bpy.ops.object.transform_apply(scale=True)
    barrel.data.materials.append(steel_mat)

    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.048, depth=0.12, location=(0.18, -0.06, 0.27), rotation=(math.radians(90), 0, 0))
    cyl = bpy.context.active_object
    cyl.data.materials.append(brass_mat)

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.18, -0.16, 0.16), rotation=(math.radians(-22), 0, 0))
    grip = bpy.context.active_object
    grip.scale = (0.042, 0.07, 0.16)
    bpy.ops.object.transform_apply(scale=True)
    grip.data.materials.append(wood_mat)

    # Phosphor sight core on barrel
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.18, 0.14, 0.325))
    sight = bpy.context.active_object
    sight.scale = (0.018, 0.04, 0.018)
    bpy.ops.object.transform_apply(scale=True)
    sight.data.materials.append(phos_mat)

    # Left-hand K4 Miner Lantern (5.5m light source)
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.10, depth=0.04, location=(-0.18, 0.0, 0.02))
    l_base = bpy.context.active_object
    l_base.data.materials.append(brass_mat)

    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.075, depth=0.18, location=(-0.18, 0.0, 0.13))
    l_glass = bpy.context.active_object
    l_glass.data.materials.append(phos_mat)

    bpy.ops.mesh.primitive_cone_add(vertices=8, radius1=0.11, radius2=0.03, depth=0.08, location=(-0.18, 0.0, 0.26))
    l_cap = bpy.context.active_object
    l_cap.data.materials.append(steel_mat)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = barrel
    bpy.ops.object.join()
    barrel.name = "VM_05_Hitscan_Tabanca_ve_Fener"
    export_asset(barrel.name)


def build_hybrid_tree_shadow_proxy():
    clear_scene()
    trunk_mat = make_mat("Mat_TreeTrunk_3D", "#633E26", roughness=0.88)
    crown_mat = make_mat("Mat_BillboardCrown_2D", "#4CA64C", roughness=0.75)
    proxy_mat = make_mat("Mat_ShadowProxy_Capsule", "#24523B", roughness=0.9)

    # 1. Low-poly 3D Trunk
    bpy.ops.mesh.primitive_cone_add(vertices=7, radius1=0.22, radius2=0.11, depth=1.15, location=(0, 0, 0.575))
    trunk = bpy.context.active_object
    trunk.data.materials.append(trunk_mat)

    # 2. Crossed Y-Billboard Foliage Planes + Clustered Foliage Volume (Tablo 12)
    bpy.ops.mesh.primitive_plane_add(size=1.35, location=(0, 0, 1.45), rotation=(math.radians(90), 0, 0))
    plane_a = bpy.context.active_object
    plane_a.data.materials.append(crown_mat)

    bpy.ops.mesh.primitive_plane_add(size=1.35, location=(0, 0, 1.45), rotation=(math.radians(90), 0, math.radians(90)))
    plane_b = bpy.context.active_object
    plane_b.data.materials.append(crown_mat)

    # 3. Low-poly Shadow Proxy Capsule (GDD Section 8.3: Cast Shadow = Shadows Only proxy)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.58, location=(0, 0, 1.48))
    proxy = bpy.context.active_object
    proxy.scale = (1.0, 1.0, 1.15)
    bpy.ops.object.transform_apply(scale=True)
    proxy.data.materials.append(proxy_mat)

    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = trunk
    bpy.ops.object.join()
    trunk.name = "SM_Hybrid_Tree_ShadowProxy"
    export_asset(trunk.name)


def export_asset(name):
    glb_path = os.path.join(OUT_DIR, f"{name}.glb")
    blend_path = os.path.join(OUT_DIR, f"{name}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=False)
    print(f"[OK] Exported {glb_path}")


if __name__ == "__main__":
    # 6 Mine Ore Veins (GDD Tablo 6)
    build_ore_vein("SM_Ore_01_Tas.glb", 101, "#3A443E", "#5A6962", metallic=0.1, roughness=0.85, crystal_count=5)
    build_ore_vein("SM_Ore_02_Bakir.glb", 202, "#3A443E", "#C86D51", metallic=0.75, roughness=0.35, crystal_count=6)
    build_ore_vein("SM_Ore_03_Demir.glb", 303, "#26332D", "#8C99A6", metallic=0.85, roughness=0.32, crystal_count=7)
    build_ore_vein("SM_Ore_04_Gumus.glb", 404, "#26332D", "#C0CBDC", metallic=0.92, roughness=0.20, crystal_count=8)
    build_ore_vein("SM_Ore_05_Altin.glb", 505, "#1E120C", "#FFD541", metallic=0.95, roughness=0.18, emission_hex="#FFD541", crystal_count=8)
    build_ore_vein("SM_Ore_06_Fosforit.glb", 606, "#0D1610", "#52FF9A", metallic=0.25, roughness=0.12, emission_hex="#52FF9A", crystal_count=9)

    # 5 FPS Viewmodels (GDD Tablo 9 & Tablo 11)
    build_vm_pickaxe()
    build_vm_hoe()
    build_vm_watering_can()
    build_vm_scythe()
    build_vm_pistol_and_lantern()

    # 1 Hybrid Tree + Shadow Proxy (GDD Tablo 12 & Section 8.3)
    build_hybrid_tree_shadow_proxy()
