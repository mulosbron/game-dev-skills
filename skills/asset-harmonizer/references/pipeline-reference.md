# Pipeline Reference

Standards and tables for the asset-harmonizer pipeline. Values are defaults; adjust them to your camera and scene scale, then record them in `docs/style_guide.json`.

## Style guide fields

| Field | Meaning |
|---|---|
| `palette` | 8-16 hex colors: one ground neutral, two shadow tones, 4-6 mid surface colors, two accents, one skin tone |
| `emissive_palette` | 2-4 colors for glowing surfaces (magic blue, lava orange) |
| `saturation_cap` | Highest allowed HSV saturation, for example 0.70 |
| `texel_density_px_cm` | Target px/cm per class |
| `poly_cap` | Triangle ceiling per class |
| `scale`, `pivot` | Unit convention and pivot rule |
| `naming_regex` | Filename pattern checked by QA |
| `auto_smooth_deg` | Shading angle: 30 hard-edged styles, 60 soft, 40 default |
| `dimension_ranges_m` | Real-world size ranges matched by filename keyword (chair 0.9-1.1 m, door 2.0-2.2 m) |

Pick two or three reference games or images and write one sentence for each: what you take and what you don't. Keep them on one board (PureRef) next to the style guide. They double as the style reference for AI retexturing.

## Texel density and texture size

| Class | px/cm | Texture size |
|---|---|---|
| Characters, close-up props | 10.24 | 1024-4096 |
| Mid-range props | 5.12 | 1024 |
| Architecture modules | 5.12 | 2048 (atlas) |
| Background decoration | 2.56 | 512-1024 |

Consistency matters more than the absolute number: two chairs at the same distance must look equally sharp.

## Polygon budgets

Background 300, prop 2000, hero 10000, character 30000-50000 triangles. Divide by three for mobile. Hero assets: manual retopo or Instant Meshes. Normal props: Decimate modifier in collapse mode.

## Engine export rules

| Engine | Format | Unit | Forward / up |
|---|---|---|---|
| Unity | FBX | 1 unit = 1 m (watch the FBX 0.01 scale factor) | +Z / +Y |
| Unreal | FBX | 1 unit = 1 cm (export at 0.01 scale) | +X / +Z |
| Godot | glTF/GLB | 1 unit = 1 m | -Z / +Y |

Do not embed textures in the GLB, and keep cameras, lights and helper empties out of the export.

## UV rules

| Situation | Fix | Tool |
|---|---|---|
| No UVs, or fully overlapping | Re-unwrap | xatlas, Smart UV Project |
| Uneven sharpness | Set common texel density | `texel_blender.py` |
| Many small props sharing one material | Atlas with 4-8 px padding and dilation | Pack Islands, UVPackmaster |
| Hero or close-up asset | Manual unwrap | Blender |

## Texture restyling without AI

- **Palette remap:** every albedo pixel goes to the nearest palette color. `asset_harmonizer.py palette` does this without dithering. For painted styles use ImageMagick: `magick in.png -dither FloydSteinberg -remap palette.png out_pal.png`.
- **Banding after remap:** process the source at 16 bit and convert to 8 bit last.
- **Alpha and emissive:** no dithering on cutouts; remap emissive with its own mini palette.
- **Materialize:** derives height, normal, roughness, metallic and AO from albedo. Record the slider values in the style guide and reuse them.
- **Real-ESRGAN:** upscale 512 px sources 4x, then scale down to the density target. Good on architecture and fabric; use sparingly on faces.

| Method | Time per asset | When |
|---|---|---|
| Palette remap | seconds, batch | always, last step |
| PBR derivation | 1-2 minutes | albedo-only sources |
| Real-ESRGAN | 10-60 s on GPU | 512-1024 px sources, close-ups |
| Hand repaint | hours | hero assets only |

## Local AI on 8 GB VRAM

| Configuration | VRAM | Verdict |
|---|---|---|
| SD1.5 fp16, 512-768 px | ~4.0 GB | comfortable |
| SD1.5 + ControlNet depth/normal | ~5.5 GB | geometry-faithful |
| SD1.5 + IPAdapter + ControlNet | ~6.5 GB | recommended |
| SDXL fp16 + `--medvram` + tiled VAE | ~7.2 GB | tight, hero assets only |
| FLUX.1-schnell GGUF Q4 | ~8.6 GB | overflows |

Usable VRAM is about 7.4-7.7 GB because the OS takes 0.3-0.6 GB. Load weights in fp16, close browsers and engines while generating, and do not change the checkpoint path between runs (it flushes the cache).

ComfyUI settings: denoise 0.45-0.60 keeps the existing texture, 0.75-0.90 makes a new one. IPAdapter weight 0.7-0.85, type style plus composition. ControlNet depth strength 0.8.

Prompt template (only `[MATERIAL]` changes per asset):

```
[MATERIAL], stylized hand-painted game asset texture, warm limited palette, soft gradients, subtle painterly noise, no text, no watermark, flat lighting, seamless, PBR-friendly
```

Time for one mid-range prop end to end: about 15-30 minutes.

## Stage 5: engine unification

Use one master shader; per-asset differences are parameters, not separate shaders.

| Function | Unity | Unreal | Godot |
|---|---|---|---|
| Palette remap | Shader Graph Replace Color or gradient ramp | Material function with curve LUT | Custom shader with palette array |
| Color grading | URP Volume: Color Adjustments + LUT | Post Process Volume LUT | WorldEnvironment adjustments |
| Fog | URP Volume fog | Exponential Height Fog | WorldEnvironment fog |
| Tonemapping | ACES or filmic | Filmic | Default plus adjustments |

Start with free LUTs, then author one from your own palette. Keep post-process saturation and contrast below the LUT, not on top of it.

Scene setup checklist:
- [ ] Fixed key light direction and intensity (for example 30 degree sun at 1.0, fill 0.2)
- [ ] Ambient color is the palette shadow tone, not neutral gray
- [ ] Fog color matches the background color
- [ ] LUT profile is bound to the scene template, not chosen by hand
- [ ] Every material references the master shader; no copies
- [ ] Shadow distance and resolution match the scene scale; no flicker
- [ ] No second saturation layer above the LUT
- [ ] Reference chair, wall and character sit in the scene for side-by-side checks

## Thirty-day plan

| Week | Work | Output |
|---|---|---|
| 1, days 1-2 | Style guide: moodboard, palette, px/cm, poly budget, naming | One-page guide and palette image |
| 1, days 3-5 | Run inventory, fill triage | `inventory.csv` with decisions |
| 2 | Engine layer: master shader, LUT, fog, reference scene | First shared frame |
| 3, days 1-2 | Blender batch normalization | Clean transforms, pivots, normals |
| 3, days 3-5 | Texel density, re-unwrap broken UVs | Checker-texture test passes |
| 4, days 1-2 | Palette pass on all albedo, PBR sets | Palette-locked runtime copy |
| 4, days 3-5 | Stable Projectorz retexture of 5-10 hero assets | New hero textures |
| 4, last day | QA gate on the full stock | QA report, v1.0 |

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| Script ran but some files unchanged | Filename does not match the pattern | List non-matching names in the inventory and rename |
| Normal maps broke after palette pass | Remap hit data maps | Restrict remap to `_diff` |
| AI seams visible | Low multi-view blend, no UV padding | Raise blend, add 8 px padding |
| Scale differs in engine | Export scale differs per file | Fix the exporter preset |
| CUDA out of memory | Too many apps holding VRAM | fp16, tiled VAE, close other apps |
| Second run differs from first | Model or parameter version changed | Record versions in `pipeline/changelog.md` and lock them |

Mistakes to avoid: leaving the palette for last (it is the cheapest step), pushing the whole stock through AI (the camera looks at about 20% of it), skipping Apply Transform and blaming the engine, judging texel density by eye, writing a new prompt per asset, and running the pipeline without scripts (the palette will change; a manual pipeline means redoing everything).

Everything in the stack is free or already owned except optional paid atlas tools such as UVPackmaster. The bottleneck is GPU memory, so close extra applications while generating.
