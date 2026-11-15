# 2.5D Farming & Retro FPS Hybrid (`farming_25d`)
### Master Project Documentation & Godot 4.x Architecture Guide

Welcome to the **2.5D FARMING & RETRO FPS HYBRID** project repository. This project fuses the fast-paced, visceral combat feel of **1990s retro first-person shooters** (in the exact aesthetic style of *Guns 'n Goblins Demo*) with the relaxing, tactile cycle of **3D grid-based farming simulation**, low-poly blocky world geometry, and CRT phosphor aesthetics.

> [!IMPORTANT]
> **Perspective Architecture:** This is strictly an **FPS 2.5D (First-Person Retro 3D World + 2D Y-Billboard Sprites)** game — NOT a top-down game!
> The player navigates a 3D environment in first-person, holding 3D/2D viewmodels (Pickaxe, Hoe, Watering Can, Scythe, Guns), aiming with a central crosshair raycast down at 1x1m ground tiles, and combating dense hordes of upright 2D billboard enemies that always face the camera.

---

## 🏛️ Project Structure & Migration Readiness

The folder `projects/farming_25d/` is **100% self-contained** and ready to be relocated anywhere (e.g. into your dedicated Godot 4 workspace):

```text
projects/farming_25d/
├── project.godot                          # Godot 4.x Master Project Configuration (480x270 Viewport, GL Compatibility, Inputs)
├── README.md                              # This document
├── ASSET_MANIFEST_600_PLUS.md             # Complete inventory of 2,480+ assets with dimensions and formats
├── CREDITS.md                             # Mandatory legal attribution ledger (EmanuelleDev, CC0, MIT, CC-BY)
├── 00_25D_FARMING_MASTER_MEGA_BOARD.png   # 1920x1080 Master Visual Atlas
│
├── scenes/                                # Godot 4 3D Scenes
│   ├── main_game_world.tscn               # Playable demo world (Campsite, Farm, Pasture, Archway, Horde, Player)
│   ├── fps_player.tscn                    # CharacterBody3D FPS controller with Camera3D, RayCast, Viewmodels
│   └── billboard_enemy.tscn               # 2D Billboard enemy with Y-billboard Sprite3D, collision, hit flash
│
├── scripts/                               # Godot 4 GDScript Core Gameplay Systems
│   ├── fps_player.gd                      # First-person WASD movement, mouse look, tool/weapon raycast interaction
│   ├── viewmodel_controller.gd            # First-person tool swings (Hoe, Can, Pickaxe) & firearm recoil/muzzle flashes
│   ├── farming_grid_manager.gd            # 3D grid soil state machine (Grass -> Tilled -> Wet -> Planted -> Harvest)
│   ├── enemy_billboard_ai.gd              # Guns 'n Goblins style horde enemy AI, pathfinding, attack, red hit flash
│   └── day_night_cycle.gd                 # 24-minute game day, Sun/Moon orbit, nighttime campfires/lanterns
│
├── shaders/                               # Custom Retro Shaders
│   ├── retro_crt_dither.gdshader          # 480x270 CRT Phosphor scanline & 4x4 Bayer Dither screen shader
│   └── pixel_billboard_lit.gdshader       # Dynamic 3D lighting shader for 2D billboards with normal maps
│
├── sprites_2d/                            # 2D Pixel Art Sprites (Quantized to 32-Color GDD Palette)
│   ├── enemies_billboard/                 # Guns 'n Goblins Horde Enemies (Goblins, Slimes, Myconids, Spikes)
│   │   ├── goblins/                       # Archer, Bomb, Spear, Merchant (Walk, Run, Attack, Damage, Dead strips + normals)
│   │   ├── slimes/                        # Green, Blue, Pink, Purple in Big, Medium, Small sizes
│   │   ├── myconids/                      # Mushroom monsters (K2 Mantar Ormanı)
│   │   └── spikes/                        # Burrowing underground spike monsters + 5 projectile types
│   ├── animals_billboard/                 # Farm Livestock & Wildlife (Cow, Sheep, Chicken, Pig, Goat, Duck, Deer, Fox)
│   ├── crops/                             # 11 Crops x 6 Stages (0 to 5) = 132 files with normal maps
│   ├── props_billboard/                   # Workbenches (Furnace, Anvil, Workbench, Alchemy), Campfire, Lanterns, Barns
│   ├── textures_3d/                       # 16x16 & 32x32 clean textures for 3D terrain/walls (Tilled/Wet Soil, Grass, Caves)
│   ├── viewmodels/                        # First-person tools (Gold Hoe, Pickaxe, Can, Scythe) & Chrome pistol
│   ├── pixelated_3d/                      # 32 Curated 3D assets converted to 64px pixel art + normal maps (160 files)
│   └── props_and_ui/                      # 11 Harvested crops + 11 seed packets from CC0 Pixel Art Atlas 1.4M
│
├── models_3d/                             # Real 3D Low-Poly Environment Meshes
│   ├── custom_blender/                    # 43 Custom low-poly meshes (Campfire, Archway, Fence, Lantern post, Shed, Ores)
│   └── regions_glb/                       # 144 ABO & Sand3D models (Buildings, Furniture, Mine carts, Barrels)
│
└── ui_ux/                                 # Retro CRT UI & Icons
    ├── components/                        # Day/Night Clock face & hand, Health/Stamina bars, HUD frames
    └── icons/                             # 10-Tier RPG progression (Wood, Cooper, Iron, Gold, Platinum... Obsidian)
```

---

## 🎮 How the Guns 'n Goblins 2.5D FPS Style Operates

### 1. Viewport & Rendering Pipeline
- **Resolution:** Virtual render target of **480×270** pixels.
- **Scaling:** Nearest-Neighbor upscaling to 1080p / 1440p / 4K with integer pixel ratios (`texture_filter = 0`).
- **Post-Processing:** `retro_crt_dither.gdshader` injects authentic CRT scanlines, 4x4 Bayer dithering, and phosphor green tints.

### 2. Environment (Real 3D Low-Poly Geometry)
- The world terrain, stone archways, ruined shacks, campfire posts, fences, dungeon corridors, and bridges are **real low-poly 3D blocky meshes** with pixelated textures.
- Dynamic 3D lighting: Point lights on campfires, hanging lanterns, glowing crystal ores, and weapon muzzle flashes cast real-time shadows and light.

### 3. Billboard Entities (`Sprite3D` with Y-Billboard Locking)
- **Living Entities:** All goblins, slimes, myconids, cows, sheep, chickens, and wildlife are **pure 2D pixel-art planar sprites** (`Sprite3D`).
- **Y-Billboard Locking:** Sprites rotate around their vertical Y axis to face the camera continuously, preventing foreshortening distortion when the player looks up or down.
- **Bottom-Center Grounding:** Every sprite has its vertical offset set to half its height (`offset.y = height / 2.0`), firmly rooting its feet/base to the 3D floor regardless of distance.
- **Normal Maps (`_n.png`):** Every sprite possesses a cluster-faceted normal map, allowing 3D point lights (such as the player's muzzle flash or campfire) to cast dynamic 3D specular and diffuse relief over the 2D pixel art.

### 4. 3D Grid Farming Mechanics in FPS
- The player holds a farming tool (Hoe, Watering Can, Seed Packet, Scythe) in first person.
- A central `RayCast3D` projects 3.5 meters forward to detect the 1x1m ground cell the player is aiming at.
- **Tilling:** Left-click with the Hoe turns grass/dry soil into tilled soil (`tex_soil_tilled_32x32.png`).
- **Watering:** Left-click with the Watering Can wets the soil (`tex_soil_wet_32x32.png`).
- **Planting:** Left-click with a Seed Packet instantiates a 2D Y-Billboard crop `Sprite3D` growing upright from the cell center.
- **Growth:** Crops cycle from Stage 0 (Seed) -> Stage 1 (Sprout) -> Stage 2 (Small) -> Stage 3 (Vegetative) -> Stage 4 (Flowering) -> Stage 5 (Mature Harvestable).
- **Harvesting:** Left-click with Scythe or Hand at Stage 5 pops the crop, spawning a floating 2D billboard pickup!

### 5. Visceral First-Person Combat
- Left-click with Pistol / Shotgun triggers:
  1. Viewmodel kickback recoil.
  2. Dynamic `PointLight3D` muzzle flash illuminating the surrounding 3D world and horde sprites for 0.08 seconds.
  3. Raycast bullet hit against enemies in the crosshair.
  4. Enemies take damage, flash bright red (`modulate = Color(1.0, 0.2, 0.2)`), receive physical knockback, and upon death collapse into loot drops.

---

## 🚀 Running the Project in Godot 4.x

1. Launch **Godot 4.2+ / 4.3+**.
2. Click **Import**, navigate to `projects/farming_25d/`, and select `project.godot`.
3. Press **F5** (or click the Play button in the top right).
4. **Controls:**
   - **W, A, S, D:** Move player
   - **Mouse:** Look around (Cursor is automatically captured; press `Escape` to release)
   - **Space:** Jump
   - **Shift:** Sprint
   - **1 to 7:** Switch hotbar tools/weapons (1: Hoe, 2: Can, 3: Pickaxe, 4: Scythe, 5: Pistol, 6: Shotgun, 7: Seeds)
   - **Left Click (LMB):** Use equipped tool / Fire weapon
   - **Right Click (RMB):** Quick plant / Interact with workbenches or campfires

---

## 📦 How to Relocate This Folder

When you are ready to move this project to another directory or disk:
1. Simply copy or move the entire folder:
   ```powershell
   Copy-Item -Path "D:\GameMaker\projects\farming_25d" -Destination "C:\Your\Path\farming_25d" -Recurse
   ```
2. The folder is **100% self-contained**: all textures, normal maps, 3D models, Godot scripts, shaders, and scene files use local relative paths (`res://...`). Nothing references external files outside `farming_25d/`.
