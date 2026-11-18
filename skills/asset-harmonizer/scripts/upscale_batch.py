"""Stage 4a - tiled Real-ESRGAN upscale (8 GB safe).
usage: python upscale_batch.py --src DIR --dst DIR [--scale 4] [--tile 256] [--exe path\\realesrgan-ncnn-vulkan.exe]
Skips data maps? NO - upscale albedo only by default (_diff/_albedo/_basecolor/_emi); pass --all to include others.
Backends: ncnn-vulkan exe (--exe, no torch) or python `realesrgan` (weights auto-downloaded to ./weights).
After upscaling, downsize to the texel-density target (the script resizes to --final px if given)."""
import argparse, subprocess, sys
from pathlib import Path
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True); ap.add_argument("--dst", required=True)
ap.add_argument("--scale", type=int, default=4); ap.add_argument("--tile", type=int, default=256)
ap.add_argument("--exe"); ap.add_argument("--final", type=int, help="final square size px after upscale")
ap.add_argument("--all", action="store_true"); ap.add_argument("--model", default="RealESRGAN_x4plus")
a = ap.parse_args()
src, dst = Path(a.src), Path(a.dst); dst.mkdir(parents=True, exist_ok=True)
ok = ("_diff", "_albedo", "_basecolor", "_emi")
files = [p for p in sorted(src.glob("*.png")) if a.all or p.stem.lower().endswith(ok)]
up = None
if not a.exe:
    import torch
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer
    import numpy as np, urllib.request
    w = Path("weights"); w.mkdir(exist_ok=True); wf = w / "RealESRGAN_x4plus.pth"
    if not wf.exists():
        urllib.request.urlretrieve("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth", wf)
    net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    up = RealESRGANer(scale=4, model_path=str(wf), model=net, tile=a.tile, tile_pad=10, half=True,
                      device="cuda" if torch.cuda.is_available() else "cpu")
for p in files:
    out = dst / p.name
    if a.exe:
        subprocess.run([a.exe, "-i", str(p), "-o", str(out), "-s", str(a.scale), "-t", str(a.tile), "-n", "realesrgan-x4plus"], check=True)
    else:
        import numpy as np
        im = Image.open(p).convert("RGB"); r, _ = up.enhance(np.asarray(im)[:, :, ::-1], outscale=a.scale)
        Image.fromarray(r[:, :, ::-1]).save(out)
    if a.final:
        im = Image.open(out); im.resize((a.final, a.final), Image.LANCZOS).save(out)
    print("upscaled", p.name)
