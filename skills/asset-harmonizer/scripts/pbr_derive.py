"""Stage 4b - PBR derivation from albedo (pure numpy/opencv fallback when Materialize CLI is unavailable).
usage: python pbr_derive.py --src DIR [--normal-strength 2.0] [--rough-base 0.8] [--metal-keys "metal,iron,steel"]
Reads *_diff.png -> writes *_nrm.png (tangent normal, OpenGL +Y), *_rma.png (R=roughness, G=metallic, B=AO).
Defaults follow style: matte-dominant, only names containing metal keys get metallic. Parameters printed -> record them in style guide.
Materialize (GUI) gives better results; this keeps batches consistent and fully scripted."""
import argparse, numpy as np, cv2
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True); ap.add_argument("--normal-strength", type=float, default=2.0)
ap.add_argument("--rough-base", type=float, default=0.8); ap.add_argument("--metal-keys", default="metal,iron,steel,gold,silver")
ap.add_argument("--overwrite", action="store_true")
a = ap.parse_args(); keys = [k for k in a.metal_keys.split(",") if k]
for p in sorted(Path(a.src).glob("*_diff.png")):
    base = p.name[:-9]; nrm = p.with_name(base + "_nrm.png"); rma = p.with_name(base + "_rma.png")
    if (nrm.exists() or rma.exists()) and not a.overwrite: continue
    img = cv2.imread(str(p), cv2.IMREAD_COLOR).astype(np.float32) / 255
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h = cv2.GaussianBlur(g, (0, 0), 1.2)
    dx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3) * a.normal_strength
    dy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3) * a.normal_strength
    n = np.dstack([-dx, dy, np.ones_like(h)]); n /= np.linalg.norm(n, axis=2, keepdims=True)
    cv2.imwrite(str(nrm), ((n * 0.5 + 0.5)[:, :, ::-1] * 255).astype(np.uint8))
    rough = np.clip(a.rough_base + (0.5 - h) * 0.3, 0.2, 1.0)
    metal = np.full_like(g, 1.0 if any(k in p.stem.lower() for k in keys) else 0.0)
    if metal.mean() > 0: rough = np.clip(rough * 0.6, 0.2, 1)
    ao = np.clip(1 - np.clip(cv2.GaussianBlur(g, (0, 0), 8) - g, 0, 1) * 2, 0.3, 1)
    cv2.imwrite(str(rma), (np.dstack([ao, metal, rough]) * 255).astype(np.uint8))  # BGR write -> file RGB = rough, metal, ao
    print("pbr", base)
print(f"params: normal_strength={a.normal_strength} rough_base={a.rough_base} metal_keys={keys}")
