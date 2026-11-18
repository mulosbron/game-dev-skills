"""Stage 4 (AI) - scripted local SD1.5 fp16 img2img retexture with IPAdapter style lock (8 GB VRAM).
Python alternative to ComfyUI for texture-level restyle (not multi-view projection; use Stable Projectorz for that).
usage: python ai_retexture.py --src DIR --dst DIR --style moodboard.png --material "weathered wood planks"
         [--denoise 0.5] [--ip-weight 0.75] [--size 768] [--seed 1234] [--ckpt PATH_OR_HF_ID]
Locks (written to dst/_run.json): checkpoint, VAE, style image hash, IP weight, prompt template, seed.
First run downloads ~2 GB (SD1.5) + ~1.3 GB (IPAdapter+CLIP) from HuggingFace; later runs offline (HF_HUB_OFFLINE=1).
Tile-seamless: enables circular padding on UNet/VAE convs."""
import argparse, hashlib, json, torch
from pathlib import Path
from PIL import Image
from diffusers import StableDiffusionImg2ImgPipeline, AutoencoderKL, DDIMScheduler

TEMPLATE = ("{m}, stylized hand-painted game asset texture, warm limited palette, soft gradients, "
            "subtle painterly noise, no text, no watermark, flat lighting, seamless, PBR-friendly")
NEG = "text, watermark, lighting, shadows, perspective, photo, noisy, oversaturated"

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True); ap.add_argument("--dst", required=True)
ap.add_argument("--style", required=True); ap.add_argument("--material", default="surface")
ap.add_argument("--denoise", type=float, default=0.5); ap.add_argument("--ip-weight", type=float, default=0.75)
ap.add_argument("--size", type=int, default=768); ap.add_argument("--seed", type=int, default=1234)
ap.add_argument("--ckpt", default="stable-diffusion-v1-5/stable-diffusion-v1-5")
ap.add_argument("--vae", default="stabilityai/sd-vae-ft-mse"); ap.add_argument("--steps", type=int, default=30)
a = ap.parse_args()
dst = Path(a.dst); dst.mkdir(parents=True, exist_ok=True)
vae = AutoencoderKL.from_pretrained(a.vae, torch_dtype=torch.float16)
pipe = StableDiffusionImg2ImgPipeline.from_pretrained(a.ckpt, vae=vae, torch_dtype=torch.float16, safety_checker=None)
pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config)
pipe.load_ip_adapter("h94/IP-Adapter", subfolder="models", weight_name="ip-adapter_sd15.bin")
pipe.set_ip_adapter_scale(a.ip_weight)
pipe.enable_model_cpu_offload(); pipe.enable_vae_tiling(); pipe.enable_attention_slicing()
for m in list(pipe.unet.modules()) + list(pipe.vae.modules()):
    if isinstance(m, torch.nn.Conv2d): m.padding_mode = "circular"
style = Image.open(a.style).convert("RGB")
meta = dict(ckpt=a.ckpt, vae=a.vae, style_sha1=hashlib.sha1(Path(a.style).read_bytes()).hexdigest(),
            ip_weight=a.ip_weight, denoise=a.denoise, template=TEMPLATE, seed=a.seed, size=a.size, steps=a.steps)
for p in sorted(Path(a.src).glob("*_diff.png")):
    im = Image.open(p).convert("RGB").resize((a.size, a.size), Image.LANCZOS)
    g = torch.Generator("cpu").manual_seed(a.seed)
    out = pipe(prompt=TEMPLATE.format(m=a.material), negative_prompt=NEG, image=im, strength=a.denoise,
               ip_adapter_image=style, guidance_scale=7.0, num_inference_steps=a.steps, generator=g).images[0]
    out.save(dst / p.name); print("retextured", p.name, "| VRAM peak GB:", round(torch.cuda.max_memory_allocated() / 1e9, 2))
(dst / "_run.json").write_text(json.dumps(meta, indent=1))
print("NEXT: run palette remap on", dst, "then pbr_derive.py")
