---
name: triposr
description: "Fast feedforward single-image-to-3D mesh reconstruction using TripoSR (`run.py`, `tsr.system.TSR`, `gradio_app.py`). Supports `rembg` background removal, `--foreground-ratio`, `--mc-resolution`, vertex colors or `--bake-texture --texture-resolution` UV atlas baking, `.obj`/`.glb` export, and NeRF turnarounds."
license: MIT
metadata:
  repository: "https://github.com/VAST-AI-Research/TripoSR"
---

# TripoSR — Fast Single-Image-to-3D Reconstruction (`triposr`)

Feedforward single-image 3D object reconstruction model developed by Tripo AI and Stability AI (based on Large Reconstruction Model / LRM principles). Reconstructs textured 3D meshes from a single RGB/RGBA image in under 0.5 seconds on an A100 GPU (~6 GB VRAM default for a single image), with automatic CPU fallback when CUDA is unavailable.

---

## Requirements & Environment Setup

- **Python**: `>= 3.8`
- **PyTorch + CUDA**: Install PyTorch compiled against the **same CUDA major version** as the locally installed CUDA toolkit (e.g., CUDA 11.x toolkit ↔ CUDA 11.x PyTorch wheel).
- **Build tooling**: `pip install --upgrade setuptools` (`setuptools >= 49.6.0` required for `torchmcubes` CUDA extension compilation).
- **Dependencies** (`requirements.txt`):
  - `omegaconf==2.3.0`, `Pillow==10.1.0`, `einops==0.7.0`, `transformers==4.35.0`
  - `git+https://github.com/tatsy/torchmcubes.git` (marching cubes extraction)
  - `trimesh==4.0.5`, `rembg`, `huggingface-hub`, `imageio[ffmpeg]`, `gradio`
  - `xatlas==0.0.9`, `moderngl==5.10.0` (used for UV parameterization and texture baking)

---

## CLI Inference (`run.py`)

Reconstruct one or more images (space-separated) from the command line:

```powershell
# Default inference: rembg background removal + vertex-colored .obj in output/0/mesh.obj
python run.py examples/chair.png --output-dir output/

# Export game-ready GLB with baked UV texture atlas
python run.py examples/chair.png --model-save-format glb --bake-texture --texture-resolution 2048 --output-dir output/

# Batch multiple images with custom foreground framing and marching cubes resolution
python run.py examples/chair.png examples/teapot.png --foreground-ratio 0.85 --mc-resolution 256 --output-dir output/
```

### Key CLI Flags (`run.py`)

| Flag | Default | Purpose |
|---|---|---|
| `image` (positional, `nargs="+"`) | — | One or more input image paths. Results are written under `<output-dir>/<index>/`. |
| `--device` | `cuda:0` | Compute device; automatically falls back to `cpu` if `torch.cuda.is_available()` is `False`. |
| `--pretrained-model-name-or-path` | `stabilityai/TripoSR` | Hugging Face repo ID or local directory containing `config.yaml` and `model.ckpt`. |
| `--chunk-size` | `8192` | Evaluation chunk size for triplane surface extraction/rendering (`0` disables chunking; lower values reduce VRAM usage at the cost of speed). |
| `--mc-resolution` | `256` | Marching cubes grid resolution (`MarchingCubeHelper`). Higher values capture finer silhouette detail but increase vertex/face counts and memory. |
| `--no-remove-bg` | `False` | Skip `rembg`. Input must already be an RGB image on a neutral gray background with a properly sized foreground. |
| `--foreground-ratio` | `0.85` | Target foreground-to-canvas ratio during `rembg` preprocessing (`resize_foreground`). Only applied when `--no-remove-bg` is not set. |
| `--output-dir` | `output/` | Base output directory (`<output-dir>/<i>/mesh.<ext>`, plus `input.png` when `rembg` runs). |
| `--model-save-format` | `obj` | Output mesh format: `obj` or `glb`. |
| `--bake-texture` | `False` | Bake a UV texture atlas (`texture.png`) instead of exporting per-vertex colors. |
| `--texture-resolution` | `2048` | Square pixel size of the baked texture atlas when `--bake-texture` is enabled. |
| `--render` | `False` | Render 30 turnaround frames (`render_000.png`–`render_029.png`) and `render.mp4` at 30 fps. |

---

## Preprocessing & Background Removal

When `--no-remove-bg` is omitted:
1. `rembg.new_session()` segments the foreground alpha mask via `tsr.utils.remove_background`.
2. `tsr.utils.resize_foreground(image, foreground_ratio)` pads/centers the object at `--foreground-ratio` (default `0.85`; recommended `>= 0.70`).
3. Alpha is composited over mid-gray (`0.5`, RGB `[128, 128, 128]`) and saved as `<output-dir>/<i>/input.png`.

When passing already-segmented RGBA images into `gradio_app.py` (or pre-composited RGB on gray in `run.py`), disable background removal (`--no-remove-bg` / uncheck **Remove Background**) to avoid double-clipping thin details.

---

## Vertex Colors vs. Baked UV Textures

| Mode | Flags | How It Works | Output Files | Best For |
|---|---|---|---|---|
| **Vertex Colors** (default) | *(omit `--bake-texture`)* | `model.extract_mesh(scene_codes, has_vertex_color=True)` queries triplane color at each marching-cubes vertex and exports via `trimesh`. | `mesh.obj` or `mesh.glb` with vertex color attributes | Quick previews, sculpting/remeshing bases, zero UV overhead |
| **Baked UV Texture Atlas** | `--bake-texture --texture-resolution 2048` | `tsr.bake_texture.bake_texture` builds a UV atlas with `xatlas`, rasterizes a 3D position atlas via `moderngl` (with edge dilation), queries triplane decoder colors, exports UV-mapped mesh via `xatlas.export`, and saves flipped-top-bottom `texture.png`. | `mesh.obj` / `mesh.glb` + `texture.png` | Game engines, web viewers, or downstream PBR material workflows |

---

## Python API (`tsr.system.TSR`)

```python
import torch
from PIL import Image
from tsr.system import TSR
from tsr.bake_texture import bake_texture

device = "cuda:0" if torch.cuda.is_available() else "cpu"
model = TSR.from_pretrained(
    "stabilityai/TripoSR",
    config_name="config.yaml",
    weight_name="model.ckpt",
)
model.renderer.set_chunk_size(8192)
model.to(device)

image = Image.open("preprocessed_rgb.png").convert("RGB")
with torch.no_grad():
    scene_codes = model([image], device=device)

# Option A: vertex-colored mesh
meshes = model.extract_mesh(scene_codes, has_vertex_color=True, resolution=256, threshold=25.0)
meshes[0].export("out_vertex.glb")

# Option B: UV-unwrapped mesh + baked texture
meshes = model.extract_mesh(scene_codes, has_vertex_color=False, resolution=256, threshold=25.0)
bake_out = bake_texture(meshes[0], model, scene_codes[0], texture_resolution=2048)

# Optional 30-view NeRF turnaround
turnaround = model.render(scene_codes, n_views=30, elevation_deg=0.0, camera_distance=1.9, fovy_deg=40.0, height=256, width=256, return_type="pil")
```

---

## Local Gradio Web App (`gradio_app.py`)

```powershell
python gradio_app.py --port 7860
# Expose on LAN or share link with optional basic auth:
python gradio_app.py --listen --port 7860 --queuesize 1 --username admin --password secret
```

- Interactive controls: **Remove Background** (default `True`), **Foreground Ratio** (`0.5`–`1.0`, step `0.05`, default `0.85`), **Marching Cubes Resolution** (`32`–`320`, step `32`, default `256`).
- Generates both `.obj` and `.glb` preview tabs (applies `to_gradio_3d_orientation` for viewer display).

---

## Troubleshooting & Downstream Cleanup

- **`AttributeError: module 'torchmcubes_module' has no attribute 'mcubes_cuda'` / CPU-only warning**:
  Ensure local CUDA toolkit major version matches PyTorch's CUDA major version and `setuptools>=49.6.0`, then rebuild:
  ```powershell
  pip uninstall torchmcubes
  pip install git+https://github.com/tatsy/torchmcubes.git
  ```
- **Game-Ready Post-Processing**: Raw marching-cubes meshes are dense and triangulated without real-world scale. Pipe exported `.glb` files through `mcp-for-blender` (`references/retopology.md` for Decimate / QuadriFlow + normal baking) or `glb-forge` (`optimize` / `lod`) before shipping to Godot/Unity/Unreal/Three.js.
