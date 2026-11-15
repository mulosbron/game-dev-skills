---
name: pixel-snapper
description: "Cleans and snaps messy, irregular AI-generated pixel art (Midjourney, DALL-E, Stable Diffusion, Flux) to crisp integer pixel grids, eliminates subpixel jitter, removes blurry gradients, and quantizes colors to strict indexed palettes (Pico-8, Dawnbringer 16/32, GameBoy, or custom hex palettes)."
---

# Pixel Snapper & Palette Quantizer Skill

This skill provides automated pixel grid alignment and palette quantization for AI-generated game art and messy spritesheets.

## Quick Start CLI

```powershell
# Auto-detect pixel grid and quantize to 16 colors:
python tools/pixel_snapper.py "path/to/ai_sprite.png"

# Lock to strict Pico-8 palette:
python tools/pixel_snapper.py "path/to/ai_sprite.png" --palette pico8

# Lock to Dawnbringer 16 palette:
python tools/pixel_snapper.py "path/to/ai_sprite.png" --palette db16

# Specify explicit grid cell size (e.g., 4x4 logical pixels) and export native resolution:
python tools/pixel_snapper.py "path/to/ai_sprite.png" --grid-size 4 --native -o "path/to/clean_1x.png"
```

## Rust & Web CLI (SpriteFusion)
Located in `libraries\com.github.hugo-dz.spritefusion-pixel-snapper`:
```powershell
# If cargo is installed:
spritefusion-pixel-snapper <INPUT> <OUTPUT> 16 --pixel-size 4
```
