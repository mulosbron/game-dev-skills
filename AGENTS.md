# Agent Game Forge & PlayForge (`game-dev-skills`) — Master Summary & Agent Tree Router

Unified game development hub combining **PlayForge**, **Agent Game Forge (`GameMaker`)**, and curated multi-engine skills (**73 top-level skills**, **79 `awesome-gamedev` sub-skills**, **78 `claude-code-game-studios` sub-skills**, **24 Reverse-DNS libraries**, **5 commercial-cleared asset collections**, **35 Python CLI tools**, and **18 hierarchical agent specs** in [`agents/`](agents/README.md)).

> **Anti-Chaos Rule:** Never load unrelated 2D, 2.5D, and 3D skills at once. Classify the request (`Mode A / B / C`), detect the engine and perspective, and **route directly into the matching specialist in [`agents/`](agents/README.md)** for full step-by-step pipelines and CLI chains.

---

## 1. Workspace Architecture

```text
game-dev-skills/
├── AGENTS.md                  # Concise Master Summary, Binding Rules & Agent Tree Router (this file)
├── README.md                  # Human quick-start, plugin setup & CLI cheat sheet
├── agents/                    # Hierarchical Agent Tree & Multi-Tool Pipelines (18 agent specs + README.md)
│   ├── asset-scout.md         # Multi-catalog search across catalogs/*.json + libraries/ + assets/ with licenses
│   ├── pixel-2d-pipeline.md   # pixel_snapper -> flat2iso -> normal_map_gen -> sprite_slicer -> vfx -> godot_pixel_tool
│   ├── 3d-forge-pipeline.md   # abo/threejs/polyspoon/sand3d -> blender_kiln -> glb_forge -> asset_harmonizer
│   ├── game-feel-qa.md        # hit_feedback + forgiveness + camera + pixel_perfect + level_pipeline + voxl Audit
│   ├── asset-harmonizer-agent.md # Root compatibility entrypoint for 6-stage 3D asset harmonization
│   ├── 00-orchestrator/       # Root Mode A/B/C & Engine Router (game-director-router.md)
│   ├── 01-2d-games/           # 2d-platformer-specialist.md · 2d-topdown-rpg-roguelike-specialist.md
│   ├── 02-25d-isometric/      # 25d-isometric-flat2iso-specialist.md · 25d-fake3d-hd2d-specialist.md
│   ├── 03-2d-asset-vfx-forge/ # pixel-character-creature-forge.md · pixel-cleanup-normals-pipeline.md · vfx-shaders-juice-specialist.md
│   ├── 04-3d-worlds-pipeline/ # 3d-model-material-forge.md · 3d-world-physics-engine-specialist.md · asset-harmonizer-specialist.md
│   └── 05-web-multiplayer-qa/ # web-multiplayer-specialist.md · level-qa-playtest-specialist.md
├── assets/                    # Commercial-cleared datasets (Pixel Atlas 1.4M, Sand3D 100k+, ABO 7,953, ThreeJS 1,041, LPC)
├── catalogs/                  # Offline JSON indexes (zero-token asset lookup)
├── libraries/                 # 24 Reverse-DNS external repos/packages
├── tools/                     # 35 Python CLI pipelines (see Branch Index below)
├── exports/                   # Generated strips, normal maps, GLBs, heatmaps & shaders
├── docs/                      # Master guides (incl. godot-pixel-texture-rehberi.md)
├── projects/                  # Local game projects (gitignored; never pushed)
└── skills/                    # 73 standardized skills + awesome-gamedev & claude-code-game-studios routers
```

---

## 2. Interactive Discovery & Q&A Gate (Modes A, B, C)

Classify every request before editing project files or writing game code (`Discover → Report/GDD → Approve → Build`):

1. **Mode A — New Game from Scratch (`GDD.md` Gate):**
   - Ask for a Markdown `GDD.md`; if absent, run 1 concise Q&A round with `(Recommended)` defaults covering **Genre & Sub-genre**, **Art Style & Palette**, **30-Second Core Loop & Camera**, **Engine & Platform**, and **v1 Exclusions** (`claude-code-game-studios/subskills/quick-design`).
   - Wait for `GDD.md` approval, then build a **single-scene 60-second playable prototype** first before layering `game-feel`, VFX/SFX, and QA.
2. **Mode B — Existing Game Project (Context → Audit → Action Report Gate):**
   - Fingerprint engine (`project.godot`, `package.json`, `*.yyp`, `*.uproject`, `CMakeLists.txt`) via `skills/awesome-gamedev/router/SKILL.md` and confirm **Genre/Sub-type**, **Art Style**, and **Target Improvement Scope** (UI/UX, VFX, SFX, Game Feel, Loop, Camera, AI, Physics).
   - **Do NOT edit yet:** Run `agents/game-feel-qa.md` + matching branch checks and present a file/line **Diagnostic & Action Report** (`Detected Issues → Why It Hurts → Proposed Fix`). Wait for approval before editing.
3. **Mode C — Standalone Asset, VFX, Audio, or Tool Production (Asset-Only):**
   - Never force a `GDD.md` or full audit. Confirm only **Target Engine Format** (`_stripN.png`, `.tres`, `.glb`), **Art Style/Palette**, and **Resolution/Frames**, then execute via `agents/asset-scout.md`, `agents/pixel-2d-pipeline.md`, or `agents/3d-forge-pipeline.md`.

---

## 3. Critical Working Rules (Always Enforced)

1. **Prototype & Core Loop First:** Build a 60-second playable prototype before menus or polish. Ask: *can the player finish the game without opening this mechanic?*
2. **NEVER run recursive directory listings (`dir /s`, `ls -R`, `Get-ChildItem -Recurse`) across `libraries/`, `assets/`, or `node_modules/`!** They hold 150,000+ files and will flood context.
3. **ALWAYS discover & inspect assets via CLI:** `python tools/asset_search.py search "<kw>" --source all --limit 20 --json` and `python tools/asset_search.py inspect "<path>"` (or dispatch `agents/asset-scout.md`).
4. **Reverse-DNS & License Provenance:** Track external sources via canonical reverse-DNS names (`com.github.*`, `org.opengameart.*`, `co.huggingface.*`, `com.amazon.*`, `com.threejsassets`) and preserve `LICENSES.txt` / `CREDITS.csv`.
5. **2D / 2.5D Pixel Import Conventions:** Export horizontal strips as `*_stripN.png` (`tools/sprite_slicer.py --gamemaker-strip`), use **Bottom-Center** origins and `depth = -bbox_bottom;` / `y_sort_enabled`, clean AI pixel art (`pixel_snapper.py`), convert flat orthographic art to 2:1 isometric via `tools/flat2iso.py` (`--scale auto`, `--sheet-mode strip4`, `--json`) or `skills/flat2iso/assets/flat2iso.html`, and generate 2D normals (`normal_map_gen.py`) *after* final projection.
6. **Human-First Level Authority Boundary:** Never auto-generate or overwrite handcrafted level/puzzle layouts unless given explicit coordinates. Use `tools/level_pipeline.py` only for plumbing (`scaffold`, BFS `validate`, `assemble`, `playtest-report`).
7. **No Implicit State Machines (Steve Ruiz Rule):** Replace entangled boolean flag combinations (`isJumping && !isClimbing && !isDead`) with explicit finite-state enums or `LimboHSM`.
8. **Cross-Pack Boundary:** Classroom/educational gamification belongs in `~/.agents/gamification-skills/`.
9. **STRICT `tools/` Boundary (General-Purpose Tools ONLY):** NEVER create or place project-specific, game-specific, or character/boss/lore-specific scripts inside `tools/`! `tools/` is strictly reserved for the 35 reusable, project-agnostic CLI pipelines. Any game-specific generator, harvester, or build script MUST be placed inside `projects/<project_name>/` (gitignored).

---

## 4. Hierarchical Agent Tree & Routing Table (`agents/`)

Full details, multi-step task chains, and exact PowerShell commands live inside each agent file (see [`agents/README.md`](agents/README.md) for the complete 73-skill & 35-tool ledger).

### Fast-Path Cross-Tool Pipeline Agents (Root `agents/`)

| Agent File | What It Orchestrates |
|---|---|
| [`agents/asset-scout.md`](agents/asset-scout.md) | One-pass search across all `catalogs/*.json` + `libraries/` + `assets/` with CC0/CC-BY/LPC license & format report |
| [`agents/pixel-2d-pipeline.md`](agents/pixel-2d-pipeline.md) | `pixel_snapper` / `image_to_pixel` → `flat2iso` → `normal_map_gen` → `sprite_slicer` → `pixelfx_tool` / `vfx_forge` → `godot_pixel_tool` / `pixel_perfect` |
| [`agents/3d-forge-pipeline.md`](agents/3d-forge-pipeline.md) | `abo_manager` / `threejsassets_manager` / `polyspoon_tool` / `sand3d_builder` → `blender_kiln` → `glb_forge` → `asset_harmonizer` |
| [`agents/game-feel-qa.md`](agents/game-feel-qa.md) | Existing-project Mode B audit & polish via `hit_feedback`, `platformer_forgiveness`, `camera_follow_2d`, `pixel_perfect`, `level_pipeline`, `voxl_client` |
| [`agents/asset-harmonizer-agent.md`](agents/asset-harmonizer-agent.md) | Compatibility entrypoint for the 6-stage mixed-source 3D harmonizer (links to `04-3d-worlds-pipeline/asset-harmonizer-specialist.md`) |

### Game Type & Discipline Specialist Branches

| Game Type / Need | Specialist Agent to Load First | Core Skills & Tools Owned |
|---|---|---|
| **Intake, Engine Detection, Studio Rigor** | [`agents/00-orchestrator/game-director-router.md`](agents/00-orchestrator/game-director-router.md) | `awesome-gamedev`, `claude-code-game-studios`, `game-engineering`, `sustainable-indie-dev`, `fantasy-first-design`, `new-game-developer`, `skill-to-script`, `asset_search.py`, `unpack_libraries.py` |
| **2D / 2.5D Platformer & Metroidvania** | [`agents/01-2d-games/2d-platformer-specialist.md`](agents/01-2d-games/2d-platformer-specialist.md) | `platformer-forgiveness`, `camera-follow-2d`, `hit-feedback`, `game-feel`, `atmospheric-perspective`, `pixel-perfect`, `godot`, `web-2d-games`, `level-pipeline`, `ldtk` (`platformer_forgiveness.py`, `camera_follow_2d.py`, `hit_feedback.py`, `atmospheric_perspective.py`, `pixel_perfect.py`, `level_pipeline.py`) |
| **2D Top-Down RPG / Roguelike / Cozy Sim** | [`agents/01-2d-games/2d-topdown-rpg-roguelike-specialist.md`](agents/01-2d-games/2d-topdown-rpg-roguelike-specialist.md) | `wang-tiles`, `water-shorelines`, `shadowcasting`, `see-through`, `loot-window`, `crafting-systems`, `game-engineering`, `dialogic`, `limboai`, `yuka`, `ldtk`, `generate2dmap`, `camera-follow-2d`, `hit-feedback`, `game-feel`, `godot` (`wang_tiles.py`, `water_shorelines.py`, `shadowcasting.py`, `see_through.py`, `loot_window.py`) |
| **2.5D 2:1 Isometric (`flat2iso`)** | [`agents/02-25d-isometric/25d-isometric-flat2iso-specialist.md`](agents/02-25d-isometric/25d-isometric-flat2iso-specialist.md) | `flat2iso` (`tools/flat2iso.py` + `skills/flat2iso/assets/flat2iso.html` Studio), `spritefusion-sprite-normals`, `pixel-snapper`, `pixel-perfect`, `see-through`, `shadowcasting`, `vfx-forge`, `generate2dmap`, `wang-tiles`, `water-shorelines` |
| **2.5D Fake-3D Puppets, Stack, HD-2D, 2.5D FPS** | [`agents/02-25d-isometric/25d-fake3d-hd2d-specialist.md`](agents/02-25d-isometric/25d-fake3d-hd2d-specialist.md) | `godot-fake-3d-character`, `sprite-stacking` (`sprite_stacker.py`), `godot-pixel-pipeline` (`godot_pixel_tool.py`), `atmospheric-perspective`, `phantom-camera`, `see-through`, `spritefusion-sprite-normals`, `godot`, `pixel-perfect` |
| **2D Characters, Atlas, LPC, Monsters, AI Sprites** | [`agents/03-2d-asset-vfx-forge/pixel-character-creature-forge.md`](agents/03-2d-asset-vfx-forge/pixel-character-creature-forge.md) | `pixel-art-atlas` (`pixel_atlas_manager.py`), `pixel-asset-manager`, `lpc-character-generator` (`lpc_character_builder.py`), `creature-gen` (`creature_gen.py`), `generate2dsprite`, `generate2dmedia`, `generate2dmap`, `video2dsprite`, `sprite-gen`, `codeart2d`, `sprite_slicer.py` |
| **Pixel Cleanup, Palette, Normals & Imports** | [`agents/03-2d-asset-vfx-forge/pixel-cleanup-normals-pipeline.md`](agents/03-2d-asset-vfx-forge/pixel-cleanup-normals-pipeline.md) | `backgroundremover`, `pixel-snapper` (`pixel_snapper.py`), `spritefusion-pixel-snapper`, `image-to-pixel` (`image_to_pixel.py`), `spritefusion-sprite-normals` (`normal_map_gen.py`), `pixelorama`, `loot-window`, `pixel-perfect`, `godot-pixel-pipeline` |
| **VFX, Combat Juice & Synthesized SFX** | [`agents/03-2d-asset-vfx-forge/vfx-shaders-juice-specialist.md`](agents/03-2d-asset-vfx-forge/vfx-shaders-juice-specialist.md) | `vfx-forge` (`vfx_forge.py`), `pixelfx` (`pixelfx_tool.py`), `hit-feedback`, `game-feel`, `effekseer`, `three-quarks`, `see-through`, `water-shorelines`, `atmospheric-perspective` |
| **3D Models, Catalogs, Blender, PBR & GLBs** | [`agents/04-3d-worlds-pipeline/3d-model-material-forge.md`](agents/04-3d-worlds-pipeline/3d-model-material-forge.md) | `polyspoon` (`polyspoon_tool.py`), `blender-kiln` (`blender_kiln.py`), `mcp-for-blender`, `glb-forge` (`glb_forge.py`), `material-maker`, `triposr`, `mesh-splatting`, `sand3d-to-roblox` (`sand3d_manager.py`, `sand3d_builder.py`), `abo_manager.py`, `threejsassets_manager.py` |
| **3D Worlds, Physics, AI & C++17 Engines** | [`agents/04-3d-worlds-pipeline/3d-world-physics-engine-specialist.md`](agents/04-3d-worlds-pipeline/3d-world-physics-engine-specialist.md) | Godot 3D (`godot`, `godot-jolt`, `godot-voxel`, `terrain3d`, `phantom-camera`, `limboai`) & C++17 (`the-forge`, `jolt-physics`, `ozz-animation`, `recastnavigation`, `effekseer`) |
| **Mixed-Source 3D Unification (6-Stage)** | [`agents/04-3d-worlds-pipeline/asset-harmonizer-specialist.md`](agents/04-3d-worlds-pipeline/asset-harmonizer-specialist.md) | `asset-harmonizer` (`asset_harmonizer.py`), `glb-forge`, `blender-kiln`, `material-maker`, `image-to-pixel` |
| **Web 2D/3D, 67js, Colyseus & Yuka AI** | [`agents/05-web-multiplayer-qa/web-multiplayer-specialist.md`](agents/05-web-multiplayer-qa/web-multiplayer-specialist.md) | `web-2d-games`, `colyseus`, `three-quarks`, `yuka`, `build-67js-scene`, `render-67js-media`, `awesome-gamedev` (`micro_engine.py`, `glb_forge.py`) |
| **Level BFS, Voxl 60FPS QA & Release** | [`agents/05-web-multiplayer-qa/level-qa-playtest-specialist.md`](agents/05-web-multiplayer-qa/level-qa-playtest-specialist.md) | `level-pipeline` (`level_pipeline.py`), `playtest`, `voxl` (`voxl_client.py`), `pixel-perfect`, `godot-pixel-pipeline`, `godot-mcp`, `sustainable-indie-dev`, `claude-code-game-studios` |

---

## 5. Quick Skill Index (`skills/<name>/SKILL.md` — 73 Skills)

- **Design, Routers & Production (15):** `awesome-gamedev` · `claude-code-game-studios` · `fantasy-first-design` · `game-engineering` · `game-feel` · `hit-feedback` · `new-game-developer` · `platformer-forgiveness` · `camera-follow-2d` · `crafting-systems` · `playtest` · `skill-to-script` · `sustainable-indie-dev` · `web-2d-games` · `level-pipeline`
- **Godot 4 Ecosystem (10):** `godot` · `godot-fake-3d-character` · `godot-jolt` · `godot-voxel` · `terrain3d` · `limboai` · `phantom-camera` · `dialogic` · `godot-mcp` · `godot-pixel-pipeline`
- **C++ Rendering, Physics, Anim, Nav & VFX (5):** `the-forge` · `jolt-physics` · `ozz-animation` · `recastnavigation` · `effekseer`
- **Web 3D, Multiplayer & JS AI (5):** `colyseus` · `three-quarks` · `yuka` · `build-67js-scene` · `render-67js-media`
- **2D Art, Isometric, Cleanup, Maps, VFX & QA (29):** `generate2dmedia` · `generate2dsprite` · `generate2dmap` · `wang-tiles` · `water-shorelines` · `see-through` · `atmospheric-perspective` · `shadowcasting` · `sprite-stacking` · `pixel-perfect` · `loot-window` · `video2dsprite` · `sprite-gen` · `codeart2d` · `backgroundremover` · `pixel-snapper` · `spritefusion-pixel-snapper` · `spritefusion-sprite-normals` · `image-to-pixel` · `flat2iso` · `pixelorama` · `ldtk` · `lpc-character-generator` · `creature-gen` · `pixelfx` · `vfx-forge` · `pixel-art-atlas` · `pixel-asset-manager` · `voxl`
- **3D Models, Blender, PBR & Harmonization (9):** `blender-kiln` · `mcp-for-blender` · `glb-forge` · `asset-harmonizer` · `polyspoon` · `material-maker` · `mesh-splatting` · `triposr` · `sand3d-to-roblox`
