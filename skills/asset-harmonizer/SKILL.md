---
name: asset-harmonizer
description: "Use when 3D assets from different sources (asset stores, AI generators, old projects) look like they come from different worlds and need one consistent visual language. Covers batch normalization of scale, pivot, polycount, UVs and texel density, palette quantization, PBR derivation, local AI retexturing on an 8 GB GPU, engine-side master shader and LUT, and an automated QA gate. Not for generating new models (see polyspoon, triposr)."
metadata:
  category: 3d-pipeline
  triggers: harmonize assets, mixed 3d assets, texel density, palette remap, batch blender normalize, asset pipeline, retexture local, style consistency
---

# Asset Harmonizer

Run mixed-source 3D stock through one offline, six-stage pipeline so everything shares a scale, a pivot convention, a texel density, a palette and a shader. Reference hardware: RTX 4070 Mobile, 8 GB VRAM. No cloud services.

Core principle: do not fix assets one by one. Write the style down, encode it in scripts, push every asset through the same pipeline, and unify the result in the engine with one master shader plus a LUT. Hand work is reserved for hero assets.

## Files

| Path | Purpose |
|---|---|
| `asset-harmonizer.html` | Interactive offline browser tool (style guide, inventory, normalization, texel, palette, QA); no AI needed |
| `tools/asset_harmonizer.py` | CLI: `open`, `init`, `doctor`, `profile`, `inventory`, `palette`, `qa`, `run` |
| `scripts/normalize_blender.py` | Stage 2: geometry normalization (Blender batch) |
| `scripts/texel_blender.py` | Stage 3: texel density to class target, no add-on needed |
| `scripts/inventory_blender.py` | Stage 1 for FBX stocks |
| `scripts/upscale_batch.py` | Stage 4: tiled Real-ESRGAN |
| `scripts/pbr_derive.py` | Stage 4: normal and roughness/metallic/AO from albedo |
| `scripts/ai_retexture.py` | Stage 4: SD1.5 fp16 + IPAdapter style-locked img2img |
| `scripts/requirements.txt`, `scripts/fix_basicsr.py` | Python dependencies and a known-bug patch |
| `references/setup.md` | What to download, where from, how to install and use each tool |
| `references/pipeline-reference.md` | Tables: texel density, poly caps, engine export rules, VRAM, prompts, scene checklist |
| `templates/qa_checklist.md` | Definition-of-done checklist copied into each project |
| `agents/asset-harmonizer-agent.md` | Agent that drives the pipeline |

Read `references/setup.md` first if the machine is not set up. Run `python tools/asset_harmonizer.py doctor` to see what is missing, and `python tools/asset_harmonizer.py open` to launch the browser tool.

## Quick start

```powershell
python tools/asset_harmonizer.py init      --root projects/my_game   # folders, style_guide.json, QA checklist
python tools/asset_harmonizer.py inventory --root projects/my_game   # GLB/OBJ scan, no Blender required
python tools/asset_harmonizer.py run       --root projects/my_game --steps 2,3
python tools/asset_harmonizer.py palette   --root projects/my_game
python tools/asset_harmonizer.py qa        --root projects/my_game   # exit code 1 if any asset fails
```

Set `BLENDER_EXE` (or put Blender on PATH) for Blender stages.

## Stages

| # | Stage | Tool |
|---|---|---|
| 1 | Inventory and triage: keep / repair / rebuild / drop | `inventory`, `inventory_blender.py` |
| 2 | Geometry: apply transforms, real scale, base-center pivot, cleanup, decimate, export GLB | `normalize_blender.py` |
| 3 | Texel density to the per-class px/cm target; unwrap if UVs are missing | `texel_blender.py` |
| 4 | Textures: upscale, derive PBR, palette remap last | `upscale_batch.py`, `pbr_derive.py`, `palette` |
| 5 | Engine: master shader, palette remap node, LUT, fog, ambient | manual, see `references/pipeline-reference.md` |
| 6 | QA gate: failing assets go back to the stage named in the report | `qa` |

Asset class comes from the filename suffix: `_bg`, `_prop`, `_hero`, `_char` (default `prop`). Example: `env_barrel_prop_a.glb`.

## Rules

1. Keep this operation order: import, fix negative scale, apply transforms, scale, pivot, cleanup, decimate, export. Apply before moving the pivot. Decimate after applying.
2. Keep this texture order: upscale, derive PBR, palette remap. Reversing it lets the upscaler split palette colors into new in-between shades.
3. Run the palette pass on albedo (`_diff`) only. Never touch `_nrm`, `_rma`, roughness, metallic or AO maps; they are data, not color. Give emissive maps their own 2-4 color palette. Preserve alpha and skip dithering on foliage and cutouts.
4. Work cheapest first: LUT, tonemapping and fog (half a day) before master shader and palette remap, then the palette pass, then local AI retexture for hero assets only (about 20% of the stock).
5. Keep two trees: `assets_source` (raw, never edited in place) and `assets_runtime` (generated, git-ignored). The engine reads runtime only.
6. Measure texel density; do not judge it by eye. Verify with a checker texture at equal camera distance.
7. Make the palette include dark and light end tones (no pure black or white) and set a saturation cap in the style guide.
8. AI consistency comes from three locks: same checkpoint and VAE, same style reference and IPAdapter weight, same prompt template. SD1.5 fp16 with ControlNet and IPAdapter (about 6.5 GB) is the sweet spot on 8 GB. SDXL only with `--medvram` and tiled VAE. FLUX is impractical. On CUDA out-of-memory, lower resolution or enable tiled VAE; do not switch models.
9. Never generate or overwrite level layouts; this pipeline handles assets only.

## Diagnose first

| Symptom | Layer | Stage |
|---|---|---|
| One asset huge, another tiny | Scale, unapplied transform | 2 |
| Pivots need manual alignment | Pivot, orientation | 2 |
| Some assets very dense, others blocky | Polygon density | 2 |
| Blurry up close, sharp far away (or reverse) | Texel density | 3 |
| One looks like glossy plastic, another matte | PBR values | 4 and 5 |
| Colors clash, saturation scattered | Palette | 4 and 5 |
| Same light, different "air" | Shader and light response | 5 |

Quick test: render everything with one gray material and one light. Palette and texture problems vanish; what remains is geometry, scale and silhouette. Then turn textures back on; the new differences are palette and texel density.

## Related skills

`glb-forge` (inspect, optimize and LOD the output GLBs), `blender-kiln` (review sheets), `material-maker` (procedural PBR), `image-to-pixel` (palettes and dithering), `polyspoon` and `triposr` (source models), `godot`.
