---
name: godot-voxel
description: Zylann's C++ volumetric voxel engine for Godot 4 (VoxelTerrain, VoxelLodTerrain, blocky/Transvoxel meshers, VoxelGeneratorGraph, VoxelStream, VoxelTool, and VoxelInstancer). Use when building blocky or smooth destructible 3D terrains in Godot 4, writing custom voxel generators/streams, configuring chunk LOD/collisions/instancing, or building as an engine module vs GDExtension.
---

# Voxel Tools for Godot (`godot_voxel`)

C++ volumetric terrain and voxel engine for Godot 4 available as either a **custom Godot Engine module** (`modules/voxel`) or a **GDExtension** (`addons/zylann.voxel/`). Supports overhangs, caves, real-time editing, chunk streaming, blocky meshes, and smooth LOD via Transvoxel.

## Core Architecture & Terrain Nodes

1. **Terrain Nodes (inherit `VoxelNode`):**
   - `VoxelTerrain`: Uniform cubic chunk grid (fixed LOD, `16×16×16` blocks by default; `32` reduces draw calls). Best for Minecraft-style blocky worlds or bounded smooth volumes.
   - `VoxelLodTerrain`: Octree-based variable LOD for huge/planetary smooth terrains (`VoxelMesherTransvoxel` recommended; limited blocky LOD support).
2. **`VoxelViewer` (Required):** Add at least one `VoxelViewer` (typically under the player or `Camera3D`). **Nothing loads or generates without a `VoxelViewer`.** Controls `view_distance`, `requires_visuals`, `requires_collisions`, `enabled_in_editor`, and `view_distance_vertical_ratio` (on `VoxelLodTerrain` clipbox mode).
3. **`VoxelBuffer` Channels & Bit Depths:**
   - `VoxelBuffer.CHANNEL_TYPE` (8/16-bit): Model IDs (`0..65535`) for `VoxelMesherBlocky`.
   - `VoxelBuffer.CHANNEL_SDF` (8/16/32-bit, default 16-bit `[-500, 500]`): Signed distance (`< 0` = solid, `> 0` = air, `0` = surface) for `VoxelMesherTransvoxel`. Avoid 8-bit SDF with LOD (quantization causes blocky artifacts).
   - `VoxelBuffer.CHANNEL_COLOR`: Direct RGB/palette index for `VoxelMesherCubes`.
   - `VoxelBuffer.CHANNEL_INDICES` / `CHANNEL_WEIGHTS`: Per-voxel smooth surface texturing.

## Meshers & Texturing

### Blocky (`VoxelMesherBlocky`)
- Assign a `VoxelBlockyLibrary` (list of `VoxelBlockyModel*` by ID, `0` = air by convention) or experimental `VoxelBlockyTypeLibrary` (`VoxelBlockyType` + `VoxelBlockyAttribute`).
- Never instantiate base `VoxelBlockyModel` directly; use `VoxelBlockyModelEmpty`, `VoxelBlockyModelCube` (set `atlas_size_in_tiles` + per-face tile coords), `VoxelBlockyModelMesh` (origin at `(0,0,0)` lower corner, vertices inside `0..1`, prefer `.obj` for Mesh resources, faces on unit cube bounds are culled automatically), or `VoxelBlockyModelFluid` (paired with shared `VoxelBlockyFluid` resource; encodes flow axis/state into `UV.x`/`UV.y`).
- Enable **Vertex Color -> Use as Albedo** on `StandardMaterial3D` to display baked blocky ambient occlusion.
- Tune `transparency_index` and `culls_neighbors` for transparent blocks (e.g., glass vs leaves). Keep non-strip mesh data if exporting as dedicated server with mesh collision.

### Smooth (`VoxelMesherTransvoxel`) & Vertex Shader Stitching
- Uses `CHANNEL_SDF`. For `VoxelLodTerrain`, assign a `ShaderMaterial` that consumes `u_transition_mask` and `CUSTOM0` to stitch LOD seams and cull inactive transition geometry:
  ```glsl
  uniform int u_transition_mask;
  vec3 get_transvoxel_position(vec3 vertex_pos, vec4 fdata) {
      int idata = floatBitsToInt(fdata.a);
      int tmask = u_transition_mask & 0xff;
      int cell_mask = (idata >> 0) & 63;
      int vert_mask = (idata >> 8) & 63;
      float t = float((tmask & cell_mask) != 0) * float((vert_mask & ~tmask) == 0);
      vec3 pos = mix(vertex_pos, fdata.xyz, t);
      int itransition = (idata >> 16) & 0xff;
      return pos * float(itransition == 0 || (itransition & u_transition_mask) != 0);
  }
  void vertex() { VERTEX = get_transvoxel_position(VERTEX, CUSTOM0); }
  ```
- **Smooth texturing:** Classic UVs do not exist; use triplanar/procedural shaders (normal/height) or voxel-stored formats:
  - **Single:** `VoxelFormat.indices_depth = 8-bit`, mesher texture mode `Single`; paint via `VoxelTool` with `MODE_SET` on `CHANNEL_INDICES`.
  - **Mixel4:** Up to 4 blended indices/weights (16 textures max, 4-bit weights) packed in 16-bit `CHANNEL_INDICES` + `CHANNEL_WEIGHTS`; no duplicate indices per voxel; edit with `VoxelTool` texture mode.

## Generators (`VoxelGenerator`)

Built-in CPU generators: `VoxelGeneratorFlat`, `VoxelGeneratorWaves`, `VoxelGeneratorImage`, `VoxelGeneratorNoise2D`, `VoxelGeneratorNoise`, `VoxelGeneratorMultipassCB`, **`VoxelGeneratorGraph`**, and **`VoxelGeneratorScript`**.

- **`VoxelGeneratorGraph`:** Node-graph SDF/type generator (`InputX/Y/Z` -> `SdfOutput` or `Select` -> `OutputType`). Can also act as a procedural brush via `InputSDF` on `VoxelLodTerrain`, and supports series (point-cloud) queries used by `VoxelInstancer` SDF snapping. Access/modify named nodes from script via `generator.get_main_function()` (`VoxelGraphFunction.find_node_by_name()`).
- **`VoxelGeneratorScript`:** Extend in GDScript/C# and override `_get_used_channels_mask()` and `_generate_block(buffer: VoxelBuffer, origin: Vector3i, lod: int)`.
  - **Thread-safety:** `_generate_block` runs concurrently on background worker threads! Pre-bake lazy resources like `Curve.bake()` in `_init()`, protect shared state with `Mutex`, and scale coordinates by `1 << lod` (`rx << lod`).

## Streams & Persistence (`VoxelStream`)

- `VoxelStreamSQLite`: Single SQLite `.sqlite` database; supports saving both voxels and persistent `VoxelInstancer` data.
- `VoxelStreamRegionFiles`: Minecraft-style multi-file region folder (voxels only).
- `VoxelStreamScript`: Custom script subclass (`_load_block`, `_save_block`).

### Async Saving & File-Locking Caveats
- Loading and saving run **asynchronously** on background threads. Edits persist only when blocks unload or when `terrain.save_modified_blocks()` is called (returns a `VoxelSaveCompletionTracker`).
- **Do not embed a `VoxelStream` inside a `.tscn` scene** if switching save slots at runtime—Godot caches the scene resource and pending async tasks can write to the wrong save. Instantiate a fresh `VoxelStreamSQLite.new()` at runtime.
- **Avoid editor/game lock conflicts:** Closing a running test with the Godot Editor's **Stop** button kills the process without flushing async saves (`SIGKILL`); quit cleanly via `get_tree().quit()`. Also avoid pointing both the editor preview and running game at the same SQLite/region path simultaneously.

## Real-Time Editing (`VoxelTool`)

Acquire via `var vt: VoxelTool = terrain.get_voxel_tool()` and cache the reference (each `get_voxel_tool()` call allocates a wrapper).

```gdscript
var vt: VoxelTool = terrain.get_voxel_tool()
vt.channel = VoxelBuffer.CHANNEL_SDF # or CHANNEL_TYPE / CHANNEL_COLOR
vt.mode = VoxelTool.MODE_REMOVE      # MODE_ADD, MODE_SET, MODE_SMOOTH, MODE_TEXTURE_PAINT
if vt.is_area_editable(AABB(hit_pos - Vector3.ONE * 4, Vector3.ONE * 8)):
    vt.do_sphere(hit_pos, 3.0)       # Also: do_box, do_path, do_point, do_mesh, grow_sphere, copy/paste
```

- **Edit limits:** Edits fail/cancel outside loaded chunks (`is_area_editable()`) and on `VoxelLodTerrain` are only allowed at **LOD 0**. Use bulk ops (`do_sphere`, `do_box`, `paste`) rather than per-voxel `set_voxel()` loops.

## Instancing (`VoxelInstancer`)

Add `VoxelInstancer` as a direct child of `VoxelTerrain` or `VoxelLodTerrain` with a `VoxelInstanceLibrary`:
- **`VoxelInstanceLibraryMultiMeshItem`:** High-density GPU instancing; supports up to 4 manual mesh LODs, optional collisions converted from a `Scene` (`PhysicsBody` -> `MeshInstance_LOD0..3` + `CollisionShape*`, using `material_override` or mesh-surface materials), and `snap_to_generator_sdf_enabled` (works with `VoxelGeneratorGraph`, ignores runtime edits unless `persistent = true`).
- **`VoxelInstanceLibrarySceneItem`:** Spawns full `Node3D` scenes (heavy—keep density low; never put the terrain scene itself inside the library or Godot crashes on cyclic recursion).
- Set `up_mode = UP_MODE_SPHERE` for spherical planets; set `persistent = true` (requires `VoxelStreamSQLite`) so dug-up foliage does not respawn when chunks reload.

## Collisions, Streaming & Performance Settings

- **Collisions:** `generate_collisions = true` builds static concave mesh colliders per chunk on demand when `VoxelViewer.requires_collisions = true`. For fast Minecraft-like AABB movement on blocky `VoxelTerrain` without triangle-mesh overhead, use `VoxelBoxMover.get_motion(pos, motion, aabb, terrain)` (reads `VoxelBlockyModel.collision_mask`).
- **Project Settings (`ProjectSettings`):**
  - Thread pool: `voxel/threads/count/minimum`, `margin_below_maximum`, `ratio_over_maximum` (requires restart; never 0 threads).
  - Frame budget: `voxel/threads/main/time_budget_ms` (limits main-thread mesh/collider upload time per frame).
  - Vulkan fast-movement hitching: freeing many small `16×16×16` mesh buffers is slow on main thread; raise mesh block size to `32` or reduce LOD/view distance.
  - C# false-positive refcount errors: disable `voxel/ownership_checks`.

## Module vs. GDExtension Build Caveats

| Aspect | Engine Module (`SCsub`) | GDExtension (`SConstruct`, Godot 4.4.1+) |
|---|---|---|
| Setup | Place repo at **`godot/modules/voxel`** (exact folder name required) and recompile Godot + export templates. | Set `GODOT_CPP_PATH` (or edit `SConstruct`) and run `scons platform=<os> target=<editor|template_release>`; drop `addons/zylann.voxel/` into project. |
| Features | Full feature set including `FastNoise2` (x86 SIMD) & Tracy (`tracy=yes`). | **No `FastNoise2`**; less battle-tested; exclude `addons/zylann.voxel/editor` on export to strip editor icons. |
| SCons Options | `voxel_tests=yes`, `voxel_smooth_meshing`, `voxel_modifiers`, `voxel_sqlite`, `voxel_instancer`, `voxel_gpu`, `voxel_mesh_sdf`, `voxel_vox`, `voxel_fast_noise_2`, `tracy`. | Same `voxel_*` flags (except `tracy`, `voxel_fast_noise_2`, `voxel_werror`). |
| C# Support | Requires compiling custom Godot .NET SDK to local NuGet feed. | No generated C# bindings—must use `ClassDB.Instantiate(...)`, `.Call()`, `.Set()`, `.Get()` (high overhead). |
| Coexistence / Web | Do not load the GDExtension in a custom Module build (class name conflicts). | Web (`platform=web`) requires **exact Emscripten version match** with Godot's web export template. |
