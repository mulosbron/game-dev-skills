---
name: image-to-pixel
description: "Convert 3D renders, photos, concept art, sprite strips, and videos into art-direction-locked retro pixel art using Image-to-Pixel 3.2.0 (16 dithering algorithms, 24 Lospec palettes, orphan pixel cleanup, pixel outlines, deduplicated tilesets, and local offline WebGL 2 studio)."
---

# Image-to-Pixel 3.2.0 (`image-to-pixel`)

Converts ordinary 3D model renders (`Sand3D`, `ABO`, `ThreeJS Assets`), concept art, and multi-frame animation strips into **art-direction-locked 2D pixel art** using `libraries/com.github.tezumie.image-to-pixel` (MIT License, by Tezumie) and `tools/image_to_pixel.py`.

---

## 🎨 How to Preserve Visual Design & Consistency Across a Whole Game

When converting multiple assets (characters, props, icons, backgrounds) for the same game, **NEVER** convert them with random widths, `extract` palettes, or mismatched dithering. Enforce these **4 Visual Consistency Rules**:

1. **Lock One Game Style Profile (`--profile`):**
   Pick a single profile for the entire project so every asset shares the exact same palette, Oklab color-matching distance, dithering texture, and outline color:
   * `clean-sprite` — Zero dithering (`none`), Endesga-32 palette, orphan cleanup + smooth clusters, outer dark outline (`#14101c`). **Mandatory for small animated sprites** to prevent frame-to-frame dither boiling!
   * `jrpg-16bit` — Endesga-32 palette, subtle `bayer4` (`0.22`) ordered dither, orphan cleanup, outer outline (`#181425`).
   * `dark-fantasy` — 46-color Apollo palette, `bluenoise` (`0.28`) dither, obsidian outer outline (`#0d0b14`). Ideal for Souls-like, Wuxia, and dark dungeon crawlers.
   * `pico-8` — Strict 16-color PICO-8 palette + `bayer2` checker dither.
   * `retro-handheld` — 4-color Game Boy DMG olive screen + `bayer2` dither.
   * `1bit-noir` — 2-color 1-Bit Monitor + `atkinson` error-diffusion (*Return of the Obra Dinn* look).
2. **Lock Texel Density (`--width`):**
   Keep a fixed pixel scale across asset categories so there are **zero mixels** (mismatched pixel sizes):
   * Icons / Loot Items: `--width 24` or `--width 32`
   * Props / Chests / Barrels / Standard Characters: `--width 48` or `--width 64`
   * Bosses / Large Structures: `--width 96` or `--width 128`
3. **Animation Strip Dither Guard (`_stripN.png`):**
   Error-diffusion dithering (`floyd-steinberg`, `atkinson`, `sierra`) recalculates noise per frame and causes distracting "pixel swimming/boiling" on animated sprites. `tools/image_to_pixel.py` automatically detects `_stripN.png` (or `--frames N`) and switches diffusion dither to ordered `bayer2` or `none` while keeping a single unified palette across all frames.
4. **No Outlines on Tilesets (`tileset` subcommand):**
   Sprites need `--outline outer` to pop against backgrounds, whereas repeatable ground/wall tiles must use `--outline none` so seams do not appear between tiles.

---

## ⚡ CLI Usage (`tools/image_to_pixel.py`)

### 1. List All Profiles, 24 Built-In Lospec Palettes & 16 Dithering Algorithms
```powershell
python tools/image_to_pixel.py list
```

### 2. Render a 6-Profile Art-Direction Comparison Matrix (`compare`)
Before converting a whole batch of assets, render a side-by-side comparison matrix PNG to pick the project's visual style:
```powershell
python tools/image_to_pixel.py compare "assets/com.threejsassets/thumbs/dun-treasure-chest.png" --width 64 --scale 3
```

### 3. Convert a 3D Render or Image into a Pixel Sprite + Normal Map (`convert`)
Exports both the `1x` native game sprite and an integer-scaled preview, plus optional Moonfell Faceted Normal Map (`_n.png`), Light Mask (`_m.png`), and Dynamic Lighting GIF (`--normal-map`):
```powershell
python tools/image_to_pixel.py convert "assets/com.threejsassets/thumbs/dun-treasure-chest.png" --profile jrpg-16bit --width 64 --scale 4 --normal-map
```

### 4. Convert a Multi-Frame Strip into a Pixelated GameMaker `_stripN.png` + GIF + JSON Atlas
```powershell
python tools/image_to_pixel.py convert "path/to/character_walk_strip8.png" --profile clean-sprite --width 64
```

### 5. Build a Deduplicated Pixel Tileset + Tilemap JSON (`tileset`)
Pixelates an image/texture and slices it into unique deduplicated `16x16` (or `8x8`) tiles (with horizontal/vertical flip deduplication) + a JSON tilemap:
```powershell
python tools/image_to_pixel.py tileset "assets/com.threejsassets/thumbs/agora-flagstone-tile.png" --profile dark-fantasy --width 128 --tile-size 16
```

### 6. Launch the 100% Local Offline WebGL 2 Browser Editor (`serve-editor`)
Runs the full Image-to-Pixel 3.2.0 interactive browser editor (including video MP4/WebM/GIF frame-by-frame pixelation and Lospec palette import) locally at `http://localhost:8080/Image-to-Pixel/editor/`:
```powershell
python tools/image_to_pixel.py serve-editor --port 8080
```
