---
name: pixel-asset-manager
description: >-
  Discovers, searches, inspects, slices, and integrates 2D pixel art assets
  (characters, animations, tilesets, UI, sounds) from PixelSRPG-Forge and other
  libraries into GameMaker and other game projects.
---

# Pixel Asset Manager Skill

This skill enables AI agents and developers to search, inspect, slice, and integrate tens of thousands of pixel art and audio assets from `com.github.huu-yuu.pixelsrpg-forge` (and future asset packs added to `libraries`) into Godot, GameMaker, and other game projects efficiently, without exhausting the LLM context window.

---

## 🚀 Core CLI Tools & Commands

With 30,000+ assets in the workspace, never use `ls -R` or `dir /s`. Use these dedicated, token-efficient tools instead:

### 1. Catalog Indexing & Search (`tools/asset_search.py`)

* **Rebuild or Update the Index:**
  Run whenever a new asset pack or library is added:
  ```powershell
  python tools/asset_search.py index
  ```

* **Search Assets:**
  Filter by keyword, category, file extension, or library:
  ```powershell
  # Search within characters
  python tools/asset_search.py search "knight" --category characters

  # Search magic / visual effects
  python tools/asset_search.py search "fire" --category effects

  # Search audio assets (WAV / OGG only)
  python tools/asset_search.py search "sword hit" --category sounds --ext wav

  # Search within a specific library
  python tools/asset_search.py search "tree" --library com.github.huu-yuu.pixelsrpg-forge --limit 15
  ```

* **Category Counts & Breakdown:**
  ```powershell
  python tools/asset_search.py categories
  ```

### 2. Inspect Asset Properties (`inspect`)

Returns image dimensions, frame count, color mode, transparency, and engine naming recommendations as structured JSON:
```powershell
python tools/asset_search.py inspect "libraries/com.github.huu-yuu.pixelsrpg-forge/Terrain_地形地块/cave.png"
```

### 3. Normal Map Generator (`tools/normal_map_gen.py`)

Generates tangent-space normal maps from 2D pixel sprites (and seamless floor tiles) for dynamic 2D/3D lighting shaders:
```powershell
# Default Moonfell cluster-faceted normal map + cavity mask + preview GIF:
python tools/normal_map_gen.py "path/to/sprite.png" --preview -s 2.0 -p 0.7

# Outline quarter-circle bevel (1px-padded, bevel=5, top=12, detail=1.5) + 6-step pixel-art lighting:
python tools/normal_map_gen.py "path/to/pots.png" --mode outline --steps 6 --preview --json

# Boxy crates (small bevel=1.5 prevents puffy pillow look) & seamless 3x3 floor tiles:
python tools/normal_map_gen.py "path/to/crate.png" --mode boxy --json
python tools/normal_map_gen.py "path/to/floor.png" --mode floor-tile --json

# Export Godot 4 stepped light() shader or run automated verification:
python tools/normal_map_gen.py --export-shader godot4 --json
python tools/normal_map_gen.py --verify --json
```
* Modes: `faceted` (default cluster-faceted), `outline` (1px-padded quarter-circle bevel), `boxy` (`1.5px` crate bevel), `floor-tile` (3×3 wrap + darkest `30%` gaps), `smooth` (classic Sobel).
* See [spritefusion-sprite-normals](../spritefusion-sprite-normals/SKILL.md) for Godot 4 `CanvasTexture` + stepped `light()` shader setup, pitfalls, and Rust/WASM batching.

### 4. Spritesheet Slicing & GameMaker Strip Exporter (`tools/sprite_slicer.py`)

GameMaker natively recognizes horizontal strips named `filename_stripN.png` and automatically configures N animation frames upon import:

* **Convert grid spritesheet to GameMaker horizontal strip:**
  ```powershell
  python tools/sprite_slicer.py "path/to/sheet.png" -W 32 -H 32 --gamemaker-strip -o "projects\MyGame\sprites\"
  ```

* **Extract individual PNG frames into a folder:**
  ```powershell
  python tools/sprite_slicer.py "path/to/sheet.png" -W 32 -H 32 -o "exports\hero_frames\" --prefix "hero_run"
  ```

---

## 📂 Category Mapping Reference (PixelSRPG-Forge)

`PixelSRPG-Forge` folders are bilingual (English + Chinese). The toolchain maps them automatically:

| Category Code | Folder Name | Description & Contents | GameMaker Prefix |
|---|---|---|---|
| `buildings` | `Buildings_建筑场景` | Castles, towns, dungeons, houses, interior walls | `spr_bld_` / `ts_bld_` |
| `interior` | `Interior_Decoration_室内装饰` | Furniture, tables, beds, props, indoor decorations | `spr_prop_` |
| `asset_packs`| `Asset_Packs_素材套图` | Complete packs (Dungeon, FarmLife, CleanCity) | `spr_` / `ts_` |
| `creatures` | `Creatures_生物动物` | Fantasy monsters, bosses, beasts, pets, mounts | `spr_creature_` |
| `characters`| `Characters_角色人物` | Heroes, warriors, NPCs, animated monsters | `spr_char_` |
| `weapons`   | `Weapons_武器装备`   | Swords, shields, armor, bows, staves | `spr_item_` |
| `costumes`  | `Costumes_服装装扮`  | Character customization apparel, capes, helms | `spr_costume_` |
| `effects`   | `Skill_Effects_技能特效`| Spells, explosions, slashes, particle bursts | `spr_fx_` |
| `icons`     | `Skill_Icons_技能图标`  | Ability icons, status effects, inventory slots | `spr_ico_` |
| `sounds`    | `Sound_Effects_音效音乐`| UI clicks, slashes, impacts, ambient music | `snd_` |
| `terrain`   | `Terrain_地形地块`   | Grass, water, cliffs, roads, lava, tilesets | `ts_` |
| `ui`        | `UI_Elements_界面元素` | Buttons, frames, dialogue boxes, health bars | `spr_ui_` |
| `other`     | `other_其他素材3万多张`| 31,000+ additional pixel art icons & sprites | `spr_misc_` |

---

## 🎮 GameMaker Import & Integration Standards

1. **Naming Conventions:**
   * Sprites: `spr_<category>_<name>_<action>` (e.g., `spr_hero_walk_down`, `spr_fx_fireball`)
   * Tilesets: `ts_<theme>_<dimensions>` (e.g., `ts_dungeon_16x16`, `ts_overworld_32x32`)
   * Audio: `snd_<sfx|bgm>_<name>` (e.g., `snd_sfx_sword_slash`, `snd_bgm_town`)
   * Objects: `obj_<name>` (e.g., `obj_player`, `obj_enemy_goblin`)

2. **Top-Down Depth & Origin:**
   * For top-down / isometric SRPG characters, set sprite Origin to **Bottom-Center**.
   * Manage draw order via:
     ```gml
     // Step or Draw Event
     depth = -bbox_bottom;
     ```

3. **Pixel Art Texture Settings:**
   * `Interpolate colours between pixels` -> **OFF (False)** to keep edges sharp.
   * Texture Page Size -> `2048x2048` or `4096x4096`.
