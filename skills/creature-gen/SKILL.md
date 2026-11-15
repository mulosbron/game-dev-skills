---
name: creature-gen
description: >-
  Generate, breed, mutate and export endless procedural pixel art creatures and monsters
  (quadrupeds, bipeds/humanoids, reptiles/dragons, arthropods/spiders, winged creatures/birds/bats,
  serpents/worms, aquatic/fish/sharks, slimes/tentacles, plantfolk) in 8 directions with idle,
  walk, run, action, hit, and sleep animations, without sprites or AI images.
  Exports ready-to-use GameMaker '_stripN.png' files, full spritesheets, genome JSON presets,
  and dynamic 2D lighting normal maps using the C# core engine (com.github.idlerunner00.procedural-pixel-creatures).
---

# Procedural Pixel Creatures - AI Agent Skill

This skill provides direct access to the **Procedural Pixel Creatures** engine (`com.github.idlerunner00.procedural-pixel-creatures`).
Creatures are 100% code-driven—bodies, limbs, faces, markings, rigs, and movements are generated procedurally on CPU with zero pre-made sprites or AI hallucination risk.

---

## 🐾 Supported Creature Families (9 Body Plans)

1. **`quadruped`** (Quadrupeds & Beasts): Mammals from rodents to heavy beasts (canine, feline, ungulate, bear, rodent).
2. **`biped`** (Bipeds & Humanoids): Goblins, orcs, dwarves, yetis, trolls, ogres, imps. Procedural armor, helmets, weapons.
3. **`reptile`** (Reptiles & Dragons): Lizards, crocodiles, turtles, salamanders, wyrms, winged dragons.
4. **`arthropod`** (Arthropods & Insects): Spiders, scorpions, beetles, mantises, crabs with jointed legs and stinger tails.
5. **`winged`** (Winged Creatures): Birds, raptors, owls, bats, dragonflies, moths with feathered or membrane wings.
6. **`serpent`** (Serpents & Worms): Snakes, cobras, constrictors, earthworms, sandworms with undulating body curves.
7. **`aquatic`** (Aquatic & Fish): Reef fish, sharks, rays, pufferfish, anglerfish, eels.
8. **`amorphous`** (Slimes & Tentacles): Slimes, oozes, floating eyes, wisps, octopuses with physics-driven trailing tentacles.
9. **`plantfolk`** (Plantfolk Extension): Mandrakes, saplings, mushroom folk, flytraps, blossoms, cacti walking on roots.

---

## ⚡ CLI Tool: `tools/creature_gen.py`

### 1. List Families
```powershell
python tools/creature_gen.py list
```

### 2. Generate a Creature (GameMaker-Ready Strips)
```powershell
# Generate a reptile with idle and walk animations facing south (camera front):
python tools/creature_gen.py generate --family reptile --seed 42 --clips idle,walk --dirs S

# Generate a humanoid warrior directly into a GameMaker project with normal maps:
python tools/creature_gen.py generate --family biped --name warrior --project "MyGame" --normal-map

# Generate a winged dragon with 8-directional walking and flying animations:
python tools/creature_gen.py generate --family winged --clips idle,walk,run --dirs all --sheet
```

### 3. Directions (`--dirs`)
- `S` (Default - Facing South / Front)
- `cardinal` (4-dir: E, N, W, S)
- `all` or `8dir` (8-dir: E, NE, N, NW, W, SW, S, SE)
- Specific indices or comma-separated names (e.g. `--dirs S,N`)

### 4. Animation Clips (`--clips`)
- `idle`: Breathing, blinking, hovering idle loop
- `walk`: Locomotion walk cycle
- `run`: High-speed sprint or flight
- `action`: Attack, strike, or bite
- `hit`: Hit reaction and damage flash
- `sleep`: Resting/sleeping coiled loop
- `all`: Exports all available actions

### 5. Breeding & Mutation
```powershell
# Mutate an existing creature preset to produce 4 variations:
python tools/creature_gen.py mutate --parent "path/to/creature_genome.json" --count 4 --strength 0.35

# Crossbreed two compatible creature parents:
python tools/creature_gen.py breed --parent-a "parent_a_genome.json" --parent-b "parent_b_genome.json" --count 4
```

---

## 🎮 GameMaker Import Convention

Generated sprites automatically conform to GameMaker Studio's strip import standard:
- File naming: `spr_creature_<name>_<action>_<dir>_strip<N>.png`
- Static Still: `spr_creature_<name>_still.png`
- Normal Map: `spr_creature_<name>_<action>_<dir>_strip<N>_n.png`
- Presets: `<name>_genome.json`
- Default Origin: **Bottom-Center** (Ground point below root)
