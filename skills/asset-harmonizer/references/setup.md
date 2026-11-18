# Setup Guide

What to install, where to get it, and how to use it. Target: Windows, RTX 4070 Mobile (8 GB VRAM). Links and versions drift; after installing, run `python tools/asset_harmonizer.py doctor` to verify.

Suggested layout: `D:\AI\` for tools, `D:\AI\models\` for weights. Downloads are one-time. Afterwards everything works offline (`set HF_HUB_OFFLINE=1`).

Disk: about 40 GB free (models take roughly 15 GB). RAM: 16 GB recommended.

## 0. Prerequisites

| What | Where | Notes |
|---|---|---|
| NVIDIA driver (current Game Ready or Studio) | nvidia.com/drivers | `nvidia-smi` must work |
| Python 3.11 (3.10-3.12 work) | python.org/downloads | Tick "Add to PATH". Stable Projectorz and Trellis want 3.11 |
| Git | git-scm.com | Needed for ComfyUI custom nodes |
| Blender 4.x (LTS) | blender.org/download | Then `setx BLENDER_EXE "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"` and reopen the terminal |
| 7-Zip | 7-zip.org | For .7z and .zip archives |

## 1. Python environment

```powershell
cd D:\agentskills\game-dev-skills
python -m venv .venv-ah ; .\.venv-ah\Scripts\Activate.ps1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
pip install -r skills/asset-harmonizer/scripts/requirements.txt
python skills/asset-harmonizer/scripts/fix_basicsr.py
python tools/asset_harmonizer.py doctor
```

Packages: pillow, numpy, opencv, scipy (images, palette, PBR); trimesh, pygltflib (meshes); xatlas (automatic UV unwrap); torch with CUDA, diffusers, transformers, accelerate, safetensors, huggingface_hub (SD1.5); realesrgan, basicsr (upscaling). `fix_basicsr.py` patches a known basicsr/torchvision incompatibility.

## 2. Tools that need no AI

| Tool | Download | Install and use |
|---|---|---|
| ImageMagick 7 | imagemagick.org/script/download.php, or `winget install ImageMagick.ImageMagick` | Check with `magick -version`. Alternative palette remap with dithering |
| Texel Density Checker (optional) | github.com/mrven/Blender-Texel-Density, Releases zip | Blender > Edit > Preferences > Add-ons > Install, select the zip, enable. The pipeline does not need it; `texel_blender.py` computes density itself |
| Instant Meshes | github.com/wjakob/instant-meshes, Releases (Windows exe) | Quad retopo for hero and mid-range props: open mesh, solve orientation and position, export. Use instead of Decimate |
| MeshLab | meshlab.net | Backup mesh repair |
| PureRef | pureref.com (free, pay what you want) | Moodboard. Export as PNG for the style reference |
| Materialize | boundingboxsoftware.com/materialize (free license key); source github.com/BoundingBoxSoftware/Materialize | Load albedo, then Height, Normal, Metallic, Smoothness, AO, Save. There is no official command-line mode; for batches use `scripts/pbr_derive.py` (same output naming) |
| chaiNNer (optional) | github.com/chaiNNer-org/chaiNNer | Node-based batch image processing and upscaling |

## 3. Upscaling with Real-ESRGAN

**Option A: ncnn-vulkan (easiest, no torch).** Download `realesrgan-ncnn-vulkan-...-windows.zip` from the Releases page of github.com/xinntao/Real-ESRGAN-ncnn-vulkan and unzip it.

```powershell
python skills/asset-harmonizer/scripts/upscale_batch.py --src assets_runtime/textures --dst pipeline/tmp/up --exe D:\AI\realesrgan\realesrgan-ncnn-vulkan.exe --tile 256 --final 1024
```

**Option B: Python.** `realesrgan` is in requirements. The `RealESRGAN_x4plus.pth` weights (about 64 MB) download from github.com/xinntao/Real-ESRGAN/releases (v0.1.0) on first run. Use the same command without `--exe`. Keep `--tile 256` on 8 GB.

## 4. AI texturing

### 4.1 Stable Projectorz (main tool, multi-view projection)

- Download: stableprojectorz.com (EXE installer or minimal ZIP). Source: github.com/IgorAherne/stableprojectorz.
- On 8 GB, run in half precision (`run-fp16.bat` or `--precision half`). Needs an NVIDIA GTX 1080 or newer and 12-16 GB RAM.
- Models: put the SD1.5 checkpoint (see 4.3) and ControlNets in the program's model folders. It shows the paths on first launch.
- Workflow:
  1. Load a normalized OBJ/GLB from `assets_runtime/meshes`. It must have UVs.
  2. Set the moodboard image as the style reference (IPAdapter) and enter the prompt template from the pipeline reference.
  3. Run Multi-View Projection over the whole surface.
  4. Fix seams with inpaint and the brush.
  5. Export at 2K-4K, rename to `*_diff.png`, run `palette`, then `pbr_derive.py`.
- Keep exports under `assets_source/raw_textures/` so the pipeline can regenerate runtime files.

### 4.2 Dream Textures (inside Blender)

github.com/carson-katri/dream-textures: download the Releases zip and install it in Blender Add-ons. Use SD 2.1-base (512 px) or SD1.5. Texture projection gives fast per-prop experiments; use 4.1 for a serious series.

### 4.3 ComfyUI with IPAdapter and ControlNet (most flexible)

1. ComfyUI: github.com/comfyanonymous/ComfyUI, Releases, Windows portable (NVIDIA). Unzip and run `run_nvidia_gpu.bat`.
2. Manager: in `ComfyUI\custom_nodes`, `git clone https://github.com/ltdrdata/ComfyUI-Manager`.
3. IPAdapter nodes: install `ComfyUI_IPAdapter_plus` (github.com/cubiq/ComfyUI_IPAdapter_plus) from the Manager.
4. Models (HuggingFace, one-time):

| File | Source | Target folder |
|---|---|---|
| SD1.5 checkpoint, fp16 (`v1-5-pruned-emaonly.safetensors`) | huggingface.co/stable-diffusion-v1-5/stable-diffusion-v1-5 | `models/checkpoints` |
| VAE `sd-vae-ft-mse` | huggingface.co/stabilityai/sd-vae-ft-mse-original | `models/vae` |
| IPAdapter `ip-adapter_sd15.safetensors` | huggingface.co/h94/IP-Adapter (`models/`) | `models/ipadapter` |
| CLIP-ViT-H image encoder (`model.safetensors`, ~2.5 GB) | huggingface.co/h94/IP-Adapter (`models/image_encoder/`) | `models/clip_vision`, renamed `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` |
| ControlNet depth `control_v11f1p_sd15_depth.pth` and normal `control_v11p_sd15_normalbae.pth` | huggingface.co/lllyasviel/ControlNet-v1-1 | `models/controlnet` |

5. Settings: denoise 0.45-0.60 to keep the existing texture, 0.75-0.90 for a new one. IPAdapter weight 0.7-0.85, style plus composition. ControlNet depth strength 0.8. 512-768 px. Full stack is about 6.5 GB. For SDXL, add `--medvram` and turn on Tiled VAE. On out-of-memory, lower resolution or enable Tiled VAE; do not change models.
6. Alternative: Forge (github.com/lllyasviel/stable-diffusion-webui-forge) handles 8 GB memory well.

### 4.4 Scripted route without ComfyUI: `ai_retexture.py`

```powershell
python skills/asset-harmonizer/scripts/ai_retexture.py --src assets_runtime/textures --dst pipeline/tmp/ai --style docs/moodboard.png --material "weathered wood planks" --denoise 0.5 --ip-weight 0.75
```

The first run downloads about 3.5 GB from HuggingFace (SD1.5, VAE, IPAdapter and image encoder). Later runs work offline. The locks (checkpoint, VAE, style image hash, IP weight, prompt template, seed) are written to `_run.json`. This restyles flat textures. For multi-view projection use 4.1.

## 5. A typical day

1. `init`, then edit `docs/style_guide.json` for your palette, caps and texel targets. Export the moodboard from PureRef to `docs/moodboard.png`.
2. Put raw meshes in `assets_source/meshes` and raw textures in `assets_source/raw_textures`. Name files like `env_role_prop_a.glb`.
3. Run `inventory` (`inventory_blender.py` for FBX) and decide keep / repair / rebuild / drop from `inventory.csv`.
4. Do the engine layer first (master shader, LUT, fog). Often that removes the need for AI.
5. `run --steps 2,3` for normalization and texel density.
6. Textures, in this order: `upscale_batch.py` if needed; AI retexture for hero assets (4.1, 4.3 or 4.4); `pbr_derive.py` or Materialize; `palette` last.
7. `qa`. Go back to the stage the report names for each failure. Work through `docs/qa_checklist.md` for the manual items.
8. Log each run in `pipeline/changelog.md` with the palette, prompt and px/cm versions.

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `CUDA out of memory` | `--size 512`, `--tile 128`, close browsers and Blender, use fp16 |
| `No module named 'torchvision.transforms.functional_tensor'` | Run `fix_basicsr.py` |
| `torch.cuda.is_available()` is False | Install the CUDA wheel (`--index-url .../cu124`) and a current driver |
| Blender not found | `setx BLENDER_EXE "<path>"`, reopen the terminal |
| HuggingFace download slow or blocked | `huggingface-cli login`, or download weights manually and pass `--ckpt <local path>` |
| Normal maps broken after palette pass | Remap must apply to `_diff` only; check data maps were not remapped |
