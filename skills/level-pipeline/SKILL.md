---
name: level-pipeline
description: "No-Engine Plain-JS Custom 2D Micro-Engine & In-Browser Level Studio generator, human-first BFS reachability validator, declarative room-piece assembler, and playtest heatmap analyzer."
---

# Custom 2D Micro-Engine & Human-First Level Pipeline (`level-pipeline`)

This skill implements a **No-Engine Plain-JS Custom Micro-Engine + Hybrid Handcrafted Level Pipeline**:
> *"Instead of fighting bulky game engines for 2D tile/puzzle games, AI builds and maintains a zero-dependency Plain-JS Custom Micro-Engine + Live In-Browser Level Studio. AI handles the engine loop, collision, BFS validation, declarative stitching, and telemetry so the human designer can spend 100% of their time placing tiles, building puzzles, hiding secrets, and pressing [TAB] to playtest immediately."*

---

## 🕹️ 1. Build a Custom Plain-JS Micro-Engine & In-Browser Studio (`tools/micro_engine.py`)

Generates a zero-dependency, single-file HTML5 Canvas + Plain JavaScript **Custom 2D Game Engine & Level Editor** (`exports/com.agent-game-forge.levels/forge_micro_studio.html`) with:
* **Instant `EDIT` ↔ `PLAY` Toggle (`TAB` key):** Hand-paint tiles (`#` Wall, `H` Ladder, `^` Spikes, `K` Key, `D` Door, `?` Secret) with the mouse, then press `TAB` to immediately playtest in the exact same window.
* **Dual Physics Engines Built-In:** Switch live between **Platformer (gravity, ladder climbing, coyote time, jump buffering)** and **Top-Down 2D Dungeon physics**.
* **Explicit Finite State Machine (Steve Ruiz Rule):** Deterministic `PLAYER_STATES` enum (`EDITOR_IDLE`, `IDLE`, `RUN`, `JUMP`, `FALL`, `CLIMB`, `DEAD`, `WIN`) with live state transition HUD—zero entangled boolean flags.
* **Live In-Browser BFS Reachability & Softlock Overlay:** Automatically stripes unreachable tiles in red while you paint tiles and checks if `Spawn (S) -> Key (K) -> Door (D) -> Exit (E)` and `Secrets (?)` are reachable.
* **Live Declarative Stitcher & Telemetry Heatmap:** Stitch handcrafted pieces from JSON rules (`never_adjacent`, `every_n_rooms`) and toggle a live Death (`X`) & Exploration Heatmap overlay right on the canvas.

```powershell
python tools/micro_engine.py build --title "Agent Game Forge 2D Studio" --genre platformer
```

---

## 🛑 STRICT AGENT AUTHORITY BOUNDARIES (MANDATORY)

| Task / Domain | Owner | Agent Rule |
| :--- | :--- | :--- |
| **Tile Placement, Puzzle Layout & Secret Hiding** | 👤 **Human** | **NEVER** overwrite or auto-generate interior puzzle/secret layouts inside human-authored `pieces/*.json` or `.ldtk` files unless given explicit coordinate instructions. |
| **Empty Room / Piece Scaffolding** | 🤖 **AI Agent** | When asked for a new room, run `python tools/level_pipeline.py scaffold <id>` to create a clean empty template for the human to paint. |
| **Schema, Collision & BFS Reachability Validation** | 🤖 **AI Agent** | Run `python tools/level_pipeline.py validate <path>` to verify `spawn -> key -> door -> exit` reachability and softlocks. Report **only technical facts**, never subjective design rewrites. |
| **Declarative Piece Stitching (Zaxik Pattern)** | 🤝 **Hybrid** | Human authors `pieces/*.json` and declarative rules (`must_include`, `never_adjacent`); AI runs `assemble` to stitch and verify connected dungeons. |
| **Playtest Telemetry & Heatmaps** | 🤖 **AI Agent** | Run `playtest-report` on `.jsonl` playtest logs to render **Death & Unvisited Secret Heatmaps (`_heatmap.png`)** so the human decides how to tune difficulty. |
| **Implicit State Machine Audit (Steve Ruiz Rule)** | 🤖 **AI Agent** | When debugging gameplay/level scripts, scan for entangled boolean flags (`isClimbing && !isGrounded && !isLocked`) and refactor/report implicit state machines into explicit states. |

---

## 🧱 Tile Legend for Handcrafted Pieces (`pieces/*.json`)

Human designers can edit room pieces directly in JSON/ASCII or export from LDtk/Tiled:
* `#` : Solid Wall (`walkable: False`)
* `.` : Walkable Floor / Open Space
* `H` : Climbable Ladder
* `^` : Spike / Hazard (`hazard: True`)
* `S` : Player Spawn
* `E` : Level Exit
* `K` : Key Item
* `D` : Locked Door
* `?` : Hidden Secret Alcove / Chest
* `+` : Border Connector Doorway (automatically stitched to `.` when adjacent to another room, or sealed to `#` on outer boundaries)

---

## ⚡ CLI Workflow (`tools/level_pipeline.py`)

### 1. Scaffold an Empty Room Piece for the Human Designer (`scaffold`)
```powershell
python tools/level_pipeline.py scaffold "crypt_puzzle_02" -W 12 -H 8
```

### 2. Validate Schema, BFS Pathfinding & Softlocks (`validate`)
Checks rectangular grid integrity, tile whitelist, safe path from `S` (Spawn) to `E` (Exit) without stepping on `^` (Spikes), key-before-door availability, and walled-off `?` secrets:
```powershell
python tools/level_pipeline.py validate "exports/com.agent-game-forge.levels/dungeon_ruins_01.json"
```

### 3. Assemble Handcrafted Pieces via Declarative Rules (`assemble`)
Reads a declarative rule file (e.g., `never_adjacent: [["spike_corridor", "secret_alcove"]]`, `must_include: [...]`) and stitches handcrafted pieces into a playable level JSON + visual PNG map:
```powershell
python tools/level_pipeline.py assemble "exports/com.agent-game-forge.levels/ruins_rules.json" --seed 7
```

### 4. Playtest Telemetry & Visual Death/Exploration Heatmap (`playtest-report`)
Parses `.jsonl` playtest event logs (`move`, `death`, `secret_found`, `complete`), dims unvisited tiles (immediately revealing if a `?` secret room was missed!), and plots red death-density circles over spike/trap hotspots:
```powershell
python tools/level_pipeline.py playtest-report \
  "exports/com.agent-game-forge.levels/dungeon_ruins_01.json" \
  "exports/com.agent-game-forge.levels/playtest_ruins_01.jsonl"
```

### 5. Run Full End-to-End Demo Suite (`demo`)
Generates 5 sample handcrafted pieces, 1 declarative rule spec, stitches the dungeon, validates BFS reachability, and renders the playtest heatmap PNG:
```powershell
python tools/level_pipeline.py demo
```
