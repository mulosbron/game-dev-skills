#!/usr/bin/env python3
"""asset_harmonizer.py - mixed-source 3D asset -> single visual language pipeline (offline).

Subcommands:
  init       scaffold project tree + docs/style_guide.json + palette placeholder
  open       launch the offline browser tool asset-harmonizer.html
  inventory  pure-python GLB/OBJ scan -> CSV (tris, dims, materials, uv, textures) + triage hint
  palette    quantize *_diff albedo textures to style palette (data maps never touched)
  qa         automatic half of the Definition-of-Done gate (naming, tri cap, dims, suffixes)
  run        chain: inventory -> blender normalize -> blender texel -> palette -> qa

Style rules live in <project>/docs/style_guide.json (single source of truth).
Blender stages call skills/asset-harmonizer/scripts/*.py via `blender -b -P`.
"""
import argparse, csv, json, os, re, struct, subprocess, sys, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "skills" / "asset-harmonizer" / "scripts"
HTML = HERE.parent / "skills" / "asset-harmonizer" / "asset-harmonizer.html"

DEFAULT_STYLE = {
    "version": "1.0",
    "palette": ["#f4e9d8", "#d9c7a7", "#b09a6f", "#87702a", "#5c4a1e", "#3f3a2e", "#7a6a58", "#a18347"],
    "emissive_palette": ["#4fc3ff", "#ff7a1a"],
    "saturation_cap": 0.70,
    "texel_density_px_cm": {"hero": 10.24, "prop": 5.12, "bg": 2.56},
    "texel_tolerance": 0.05,
    "poly_cap": {"bg": 300, "prop": 2000, "hero": 10000, "char": 40000},
    "scale": "1 unit = 1 m",
    "pivot": "bottom-center; Z up; forward +X (Unity: +Z, Unreal: +X, Godot: -Z)",
    "engine": "godot",
    "naming_regex": r"^(env|char|ui)_[a-z0-9]+(_[a-z0-9]+)*\.(fbx|obj|glb|gltf)$",
    "auto_smooth_deg": 40,
    "dither": "none",
    "dimension_ranges_m": {"chair": [0.9, 1.1], "door": [2.0, 2.2]},
}

MESH_EXT = (".glb", ".gltf", ".obj", ".fbx")
ALBEDO_SUFFIX = ("_diff", "_albedo", "_basecolor")
DATA_SUFFIX = ("_nrm", "_rma", "_rough", "_metal", "_ao", "_normal", "_orm", "_height")
EMISSIVE_SUFFIX = ("_emi", "_emissive")
CLASS_RE = re.compile(r"_(bg|prop|hero|char)(_|\.)")


def load_style(root):
    p = Path(root) / "docs" / "style_guide.json"
    if p.exists():
        s = dict(DEFAULT_STYLE); s.update(json.loads(p.read_text(encoding="utf-8"))); return s
    return DEFAULT_STYLE


def hex2rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def asset_class(name):
    m = CLASS_RE.search(name)
    return m.group(1) if m else "prop"


# ---------------------------------------------------------------- GLB / OBJ metrics
def glb_metrics(path):
    data = Path(path).read_bytes()
    if path.lower().endswith(".gltf"):
        j = json.loads(data.decode("utf-8"))
    else:
        if data[:4] != b"glTF":
            raise ValueError("not a GLB")
        clen, ctype = struct.unpack_from("<II", data, 12)
        j = json.loads(data[20:20 + clen].decode("utf-8"))
    tris = 0; mn = [1e9] * 3; mx = [-1e9] * 3; uv = True; prims = 0
    for mesh in j.get("meshes", []):
        for pr in mesh.get("primitives", []):
            prims += 1
            acc = j["accessors"]
            pos = acc[pr["attributes"]["POSITION"]]
            n = acc[pr["indices"]]["count"] if "indices" in pr else pos["count"]
            tris += n // 3
            for i in range(3):
                mn[i] = min(mn[i], pos["min"][i]); mx[i] = max(mx[i], pos["max"][i])
            if "TEXCOORD_0" not in pr["attributes"]:
                uv = False
    dims = [round(mx[i] - mn[i], 3) for i in range(3)] if prims else [0, 0, 0]
    return dict(tris=tris, dims=dims, materials=len(j.get("materials", [])), uv=uv,
                textures=len(j.get("images", [])), grounded=bool(prims) and abs(mn[1]) < 1e-3,
                has_scale_nodes=any("scale" in n and n["scale"] != [1, 1, 1] for n in j.get("nodes", [])))


def obj_metrics(path):
    mn = [1e9] * 3; mx = [-1e9] * 3; tris = 0; uv = False
    with open(path, errors="ignore") as f:
        for ln in f:
            if ln.startswith("v "):
                c = [float(x) for x in ln.split()[1:4]]
                for i in range(3): mn[i] = min(mn[i], c[i]); mx[i] = max(mx[i], c[i])
            elif ln.startswith("vt "): uv = True
            elif ln.startswith("f "): tris += max(len(ln.split()) - 3, 1)
    return dict(tris=tris, dims=[round(mx[i] - mn[i], 3) for i in range(3)], materials=0, uv=uv,
                textures=0, grounded=abs(mn[2]) < 1e-3, has_scale_nodes=False)


def triage(m, cap):
    if m["tris"] == 0: return "rebuild"
    if m["tris"] <= cap and m["uv"] and not m["has_scale_nodes"]: return "keep"
    if not m["uv"]: return "repair_uv"
    return "repair"


def cmd_inventory(a):
    st = load_style(a.root); src = Path(a.root) / a.src
    out = Path(a.root) / "pipeline" / "inventory.csv"; out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted(src.rglob("*")):
        ext = p.suffix.lower()
        if ext not in MESH_EXT: continue
        if ext == ".fbx":
            rows.append([p.name, "", "", "", "", "", "", "fbx: run Blender inventory (scripts/inventory_blender.py)"]); continue
        try:
            m = glb_metrics(str(p)) if ext in (".glb", ".gltf") else obj_metrics(str(p))
        except Exception as e:
            rows.append([p.name, "", "", "", "", "", "", f"error:{e}"]); continue
        cap = st["poly_cap"].get(asset_class(p.name), 2000)
        rows.append([p.name, m["materials"], m["tris"], cap, "x".join(map(str, m["dims"])), m["uv"],
                     m["textures"], triage(m, cap)])
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["file", "materials", "tris", "cap", "dims_m", "uv", "textures", "triage"]); w.writerows(rows)
    print(f"{len(rows)} assets -> {out}")


# ---------------------------------------------------------------- palette
def cmd_palette(a):
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        sys.exit("pip install pillow numpy")
    st = load_style(a.root)
    pal = np.array([hex2rgb(h) for h in st["palette"]], dtype=np.float32)
    epal = np.array([hex2rgb(h) for h in st["emissive_palette"]], dtype=np.float32)
    tex = Path(a.root) / a.tex; n = 0
    for p in sorted(tex.rglob("*.png")):
        stem = p.stem.lower()
        if stem.endswith("_pal") or any(stem.endswith(s) for s in DATA_SUFFIX): continue
        is_e = any(stem.endswith(s) for s in EMISSIVE_SUFFIX)
        if not (is_e or any(stem.endswith(s) for s in ALBEDO_SUFFIX)): continue
        im = Image.open(p).convert("RGBA"); arr = np.asarray(im).astype(np.float32)
        rgb = arr[..., :3]; alpha = arr[..., 3]
        P = epal if is_e else pal
        flat = rgb.reshape(-1, 3)
        idx = np.empty(len(flat), dtype=np.int64)
        for s in range(0, len(flat), 262144):  # chunked nearest-colour (bounded RAM)
            d = ((flat[s:s + 262144, None, :] - P[None, :, :]) ** 2).sum(-1); idx[s:s + 262144] = d.argmin(1)
        out = P[idx].reshape(rgb.shape)
        res = np.dstack([out, alpha]).astype(np.uint8)
        dst = p if a.inplace else p.with_name(p.stem + "_pal.png")
        Image.fromarray(res, "RGBA" if (alpha < 255).any() else "RGBA").save(dst); n += 1
    print(f"palette-remapped {n} albedo/emissive textures (data maps skipped, alpha preserved, no dither)")


# ---------------------------------------------------------------- QA
def cmd_qa(a):
    st = load_style(a.root); rx = re.compile(st["naming_regex"]); rt = Path(a.root) / a.rt
    report = []; fails = 0
    for p in sorted(rt.rglob("*")):
        ext = p.suffix.lower()
        if ext in (".glb", ".gltf", ".obj"):
            errs = []
            if not rx.match(p.name): errs.append(("naming", "stage1: rename"))
            try:
                m = glb_metrics(str(p)) if ext != ".obj" else obj_metrics(str(p))
                cap = st["poly_cap"].get(asset_class(p.name), 2000)
                if m["tris"] > cap: errs.append((f"tris {m['tris']}>{cap}", "stage2: decimate"))
                if m["has_scale_nodes"]: errs.append(("node scale != 1", "stage2: apply transforms"))
                if not m["uv"]: errs.append(("no UV", "stage3: unwrap"))
                if ext != ".obj" and not m["grounded"]: errs.append(("pivot not at base (min Y != 0)", "stage2: pivot"))
                if max(m["dims"]) > 100 or (max(m["dims"]) < 0.01 and m["tris"]): errs.append(("implausible size (unit error?)", "stage2: scale"))
            except Exception as e:
                errs.append((f"unreadable:{e}", "stage1: triage"))
            report.append((p.name, errs)); fails += bool(errs)
        elif ext == ".png":
            s = p.stem.lower()
            if not re.search(r"_(diff|nrm|rma|emi)(_pal)?$", s):
                report.append((p.name, [("texture suffix not _diff/_nrm/_rma/_emi", "stage4: rename")])); fails += 1
            elif s.endswith("_diff") and not a.allow_unpaletted and not (p.with_name(s + "_pal.png").exists()):
                report.append((p.name, [("albedo without _pal pass", "stage4: palette")])); fails += 1
    for name, errs in report:
        print(("FAIL " if errs else "PASS ") + name + ("  <- " + "; ".join(f"{e} [{b}]" for e, b in errs) if errs else ""))
    out = Path(a.root) / "pipeline" / "qa_report.json"; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([{"file": n, "errors": e} for n, e in report], indent=1), encoding="utf-8")
    print(f"{len(report) - fails}/{len(report)} passed -> {out}. Manual items left: visual cohesion, camera-distance test, LUT.")
    sys.exit(1 if fails else 0)


# ---------------------------------------------------------------- init / run
def cmd_init(a):
    r = Path(a.root)
    for d in ["docs", "assets_source/meshes", "assets_source/raw_textures", "assets_runtime/meshes",
              "assets_runtime/textures", "assets_runtime/materials", "pipeline/tmp"]:
        (r / d).mkdir(parents=True, exist_ok=True)
    sg = r / "docs" / "style_guide.json"
    if not sg.exists(): sg.write_text(json.dumps(DEFAULT_STYLE, indent=2), encoding="utf-8")
    (r / ".gitignore").write_text("assets_runtime/\npipeline/tmp/\n", encoding="utf-8") if not (r / ".gitignore").exists() else None
    tpl = SCRIPTS.parent / "templates" / "qa_checklist.md"
    if tpl.exists() and not (r / "docs" / "qa_checklist.md").exists(): shutil.copy(tpl, r / "docs" / "qa_checklist.md")
    print(f"scaffolded {r}. Edit docs/style_guide.json (palette, caps, texel) before running.")


def blender_stage(script, a, extra):
    exe = shutil.which("blender") or os.environ.get("BLENDER_EXE")
    if not exe: sys.exit("blender not found (PATH or BLENDER_EXE)")
    cmd = [exe, "-b", "-P", str(SCRIPTS / script), "--", "--root", a.root, "--style", str(Path(a.root) / "docs" / "style_guide.json")] + extra
    print(">>", " ".join(cmd)); subprocess.run(cmd, check=True)


def cmd_run(a):
    steps = a.steps.split(",")
    ns = argparse.Namespace(**vars(a))
    for s in steps:
        s = s.strip()
        if s == "1": ns.src = "assets_source/meshes"; cmd_inventory(ns)
        elif s == "2": blender_stage("normalize_blender.py", a, ["--src", "assets_source/meshes", "--out", "assets_runtime/meshes"])
        elif s == "3": blender_stage("texel_blender.py", a, ["--dir", "assets_runtime/meshes"])
        elif s == "4": ns.tex = "assets_runtime/textures"; ns.inplace = False; cmd_palette(ns)
        elif s == "6":
            ns.rt = "assets_runtime"; ns.allow_unpaletted = False
            try: cmd_qa(ns)
            except SystemExit as e: print("qa exit", e.code)
        else: sys.exit(f"unknown step {s} (1,2,3,4,6; stage 5 = engine LUT/master shader, see SKILL.md)")


def cmd_open(a):
    if not HTML.exists(): sys.exit(f"HTML not found at {HTML}")
    print(f"Opening the browser tool: {HTML}")
    if sys.platform == "win32": os.startfile(str(HTML))
    elif sys.platform == "darwin": subprocess.run(["open", str(HTML)])
    else: subprocess.run(["xdg-open", str(HTML)])


def cmd_doctor(a):
    import importlib.util
    ok = lambda b: "OK  " if b else "MISS"
    print("== Python packages ==")
    for mod, pipn in [("PIL", "pillow"), ("numpy", "numpy"), ("cv2", "opencv-python-headless"), ("scipy", "scipy"),
                      ("trimesh", "trimesh"), ("pygltflib", "pygltflib"), ("xatlas", "xatlas"), ("torch", "torch (cu124 wheel)"),
                      ("diffusers", "diffusers"), ("transformers", "transformers"), ("accelerate", "accelerate"),
                      ("safetensors", "safetensors"), ("huggingface_hub", "huggingface_hub"),
                      ("realesrgan", "realesrgan"), ("basicsr", "basicsr")]:
        print(ok(importlib.util.find_spec(mod) is not None), pipn)
    print("== CUDA / VRAM ==")
    try:
        import torch
        print(ok(torch.cuda.is_available()), "torch.cuda", torch.version.cuda)
        if torch.cuda.is_available():
            pr = torch.cuda.get_device_properties(0); gb = pr.total_memory / 1e9
            print(f"     {pr.name} {gb:.1f} GB ->", "SD1.5 fp16 + ControlNet + IPAdapter OK" if gb >= 7.5 else "low VRAM: use --size 512, tiled VAE")
    except ImportError:
        print("MISS torch")
    nv = shutil.which("nvidia-smi")
    print(ok(bool(nv)), "nvidia-smi")
    print("== External tools ==")
    b = shutil.which("blender") or os.environ.get("BLENDER_EXE")
    print(ok(bool(b) and Path(b).exists()), "Blender", b or "(set BLENDER_EXE)")
    print(ok(bool(shutil.which("magick"))), "ImageMagick (magick)")
    print(ok(bool(shutil.which("git"))), "git")
    for name, hint in [("realesrgan-ncnn-vulkan", "github.com/xinntao/Real-ESRGAN-ncnn-vulkan"),
                       ("Instant Meshes", "github.com/wjakob/instant-meshes"),
                       ("Materialize / Stable Projectorz / ComfyUI / PureRef", "GUI apps: see references/setup.md (cannot be auto-detected)")]:
        print("INFO", name, "->", hint)
    hf = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    for rid in ["models--stable-diffusion-v1-5--stable-diffusion-v1-5", "models--h94--IP-Adapter", "models--stabilityai--sd-vae-ft-mse"]:
        print(ok((hf / rid).exists()), "HF cache", rid, "(auto-downloads on first ai_retexture run)")
    print("Full install guide: skills/asset-harmonizer/references/setup.md")


def detect_hardware():
    hw = {"os": sys.platform, "gpu": None, "vram_gb": None, "ram_gb": None, "disk_free_gb": None}
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        if out:
            name, mem = [x.strip() for x in out[0].split(",")]
            hw["gpu"], hw["vram_gb"] = name, round(float(mem) / 1024, 1)
    except Exception:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("l", ctypes.c_ulong), ("m", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                            ("tpf", ctypes.c_ulonglong), ("apf", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong),
                            ("ae", ctypes.c_ulonglong)]
            s = MS(); s.l = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
            hw["ram_gb"] = round(s.tp / 1e9, 1)
        else:
            hw["ram_gb"] = round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9, 1)
    except Exception:
        pass
    hw["disk_free_gb"] = round(shutil.disk_usage(Path.cwd()).free / 1e9)
    return hw


def recommend_route(hw):
    v = hw["vram_gb"]
    if v is None:
        return ("A: no-AI route", "No NVIDIA GPU detected. Use engine LUT + master shader, palette remap, PBR derivation, and "
                "Real-ESRGAN ncnn-vulkan (works on AMD/Intel GPUs). Skip local AI retexturing or rent nothing; hand-paint heroes.")
    if v < 6:
        return ("B: light AI", f"{v} GB VRAM. SD1.5 fp16 img2img at 512 px only (ai_retexture.py --size 512). No ControlNet stack. "
                "Stable Projectorz only at low resolution. Everything else as route A.")
    if v < 10:
        return ("C: standard AI (reference setup)", f"{v} GB VRAM. SD1.5 fp16 + ControlNet + IPAdapter (~6.5 GB). Stable Projectorz in fp16 mode. "
                "SDXL only with --medvram + tiled VAE for a few hero assets.")
    return ("D: full AI", f"{v} GB VRAM. SDXL is comfortable; Stable Projectorz at full quality; larger textures (1024+) in ComfyUI.")


def cmd_profile(a):
    hw = detect_hardware()
    print("== Detected hardware ==")
    for k, v in hw.items():
        print(f"  {k}: {v if v is not None else 'not detected'}")
    r, why = recommend_route(hw)
    print(f"\nRecommended route: {r}\n  {why}")
    if hw["ram_gb"] and hw["ram_gb"] < 12: print("  WARNING: under 12 GB RAM; Stable Projectorz may be unstable.")
    if hw["disk_free_gb"] < 40: print(f"  WARNING: {hw['disk_free_gb']} GB free here; AI models need about 15 GB, plan 40 GB.")
    print("\nThe agent must confirm these with the user (detection can be wrong, e.g. laptop hybrid GPUs).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def add(n, f, **kw):
        p = sp.add_parser(n); p.add_argument("--root", default="."); p.set_defaults(fn=f); return p
    add("init", cmd_init)
    add("open", cmd_open)
    add("doctor", cmd_doctor)
    add("profile", cmd_profile)
    p = add("inventory", cmd_inventory); p.add_argument("--src", default="assets_source/meshes")
    p = add("palette", cmd_palette); p.add_argument("--tex", default="assets_runtime/textures"); p.add_argument("--inplace", action="store_true")
    p = add("qa", cmd_qa); p.add_argument("--rt", default="assets_runtime"); p.add_argument("--allow-unpaletted", action="store_true")
    p = add("run", cmd_run); p.add_argument("--steps", default="1,2,3,4,6")
    a = ap.parse_args(); a.fn(a)


if __name__ == "__main__":
    main()
