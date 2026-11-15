---
name: mesh-splatting
description: Official CVPR 2026 implementation of MeshSplatting (`meshsplatting/mesh-splatting`) for differentiable surface reconstruction and real-time rendering with opaque triangle meshes, normal/depth supervision, SAM2 single-object mesh extraction, and `.ply` export for game engines and Web viewers.
metadata:
  homepage: "https://meshsplatting.github.io"
  repository: "https://github.com/meshsplatting/mesh-splatting"
---

# MeshSplatting (`meshsplatting/mesh-splatting`)

Use this skill when reconstructing 3D scenes or individual game-ready objects as opaque triangle meshes (`.ply` / Web export) from multi-view images via differentiable rendering (`Python 3.11`, `CUDA 12.6`, `PyTorch 2.7.1`).

## Installation

```bash
git clone https://github.com/meshsplatting/mesh-splatting --recursive
cd mesh-splatting

micromamba create -n mesh_splatting python=3.11
micromamba activate mesh_splatting
micromamba install nvidia/label/cuda-12.6.0::cuda

pip install torch==2.7.1 torchvision==0.22.1
pip install -r requirements.txt

bash compile.sh
cd submodules/simple-knn && pip install . --no-build-isolation
cd ../effrdel && pip install -e .
```

Optional speed optimization: install `fused-ssim` (`pip install git+https://github.com/rahul-goel/fused-ssim/ --no-build-isolation`).

## Core Workflows

### 1. Train / Reconstruct a Scene
```bash
# Outdoor / general scene
python train.py -s <path_to_scenes> -m <output_model_path> --eval

# Indoor scene
python train.py -s <path_to_scenes> -m <output_model_path> --indoor --eval
```
Optional geometric priors before training:
- **Normals**: `python extract_normals.py -s <path_to_dataset>`
- **Depth**: generate grayscale depth maps under `<scene>/depth` (e.g. Depth Anything v2) + `python utils/make_depth_scale.py --base_dir <path_to_colmap> --depths_dir <path_to_generated_depths>`

### 2. Render, Export Video & `.ply` Mesh for Game Engines
```bash
python render.py -m <path_to_model>
python create_video.py -m <path_to_model> -s <path_to_scenes>
python create_ply.py <output_model_path>
```
Additional repository scripts: `export_web.py`, `eval.py`, `full_eval.py`.

### 3. Single-Object Extraction via SAM2
Isolate and export triangles belonging to a specific object as its own `.ply` mesh:
```bash
python annotate_points_boxes.py <Image.png>
python -m segmentation.extract_images -s <path_to_scenes> -m <path_to_model> --eval
python -m segmentation.sam_mask_generator_json --data_path <path_to_images> --save_path <path_to_save_masks> --json_path <path_to_json_file>
python -m segmentation.segment -s <path_to_scenes> -m <path_to_model> --eval --path_mask <path_to_masks> --object_id <object_id>
python -m segmentation.run_single_object -s <path_to_scenes> -m <path_to_model> --eval --ratio_threshold 0.90
python -m segmentation.create_ply <path_to_model>
```

## Notes & Guardrails

- Exported `.ply` files store vertex/RGB colors only (averaging ~2 dB PSNR lower than the native renderer); use 4x supersampling in engine/Unity previews for best visual quality.
- Use higher `--ratio_threshold` (e.g. `0.90`) for clean object extraction and lower values for object removal.
