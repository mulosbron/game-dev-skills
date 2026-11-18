# Asset Harmonizer

Turns a pile of mismatched 3D assets into a set that looks like it belongs to one game. Everything runs locally, and the setup is sized for an 8 GB GPU (RTX 4070 Mobile class).

Mixed assets rarely clash for one reason. Scale, pivot, polygon density, texel density, PBR values, palette and shader response each break independently, and each has its own fix. This pipeline handles them in order, so hundreds of files get the same treatment in one pass.

## What it does

1. **Inventory and triage.** Scans meshes and reports triangles, size, UVs and textures, with a keep/repair/rebuild/drop suggestion per file.
2. **Geometry normalization** (Blender, headless). Applies transforms, sets real-world scale, moves the pivot to the base center, cleans the mesh and decimates to the class budget.
3. **Texel density.** Rescales UVs so every asset class hits its px/cm target.
4. **Texture restyling.** Upscale, derive PBR maps, then snap albedo to your palette. Optional local AI retexturing for hero assets.
5. **Engine unification.** Master shader, palette remap and a LUT (manual; documented in the reference).
6. **QA gate.** Automated checks with the stage to go back to for each failure.

## Install

Full instructions, including every download link, are in [references/setup.md](references/setup.md). The short version:

```powershell
python -m venv .venv-ah; .\.venv-ah\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r skills/asset-harmonizer/scripts/requirements.txt
python skills/asset-harmonizer/scripts/fix_basicsr.py
python tools/asset_harmonizer.py doctor
```

`doctor` lists what is missing and where to get it. Install Blender 4.x and set `BLENDER_EXE` for stages 2 and 3.

## Use

```powershell
python tools/asset_harmonizer.py init      --root projects/my_game
# edit projects/my_game/docs/style_guide.json: palette, poly caps, texel targets
# drop raw files into assets_source/meshes and assets_source/raw_textures
python tools/asset_harmonizer.py inventory --root projects/my_game
python tools/asset_harmonizer.py run       --root projects/my_game --steps 2,3
python skills/asset-harmonizer/scripts/upscale_batch.py --src projects/my_game/assets_runtime/textures --dst projects/my_game/pipeline/tmp/up
python skills/asset-harmonizer/scripts/pbr_derive.py    --src projects/my_game/assets_runtime/textures
python tools/asset_harmonizer.py palette   --root projects/my_game
python tools/asset_harmonizer.py qa        --root projects/my_game
```

Name files `category_role_variant`, lowercase with underscores, and end them with a class suffix (`_bg`, `_prop`, `_hero`, `_char`): `env_barrel_prop_a.glb`.

Do the engine layer (stage 5) before expensive retexturing. A LUT plus fog often removes most of the mismatch without touching a texture.

## Contents

| Path | What |
|---|---|
| [SKILL.md](SKILL.md) | Agent instructions and hard rules |
| [references/setup.md](references/setup.md) | Tool downloads and step-by-step usage |
| [references/pipeline-reference.md](references/pipeline-reference.md) | Standards, tables and checklists |
| [scripts/](scripts) | Blender and Python stage scripts, requirements |
| [templates/qa_checklist.md](templates/qa_checklist.md) | Definition-of-done checklist |
| [agents/asset-harmonizer-agent.md](agents/asset-harmonizer-agent.md) | Pipeline-driving agent |
| `tools/asset_harmonizer.py` (repo root) | CLI entry point |

## Limits

- Palette remap is nearest-color, no dithering. For painted styles with soft gradients, add dithering with ImageMagick (`-dither FloydSteinberg -remap`).
- `pbr_derive.py` is a scripted fallback. Materialize gives better maps but has no official command-line mode.
- `ai_retexture.py` restyles flat textures. Use Stable Projectorz when you need multi-view projection onto the model.
- The GLB reader in `inventory` and `qa` ignores node transforms other than scale flags, and the Blender scripts have not been run against a real stock yet.
