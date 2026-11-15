---
name: material-maker
description: "Godot-based procedural PBR material authoring, 2D/3D SDF & shader graph editor, and 3D texture painting tool (`.ptex`). Supports headless CLI material export and shader/texture generation for Godot 3/4, Unity (3D/URP/HDRP), Unreal Engine 4/5, Blender, and glTF."
license: MIT
metadata:
  repository: "https://github.com/RodZill4/material-maker"
  docs: "https://rodzill4.github.io/material-maker/doc/"
---

# Material Maker — Procedural PBR & 3D Texture Painting (`material-maker`)

Open-source procedural PBR material authoring and 3D model texture-painting application built on **Godot Engine** (`MIT`). Stores procedural node graphs and painted layers in `.ptex` project files and exports baked PBR texture maps, shaders, and engine-native material assets for **Godot**, **Unity**, **Unreal Engine**, **Blender**, and **glTF**.

---

## Installation & Launch

- **Package managers**:
  - Windows (Scoop): `scoop bucket add extras && scoop install material-maker`
  - Windows (Chocolatey): `choco install material-maker` (or `material-maker.portable`)
  - macOS (Homebrew): `brew install material-maker`
  - Desktop installers: itch.io or Steam
- **From source**: Open `project.godot` in Godot 4 or launch via the Godot binary.
- **Launch with a `.ptex` file**:
  ```powershell
  material_maker path/to/material.ptex --no-splash
  ```

---

## Procedural `.ptex` Node & SDF Graphs

Material Maker uses Godot's `GraphEdit` to compose resolution-independent GLSL/Godot Shading Language node graphs:

- **Material Root Nodes** (`addons/material_maker/nodes/material*.mmg`): One material node per graph defines preview shading, PBR channels, and export targets:
  - **Static PBR Material** (`material.mmg`): Outputs baked Albedo, Metallic, Roughness, Emission, Normal, Depth, Ambient Occlusion, and Subsurface Scattering maps.
  - **3D Material** (`material_3d.mmg`): Shader driven by world or local 3D surface coordinates (triplanar/procedural 3D space).
  - **Dynamic PBR Material** (`material_dynamic.mmg`): Generates live, animated, resolution-independent shaders instead of static bitmaps.
  - **Raymarching Material** (`material_raymarching.mmg`): Raymarches a 3D SDF input with Albedo, Metallic, and Roughness shading.
  - **Tesselated Material** (`material_tesselated.mmg`), **Unlit Material** (`material_unlit.mmg`), and **Dynamic Sky** (`material_dynamic_sky.mmg`).
- **2D Signed Distance Functions (SDF)**: Inigo Quilez–based 2D primitives (`sdCircle`, `sdBox`, `sdRoundedBox`, `sdPolygon`, `sdStar`, `sdArc`, etc.), boolean/smooth boolean/morph/repeat/annular operators, `sd_mask_to_sdf`, and `sdShow` to rasterize grayscale masks.
- **3D SDF Nodes**: 3D primitives (`Sphere`, `Box`, `Cylinder`, `Capsule`, `Cone`, `Torus`, `Hex Prism`, `Octahedron`, etc.), boolean/smooth-boolean/elongation/repeat/extrusion/revolution/`sdf_fbm` operators, `Color` index tagging, and `3D SDF Render` (outputs heightmap + normal map) or direct connection to `Raymarching Material`.
- **Custom Map Export Nodes**:
  - **Export** node: Saves an individual node's texture (PNG, JPG, WebP, or EXR) with template placeholders (`$node`, `$project`, `$idx`, `$resolution`) during project export or **Quick Export**.
  - **Auto Export** node: Automatically re-saves the connected texture whenever upstream graph inputs change.

---

## 3D Texture Painting (`File -> New paint project`)

- **Supported meshes**: Single-submesh `.obj`, `.glb`, `.gltf`, or `.fbx` files with UV texture coordinates.
- **Painting engines**:
  - **View-space projection**: Paints cleanly across UV seams (stretches where surfaces slope sharply away from the camera).
  - **Texture-space painting**: Paints directly in UV texture space with zero view distortion (keep full brush footprint within visible UV islands).
- **Tools & Channels**: Freehand, Freehand Line, Straight Line, Stamp, Color Picker, Fill, Eraser, and ID-map Mask Selector.
- **Procedural Brushes**: Brush graphs terminate at a `Brush` node driving `albedo`, `metallic`, `roughness`, `emission`, `normal`, `occlusion`, and `depth` channels simultaneously (`material_maker/panels/paint/export.gd` compiles painted layers into a `material` node for engine export).

---

## Headless / CLI Export (`parse_args.gd`)

Batch-export `.ptex` files (wildcards or Material Maker website IDs supported) from the command line:

```powershell
material_maker --export-material -t "Godot/Godot 4 Standard" -o "path/to/out" --size 2048 "materials/*.ptex"
```

### CLI Options (`parse_args.gd`)

| Flag | Default | Description |
|---|---|---|
| `--export` or `--export-material` | — | Enables CLI batch export mode and quits when finished. |
| `-t`, `--target <TARGET>` | `"Godot/Godot 4 Standard"` | Export profile name. If not an exact match, Material Maker selects the closest available profile by string similarity. |
| `-o`, `--output-dir <DIR>` | Current working directory | Destination folder (created if missing). |
| `--output-file <PATTERN>` | `"%f"` | Output prefix pattern: `%f` (file basename), `%N` (material name), `%A` (author), `%n` / `%a` (lowercase snake_case). |
| `--size <PIXELS>` | `2048` | Square resolution for baked output maps. |
| `<INPUTS...>` | — | `.ptex` file paths, wildcard globs (e.g. `*.ptex`), or `website:<id>` / `website:<start>-<end>`. |

---

## Engine Export Targets & Workflows

Verified export targets defined in `addons/material_maker/nodes/material*.mmg` and `material_maker/doc/export.rst`:

| Engine / Format | Export Targets | Generated Output & Integration |
|---|---|---|
| **Godot 4 / 3** | `Godot/Godot 4 Standard`, `Godot/Godot 4 ORM`, `Godot/Godot 3 Spatial`, `Godot/Godot 4`, `Godot/Godot 3`, `Godot 4/CanvasItem`, `Godot 4/Spatial`, `Godot 4/Dynamic Sky` | Generates textures + ready-to-use `.tres` material/shader resources. Additionally, copying `addons/material_maker` into a Godot project activates `ptex_import.gd` (`EditorImportPlugin`) to import `.ptex` files directly as `StandardMaterial3D` (`Render in game` or `Prerender` presets). |
| **Unity** | `Unity/3D`, `Unity/URP`, `Unity/HDRP`, `Unity` | Generates textures + configured `.mat` material file ready for direct placement in `Assets/`. |
| **Unreal Engine 5** | `Unreal/Unreal Engine 5` | Outputs textures, shader file, and a Python script using `material_maker/misc/export/mm.py` (`unreal.MaterialEditingLibrary`). Add Material Maker's `export` directory to Unreal **Project Settings → Plugins/Python → Additional paths**, then paste/run the generated script path in Unreal's Python console. |
| **Unreal Engine 4** | `Unreal/Unreal Engine 4` (or `Unreal`) | Outputs PNG textures + `.mm2ue` file containing Custom node HLSL/setup steps referencing base `.uasset` templates in `material_maker/misc/export/` (`material.uasset`, `material_3d.uasset`, `material_dynamic.uasset`, `material_raymarching.uasset`, `material_unlit.uasset`). |
| **Blender** | `Blender` | Outputs `_albedo.png`, `_rough.exr`, `_metal.exr`, `_normal.png`, `_displace.exr`, `_sss.exr`, `_emission.png`, `_occlusion.exr`. Import in one step via Blender's **Node Wrangler** `Add Principled Texture Setup` (`Ctrl+Shift+T`). |
| **glTF** | `GLTF/Plane` | Exports `_albedo.png`, `_orm.png`, `_emission.png`, `_normal.png` plus a sample `.gltf` plane. |
