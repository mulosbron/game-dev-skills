# Godot 4.x Pixel Texture Guide
### Pixel-art texture pipeline for 2D • 3D • 2.5D FPS • 2.5D Top-Down games — complete reference document

| Target Version | Godot 4.3+ (differences for 4.0–4.2 are noted) |
| :--- | :--- |
| **Format** | Reference document: settings tables + complete code examples |
| **Level** | Fast fundamentals, detailed advanced sections (PSX shader, SubViewport render) |

---

## Table of Contents
0. [Quick Decision Table](#0-quick-decision-table)
1. [Shared Foundation: Three Golden Rules](#1-shared-foundation-three-golden-rules)
2. [2D Games](#2-2d-games)
3. [3D Games (Low-Poly + Pixel Texture)](#3-3d-games-low-poly--pixel-texture)
4. [2.5D FPS (Doom/Wolfenstein Style)](#4-25d-fps-doomwolfenstein-style)
5. [2.5D Top-Down](#5-25d-top-down)
6. [Shader Reference](#6-shader-reference)
7. [Automation and Batch Processing](#7-automation-and-batch-processing)
8. [External Tool Export Settings (Aseprite / Blender)](#8-external-tool-export-settings-aseprite--blender)
9. [Troubleshooting](#9-troubleshooting)
10. [Quick Checklist](#10-quick-checklist)

---

## 0. Quick Decision Table
Each game type produces its "pixel look" in a different layer. Before diving into the guide, find the row for your project:

| Game Type | Scene Root | Where Does the Pixel Look Come From? | Critical 3 Settings |
| :--- | :--- | :--- | :--- |
| **2D** | `Node2D` | Canvas filter + stretch settings | Default Filter = Nearest, Stretch Mode = canvas_items, Scale Mode = integer |
| **3D (low-poly)** | `Node3D` | Material filter + texel density | Material Texture Filter = Nearest, Mipmaps = Off, Shading = Per-vertex |
| **2.5D FPS** | `Node3D` + `CanvasLayer` | Sprite3D billboard + low-resolution render | Billboard = Enabled, Alpha Cut = Discard, SubViewport stretch_shrink |
| **2.5D Top-Down** | `Node2D` (Y-sort) or `Node3D` (HD-2D) | Y-sort ordering or Sprite3D billboard | y_sort_enabled, Sprite3D Billboard = Fixed Y, pivot = foot point |

---

## 1. Shared Foundation: Three Golden Rules
All four game types rest on the same three fundamentals. If these break, the visuals break no matter what else you do; once set up right, everything else is detail.

### 1.1 Rule 1 — Same palette everywhere
* Author all textures from a single palette (16–64 colors). Grab a preset palette from Lospec or lock it in Aseprite.
* Use exact color values in the palette, not "close enough" shades. If two shades of blue appear across different sprites, ground and character blend together.
* Export PNG between tools to avoid color drift; never use JPG (lossy compression corrupts pixels).
* If in-game post-process color reduction is needed, use the posterize + dither shader in §6.2; however, your goal should be locking the palette during asset production (§7.1).

### 1.2 Rule 2 — Keep pixel density (PPU) consistent
PPU (Pixels Per Unit): how many texture pixels map to 1 world unit. Decide once at project start (common choices: 16, 32, 48) and never mix them. If a 16 PPU character stands next to a 32 PPU crate in the same scene, one's pixels look chunkier than the other's — the most common mistake in retro projects.

| Context | PPU Equivalent | Example (PPU = 32) |
| :--- | :--- | :--- |
| **2D** | 1 texture pixel = 1 canvas unit; scaling via `Camera2D.zoom` | `zoom = Vector2(4, 4)` → 4× on screen |
| **3D** | `pixel_size = 1 / PPU` (meters/pixel) | `pixel_size = 0.03125` |
| **Sprite3D (2.5D)** | 32 px texture → 1 meter height | `pixel_size = 0.03125` |
| **3D wall tiling** | meters/texel = mesh size / texture resolution | 3 m wall, 96 px texture → 1 texel = 3.125 cm |

### 1.3 Rule 3 — Filtering: Nearest, at every layer
If textures are sampled with "Linear" at any layer, pixels blur. In Godot 4, filtering can be set in four places; the hierarchy overrides bottom-up (node setting overrides project default):

| Layer | Where | When Used |
| :--- | :--- | :--- |
| **1. Project default** | Project Settings → `rendering/textures/canvas_textures/default_texture_filter = Nearest` | Mandatory in all 2D projects. Does not affect 3D. |
| **2. Node (CanvasItem)** | `Texture Filter = Nearest` on each Sprite2D/TileMapLayer/Control | Only when a single node needs a different filter |
| **3. 3D material** | StandardMaterial3D → `Texture Filter = Nearest` | Per material in all 3D and 2.5D |
| **4. Shader** | `filter_nearest` hint on uniform (§6) | When using a custom shader (overrides material filter) |

> [!NOTE]
> Godot 3's "texture import Filter" flag was removed in Godot 4. In Godot 4, filtering is set in one of the layers above (usually project default or material), not at import time. This is Godot's equivalent of Unity's "Filter Mode = Point".

### 1.4 Project-Wide Settings (common to every type)
In Project Settings (with Project → Project Settings → Advanced Settings enabled):

| Setting | Full Path | Value | Purpose |
| :--- | :--- | :--- | :--- |
| **Default Texture Filter** | `rendering/textures/canvas_textures/default_texture_filter` | `Nearest` (0) | Eliminates blurriness across all 2D rendering |
| **Stretch Mode** | `display/window/stretch/mode` | `canvas_items` (or `viewport`) | Preserves pixel aspect across window sizes |
| **Stretch Aspect** | `display/window/stretch/aspect` | `keep` | Prevents stretch distortion |
| **Stretch Scale Mode** | `display/window/stretch/scale_mode` | `integer` (4.2+) | Integer scaling → pixels scale evenly (on 4.0–4.1 open window at fixed resolution) |
| **Snap 2D Transforms** | `rendering/2d/snap/snap_2d_transforms_to_pixel` | `On` (`true`) | Stops jitter on sub-pixel camera movement |
| **MSAA 3D** | `rendering/anti_aliasing/quality/msaa_3d` | `Disabled` (0) | Anti-aliasing in 3D ruins the crisp pixel look |
| **Screen Space AA** | `rendering/anti_aliasing/quality/screen_space_aa` | `Disabled` (0) | Same purpose (FXAA off) |

**Stretch Mode choice (reference):**
* `canvas_items`: 2D canvas renders at window resolution, sprites upscale with Nearest; UI text stays sharp (recommended starting point for most pixel-art games).
* `viewport`: Entire root viewport (including 2D and 3D) renders at base resolution and upscales (Full retro look: PS1-era render, low-res 3D + UI).

### 1.5 Texture Import Settings
When PNGs are imported in Godot 4, they are processed as `CompressedTexture2D`:

| Import Option | For 2D Sprite | For 3D Albedo | Why |
| :--- | :--- | :--- | :--- |
| **Compress > Mode** | `Lossless` (0) | `Lossless` (0) | VRAM Compressed corrupts palette colors and creates blocky artifacts |
| **Mipmaps > Generate** | `Off` (`false`) | `Off` (see note) | Mipmaps melt pixels at a distance |
| **Detect 3D** | Doesn't matter | `Off` (`false`) | When enabled, Godot switches settings to VRAM + mipmaps once used in a 3D material |
| **Process > Fix Alpha Border** | `On` (`true`) | `On` (`true`) | Cleans color bleeding (black fringe) on transparent edges |

> [!TIP]
> **Mipmap note:** If distant object shimmer becomes severe, as an exception use `Mipmaps > Generate = On` + `Texture Filter = Nearest With Mipmaps` (enum 2) on the material.

### 1.6 Folder Structure
```text
res://
├─ assets/
│  ├─ raw/              # Aseprite/Blender originals — place a .gdignore file inside!
│  ├─ sprites/          # processed PNGs (shared by 2D + Sprite3D)
│  ├─ tilesets/
│  ├─ models/           # .glb files
│  ├─ materials/        # extracted .tres materials (§3.5)
│  └─ shaders/          # .gdshader files (§6)
├─ scenes/
├─ scripts/
└─ import_defaults.md   # your chosen import settings
```
*Critical:* Place an empty `.gdignore` file in `raw/`. Godot will completely ignore that folder.

---

## 2. 2D Games

### 2.1 Project Settings
* Viewport Size: `display/window/size/viewport_width` / `viewport_height` = Base resolution (e.g. 640×360, 480×270).
* Stretch Scale Mode: `integer`.
* Default Texture Repeat: `Disabled`.

### 2.2 Camera (`Camera2D`)
```gdscript
# pixel_camera_2d.gd — simple pixel-perfect camera
class_name PixelCamera2D
extends Camera2D

@export var pixel_scale: int = 4  # PPU scale factor

func _ready() -> void:
    zoom = Vector2(pixel_scale, pixel_scale)

func _physics_process(_delta: float) -> void:
    # Lock camera position to pixel grid (stops jitter)
    global_position = global_position.floor()
```

### 2.3 TileMapLayer (Godot 4.3+) / TileMap
* **TileSet source:** Use a single atlas PNG.
* **Use Texture Padding:** `On` (default) — adds a 1 px transparent border to prevent texture bleeding.
* **Margins / Separation:** Leave 1–2 px spacing between tiles.
* **Texture Filter:** `Nearest`.
* **Y Sort Origin:** Pixel offset for tall tiles (foot point).

### 2.4 Animation (`AnimatedSprite2D` + `SpriteFrames`)
Keep FPS at 6–12 FPS for retro feel. Ensure `Texture Filter = Nearest`.

---

## 3. 3D Games (Low-Poly + Pixel Texture)

### 3.1 StandardMaterial3D Settings
| Property | Inspector Path | Value | Purpose |
| :--- | :--- | :--- | :--- |
| **Texture Filter** | Material Properties → Texture Filter | `Nearest` (0) | Eliminates blurriness |
| **Albedo Texture** | Albedo → Texture | Pixel PNG | Color map (Lossless import) |
| **Shading Mode** | Shading → Mode | `Per-vertex` | Computes lighting at vertices → retro gradients |
| **Metallic** | Metallic | `0.0` | Prevents reflections from killing pixels |
| **Roughness** | Roughness | `1.0` | Disables specular shine |
| **Specular** | Specular | `0.0` | Suppresses surface gloss |
| **Vertex Color** | Vertex Color → Use as Albedo | `On` if needed | Blender vertex color multiplies with albedo |
| **Transparency** | Transparency → Mode | `Disabled` / `Alpha Scissor` (Threshold 0.5) | Crisp pixel edges |

### 3.2 Texel Density Formula
$$\text{meters/texel} = \frac{\text{mesh surface length (m)}}{\text{texture pixels covering that surface}}$$
* Example: 3 m wall, 96 px texture → 1 texel = 3.125 cm.

### 3.3 Lighting & Environment
* **DirectionalLight3D:** Shadow optional (usually off for retro).
* **WorldEnvironment Ambient:** Color + constant color.
* **Tonemap:** `Linear`.
* **Glow / SSS / AO:** `Off`.

### 3.4 glTF Import Flow (Blender → Godot)
1. Export the model as `.glb`.
2. Select the `.glb` in FileSystem → Import dock → Advanced → Actions… → **Extract Materials** (`res://assets/materials/`).
3. Use **Extract Textures** to extract textures into `res://assets/sprites/` (Lossless, Mipmaps Off, Detect 3D Off).
4. Batch material filtering EditorScript:
```gdscript
# tools/set_nearest_materials.gd
@tool
extends EditorScript

const ROOT := "res://assets"

func _run() -> void:
    _scan(ROOT)
    print("Material filters updated.")

func _scan(path: String) -> void:
    var dir := DirAccess.open(path)
    if dir == null:
        push_warning("Folder not found: " + path)
        return
    dir.list_dir_begin()
    var fname := dir.get_next()
    while fname != "":
        var full := path.path_join(fname)
        if dir.current_is_dir() and not fname.begins_with("."):
            _scan(full)
        elif fname.ends_with(".tres") or fname.ends_with(".material"):
            var res := load(full)
            if res is BaseMaterial3D:
                res.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
                ResourceSaver.save(res, full)
                print("[ok] ", full)
        fname = dir.get_next()
```

---

## 4. 2.5D FPS (Doom/Wolfenstein Style)

### 4.1 Scene Structure
```text
Main (Node)
├─ Render (SubViewportContainer)     # For low resolution (Stretch, Stretch Shrink=3..6, Nearest)
│  └─ World (Node3D)
│     ├─ Environment (WorldEnvironment)
│     ├─ Light (DirectionalLight3D)
│     ├─ Map (Node3D or GridMap)
│     ├─ Enemies (Node3D)            # CharacterBody3D + Sprite3D
│     └─ Player (CharacterBody3D)
│        └─ Camera (Camera3D)
└─ HUD (CanvasLayer)                 # Full-resolution UI layer
   └─ Weapon (Sprite2D)
```

### 4.2 Sprite3D Billboard Settings
* **Billboard:** `Enabled` (faces the camera every frame).
* **Alpha Cut:** `Discard` (Threshold 0.5; writes to depth buffer, fixes sorting issues).
* **Texture Filter:** `Nearest`.
* **Pixel Size:** `1 / PPU` (`0.03125` for PPU=32).
* **Pivot:** `Centered = Off`, `Offset = Vector2(-w/2, -h)` (bottom-center pivot).

### 4.3 Weapon Sprite (`Sprite2D` on `CanvasLayer`)
```gdscript
# weapon_sprite.gd — places weapon sprite at bottom-center at integer scale
extends Sprite2D

@export var scale_factor: int = 4

func _ready() -> void:
    scale = Vector2(scale_factor, scale_factor)

func _process(_delta: float) -> void:
    var vp := get_viewport_rect().size
    var half := texture.get_size() * scale_factor / 2.0
    position = Vector2(vp.x / 2.0 - half.x, vp.y - texture.get_size().y * scale_factor)
```

### 4.4 Low-Resolution SubViewport Render
* `SubViewportContainer`: Stretch = `On`, Stretch Shrink = `6` (1080p → 180p render), Texture Filter = `Nearest`.
* `SubViewport`: MSAA 3D = `Disabled`, Screen Space AA = `Disabled`.

---

## 5. 2.5D Top-Down

### 5.1 Approach A: Pure 2D + Y-Sort
* World (`Node2D`): `y_sort_enabled = On`.
* Walls/Objects (`TileMapLayer`): `y_sort_enabled = On`, `Y Sort Origin` configured.
* Character Sprite: `Centered = Off`, `Offset = Vector2(-w/2, -h)` (foot pivot).

### 5.2 Approach B: HD-2D (3D World + Sprite3D Characters)
* `Sprite3D` Billboard: `Fixed Y` (does not lie flat under a tilted camera).
* `Alpha Cut`: `Discard`.
* `Shaded`: `On` (for day/night cycle and 3D lights).
* Camera Tilt: 50–60°, FOV 40–55°.

---

## 6. Shader Reference

### 6.1 PSX-Style Spatial Shader (`psx_retro.gdshader`)
```glsl
// psx_retro.gdshader
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, shadows_disabled;

uniform sampler2D base_tex : source_color, filter_nearest, repeat_enable;
uniform float vertex_snap_res : hint_range(120.0, 1080.0) = 240.0; // virtual vertical resolution
uniform bool affine_mapping = true;
uniform float color_levels : hint_range(2.0, 256.0) = 32.0;

varying vec2 uv_affine;
varying float clip_w;

void vertex() {
    vec4 clip = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
    if (clip.w > 0.0001) {
        // Vertex snapping: lock vertices to a virtual grid in NDC space
        vec3 ndc = clip.xyz / clip.w;
        float half_res = vertex_snap_res * 0.5;
        ndc.xy = floor(ndc.xy * half_res + 0.5) / half_res;
        clip.xyz = ndc * clip.w;
    }
    POSITION = clip;
    uv_affine = UV * clip.w;
    clip_w = max(clip.w, 0.0001);
}

void fragment() {
    vec2 uv = affine_mapping ? uv_affine / clip_w : UV;
    vec3 col = texture(base_tex, uv).rgb * COLOR.rgb;
    col = floor(col * color_levels + 0.5) / color_levels; // posterize
    ALBEDO = col;
}
```

### 6.2 2D Posterize + Ordered Dither Shader (`posterize_dither.gdshader`)
```glsl
// posterize_dither.gdshader
shader_type canvas_item;

uniform float levels : hint_range(2.0, 64.0) = 8.0;          // steps per channel
uniform float dither_strength : hint_range(0.0, 1.0) = 1.0;  // 0 = flat posterize

// 4x4 Bayer matrix (0..1 range)
const mat4 BAYER = mat4(
    vec4(0.000, 0.500, 0.125, 0.625),
    vec4(0.750, 0.250, 0.875, 0.375),
    vec4(0.188, 0.688, 0.062, 0.562),
    vec4(0.812, 0.312, 0.938, 0.438)
);

void fragment() {
    vec4 c = COLOR;
    ivec2 px = ivec2(FRAGCOORD.xy) % 4;
    float d = (BAYER[px.x][px.y] - 0.5) * dither_strength;
    c.rgb = floor((c.rgb + d / levels) * levels + 0.5) / levels;
    COLOR = c;
}
```

---

## 7. Automation and Batch Processing

### 7.1 Python + Pillow Batch Pipeline
Usage:
```bash
python tools/godot_pixel_tool.py batch-process --scale 4 --alpha 128 --src raw_assets --dst res://assets/sprites
```

### 7.2 Aseprite CLI Automation
```bash
# Horizontal strip export
aseprite -b character.aseprite --sheet-type horizontal --sheet character.png --data character.json
```

---

## 8. External Tool Export Settings

### 8.1 Aseprite
* Color Mode: `Indexed` (lock the palette).
* Resize: `Nearest Neighbor`.
* Extrude: `Off` (Godot's Use Texture Padding handles this on the engine side).

### 8.2 Blender → glTF (.glb)
* Format: `glTF Binary (.glb)`.
* +Y Up: On.
* Mesh: `UVs` and `Normals` enabled. Tangents disabled.
* Materials: Export `StandardMaterial3D`.
* Vertex Colors: Enabled if present.
* Keep Texel Density uniform across the UV grid.

---

## 9. Troubleshooting

| # | Issue | Solution |
| :--- | :--- | :--- |
| 1 | Sprites are blurry | `rendering/textures/canvas_textures/default_texture_filter = Nearest` (0) |
| 2 | 3D model is blurry | Set `Texture Filter = Nearest` on material |
| 3 | Colors shifted, blocky artifacts | Import: `Compress > Mode = Lossless` |
| 4 | Texture suddenly broke in 3D | Import: `Detect 3D = Off` |
| 5 | Thin lines between TileMap tiles | TileSet: `Use Texture Padding = On`, Separation $\ge 1$ |
| 6 | Sprite3Ds clipping / wrong sort order | `Alpha Cut = Discard` (Threshold 0.5) |
| 7 | Character suddenly vanishes behind | Pivot not at feet: `Centered=Off`, `Offset=(-w/2, -h)` |
| 8 | Pixel shimmer on camera movement | `snap_2d_transforms_to_pixel = On`, integer zoom/shrink |
| 9 | Uneven pixels when window resizes | `display/window/stretch/scale_mode = integer` |
| 10 | Weapon sprite pixels are uneven | Scale must be an integer vector (`Vector2(4, 4)`) |

---

## 10. Quick Checklist
- [ ] Single palette file exists; all assets drawn from it (§1.1, §8.3)
- [ ] PPU value decided and consistent everywhere (§1.2)
- [ ] `default_texture_filter = Nearest` (§1.4)
- [ ] Stretch: `canvas_items` + `keep` + `integer` (§1.4)
- [ ] `snap_2d_transforms_to_pixel = On` (§1.4)
- [ ] MSAA / Screen Space AA disabled (§1.4)
- [ ] All texture imports: Lossless, Mipmaps Off, Detect 3D Off, Fix Alpha Border On (§1.5)
- [ ] `.gdignore` present in `raw/` folder (§1.6)
- [ ] 2D: integer camera zoom; sprites not upscaled via transform scale (§2.2)
- [ ] TileSet: Use Texture Padding enabled; origin set on y-sort tiles (§2.3, §5.1)
- [ ] 3D: material filter Nearest, metallic/roughness/specular zeroed out (§3.1)
- [ ] glTF: Extract Materials done, Nearest EditorScript executed (§3.4)
- [ ] FPS: Sprite3D Billboard=Enabled, Alpha Cut=Discard; integer scale on weapon sprite (§4.3–4.4)
- [ ] If low-res desired, SubViewportContainer: Stretch, Stretch Shrink, Nearest (§4.6)
- [ ] Top-Down: y-sort chain verified (§5)
