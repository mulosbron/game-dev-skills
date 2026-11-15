# Web 2D Games — Architecture Playbook

Generalized TypeScript patterns for hybrid Phaser 3 + React 18 + Zustand web games.

---

## 1. EventBus Singleton

The event boundary between the Phaser canvas world and React UI.

```typescript
// src/events/EventBus.ts
import Phaser from 'phaser';

export const EventBus = new Phaser.Events.EventEmitter();
```

---

## 2. React-Phaser Zustand Bridge

Phaser emits events via `EventBus` → Zustand updates state → React re-renders.
React user interactions trigger Zustand actions / emit events → Phaser responds.

```typescript
// src/state/useGameStore.ts
import { create } from 'zustand';
import { EventBus } from '../events/EventBus';

export interface GridItem {
  id: string;
  type: string;
  quantity: number;
  weight: number;
}

interface GameState {
  health: number;
  maxHealth: number;
  inventory: GridItem[];
  isInventoryOpen: boolean;

  // Actions called from React UI
  toggleInventory: () => void;
  useItem: (itemId: string) => void;
  dropItem: (itemId: string) => void;
}

export const useGameStore = create<GameState>((set, get) => ({
  health: 100,
  maxHealth: 100,
  inventory: [],
  isInventoryOpen: false,

  toggleInventory: () => set((state) => ({ isInventoryOpen: !state.isInventoryOpen })),

  useItem: (itemId) => {
    EventBus.emit('ui-use-item', itemId);
  },

  dropItem: (itemId) => {
    EventBus.emit('ui-drop-item', itemId);
  },
}));

// Synchronize engine updates into the global store
EventBus.on('engine-player-health-changed', (health: number) => {
  useGameStore.setState({ health });
});

EventBus.on('engine-inventory-synced', (inventory: GridItem[]) => {
  useGameStore.setState({ inventory });
});
```

---

## 3. Dynamic Chunk Manager (Infinite Static Tilemaps)

Since Phaser tilemaps are static, instantiate discrete chunk tilemaps and prune out-of-range chunks.

```typescript
// src/systems/ChunkManager.ts
import Phaser from 'phaser';
import { createNoise2D } from 'simplex-noise';

export const CHUNK_SIZE = 16; // 16x16 tiles per chunk
export const TILE_SIZE = 16;  // 16x16 px per tile

export class ChunkManager {
  private scene: Phaser.Scene;
  private activeChunks: Map<string, Phaser.Tilemaps.Tilemap> = new Map();
  private noise2D = createNoise2D();

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  private chunkKey(cx: number, cy: number): string {
    return `${cx},${cy}`;
  }

  public update(playerWorldX: number, playerWorldY: number, radius = 2) {
    const centerChunkX = Math.floor(playerWorldX / (CHUNK_SIZE * TILE_SIZE));
    const centerChunkY = Math.floor(playerWorldY / (CHUNK_SIZE * TILE_SIZE));

    const visibleKeys = new Set<string>();

    for (let dx = -radius; dx <= radius; dx++) {
      for (let dy = -radius; dy <= radius; dy++) {
        const cx = centerChunkX + dx;
        const cy = centerChunkY + dy;
        const key = this.chunkKey(cx, cy);
        visibleKeys.add(key);

        if (!this.activeChunks.has(key)) {
          this.generateChunk(cx, cy, key);
        }
      }
    }

    // Prune distant chunks
    for (const [key, tilemap] of this.activeChunks.entries()) {
      if (!visibleKeys.has(key)) {
        tilemap.destroy();
        this.activeChunks.delete(key);
      }
    }
  }

  private generateChunk(cx: number, cy: number, key: string) {
    const data: number[][] = [];
    for (let y = 0; y < CHUNK_SIZE; y++) {
      const row: number[] = [];
      for (let x = 0; x < CHUNK_SIZE; x++) {
        const worldX = cx * CHUNK_SIZE + x;
        const worldY = cy * CHUNK_SIZE + y;
        const n = this.noise2D(worldX * 0.05, worldY * 0.05);

        // Noise thresholds
        if (n < -0.2) row.push(0); // Water
        else if (n < 0.0) row.push(1); // Sand
        else row.push(2); // Grass / Ground
      }
      data.push(row);
    }

    const map = this.scene.make.tilemap({
      data,
      tileWidth: TILE_SIZE,
      tileHeight: TILE_SIZE,
    });

    const tileset = map.addTilesetImage('terrain_tileset');
    if (tileset) {
      const layer = map.createLayer(0, tileset, cx * CHUNK_SIZE * TILE_SIZE, cy * CHUNK_SIZE * TILE_SIZE);
      if (layer) {
        layer.setCollision([0]); // Collision on water
      }
    }

    this.activeChunks.set(key, map);
  }
}
```

---

## 4. Weighted A* Pathfinding (~100 Lines)

Tactical / Siege AI pathfinding supporting weighted obstacles (floors: 1, doors: 50, breakable walls: 200).

```typescript
// src/systems/AStarPathfinder.ts
export interface PathNode {
  x: number;
  y: number;
  g: number;
  h: number;
  f: number;
  parent?: PathNode;
}

export type CostFunction = (x: number, y: number) => number;

export class AStarPathfinder {
  constructor(private getCost: CostFunction) {}

  public findPath(startX: number, startY: number, targetX: number, targetY: number): { x: number; y: number }[] {
    const openList: PathNode[] = [];
    const closedSet = new Set<string>();
    const nodeKey = (x: number, y: number) => `${x},${y}`;

    openList.push({
      x: startX,
      y: startY,
      g: 0,
      h: Math.abs(targetX - startX) + Math.abs(targetY - startY),
      f: 0,
    });

    while (openList.length > 0) {
      openList.sort((a, b) => a.f - b.f);
      const current = openList.shift()!;

      if (current.x === targetX && current.y === targetY) {
        const path: { x: number; y: number }[] = [];
        let curr: PathNode | undefined = current;
        while (curr) {
          path.unshift({ x: curr.x, y: curr.y });
          curr = curr.parent;
        }
        return path;
      }

      closedSet.add(nodeKey(current.x, current.y));

      const neighbors = [
        { x: current.x + 1, y: current.y },
        { x: current.x - 1, y: current.y },
        { x: current.x, y: current.y + 1 },
        { x: current.x, y: current.y - 1 },
      ];

      for (const n of neighbors) {
        if (closedSet.has(nodeKey(n.x, n.y))) continue;

        const cost = this.getCost(n.x, n.y);
        if (!isFinite(cost)) continue; // Impassable void

        const g = current.g + cost;
        const h = Math.abs(targetX - n.x) + Math.abs(targetY - n.y);
        const existing = openList.find((node) => node.x === n.x && node.y === n.y);

        if (!existing) {
          openList.push({ x: n.x, y: n.y, g, h, f: g + h, parent: current });
        } else if (g < existing.g) {
          existing.g = g;
          existing.f = g + existing.h;
          existing.parent = current;
        }
      }
    }

    return []; // No path found
  }
}
```

---

## 5. Runtime Palette Swap ("1 Asset, 100 Variations")

```typescript
// src/data/palette.ts
export interface VariantDefinition {
  id: string;
  tint: number;
  health: number;
}

export const VARIANTS: Record<string, VariantDefinition> = {
  TYPE_A: { id: 'type_a', tint: 0x95a5a6, health: 3 },
  TYPE_B: { id: 'type_b', tint: 0xbdc3c7, health: 2 },
  TYPE_C: { id: 'type_c', tint: 0x2c3e50, health: 4 },
  TYPE_D: { id: 'type_d', tint: 0xf39c12, health: 1 },
  TYPE_E: { id: 'type_e', tint: 0x1b1464, health: 5 },
};

// Spawn sprite with grayscale base + runtime tint
export function createTintedSprite(
  scene: Phaser.Scene,
  x: number,
  y: number,
  baseTexture: string,
  variant: VariantDefinition
): Phaser.GameObjects.Sprite {
  const sprite = scene.add.sprite(x, y, baseTexture);
  sprite.setTint(variant.tint);
  sprite.setData('variant', variant);
  return sprite;
}
```
