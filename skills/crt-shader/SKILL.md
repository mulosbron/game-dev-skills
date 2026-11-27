---
name: crt-shader
description: "One-pass pixel-art CRT post-process shader (NTSC YIQ horizontal dither-melt, variable-thickness scanline beam, 6px RGB aperture grille phosphor mask, 5x5 phosphor glow, barrel curvature, and vignette) for Godot 4, Unity URP HLSL, and WebGL2/GLSL ES 3.0. Use whenever the user mentions CRT shader, scanlines, phosphor mask, aperture grille, NTSC dither blending, retro TV look, screen curvature, barrel warp, or says pixel art looks too sharp/clinical on modern screens (`tools/crt_shader.py`)."
---

# Pixel-Art CRT Shader (`crt-shader`)

Transforms crisp native-resolution pixel art into a warm, authentic CRT display in **one fullscreen pass** — melting 1-pixel checker/vertical dithers into smooth tones while preserving horizontal scanline structure, variable-thickness bright beams, RGB aperture grille stripes, phosphor glow, and subtle glass curvature.

Bundled shaders:
- **Godot 4 (`canvas_item`):** [`shaders/crt.gdshader`](shaders/crt.gdshader)
- **Unity URP (`HLSL / ShaderLab`):** [`shaders/PixelArtCRT.shader`](shaders/PixelArtCRT.shader)
- **WebGL2 (`GLSL ES 3.0`):** [`shaders/crt.glsl`](shaders/crt.glsl)

Reference renderer, verifier, and exporter: [`tools/crt_shader.py`](../../tools/crt_shader.py).

---

## 1. Pre-Code Project Audit (Always Do This First)

Before adding a CRT pass, inspect the project and confirm:
1. **Engine & pipeline:** Godot 4 (`SubViewport` + `TextureRect`), Unity URP (fullscreen blit `RenderTexture`), WebGL2/Canvas, or custom renderer.
2. **Native resolution & display scale:** The CRT pass MUST sample the game rendered at **native pixel resolution** (`filter_nearest` / `FilterMode.Point`) and output at an **integer multiple** (`4x`–`6x` recommended; `6x` gives 1 clean RGB triad per game pixel at `MASK_PX = 2.0`).
3. **Color space:** The shader expects **gamma/sRGB-encoded** game colors in and writes gamma-encoded colors out (`pow(x, 2.4)` decode -> `pow(x, 1/2.2)` encode). If your render target is linear (e.g. Unity Linear color space), convert once at the boundary so colors are not double-darkened.
4. **User toggle:** Always expose a clean bypass/toggle that restores the raw nearest-neighbor integer-scaled frame pixel-for-pixel.

---

## 2. The 5-Stage One-Pass Pipeline & Tuned Knobs

| Stage | Knob | Default | Purpose |
|---|---|---|---|
| **1. NTSC YIQ Signal** | `LUMA_BLUR` / `CHROMA_BLUR` | `0.45` / `1.20` game px | Horizontal-only blur in YIQ space; `[1 2 1]` luma pre-filter melts 1px checkerboard & vertical-line dither into flat color while keeping horizontal rows sharp. |
| **2. Variable Beam** | `BEAM_MIN` / `BEAM_MAX` | `0.21` / `0.40` lines | Sums the 2 nearest game rows (`* 1.32`); bright pixels fatten (`pow(lin, 0.6)`) until scanlines nearly touch, dark rows stay thin. |
| **3. Aperture Grille** | `MASK_PX`, `MASK_DARK`, `MASK_LIGHT` | `2.0` px, `0.62`, `1.22` | Repeating R/G/B vertical phosphor stripes every `3 * MASK_PX = 6` screen pixels. |
| **4. Phosphor Glow** | `GLOW`, `BOOST` | `0.26`, `1.50` | `5x5` wide Gaussian bloom (`sigma = 1.6`, `sigma^2 = 2.56`) in linear space (`pow 2.4`), plus `BOOST` to recover brightness lost to scanline gaps & mask. *(On mobile/low-end GPUs, shrink glow loop from `-2..2` to `-1..1` with `sigma^2 = 1.2` or disable.)* |
| **5. Glass Warp & Vignette** | `WARP`, vignette | `(0.031, 0.041)`, `0.22` | Barrel distortion applied first (pure black outside `[0, 1]`), edge darkening `1 - 0.22 * (dot(c,c)*0.5)^1.5`. Set `WARP = (0, 0)` for a flat screen. |

---

## 3. CLI Pipeline (`tools/crt_shader.py`)

Always pass `--json` in agent workflows:

```powershell
# 1. Run all 4 automated CRT verification groups (A: dither melt + hlines, B: scanline peaks + 6px RGB mask, C: warp black corners, D: off bypass)
python tools/crt_shader.py verify --json

# 2. Export production shaders (godot4, unity, webgl2, or all)
python tools/crt_shader.py export-shader --engine all --out-dir exports/crt_shader/shaders --json

# 3. Render a headless Python reference CRT preview of a native-res sprite/frame (or built-in 64x48 dungeon room)
python tools/crt_shader.py render --demo --scale 6 -o exports/crt_shader/room_crt.png --json
python tools/crt_shader.py render path/to/native_frame.png --scale 6 -o exports/crt_shader/frame_crt.png --json
```

---

## 4. Pitfalls & Verification Checklist

### Common Pitfalls
- **Non-integer output scaling (e.g. `3.5x`):** Produces uneven scanline thickness and shimmering moiré across the aperture grille. Pair with [`pixel-perfect`](../pixel-perfect/SKILL.md) integer scaling.
- **Applying CRT before scaling (at native resolution):** Scanlines and 6px RGB triads require multiple screen pixels per game pixel (`>= 4x`, tuned at `6x`).
- **Bilinear filtering on the game texture:** Smears pixels vertically too, destroying horizontal line contrast. Keep `filter_nearest` / `FilterMode.Point` and fetch via `texelFetch` / `Load`.
- **Double-gamma darkening in Unity Linear mode:** The HLSL shader decodes `pow(x, 2.4)` internally; feed sRGB-encoded color or adjust `GAMMA_IN`.

### Verification Checklist (`tools/crt_shader.py verify`)
- [ ] **Check A (Dither Melt):** At `6x` flat (`WARP = 0`), 1px checkerboard and 1px vertical lines melt along each scanline center (`std < 0.01`), while 1px horizontal lines keep strong scanline contrast (`std > 0.15`).
- [ ] **Check B (Scanline & Mask Structure):** Flat mid-gray shows exactly 1 bright peak per game row at identical offset, and dominant channel cycles `R -> G -> B` every `6` screen pixels.
- [ ] **Check C (Curvature Corners):** With default `WARP = (0.031, 0.041)`, all four output corners are pure black (`< 0.01`).
- [ ] **Check D (Toggle Off):** Bypassing the shader restores the exact nearest-neighbor integer-upscaled input frame.
