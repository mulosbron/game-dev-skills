---
name: spritefusion-sprite-normals
description: "Generate tangent-space normal maps for 2D pixel art sprites, sprite sheets, and GIF/APNG animations using Euclidean distance transform silhouette heightmaps, perceptual lightness relief, and Sobel filtering (`Hugo-Dz/spritefusion-sprite-normals`). Available as a Rust CLI and WebAssembly library."
license: MIT
metadata:
  homepage: "https://www.spritefusion.com/sprite-normals"
  repository: "https://github.com/Hugo-Dz/spritefusion-sprite-normals"
---

# Sprite Fusion Sprite Normals (`spritefusion-sprite-normals`)

Local-first Rust CLI and WebAssembly library for generating pixel-accurate tangent-space normal maps from 2D pixel art sprites, uniform sprite sheets, and animated GIF/APNG files.

Located in `libraries\com.github.hugo-dz.spritefusion-sprite-normals`.

---

## How the Algorithm Works (`src/lib.rs`, `distance.rs`, `field.rs`, `relief.rs`)

1. **Frame & Island Isolation**: Splits uniform `--frame-size` sprite-sheet cells and separates disconnected opaque sprite islands (`alpha > alpha_threshold`) so neighboring frames or sprites never bleed normals into each other.
2. **Silhouette Distance Transform + Heightmap**: Computes an exact 2D Euclidean Distance Transform (`distance::edt` using separable parabolic lower envelopes) inward from transparent pixels, maps distance to logarithmic volume (`shape_strength * shape_radius * ln(1 + inset / shape_radius)`), and smooths it with a separable Gaussian (`shape_softness`).
3. **Shading Detail Heightmap**: Extracts centered perceptual lightness (`color::lightness`), applies opacity-weighted normalized Gaussian convolution (`field::masked_gaussian` so hidden RGB behind `alpha = 0` never leaks) at `detail_scale` (70%) and `2 * detail_scale` (30%), scales by `detail_strength`, and adds it to the silhouette heightmap.
4. **Sobel Normal Extraction**: Evaluates normalized 3x3 Sobel correlation (`field::sobel`) over the padded combined heightmap and converts `(dx, dy)` slopes into unit normals (`normal_strength`, OpenGL `+Y` up or DirectX `-Y` down), preserving input alpha and writing neutral `(128, 128, 255)` on transparent pixels.

---

## Build & Install (Rust `>= 1.85`)

```powershell
cd libraries\com.github.hugo-dz.spritefusion-sprite-normals

# Build optimized native CLI binary
cargo build --release --locked

# Or install globally into Cargo bin
cargo install --path . --locked
```

Run checks/tests:
```powershell
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
cargo fmt --check
```

---

## CLI Usage (`src/main.rs`, `src/settings.rs`)

```text
spritefusion-sprite-normals <INPUT>... [OPTIONS]
```

### Examples

```powershell
# Single PNG sprite -> sprite_n.png (default suffix beside input if -o omitted)
spritefusion-sprite-normals sprite.png -o sprite_n.png

# Batch directory into separate output folder
spritefusion-sprite-normals sprites\*.png --output-dir normals

# Stronger normal relief for chunky 2.5D pixel lighting
spritefusion-sprite-normals sprite.png -o sprite_n.png --normal-strength 2.0 --detail-strength 6.0

# Uniform sprite sheet -> outputs sheet_n.png, sheet_n.color.png, sheet_n.frames.json
spritefusion-sprite-normals sheet.png --frame-size 32x32 -o sheet_n.png

# Animated GIF/APNG -> normal atlas + color atlas + frame metadata JSON
spritefusion-sprite-normals walk.gif -o walk_n.png

# DirectX-style inverted green channel (e.g., certain Unity/Unreal shaders)
spritefusion-sprite-normals sprite.png --normal-format directx -o sprite_n.png
```

### CLI Options & Defaults

| Option | Default | Valid Range / Notes |
|---|---|---|
| `<INPUT>...` | *(required)* | PNG sprites/sheets, GIF, or APNG files. |
| `-o`, `--output <PATH>` | `<stem>_n.png` | Output `.png` path (single input only; conflicts with `--output-dir`). |
| `--output-dir <DIR>` | Input parent dir | Output directory for batch `<stem>_n.png` files. |
| `--force` | `false` | Replace existing outputs (source input files are always protected). |
| `--frame-size <WxH>` | `None` | Isolate uniform PNG sheet cells (e.g. `32x32`); image width/height must be exact multiples. |
| `--normal-strength <VAL>` | `1.5` | Final normal slope multiplier (`0..8`). |
| `--detail-strength <VAL>` | `6.0` | Painted-shading relief weight (`0..8`). |
| `--detail-scale <PX>` | `0.6` | Shading smoothing radius in native pixels (`0.6..8`). |
| `--shape-strength <VAL>` | `1.15` | Silhouette height volume (`0..8`). |
| `--shape-radius <PX>` | `4.0` | Silhouette distance falloff reach in pixels (`0.5..512`). |
| `--shape-softness <PX>` | `1.15` | Gaussian smoothing applied to silhouette height (`0..8`). |
| `--alpha-threshold <VAL>` | `0.03` | Opacity cutoff for solid pixels (`0..0.99`). |
| `--normal-format <FMT>` | `opengl` | `opengl` (`+Y` up, Godot/Three.js/WebGL) or `directx` (`-Y` inverted green). |
| `--invert-x` / `--invert-y` | `false` | Independently flip red (X) or green (Y) normal channels. |

---

## Animations, Sprite Sheets & Limits

- **Multi-file output for animations / `--frame-size`**:
  - `<name>_n.png`: Lossless normal-map atlas in row-major order.
  - `<name>_n.color.png`: Matching color atlas with identical frame layout.
  - `<name>_n.frames.json`: Metadata `{ width, height, animation: { frame_width, frame_height, columns, frame_count, delays_ms } }` where `delays_ms` stores `[numerator, denominator]` millisecond pairs (PNG sheets default to `[100, 1]` ms).
- **Input Limits**: Up to **64 MiB** per input file and **4,194,304 pixels** including convolution padding; animations up to **256 frames** and **4,194,304 total decoded pixels**.

---

## WebAssembly (WASM) Build & JS API

Build with `wasm32-unknown-unknown` and `wasm-bindgen` CLI `0.2.126`:

```powershell
cargo build --release --target wasm32-unknown-unknown --no-default-features --locked
wasm-bindgen target\wasm32-unknown-unknown\release\spritefusion_sprite_normals.wasm --target web --out-dir pkg
```

```js
import init, { generate_normal_map } from "./pkg/spritefusion_sprite_normals.js";

await init();
const result = generate_normal_map(
  inputBytes, // Uint8Array (PNG, GIF, or APNG)
  JSON.stringify({
    strength: 1.5,
    detail: 6.0,
    smoothing: 0.6,
    volume: 1.15,
    // Optional: frame_width, frame_height, directx
  })
);
try {
  const normalPng = result.normal_png;   // Uint8Array
  const colorPng = result.color_png;     // Uint8Array
  const metadata = JSON.parse(result.metadata);
} finally {
  result.free();
}
```

---

## Engine Import Guardrails

- **Disable sRGB sampling**: Normal maps are linear data textures—disable sRGB color-space conversion in Godot/Unity/Unreal/Three.js so tangent vectors are not gamma-warped.
- **Native pixel resolution**: Pair with `spritefusion-pixel-snapper` beforehand if sprites are upscaled or off-grid, and keep nearest-neighbor filtering on color sprites.

---

## Outline Bevel, Floor Tiles & Stepped Pixel-Art Lighting (`tools/normal_map_gen.py`)

When Rust/Cargo is unavailable, or when you specifically need **quarter-circle outline bevels** (`outline` / `boxy`), **3×3 seamless floor-tile gap normals** (`floor-tile`), or **stepped pixel-art lighting** (`bands = 6`), use `tools/normal_map_gen.py`:

### Pre-Code Project Audit
Before adding 2D normal-mapped lights, inspect: engine & language, how sprites and 2D lights are currently drawn, and sprite sizes. Fit into existing lights/build pipeline instead of creating a parallel system; keep existing light positions and colors. If no 2D lights exist yet, ask the user before inventing them.

### CLI Recipes (`tools/normal_map_gen.py`)
```powershell
# 1. Round/organic pixel sprite (~30 px wide): 1px-padded quarter-circle bevel (bevel=5, top=12, detail=1.5)
python tools/normal_map_gen.py pots.png --mode outline --steps 6 --preview --json

# 2. Boxy sprite (crates/chests): small bevel prevents puffy pillow rounding
python tools/normal_map_gen.py crate.png --mode boxy --json

# 3. Seamless floor tile (no transparent edges): 3x3 wrap + darkest 30% mortar gaps (bevel=3, top=2.5, detail=1.0)
python tools/normal_map_gen.py floor.png --mode floor-tile --json

# 4. Export Godot 4 stepped canvas_item light() shader (or Unity URP 2D guidance)
python tools/normal_map_gen.py --export-shader godot4 --json

# 5. Run automated normal-map & stepped-lighting verification suite
python tools/normal_map_gen.py --verify --json
```

### Tuned Numbers & Godot 4 Setup
- **Round sprites (~30 px wide):** `bevel = 5.0 px`, `top = 12.0 px`, `detail = 1.5`, `blur = 0.7` (scale `bevel` and `top` with sprite width).
- **Boxy crates/blocks:** `bevel = 1.0–2.0 px` (`--mode boxy` uses `bevel = 1.5`, `top = 3.6`).
- **Floor tiles:** `bevel = 3.0 px`, `top = 2.5 px`, `detail = 1.0`, `gap_percentile = 30.0`.
- **Stepped Light:** `steps = 6` (`0` = smooth), `radius = 70 px`, `PointLight2D` `height = 26 px` (keep well above `12 px` bevel top), `energy = 1.6`, warm `color = (1.0, 0.8, 0.56)`, `CanvasModulate` `ambient = (0.24, 0.25, 0.33)`.
- **Godot 4 wiring:** Put sprite in `CanvasTexture.diffuse_texture` and `<sprite>_n.png` in `CanvasTexture.normal_texture` with filter `Nearest`. Apply `pixel_art_stepped_light.gdshader` to **every** sprite/floor the light touches so smooth and stepped bands do not mix. If light from above illuminates the bottom rim, re-run with `--invert-y`.

### Pitfalls & Verification Checklist
- **Sprite touches canvas border / packed sheet:** Without 1 px transparent padding (`outline` mode adds this automatically), border pixels lose their bevel. Run sprite-sheet frames individually.
- **Soft/ragged alpha edges:** Use hard-edged pixel sprites (`alpha > 127`); clean soft AI edges first (`tools/pixel_snapper.py`).
- **Verification checks (`--verify`):**
  - [ ] Round sprite middle row: leftmost inside `R < 100`, rightmost `R > 156`, top `+1 px` `G > 156`.
  - [ ] Pixels `> 5 px` outside sprite equal `(128, 128, 255)` within `1`.
  - [ ] Flat normal stepped falloff (`steps=6, radius=70, height=26`): `10 px -> 5/6`, `35 px -> 2/6`, `>=70 px -> 0`.
  - [ ] Light on left makes left half brighter than right half; `steps = 0` restores smooth light; neutral `(128, 128, 255)` restores flat lighting.
