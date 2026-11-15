---
name: spritefusion-pixel-snapper
description: Fix AI-generated or uneven 2D pixel art sprites, tilemaps, and textures by snapping pixels to a uniform grid and quantizing colors to a strict or custom hex palette (`Hugo-Dz/spritefusion-pixel-snapper`). Use via Rust CLI or WASM in browser/game asset pipelines.
license: MIT
metadata:
  homepage: "https://spritefusion.com/pixel-snapper"
  repository: "https://github.com/Hugo-Dz/spritefusion-pixel-snapper"
---

# Sprite Fusion Pixel Snapper (`Hugo-Dz/spritefusion-pixel-snapper`)

Use this skill when cleaning up AI-generated pixel art or off-grid procedural 2D sprites, isometric maps, tilemaps, and 3D pixel textures by snapping them to an exact pixel grid and quantizing colors to a controlled palette (`MIT`).

## Installation

```bash
# Homebrew
brew install Hugo-Dz/tap/spritefusion-pixel-snapper

# Cargo (Rust standalone native binary)
cargo install spritefusion-pixel-snapper
```

Build from source:
```bash
git clone https://github.com/Hugo-Dz/spritefusion-pixel-snapper.git
cd spritefusion-pixel-snapper
cargo build --release
```

## CLI Usage

Syntax:
```text
spritefusion-pixel-snapper <INPUT> <OUTPUT> [COLOR_COUNT] [OPTIONS]
```

- `<INPUT>`: Input PNG/JPEG image or directory (batch mode)
- `<OUTPUT>`: Output PNG file or separate output directory (batch mode)
- `[COLOR_COUNT]`: Palette color count (default: `16`)
- `--pixel-size <PIXELS>`: Override auto-detected pixel size (`1` to half the smallest image dimension)
- `--palette <HEX,...>`: Comma-separated 6-digit hex colors

Examples:
```bash
# Quantize single sprite to 16 colors and snap grid
spritefusion-pixel-snapper input.png output.png 16

# Batch process a sprite directory with explicit 8px pixel size
spritefusion-pixel-snapper sprites/batch_inputs sprites/batch_outputs 16 --pixel-size 8

# Lock output to a custom hex palette
spritefusion-pixel-snapper input.png output.png --palette "0d2b45,203c56,544e68,8d697a,d08159,ffaa5e,ffd4a3,ffecd6"
```

## WebAssembly (WASM) Usage

```bash
wasm-pack build --target web --out-dir pkg --release
```

```js
import init, { process_image } from "./pkg/spritefusion_pixel_snapper.js";

await init();
const outputBytes = process_image(inputBytes, 16);

// Custom hex palette (pass null to keep defaults for other parameters)
const recoloredBytes = process_image(inputBytes, null, null, "0f0f1b,ffecd6,ff4d6d,29adff");
```

## Guardrails

- For batch directory processing, always specify a separate `<OUTPUT>` directory to avoid overwriting source sprites in place.
- Set `--pixel-size` explicitly when auto-detection misreads upscaled or mixed-resolution sprites.
