---
name: terrain3d
description: TokisanGames Godot 4 C++ GDExtension geometry clipmap terrain system (Terrain3D, Terrain3DData, Terrain3DMaterial, Terrain3DAssets, Terrain3DInstancer, collision, and navmesh baking). Use when building large editable 3D terrains in Godot 4, channel-packing 32 terrain texture sets, importing 16/32-bit heightmaps, sculpting/editing terrain via API, placing MultiMesh foliage, or configuring collision and NavMesh baking.
---

# Terrain3D (TokisanGames Godot 4 GDExtension)

C++ GDExtension geometry-clipmap terrain system for Godot 4 (MIT license). Generates clipmap meshes once, recenters them around the camera, and displaces vertices on the GPU from per-region texture arrays (`1 pixel = 1 vertex` at LOD 0, scaled laterally by `Terrain3D.vertex_spacing`).

## Core Architecture & Classes

- **`Terrain3D` (`Node3D`):** Root node. Holds `data_directory`, `region_size` (`SIZE_64`..`SIZE_2048`, default `256`), `vertex_spacing` (`1.0`), `mesh_lods` (up to `10`), `tessellation_level`, `ocean_enabled`, and aliases to collision/material overlays.
- **`Terrain3DData`:** Manages up to **1024 active regions** in a **32×32 grid** (locations `(-16,-16)` to `(15,15)`, max `65.5 × 65.5 km` at `SIZE_2048`), storing per-region `Terrain3DRegion` files (`terrain3d_XX-YY.res`).
  - Region keys: **Always key by `region_location: Vector2i`** (`data.get_region_location(global_pos)`), **never** by `region_id: int` (internal index changes when regions are added/removed).
  - Outside allocated regions, there is **no collision**, raycasts miss, and `get_height()` returns `NAN`.
- **`Terrain3DMaterial` (`Resource`):** Compiles shader + `Texture2DArray` uniforms (`_height_maps`, `_control_maps`, `_color_maps`, `_texture_array_albedo`, `_texture_array_normal`). Supports `world_background` (`NONE`, `FLAT`, `NOISE`), `auto_shader_enabled` (height/slope auto-blending), `dual_scaling_enabled`, `macro_variation_enabled`, `projection_enabled`, `shader_override_enabled`, and `buffer_shader_override_enabled` (displacement buffer).
- **`Terrain3DAssets` (`Resource`):** Holds up to **32 `Terrain3DTextureAsset`** slots and **256 `Terrain3DMeshAsset`** slots.
- **`Terrain3DInstancer`:** `32×32 m` MultiMesh foliage cell manager attached to `Terrain3D`.
- **`Terrain3DObjects`:** Parent node whose child `MeshInstance3D` nodes automatically snap vertically to terrain height edits in-editor.

## 32-Texture Channel Packing & Control Map

### Preparing Texture Sets (`Terrain3DTextureAsset`)
Each of the 32 slots takes **2 channel-packed textures** (use **Terrain3D -> Pack Textures...** in the viewport top menu):
1. `albedo_texture`: `RGB` = Albedo, `A` = Height (centered around `0.5` for smooth height-blending).
2. `normal_texture`: `RGB` = OpenGL `+Y` Normal (`unpacked_normal * (sqrt(ao) * 0.5 + 0.5)` for baked AO), `A` = Roughness (invert DirectX `-Y` normals or Smoothness maps in the packer).

**Critical Array Constraints:**
- All `albedo_texture` files must share the **exact same dimensions and Godot compression format**; all `normal_texture` files must share the same dimensions and format (albedo vs. normal sizes/formats may differ from each other).
- Recommended Godot Import settings for PNGs: `Mode: VRAM Compressed`, `High Quality: On` (BPTC; or off for DXT5), `Normal Map: Disabled`, `Mipmaps Generate: On`. Do not use EXR for albedo/normal maps.
- Unused texture slots still allocate default textures—clear unused slots from the end of the list.

### Control Map Bit Layout (`FORMAT_RF`)
Each vertex's control pixel packs `uint32` bitfields directly inside `Image.FORMAT_RF` (do not interpret as float; use `Terrain3DUtil` or `Terrain3DData.set_control_*`):
- Bits `32–28` (5b): Base texture ID (`0–31`)
- Bits `27–23` (5b): Overlay texture ID (`0–31`)
- Bits `22–15` (8b): Blend weight (`0–255`)
- Bits `14–11` (4b): UV angle (`0–15`) | Bits `10–8` (3b): UV scale (`0–7`)
- Bit `3`: Hole (`1 = hole` in visual & collision) | Bit `2`: Navigable (`1 = yes`) | Bit `1`: Autoshader (`1 = auto`)

## Heightmaps & Runtime Sculpting / Editing

- **Importing Heightmaps:** Use **16/32-bit `exr`** (real metric heights, `0` = sea level, RGB, no alpha) or **`r16`/`raw`** (16-bit unsigned). **Never use 8-bit PNG** (causes stair-stepped terracing). Ensure `region_size >= image_width / 32`. Use `addons/terrain_3d/tools/importer.tscn` or `terrain.data.import_images(images, global_pos, offset, scale)`.
- **Height & Normal Queries:**
  - Single lookup: `terrain.data.get_height(global_pos)` (`NAN` in holes or outside regions), `terrain.data.get_normal(global_pos)`.
  - Non-physics raycast: `terrain.get_intersection(src_pos, dir, gpu_mode)` (`gpu_mode=true` works on `WorldBackground` noise too, but lags 1 frame and allows max 1 call/frame).
- **Runtime Editing:** `data.set_height()`, `data.set_control_hole()`, `data.set_control_navigation()`, etc. work for sparse edits. For **bulk runtime sculpting/generation**, edit `region.get_map(Terrain3DRegion.TYPE_HEIGHT)` `Image` pixels directly, then finalize:
  ```gdscript
  for region in modified_regions.values():
      region.calc_height_range()
      region.set_modified(true)
      region.set_edited(true)
  terrain.data.update_maps(Terrain3DRegion.TYPE_HEIGHT, false)
  for region in modified_regions.values():
      region.set_edited(false)
  ```
  Note: CPU sculpting lags above brush size `200`. Call `terrain.collision.update()` if collision shapes need updating after runtime terrain edits.

## Foliage Instancing (`Terrain3DInstancer`)

- Assign `Terrain3DMeshAsset` entries in the Asset Dock (`Meshes` tab, up to 256 IDs).
- **Mesh Asset Rules & Pitfalls:**
  - **Single mesh only:** MultiMesh renders one mesh resource—join multi-part trees/props into one mesh in Blender (multiple material surfaces are OK if assigned on the `Mesh` resource; only 1 material override slot exists).
  - **Neutral transforms required:** Instancer grabs the first `Mesh` in a scene and **ignores node position/rotation/scale**. Bake origin/scale/rotation to `(0,0,0) / (1,1,1)` before export (prefer `.glb`/`.gltf`).
  - **Artist LODs & Shadows:** Name sibling `MeshInstance3D` nodes `*LOD0`, `*LOD1`, ... (up to 10; recommend `<= 4`), disable Godot's auto-LOD on import, and set `last_shadow_lod` + `shadow_impostor` to cut shadow cost.
  - **No collision on MultiMeshes:** Use `Terrain3DInstancer` for grass/non-colliding foliage (rendered in `32×32 m` cells for culling); place collidable props via nodes or tools like Scatter/AssetPlacer.
  - **Runtime placement:** Use `terrain.instancer.add_transforms(mesh_id, xforms, colors)` or `add_multimesh()`.

## Collision & NavMesh Baking

### Collision Modes (`Terrain3D.collision_mode` / `Terrain3DCollision.CollisionMode`)
- `DYNAMIC_GAME` (default): Node-less `PhysicsServer3D` shapes around `collision_target`/camera; fastest.
- `DYNAMIC_EDITOR` / `FULL_EDITOR`: Attaches a `StaticBody3D` + `CollisionShape3D` children for editor visualization or addons needing scene-tree colliders.
- `FULL_GAME`: Node-less shapes for the whole terrain at startup (high RAM on large worlds).
- `DISABLED`: No physics collision.
- **Raycast Collider Pitfall:** In `Game` modes `result["collider"]` is the `Terrain3D` node; in `Editor` modes it is the child `StaticBody3D`. Either check parent (`if node is StaticBody3D and node.get_parent() is Terrain3D: node = node.get_parent()`) or call `terrain.get_raycast_result(src, dir)`.
- **AI Enemy Perf:** Avoid capsule physics against detailed terrain for hordes—use raycasts or clamp `global_position.y = maxf(y, terrain.data.get_height(global_position))`.

### NavMesh Baking Workflow
All terrain is **non-navigable by default**.
1. Paint navigable areas using the **Navigation** brush (`Control` map bit `2`), or set via `data.set_control_navigation(pos, true)`.
2. Select `Terrain3D` -> top menu **`Terrain3D -> Set up Navigation`** (adds `NavigationRegion3D` + `NavigationMesh`, or parents `Terrain3D` / assigns group for multi-region baking).
3. Bake **ONLY via `Terrain3D -> Bake NavMesh`** (Godot's built-in `NavigationRegion3D` Bake button ignores Terrain3D).
4. **Foliage/Props in NavMesh:** Change `NavigationMesh.parsed_geometry_type` to **`Static Colliders`**. Save large `NavigationMesh` resources as binary `.res` files.
5. **Runtime NavMesh:** Use `terrain.generate_nav_mesh_source_geometry(aabb, true)` periodically around moving targets (see `CodeGeneratedDemo.tscn`), keeping `mesh_size` small and `cell_size` large enough to avoid frame spikes.

## Language & Build Notes

- **GDScript / C#:** Typed C# wrappers live under `namespace TokisanGames;` (or access via `ClassDB.Instantiate` / `Call` / `Set` reflection).
- **Lighting / Shading Caveats:** Lightmaps are **not supported** (no static mesh/UV2; use SDFGI/VoxelGI). For day/night cycles where sun dips below terrain, toggle light energy/visibility instead of adding/removing `DirectionalLight3D` nodes mid-frame, or enable `cull_disabled` in a shader override.
- **Source Build (`SConstruct`):** Uses `godot-cpp` + SCons (`ARGUMENTS.setdefault("api_version", "4.6")`); outputs shared library under `project/addons/terrain_3d/bin/`.
