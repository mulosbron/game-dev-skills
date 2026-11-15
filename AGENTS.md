# Agent Game Forge & PlayForge (`game-dev-skills`) — Master Agent Guidelines

Unified hub combining **PlayForge**, **Agent Game Forge (`GameMaker`)**, and curated engine/graphics/asset/AI game-development skills (**68 top-level skills**, **79 `awesome-gamedev` sub-skills**, **78 `claude-code-game-studios` studio sub-skills**, **24 Reverse-DNS libraries**, **5 asset collections**, and **40 Python CLI tools**).

## Workspace Architecture

```text
game-dev-skills/
├── AGENTS.md                  # Binding instructions & full skill/tool index
├── README.md                  # Human guide, CLI cheat sheet, license ledgers
├── plugin.json                # Antigravity plugin manifest
├── .claude-plugin/plugin.json # Claude Code plugin manifest
├── .codex-plugin/plugin.json  # Codex plugin manifest
├── gemini-extension.json      # Gemini CLI extension config (points to AGENTS.md)
├── package.json               # 67js & Workspace JS dependencies
├── .polyspoon/                # Polyspoon local procedural runtime & receipts
├── .agents/skills/polyspoon/  # Kept for .polyspoon SHA-256 verification
├── assets/                    # Commercial-cleared datasets (Reverse-DNS)
│   ├── co.huggingface.angais.pixel-art-atlas-1.4m/  # 1,409,404 sprites (CC0)
│   ├── co.huggingface.sandflow.sand3d/              # 100k+ open 3D objects
│   ├── com.amazon.berkeley.abo/                     # 7,953 .glb + convex hulls (CC-BY-4.0)
│   ├── com.threejsassets/                           # 1,041 web-ready low-poly .glb
│   └── org.opengameart.lpc/                         # Liberated Pixel Cup ledger
├── libraries/                 # 24 Reverse-DNS packages (`com.github.*`, `org.opengameart.*`, etc.)
├── catalogs/                  # Offline token-free JSON catalogs (4,200+ 2D assets, 6,194 atlas subjects, 3D/Polyspoon)
├── tools/                     # 40 Python CLI pipelines (`asset_search.py`, `glb_forge.py`, `vfx_forge.py`, `wang_tiles.py`, `water_shorelines.py`, `see_through.py`, `atmospheric_perspective.py`, `shadowcasting.py`, `camera_follow_2d.py`, `platformer_forgiveness.py`, `sprite_stacker.py`, `hit_feedback.py`, `pixel_perfect.py`, `loot_window.py`, ...)
├── exports/                   # Generated strips, normal maps, GLBs, heatmaps & shaders
├── docs/                      # Master guides (incl. `godot-pixel-texture-rehberi.md`)
├── projects/                  # Active engine projects (`farming_25d/`, etc.)
└── skills/                    # 68 standardized skills + sub-skill routers
```

## Interactive Discovery & Q&A Protocol (Three Modes)

Always classify the request into Mode A, B, or C before editing project files or writing game code (`Discover → Report/GDD → Approve → Build`):

### Mode A — New Game from Scratch (Markdown GDD Gate)
1. **Request or Co-Author a Markdown GDD (`GDD.md`) First:**
   - Ask the user for their **Markdown Game Design Document (`GDD.md`)** (or paste its sections).
   - **If they already have a `GDD.md`:** Read and validate it for gaps; ask only for missing technical choices (`Engine & Target Platform`, `Asset Pipeline`, `v1 Exclusions`) using `(Recommended)` defaults.
   - **If they do NOT have a `GDD.md` yet:** Run 1 concise Q&A round (with `(Recommended)` defaults so `"sen seç"` works) covering: **Genre & Sub-genre (türü/cinsi)**, **Art Style & Palette**, **30-Second Core Loop & Camera**, **Engine & Platform** (`godot`, `web-2d-games`/`three-quarks`, `GameMaker`, `awesome-gamedev`, C++ `the-forge`/`jolt-physics`), and **Explicit v1 Exclusions** (e.g., no menu/save/multiplayer yet) — then generate a clean Markdown `GDD.md` (use `claude-code-game-studios/subskills/quick-design` or `game-docs` templates when helpful) and wait for approval.
2. **Skill Routing & 60-Second Prototype First:** Once `GDD.md` is approved, list the exact skills/tools to apply and build a single-scene 60-second runnable prototype first, then layer `game-feel`, VFX/SFX, and QA checks (`level-pipeline` / `voxl`).

### Mode B — Existing Game Project (Context → Audit → Action Report Gate)
1. **Understand the Game First (Before Auditing or Changing Code):**
   - Scan the project root (`project.godot`, `package.json`, `*.yyp`, `Assets/ProjectSettings/`, `*.uproject`, `CMakeLists.txt`) via `skills/awesome-gamedev/router/SKILL.md` (`Step 1 Engine Detection`), AND ask/confirm with the user:
     - **Game Genre & Sub-type (türü & cinsi):** e.g., roguelike action, cozy farming sim, turn-based RPG, platformer.
     - **Art Style & Technical Look:** e.g., top-down 16x16 pixel art, HD-2D, low-poly 3D, hand-drawn 2D.
     - **Target Improvement Scope:** What the user wants improved — **UI/UX, VFX, SFX/Audio, Game Feel, Core Loop/Progression, Camera, AI, or Physics** (or a full audit).
2. **Detect Problems & Prepare an Action Report (Do NOT edit yet):**
   - Audit the codebase against the matching skills (`game-engineering`, `game-feel`, `platformer-forgiveness`, `godot-pixel-pipeline`, `vfx-forge`, `limboai`, `phantom-camera`, implicit-state-machine rule, etc.) and present a structured **Diagnostic & Action Report**:
     - **Detected Issues (Tespit Edilen Sorunlar):** Concrete file paths, missing feedback/UX/VFX/SFX/loop gaps, or architectural bottlenecks.
     - **Why It Hurts & Proposed Fix ("Şunu Şöyle Yapacağız"):** Exact plan per area (UI/UX, VFX, SFX, gameplay, scripts/shaders/tools to add or edit) and expected player-feel impact.
3. **Wait for Approval, Then Execute Incrementally:** Present options if multiple fixes exist, obtain `"Onayla / Uygula"`, and apply changes without breaking existing architecture.

### Mode C — Standalone Asset, VFX, Audio, or Tool Production (Asset-Only)
1. Use this mode when the user only wants **sprites, tilesets, 3D models, PBR materials, normal maps, VFX strips, or SFX/music**—never force a `GDD.md` or full-game audit here.
2. Confirm only missing export specs: **Target Engine/Format** (`_stripN.png` for GameMaker, `.tres`/Nearest imports for Godot, `.glb`/Draco/Meshopt for Three.js/Roblox), **Art Style / Palette**, and **Resolution / Frame Count**.
3. Execute directly via `tools/*.py` (`asset_search.py`, `pixel_atlas_manager.py`, `lpc_character_builder.py`, `creature_gen.py`, `pixelfx_tool.py`, `vfx_forge.py`, `normal_map_gen.py`, `flat2iso.py`, `polyspoon_tool.py`, `glb_forge.py`, `blender_kiln.py`, `sand3d_builder.py`) or the matching asset skill (`generate2dsprite`, `video2dsprite`, `flat2iso`, `spritefusion-sprite-normals`, `triposr`, `material-maker`, `mcp-for-blender`).

## Critical Working Rules (Always Enforced)

1. **Prototype & Core Loop First:** Build a 60-second playable prototype before menus, polish, or extra systems. Before adding any mechanic ask: can the player finish the game without opening it?
2. **NEVER run recursive directory listings (`dir /s`, `ls -R`, `Get-ChildItem -Recurse`) across `libraries/`, `assets/`, or `node_modules/`!** They hold 150,000+ files and will flood context.
3. **ALWAYS discover & inspect assets via CLI:**
   - `python tools/asset_search.py search "<keyword>" --limit 20`
   - `python tools/asset_search.py inspect "<file_path>"`
4. **Reverse-DNS & License Provenance:** Track external sources via canonical reverse-DNS names (`com.github.*`, `org.opengameart.*`, `co.huggingface.*`, `com.amazon.*`, `com.threejsassets`) and preserve `LICENSES.txt` / `CREDITS.csv` attributions.
5. **2D / GameMaker Import Conventions:** Export horizontal strips as `_stripN.png` (`tools/sprite_slicer.py --gamemaker-strip`), use Bottom-Center origins and `depth = -bbox_bottom;` for top-down sorting, clean AI pixel art (`tools/pixel_snapper.py` / `spritefusion-pixel-snapper`), convert flat orthographic pixel art to 2:1 isometric (`tools/flat2iso.py` with `--scale auto`, `--sheet-mode strip4`, `--json`), and generate 2D normals (`tools/normal_map_gen.py` / `spritefusion-sprite-normals`) before lit shaders.
6. **Human-First Level Authority Boundary:** Never auto-generate or overwrite handcrafted level/puzzle layouts unless given explicit coordinates. Use `tools/level_pipeline.py` only for plumbing (`scaffold`, BFS `validate`, `assemble`, `playtest-report`).
7. **No Implicit State Machines (Steve Ruiz Rule):** Replace entangled boolean flag combinations (`isJumping && !isClimbing && !isDead`) with explicit finite-state enums.
8. **Cross-Pack Boundary:** Classroom/educational gamification belongs in `~/.agents/gamification-skills/`.

## Skills Index (68 Top-Level Skills)

### Game Design, Feel, Architecture & Routers (11)
| Skill | Use when |
|---|---|
| `skills/game-feel/SKILL.md` | A mechanic works but feels dead; adding visual, audio, camera, and temporal juice. |
| `skills/hit-feedback/SKILL.md` | Making 2D hits feel heavy from one call (5/9-tick hitstop, white shader flash, 12px knockback, pixel-rounded shake, sparks, slash trail, 46-tick numbers, `tools/hit_feedback.py`). |
| `skills/platformer-forgiveness/SKILL.md` | Tuning tight 2D/2.5D platformer controls (0.1s fixed-tick coyote time, jump buffer, 4px dual ledge/ceiling corner correction via `tools/platformer_forgiveness.py`). |
| `skills/camera-follow-2d/SKILL.md` | Choosing and tuning 8 2D camera modes (locked, smooth, dead zone, rooms, look-ahead, POIs, aim, two targets) for Godot 4 `Camera2D` & Unity Cinemachine 3 (`tools/camera_follow_2d.py`). |
| `skills/game-engineering/SKILL.md` | Diagnosing boring loops, player churn, progression curves, and motivation/reward design. |
| `skills/crafting-systems/SKILL.md` | Designing crafting, inventory, and resource economies integrated into the core loop. |
| `skills/sustainable-indie-dev/SKILL.md` | Scoping projects, planning milestones, marketing hooks, Steam/itch positioning, avoiding burnout. |
| `skills/web-2d-games/SKILL.md` | Building 2D top-down/tilemap web games (Phaser 3.8+ + React + Zustand + Vite), Godot→Web ports. |
| `skills/level-pipeline/SKILL.md` | No-engine plain-JS 2D micro-engine, BFS reachability validation, piece assembly, heatmaps. |
| `skills/claude-code-game-studios/SKILL.md` | Multi-agent studio router (`78` slash subskills in `subskills/`, `49` agents, engine/genre playbooks, QA gates). |
| `skills/awesome-gamedev/SKILL.md` | Engine/genre/publishing dispatcher (`router/SKILL.md` across `79` sub-skills for Unity, Unreal, Godot, Bevy, Ebitengine, Defold, LÖVE, pygame, Phaser, PixiJS, three.js, Roblox). |

### Godot 4 Engine & Addons (10)
| Skill | Use when |
|---|---|
| `skills/godot/SKILL.md` | Writing Godot 4 / GDScript (`playbook.md` house style, state machines, pooling, Godot 3→4 migration). |
| `skills/godot-fake-3d-character/SKILL.md` | Building 2.5D top-down puppet characters in Godot 4 with 2D nodes, `RemoteTransform2D`, Y-scale rigs. |
| `skills/godot-jolt/SKILL.md` | Integrating Jolt Physics GDExtension (`JoltPhysicsServer3D`, joints, settings, source builds) in Godot 4. |
| `skills/godot-voxel/SKILL.md` | Building blocky/smooth Transvoxel destructible worlds (`VoxelTerrain`, `VoxelLodTerrain`, `VoxelGeneratorGraph`). |
| `skills/terrain3d/SKILL.md` | Large clipmap 3D terrains (`Terrain3D`, 32-texture blending, heightmaps, `Terrain3DInstancer`). |
| `skills/limboai/SKILL.md` | Godot 4 C++ Behavior Trees (`BTPlayer`), HSM (`LimboHSM`), and `Blackboard` game AI. |
| `skills/phantom-camera/SKILL.md` | Dynamic 2D/3D virtual cameras (`PhantomCameraHost`, priority switching, follow/look-at, tweens, noise). |
| `skills/dialogic/SKILL.md` | Dialogic 2 narrative/RPG/visual novel timelines (`.dtl`), characters (`.dch`), portraits, variables, saves. |
| `skills/godot-mcp/SKILL.md` | Driving Godot headlessly from AI agents via MCP (`libraries/com.github.coding-solo.godot-mcp`). |
| `skills/godot-pixel-pipeline/SKILL.md` | Lossless pixel textures, Nearest filtering, PSX/Bayer dither shaders & audits (`tools/godot_pixel_tool.py`). |

### C++ Rendering, Physics, Animation, Navigation & VFX (5)
| Skill | Use when |
|---|---|
| `skills/the-forge/SKILL.md` | ConfettiFX cross-platform C/C++ rendering (`IGraphics.h`, FSL shaders, D3D12/Vulkan/Metal, Visibility Buffer). |
| `skills/jolt-physics/SKILL.md` | Standalone C++17 3D physics (`JoltPhysics` v5.7.0, CMake `Build/CMakeLists.txt`, double precision, determinism). |
| `skills/ozz-animation/SKILL.md` | C++17 SIMD skeletal animation (`Skeleton`, `SamplingJob`, `BlendingJob`, IK, root motion, `gltf2ozz`). |
| `skills/recastnavigation/SKILL.md` | C++ navmesh baking (`Recast`), pathfinding (`Detour`), dynamic obstacles (`DetourTileCache`), `DetourCrowd`. |
| `skills/effekseer/SKILL.md` | Cross-platform `.efkefc`/`.efk` 3D/2D particle VFX runtimes (C++ DX11/12/Vulkan/GL/Metal, LLGI, engines). |

### Web Multiplayer, Web 3D & Game AI (5)
| Skill | Use when |
|---|---|
| `skills/colyseus/SKILL.md` | Authoritative Node.js/TS multiplayer (`Server`, `Room`, `@colyseus/schema`, v0.18 prediction & `references/`). |
| `skills/three-quarks/SKILL.md` | Batched GPU/CPU particle systems, trails, node graphs & WebGPU VFX in Three.js / React Three Fiber. |
| `skills/yuka/SKILL.md` | Engine-agnostic JS Game AI (`EntityManager`, `Vehicle` steering, FSM, `Think` goals, `NavMesh`/A*, `Vision`). |
| `skills/build-67js-scene/SKILL.md` | Interactive WebGL2 3D scenes, procedural nature/worlds, materials, camera & MSAA via `67js`. |
| `skills/render-67js-media/SKILL.md` | Deterministic PNG/MP4 exports from `67js` scenes with bounded memory on GPU or CPU. |

### 2D Art, Sprites, Pixel Tooling, VFX, Maps & Testing (29)
| Skill | Use when |
|---|---|
| `skills/generate2dmedia/SKILL.md` | Art-route layer (`route_media.py`) routing image/video calls to configured APIs or local Codex/Grok CLIs. |
| `skills/generate2dsprite/SKILL.md` | Generating game-ready 2D character stills, props, FX/icon sheets, slicing, palette lock, and engine exports. |
| `skills/generate2dmap/SKILL.md` | Building 2D top-down/side-scrolling maps, tilemaps, parallax & HD-2D plates with reachability checks. |
| `skills/wang-tiles/SKILL.md` | Eliminating 2D terrain grid repetition with 16-tile edge-matched Wang sets, chunk edge hashing & image quilting (`tools/wang_tiles.py`). |
| `skills/water-shorelines/SKILL.md` | Baking 2D distance-field water shorelines (depth bands, breathing foam, incoming waves, Godot/Unity shaders via `tools/water_shorelines.py`). |
| `skills/see-through/SKILL.md` | Keeping 2D characters visible behind trees/fog/miasma/walls with Fade (A), Bayer Dither (B), Cutout (C), and Silhouette + stealth alarm-red (D) (`tools/see_through.py`). |
| `skills/atmospheric-perspective/SKILL.md` | Adding sky-row atmospheric perspective & base mist to 2D parallax platformers and 2.5D Limbo-style depth cards (`tools/atmospheric_perspective.py`). |
| `skills/shadowcasting/SKILL.md` | Computing 8-octant Bergstrom shadowcasting for wall-occluded torchlight, fog of war, and enemy LOS in top-down & platformer 2D games (`tools/shadowcasting.py`). |
| `skills/sprite-stacking/SKILL.md` | Carving 4 orthographic views into ground-first slice strips (`slices_strip.png` + `preview.gif`) and rendering rotating fake-3D pixel stacks (`tools/sprite_stacker.py`). |
| `skills/pixel-perfect/SKILL.md` | Enforcing 8 pixel-perfect rules (integer viewport scaling, GCD mixel detection, Nearest/Lossless/snap settings, Godot/Unity scene audits via `tools/pixel_perfect.py`). |
| `skills/loot-window/SKILL.md` | Pixel art loot window (`222x172` @ 4x): tiled `96x96` (`16px` cut) 9-slice frame, code-drawn rarity slots, staggered chest shake/lid/glow shafts/sparkle reveal & Godot/Unity export (`tools/loot_window.py`). |
| `skills/video2dsprite/SKILL.md` | Turning an approved master still into multi-action animated sprite clips with matte keying & loops. |
| `skills/sprite-gen/SKILL.md` | Generating sprites, logos/typography, image-to-video motion loops & palette swaps via GPT/Grok. |
| `skills/codeart2d/SKILL.md` | Explicit-only code-drawn PixelSpec/SVG/rigged 2D sprites, autotiles & JS FX runtime fallback. |
| `skills/backgroundremover/SKILL.md` | Stripping backgrounds cleanly with U2-Net AI alpha mattes (`libraries/com.github.nadermx.backgroundremover`). |
| `skills/pixel-snapper/SKILL.md` | Cleaning AI pixel art jitter to integer grids + Pico-8/DB16/GameBoy palettes (`tools/pixel_snapper.py`). |
| `skills/spritefusion-pixel-snapper/SKILL.md` | Rust CLI & WASM grid snapping + custom hex palette quantization (`Hugo-Dz/spritefusion-pixel-snapper`). |
| `skills/spritefusion-sprite-normals/SKILL.md` | Generating 2D pixel sprite tangent normal maps (`_n.png`) & height reliefs via Rust/WASM (`libraries/com.github.hugo-dz.spritefusion-sprite-normals`). |
| `skills/image-to-pixel/SKILL.md` | Art-direction-locked dithering (16 algos), Lospec palettes, outlines & tilesets (`tools/image_to_pixel.py`). |
| `skills/flat2iso/SKILL.md` | Lossless 2:1 isometric pixel art (`tools/flat2iso.py`: `inspect`/`shift`/`box`/`serve`, `--scale auto`, `_stripN.png` & 4-dir `_strip4.png`, `--json`). |
| `skills/pixelorama/SKILL.md` | Godot-powered pixel art & animation editor workflows (`libraries/com.github.orama-interactive.pixelorama`). |
| `skills/ldtk/SKILL.md` | Rule-based autotiling, entity layers & `.ldtk` JSON level maps (`libraries/com.github.deepnight.ldtk`). |
| `skills/lpc-character-generator/SKILL.md` | Modular 64x64 LPC characters & automated `CREDITS.csv` ledgers (`tools/lpc_character_builder.py`). |
| `skills/creature-gen/SKILL.md` | Zero-image 9-family procedural pixel monsters, genetics & `_stripN.png` (`tools/creature_gen.py`). |
| `skills/pixelfx/SKILL.md` | 244+ code-driven combat/magic pixel VFX animations & recoloring (`tools/pixelfx_tool.py`). |
| `skills/vfx-forge/SKILL.md` | 2D-native top-down 5-Family SDF VFX, Selective Glow & Menpai presets (`tools/vfx_forge.py`). |
| `skills/pixel-art-atlas/SKILL.md` | O(1) mmap lookup across 1.4M CC0 sprites & strip exports (`tools/pixel_atlas_manager.py`). |
| `skills/pixel-asset-manager/SKILL.md` | Searching/slicing 30k+ SRPG & Pixel packs (`tools/asset_search.py`, `tools/sprite_slicer.py`). |
| `skills/voxl/SKILL.md` | 60 FPS remote game stream visual testing (`/screenshot`, `/record`, `tools/voxl_client.py`). |

### 3D Models, Reconstruction, Blender & Procedural Materials (8)
| Skill | Use when |
|---|---|
| `skills/blender-kiln/SKILL.md` | Headless Blender 5.2 3D forge, 6-view Colour/Clay review sheets, UV/print checks (`tools/blender_kiln.py`). |
| `skills/mcp-for-blender/SKILL.md` | Connecting agents to live Blender 3.0+ sessions via MCP (`libraries/com.github.3d-gen-ai.mcp-for-blender` + `references/`). |
| `skills/glb-forge/SKILL.md` | Inspecting/optimizing GLBs (Meshopt, Draco, WebP, LOD chains, TSL materials, `tools/glb_forge.py`). |
| `skills/polyspoon/SKILL.md` | Editing/exporting 20 families of recipe-driven procedural low-poly 3D assets (`tools/polyspoon_tool.py`). |
| `skills/material-maker/SKILL.md` | Authoring procedural PBR `.ptex` node/SDF materials & 3D paint exports to Godot/Unity/UE/Blender. |
| `skills/mesh-splatting/SKILL.md` | Differentiable opaque triangle-mesh 3D reconstruction, SAM2 segmentation, and `.ply` export. |
| `skills/triposr/SKILL.md` | Single-image feedforward 3D mesh reconstruction (`run.py`, `rembg`, UV texture baking to `.obj`/`.glb`). |
| `skills/sand3d-to-roblox/SKILL.md` | Searching/rebuilding Sand3D 100k+ open 3D objects for Roblox & game engines (`tools/sand3d_manager.py`, `tools/sand3d_builder.py`). |
