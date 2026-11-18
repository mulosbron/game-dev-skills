# PlayForge & Agent Game Forge (`game-dev-skills`)

Unified game development workspace, asset/library forge, CLI toolkit, and skill collection (**68 top-level skills**, **79 `awesome-gamedev` sub-skills**, **78 `claude-code-game-studios` studio sub-skills**, **24 Reverse-DNS libraries**, **5 commercial-cleared asset collections**, and **40 Python CLI tools**). Compatible with Antigravity, Claude Code, Codex, Gemini CLI, Cursor, and Windsurf.

## Directory Layout

```text
game-dev-skills/
├── AGENTS.md                  # Binding agent guidelines, rules & full skill index
├── CLAUDE.md                  # @AGENTS.md entrypoint
├── README.md                  # Human quick-start & architecture overview
├── plugin.json                # Antigravity plugin manifest
├── .claude-plugin/plugin.json # Claude Code plugin manifest
├── .codex-plugin/plugin.json  # Codex plugin manifest
├── gemini-extension.json      # Gemini CLI extension config
├── package.json               # 67js & Node runtime deps (`node_modules/`)
├── .polyspoon/                # Polyspoon local procedural runtime
├── assets/                    # Commercial-cleared datasets (Reverse-DNS + LICENSES.txt)
│   ├── co.huggingface.angais.pixel-art-atlas-1.4m/  # 1,409,404 sprites (CC0)
│   ├── co.huggingface.sandflow.sand3d/              # 100k+ 3D objects (CC0 / CC-BY / Apache-2.0)
│   ├── com.amazon.berkeley.abo/                     # 7,953 .glb + convex hulls (CC-BY-4.0)
│   ├── com.threejsassets/                           # 1,041 web-ready low-poly .glb
│   └── org.opengameart.lpc/                         # Liberated Pixel Cup ledger
├── libraries/                 # 24 Reverse-DNS external repos/packages
├── catalogs/                  # Cached JSON indexes (`assets_index.json`, `polyspoon_catalog.json`, ...)
├── tools/                     # 40 Python asset, 3D, VFX, level & audio CLIs
├── exports/                   # Generated strips, normal maps, GLBs, levels & shaders
├── docs/                      # Reference guides (`godot-pixel-texture-rehberi.md`)
├── projects/                  # Active engine projects (`farming_25d/`, etc.)
└── skills/                    # 68 top-level skill directories (every skill listed in AGENTS.md)
```

## Step-by-Step User & Plugin Guide

### 1. Load as a Plugin or Workspace Pack
All four major agent ecosystems are pre-configured at the root of `game-dev-skills/`:

| Client | Config File | How to Use |
|---|---|---|
| **Antigravity IDE / CLI** | `plugin.json` | Installed under `~/.agents/game-dev-skills/` — automatically discovered; reference `@game-dev-skills` or open the folder as a workspace. |
| **Claude Code** | `.claude-plugin/plugin.json` + `CLAUDE.md` | Install/load plugin directory (`claude --plugin-dir ~/.agents/game-dev-skills` or copy into project). `CLAUDE.md` imports `@AGENTS.md`. |
| **Codex** | `.codex-plugin/plugin.json` (`"skills": "./skills/"`) | Register plugin/workspace directory so Codex indexes all 68 skills in `./skills/` plus `./AGENTS.md`. |
| **Gemini CLI** | `gemini-extension.json` (`"contextFileName": "AGENTS.md"`) | Link or install as an extension (`gemini extensions link ~/.agents/game-dev-skills`). |
| **Cursor / Windsurf** | `AGENTS.md` | Add `@AGENTS.md` or copy `AGENTS.md` + needed `skills/` into your project root. |

### 2. How the 3 Interactive Workflows Operate (`Discover → Report/GDD → Approve → Build`)

1. **Mode 1 — New Game from Scratch (Markdown `GDD.md` Gate):**
   - **Step 1 (`GDD.md`):** The agent first requests a **Markdown GDD (`GDD.md`)**. If you already have one, it only asks about missing technical decisions; otherwise, in 1 brief Q&A round (covering genre, art style, 30s core loop, engine, asset pipeline, v1 exclusions — each with a `(Recommended)` option), it drafts **`GDD.md`** and waits for your approval.
   - **Step 2 (Prototype → Layers):** After approval, it builds a single-scene **60-second playable prototype** with the selected skills/tools, then layers in `game-feel`, VFX/SFX, and QA/level checks.
   - *(Optional Studio Pipeline: `skills/claude-code-game-studios/SKILL.md` with `/start`, `/brainstorm`, `/art-bible`, `/prototype`, `/qa-plan`, `/playtest-report` phases.)*

2. **Mode 2 — Improving an Existing Game (Genre/Art Discovery → Diagnostic & Action Report):**
   - **Step 1 (Understand the Game):** Without modifying code first, the agent reads the game's **genre, sub-type, art style, and engine** from project files and clarifies which area you want improved (**UI/UX, VFX, SFX/Audio, Game Feel, Gameplay/AI, Camera, Physics**).
   - **Step 2 (Problem Detection & Report):** It scans the project and presents a file/line-level **Diagnostic & Action Report** (*"Detected Issues → Proposed UI/VFX/SFX/feel changes"*).
   - **Step 3 (Approved Execution):** After your approval, it applies changes step by step without breaking existing architecture.

3. **Mode 3 — Asset-Only Production (Standalone Asset / VFX / 3D / Audio Generation):**
   - No GDD or full-project audit is required; it only confirms the target engine format (`_stripN.png`, `.glb`, `.tres`, palette/resolution) and directly runs `tools/*.py` or the matching asset skills (`pixelfx`, `vfx-forge`, `polyspoon`, `blender-kiln`, `triposr`, `material-maker`, `spritefusion-sprite-normals`, `generate2dsprite`).

## Skill Highlights by Domain

- **Design, Loops, Production & Multi-Engine Routing (11):** `game-feel`, `hit-feedback`, `platformer-forgiveness`, `camera-follow-2d`, `game-engineering`, `crafting-systems`, `sustainable-indie-dev`, `web-2d-games`, `level-pipeline`, `claude-code-game-studios` (78 studio subskills, 49 agents, QA gates), and `awesome-gamedev` (`router/SKILL.md` dispatching 79 engine/genre/publishing sub-skills).
- **Godot 4 Ecosystem (10):** `godot`, `godot-fake-3d-character`, `godot-jolt`, `godot-voxel`, `terrain3d`, `limboai`, `phantom-camera`, `dialogic`, `godot-mcp`, `godot-pixel-pipeline`.
- **C++ Rendering, Physics, Animation, Navigation & VFX (5):** `the-forge`, `jolt-physics`, `ozz-animation`, `recastnavigation`, `effekseer`.
- **Multiplayer, Web 3D & JS Game AI (5):** `colyseus` (v0.18 + `references/`), `three-quarks`, `yuka`, `build-67js-scene`, `render-67js-media`.
- **2D Pixel Art, AI Sprites, VFX, Maps & Testing (29):** `generate2dmedia`, `generate2dsprite`, `generate2dmap`, `wang-tiles`, `water-shorelines`, `see-through`, `atmospheric-perspective`, `shadowcasting`, `sprite-stacking`, `pixel-perfect`, `loot-window`, `video2dsprite`, `sprite-gen`, `codeart2d`, `backgroundremover`, `pixel-snapper`, `spritefusion-pixel-snapper`, `spritefusion-sprite-normals`, `image-to-pixel`, `flat2iso`, `pixelorama`, `ldtk`, `lpc-character-generator`, `creature-gen`, `pixelfx`, `vfx-forge`, `pixel-art-atlas`, `pixel-asset-manager`, `voxl`.
- **3D Authoring, Reconstruction, Blender MCP & PBR Materials (8):** `blender-kiln`, `mcp-for-blender` (+ `references/`), `glb-forge`, `asset-harmonizer`, `polyspoon`, `material-maker`, `mesh-splatting`, `triposr`, `sand3d-to-roblox`.

## CLI Quick Reference (`tools/`)

```powershell
# Search indexed 2D assets without flooding context
python tools/asset_search.py search "idle" --limit 10

# Search & build procedural low-poly 3D models (Polyspoon)
python tools/polyspoon_tool.py search "tree"

# Search 1.4M CC0 sprites & export GameMaker _stripN.png
python tools/pixel_atlas_manager.py search "dragon"
python tools/pixel_atlas_manager.py strip --subject "baby dragon" --count 6 --scale 2

# Snap AI pixel art to integer grid & generate 2D normal maps
python tools/pixel_snapper.py "path/to/sprite.png" --palette pico8
python tools/normal_map_gen.py "path/to/sprite.png" --preview

# Search Sand3D / ABO / ThreeJS 3D asset catalogs & optimize GLBs
python tools/sand3d_manager.py search "chest"
python tools/abo_manager.py search "chair" --category chair
python tools/threejsassets_manager.py search "crate"
```

## Commercial Clearance & Provenance

All bundled `assets/` collections track licenses in `LICENSES.txt` (`CC0 1.0`, `CC-BY-4.0`, `Apache-2.0`, Free Commercial License v1 — zero NC restrictions on asset packs), and `libraries/` follows Reverse-DNS naming (`com.github.*`, `org.opengameart.*`, etc.).

## Related Packs
- `~/.agents/gamification-skills/` — Education-oriented classroom, card, board, and escape-room gamification.
