---
name: web-2d-games
description: Use when building 2D top-down, tile-based, or UI-heavy web games (Phaser 3 + React/Tailwind/Zustand), translating 2D desktop/Godot game designs to the web stack, or designing chunked procedural tilemaps.
---

# Web 2D Games (Hybrid Architecture)

Architecture, desktop-to-web translation rules, and non-negotiable boundaries for 2D top-down, tile-based, UI-heavy web games built with **Phaser 3.8x + React 18 + Zustand + Vite**.

Code templates for EventBus, Zustand bridge, ChunkManager, and Weighted A* live in `playbook.md`.

## The Core Philosophy: The Hybrid Stack

Pure canvas UI in web games is a maintenance trap. For UI-dense games (grid inventory, crafting minigames, slot drag-and-drop, rich tooltips), canvas UI takes 5x longer to build and lacks accessibility, responsive layout, and DOM drag-and-drop tooling.

**The Golden Split:**
- **Canvas / WebGL (Phaser 3.8x):** World rendering, tilemaps, physics, lighting (Light2D), particle pools, camera lerp/zoom.
- **DOM / React (React 18 + Tailwind + Zustand + @dnd-kit):** HUD, slot drag-and-drop inventory, crafting screens, tooltips, dialogue menus.

### Recommended Stack Matrix

| Layer | Tool | Rationale |
|---|---|---|
| **Game Engine** | **Phaser 3.8x + TypeScript** | Built-in tilemap, Arcade physics, camera lerp/zoom, Light2D pipeline, scene lifecycle. |
| **Build Tool** | **Vite** | Instant HMR for rapid playtest cycles. |
| **UI Layer** | **React 18 + Tailwind** | Fast declarative DOM layouts for complex game menus. |
| **State Bridge** | **Zustand** | Lightweight global store decoupled from engine internals. |
| **Drag & Drop** | **@dnd-kit/core** | Slot-based grid inventory drag-and-drop. |
| **Worldgen Noise** | **simplex-noise** | FastNoiseLite equivalent in JS with FBM support. |
| **Pathfinding** | **Custom A\* (~100 lines)** | Weighted cost grid (floor: 1, door: 50, wall: 200) for tactical / siege AI. |
| **Persistence** | **localForage** (IndexedDB) | Async storage for chunk deltas and inventory serialization. |
| **Audio** | **Phaser Web Audio** | Built-in sound manager with pitch/volume randomization; no external library needed. |
| **Desktop Export** | **Tauri v2** | Zero-bloat native wrapper for Steam/Desktop releases. |

---

## Desktop Engine → Web Translation Matrix (Godot to Web)

When adapting 2D desktop designs (e.g. Godot GDDs) to the web ecosystem:

| Desktop / Godot Concept | Web / Phaser / TypeScript Equivalent | Rule |
|---|---|---|
| `TileMapLayer` + Terrain Set (autotile) | Phaser Tilemap + **Tiled editor** | Export Wang tiles / terrain brush as JSON. |
| `CharacterBody2D.move_and_slide()` | Arcade Physics collider + custom `move_toward` | Calculate velocity vectors directly in TS update loop. |
| `CanvasModulate` (day/night) | Phaser **Light2D pipeline**: `setAmbientColor()` + tint | WebGL only. Fallback: blend-mode overlay. |
| `PointLight2D` | Phaser PointLight | Built-in native lights. |
| `modulate` (Palette Swap) | `sprite.setTint(hex)` | **1 Asset, 100 Variations**: grayscale base sprite + runtime tint. |
| `change_scene()` (layer transition) | `this.scene.start('SceneKey')` | Native Phaser scene lifecycle. |
| Signals (`emit_signal`) | Singleton `EventBus extends Phaser.Events.EventEmitter` | Strict event-driven decoupling between game and UI. |
| `.tres` Resources (ItemData, MobDB) | Plain TypeScript typed constants | `export const ITEM_DATABASE = { ... } as const;` |
| `NavigationServer2D` | Custom A* Cost Grid | Weighted tile costs enable destructible paths (breaking walls). |
| `AnimationPlayer` (tweens / swings) | Phaser Tweens + sprite frame animations | Programmatic tweens for juice; sprite sheets for walk cycles. |
| Autoloads | Plain TS Singletons | `EventBus`, `SaveManager`, `GameTime`. |
| `Viewport stretch keep` (Pixel art) | Phaser Scale Manager config | `zoom: N, roundPixels: true`, `pixelArt: true`. |

---

## Non-Negotiable Architectural Laws

### 1. The Bridge Law (Decoupled State)
- **Engine → UI:** Phaser systems emit events via `EventBus` → Zustand store subscribes and updates state → React re-renders HUD/Menus.
- **UI → Engine:** React actions invoke Zustand actions / dispatch to `EventBus` → Phaser scenes listen and execute simulation logic.
- **CRITICAL:** NEVER pass Phaser `Scene`, `Sprite`, or physics body instances into React state. Passing engine instances into React causes memory leaks, broken garbage collection, and re-render thrashing. `EventBus` is the single border patrol.

### 2. Infinite Worlds on Static Tilemaps (Chunking)
Phaser tilemaps are static structures with fixed dimensions. There is no native infinite streaming mode.
- **Per-Chunk Instances:** Treat every chunk (e.g., 16x16 tiles) as an independent `Tilemap` instance.
- **Streaming Lifecycle:** As the player traverses chunks, create entering chunks with `scene.make.tilemap()` and destroy distant chunks with `tilemap.destroy()`.
- **Dynamic / Destructible Separation:** Never place destructible or breakable tiles (e.g. mineable ores, collapse structures) directly into the static Tilemap layer. Render them as **Sprite entities inside a Container**. This allows pure JS BFS collapse algorithms and health tracking without rebuilding GPU tile buffers.

### 3. Light2D Performance Fallback
- Light2D relies on WebGL pipelines. On low-end mobile browsers, fallback to a full-screen ambient rectangle with radial gradient light mask sprites using `Phaser.BlendModes.MULTIPLY`.

---

## Standard Layout

```
src/
  scenes/        → Boot, Surface, Dungeon, ...
  systems/       → WorldGenerator, ChunkManager, Pathfinding, GameTime
  entities/      → Player, Enemy, BreakableRock, DroppedItem
  data/          → items.ts, recipes.ts, terrainBiomes.ts
  state/         → useGameStore.ts (Zustand)
  ui/            → React: HUD, InventoryGrid, CraftingWindow, Tooltip
  events/        → EventBus.ts
```

## Bootstrap Quickstart

```bash
npm create vite@latest my-2d-game -- --template react-ts
npm i phaser zustand localforage simplex-noise @dnd-kit/core
npm i -D tailwindcss @types/node
```

## Definition of Done (First Milestone: Asset Pipeline Validation)
Before generating procedural worlds or complex AI:
1. Load a single grayscale base asset (e.g. `rock_base.png`).
2. Tint it into 5 distinct biome/mineral variants at runtime using `setTint()`.
3. Verify pixel art scaling without blur (`pixelArt: true`, integer zoom).
If runtime tinting and pixel alignment do not work cleanly in under 20 lines of TS, pause and fix the asset pipeline before writing gameplay systems.
