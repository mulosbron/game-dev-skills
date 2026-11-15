---
name: pixel-art-atlas
description: >-
  Instant search, retrieval, inspection, and GameMaker '_stripN.png' export for the 1.4-million
  synthetic pixel art sprite dataset (Angais/pixel-art-atlas-1.4m / co.huggingface.angais.pixel-art-atlas-1.4m).
  Features 6,194 subject categories (weapons, monsters, armor, food, props, biomes, icons) in native 16x16 RGBA,
  O(1) memory-mapped lookup via tokens.npy, nearest-neighbor scaling (1x, 2x, 4x, 8x), and cluster-faceted
  dynamic 2D lighting normal map generation.
---

# Pixel Art Atlas 1.4M — AI Agent Skill

This skill provides instant, token-free search and GameMaker-ready sprite export from the **Pixel Art Atlas 1.4M** dataset (`Angais/pixel-art-atlas-1.4m` / `co.huggingface.angais.pixel-art-atlas-1.4m`).

The collection contains **1,409,404 native 16×16 transparent sprites** spanning **6,194 unique subject categories**, completely cleared under **CC0 1.0 Universal (Public Domain Dedication)**.

---

## ⚡ Architecture & Zero-Cost Memory Mapping

Instead of polluting the filesystem with 1.4 million individual disk files, the dataset is loaded via a zero-cost memory-mapped token array:

```
[6,194 Categories] ---> [catalogs/pixel_art_atlas_index.json] (Sub-millisecond keyword lookup)
                               |
                               v
[Sprite Row ID]    ---> [assets/co.huggingface.angais.pixel-art-atlas-1.4m/tokens.npy] (O(1) mmap)
                               |
                               v
                       [palette.npy] (256 RGB Colors + Index 0 Alpha)
                               |
            +------------------+------------------+
            |                                     |
            v                                     v
  [Single Scaled Sprite]              [GameMaker _stripN.png]
  (spr_<subject>_s4.png)              (spr_<subject>_strip6.png)
            |                                     |
            +------------------+------------------+
                               |
                               v
               [tools/normal_map_gen.py]
         (Faceted Normal Map *_n.png + Preview GIF)
```

---

## 🛠️ CLI Tool: `tools/pixel_atlas_manager.py`

### 1. Fast Keyword Search (`search`)
Search subject categories or full English captions:
```powershell
# Search matching categories and sample sprite IDs:
python tools/pixel_atlas_manager.py search "potion" --limit 10

# Search only subject names (faster):
python tools/pixel_atlas_manager.py search "dragon" --subjects-only

# Search specific item keywords:
python tools/pixel_atlas_manager.py search "crystal sword" --limit 5
```

### 2. Export Single Sprite (`export`)
Export one or more sprites by ID with integer scaling and transparent alpha:
```powershell
# Export sprite #553 scaled 4x (64x64) to exports/co.huggingface.angais.pixel-art-atlas-1.4m/:
python tools/pixel_atlas_manager.py export --id 553 --scale 4

# Export multiple sprite IDs at once:
python tools/pixel_atlas_manager.py export --id 105 224 260 --scale 2

# Export sprite and automatically generate 2D dynamic lighting normal map:
python tools/pixel_atlas_manager.py export --id 553 --scale 4 --normal
```

### 3. Export GameMaker Horizontal Strip (`strip`)
Assembles multiple sprites from a subject category into a standard GameMaker horizontal strip:
```powershell
# Export a 6-frame strip scaled 2x (32x32 per frame):
python tools/pixel_atlas_manager.py strip --subject "baby dragon" --count 6 --scale 2

# Output file:
# exports/co.huggingface.angais.pixel-art-atlas-1.4m/spr_baby_dragon_strip6.png
```

### 4. Generate 2D Tangent Normal Maps (`normal`)
Converts pixel art into tangent-space normal maps (`*_n.png`) and cavity light masks (`*_m.png`):
```powershell
python tools/pixel_atlas_manager.py normal --id 553 --scale 4
```

### 5. Verify Dataset Status (`stats`)
Check disk footprint, shard integrity, and catalog counts:
```powershell
python tools/pixel_atlas_manager.py stats
```

---

## 📜 Legal Ledger & Attribution
- **Dataset Author**: Angais ([Hugging Face profile](https://huggingface.co/Angais), [Buy Me a Coffee](https://buymeacoffee.com/angaisb_))
- **License**: CC0 1.0 Universal (Public Domain)
- **Master Legal Ledger**: `assets/co.huggingface.angais.pixel-art-atlas-1.4m/LICENSES.txt`
- **Reverse-DNS Identifier**: `co.huggingface.angais.pixel-art-atlas-1.4m`
