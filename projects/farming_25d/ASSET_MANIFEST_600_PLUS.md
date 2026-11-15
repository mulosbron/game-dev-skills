# 2.5D Farming & Retro FPS Hybrid — Asset Manifest & Inventory
### Document Version 2.0 (Guns 'n Goblins FPS 2.5D Architecture Edition)

This manifest provides a comprehensive index of all **2,484 production-grade assets** integrated into [`projects/farming_25d/`](file:///D:/GameMaker/projects/farming_25d/). All 2D sprites are quantized to the GDD Section 8.4 32-color palette and feature cluster-faceted normal maps (`_n.png`) for dynamic 3D lighting.

---

## 📊 High-Level Inventory Breakdown

| Asset Category | Subfolder Path | File Count | Format & Specifications |
| :--- | :--- | :---: | :--- |
| **Guns 'n Goblins Horde Enemies** | `sprites_2d/enemies_billboard/` | **318** | 4-Direction sheets + Front-Facing `_stripN.png` + normal maps (`_n.png`). Goblins (Archer, Bomb, Spear, Merchant), Slimes (Green, Blue, Pink, Purple in 3 sizes), Myconids, Spikes, Venom Blooms. |
| **Farm Livestock & Wildlife** | `sprites_2d/animals_billboard/` | **452** | Y-Billboard strips + normal maps. Dairy Cows, Brown Cows, Wool Sheep, Pigs, Chickens, Ducks, Goats, plus Forest Wildlife (Deer, Foxes, Rabbits, Frogs, Bees, Snails, Crows). |
| **Farming Crops Pipeline** | `sprites_2d/crops/` | **132** | 11 Crops x 6 Growth Stages (Stage 0 to 5) + cluster-faceted normal maps. Bottom-center grounded. |
| **Workbenches & Campfire Props** | `sprites_2d/props_billboard/` | **418** | Workbenches (Furnace, Anvil, Workbench, Alchemy, Sawmill, Butter churn, Cheese press, Jam maker, Beehive, Barrel), Campfire, Lanterns, Mine rails, Mine carts, Barns, Coops, Silos. |
| **3D Terrain & Wall Textures** | `sprites_2d/textures_3d/` | **22** | 16x16 & 32x32 seamless textures for 3D floors/walls: Dry Soil, Tilled Soil, Wet Soil, Caves, Dungeon, Spring/Fall Grass. |
| **First-Person Viewmodels** | `sprites_2d/viewmodels/` | **25** | FPS Viewmodels with sway & recoil: Gold Pickaxe, Gold Hoe, Gold Watering Can, Gold Scythe, Chrome Pistol with Muzzle Flash. |
| **Curated 3D-to-Pixel Renders** | `sprites_2d/pixelated_3d/` | **160** | 32 Curated 3D assets converted to 64px pixel art with cluster-faceted normal maps (`_n.png`), cavity light masks (`_m.png`), and lighting preview GIFs. |
| **Harvested Items & Seed Packets** | `sprites_2d/props_and_ui/` | **83** | 11 Harvested crops + 11 seed packets from CC0 Pixel Art Atlas 1.4M + soil tiles and tool icons. |
| **Procedural Combat VFX** | `enemies_8dir/` & `vfx/` | **324** | 8-Directional creature animations + procedural magic/combat VFX strips (`_stripN.png`). |
| **Environment 3D Models** | `models_3d/` | **191** | 43 Custom low-poly Blender meshes + 144 ABO/Sand3D game-ready GLB models (Campfire, Archway, Fence, Lantern post, Shed, Ores, Furniture). |
| **UI Components & Tool Progression** | `ui_ux/` | **220** | Day/Night clock face & hand, Health/Stamina bars, HUD frames, and 10 complete RPG tool tiers (Wood, Cooper, Iron, Gold, Platinum, Crimson, Frost, Shadow, Fairy, Obsidian). |
| **Godot 4 Engine Scenes & Scripts** | `scenes/`, `scripts/`, `shaders/` | **12** | Complete Godot 4.x playable project: `project.godot`, FPS Player, 3D Farming Grid Manager, Horde Enemy AI, Day/Night Cycle, CRT post-processing shader. |
| **TOTAL REGISTERED ASSETS** | `projects/farming_25d/` | **2,484** | **100% Complete, Self-Contained, Relocation-Ready** |

---

## 🌿 11 Crops Growth Matrix (132 Files)

Every crop includes:
- Stages 0 to 5 (`crop_<name>_stage_00.png` to `crop_<name>_stage_05.png`)
- Tangent-space normal maps (`crop_<name>_stage_XX_n.png`)
- Harvested crop item icon (`item_crop_<name>.png`)
- Seed packet icon (`item_seed_<name>.png`)

1. **Buğday (Wheat)** — Single harvest, fast growth (4 days).
2. **Domates (Tomato)** — Multi-harvest, yields fruit every 3 days after maturity.
3. **Havuç (Carrot)** — Single harvest underground root.
4. **Patates (Potato)** — Chance of bonus yield per plant.
5. **Kabak (Pumpkin)** — Large 32px blocky crop.
6. **Mısır (Corn)** — Tall 2-block crop in FPS perspective.
7. **Lahana (Cabbage)** — Dense leafy crop.
8. **Turp (Radish)** — Fast 3-day turnaround crop.
9. **Ayçiçeği (Sunflower)** — Tall bloom yielding sunflower seeds and oil.
10. **Pancar (Beetroot)** — High-tier sugar crafting ingredient.
11. **Kale (Kale)** — Hardy winter crop.

---

## 👹 Guns 'n Goblins Horde Enemies (318 Files)

Every enemy is exported as:
1. Full 4-Direction spritesheet (`<name>.png` + `<name>_n.png`).
2. Front-Facing horizontal animation strip (`<name>_front_stripN.png` + `<name>_front_stripN_n.png`) for instant Y-billboard instantiation in Godot 4.

- **Archer Goblin:** `Idle` (4 frames), `Walk` (6 frames), `Run` (6 frames), `Bow` (7 frames), `Damage` (2 frames), `Dead` (5 frames).
- **Bomb Goblin:** `Idle` (4 frames), `Walk` (6 frames), `Run` (6 frames), `Throw a bomb` (6 frames), `Damage` (2 frames), `Dead` (5 frames).
- **Spear Goblin:** `Idle` (4 frames), `Walk` (6 frames), `Run` (6 frames), `Spear` (7 frames), `Damage` (2 frames), `Dead` (5 frames).
- **Goblin Merchant:** Friendly NPC animations (4 variants).
- **Slimes (Green, Blue, Pink, Purple):** Big Slime, Normal Slime, Small Slime with `Idle`, `Walk`, `Damage`, `Dead`.
- **Myconids (Green, Blue, Pink, Purple):** Mushroom humanoids for K2 Mantar Ormanı with `Idle`, `Walk`, `Attack`, `Damage`, `Dead`.
- **Spike Monsters:** Underground burrowing monsters with `entering`, `idle`, `spitting`, `leaving`, `damage`, `dead`, plus 5 colored projectile sprites.
- **Venom Blooms:** Toxic dungeon plants with `Wake up`, `Idle`, `Attack`, `Damage`, `Dead`, `Fx`.

---

## 🛠️ 10 Tiers of RPG Tool Progression (150 Files)

Located in `ui_ux/icons/`:
- **Tier 1:** Wood (`tier_1_wood/`)
- **Tier 2:** Copper (`tier_2_cooper/`)
- **Tier 3:** Iron (`tier_3_iron/`)
- **Tier 4:** Gold (`tier_4_gold/`)
- **Tier 5:** Platinum (`tier_5_platinum/`)
- **Tier 6:** Crimson (`tier_6_crimson/`)
- **Tier 7:** Frost (`tier_7_frost/`)
- **Tier 8:** Shadow (`tier_8_shadow/`)
- **Tier 9:** Fairy (`tier_9_fairy/`)
- **Tier 10:** Obsidian (`tier_9_obsidian/`)

Each tier contains 15 icons: `Hoe`, `Pickaxe`, `Axe`, `Sword`, `Bow`, `Fishing Rod`, `Helmet`, `Chestplate`, `Leggings`, `Boots`, `Arrow`, `Shield`.

---

## 📜 Legal Attributions & Licenses
- **Farm RPG Tiny Asset Pack:** Created by EmanuelleDev ([emanuelledev.itch.io](https://emanuelledev.itch.io)). Full commercial rights granted with attribution.
- **Pixel Art Atlas 1.4M:** Created by Angais. Dedicated to the Public Domain under **CC0 1.0 Universal**.
- **Procedural Pixel Creatures:** Created by idlerunner00 under the **MIT License**.
- **Amazon Berkeley Objects (ABO):** Created by Amazon under **CC-BY-4.0**.
- **Sand3D:** Created by Sandflow AI under **Apache 2.0**.
- **Moonfell Pixel Art Lighter:** Normal map cluster-faceted algorithm under **MIT License**.
