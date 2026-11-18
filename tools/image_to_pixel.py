#!/usr/bin/env python3
"""
Image-to-Pixel 3.2.0 Art-Direction & Game Pipeline CLI (tools/image_to_pixel.py)
Backed by `libraries/com.github.tezumie.image-to-pixel` (MIT License, by Tezumie).

Why "Art-Direction Lock" Matters in Games:
Converting 3D renders, concept art, or video clips into pixel art one by one with random
settings breaks visual cohesion ("mixels", clashing palettes, dither boiling on animated frames).
This tool enforces strict Game Visual Style Profiles across single sprites, batch folders,
animated `_stripN.png` sheets, and deduplicated tilesets:

1. Locked Texel Density (`--width` per sprite/frame so 1 pixel = 1 game unit everywhere)
2. Locked Master Palette (`endesga-32`, `apollo`, `pico-8`, `game-boy-dmg`, `1-bit-monitor`, etc.)
3. Animation-Safe Dithering (`none` or ordered `bayer2`/`bayer4` on strips to prevent frame-to-frame dither boil!)
4. Silhouette & Cleanup Enforcement (`cleanup.orphans`, `cleanup.smooth`, `outline.mode = outer/inner`)
5. Deduplicated Tileset Builder (`buildTileset` -> unique tiles PNG + tilemap JSON)
6. Local Offline WebGL 2 Studio Server (`serve-editor`)

Usage:
  python tools/image_to_pixel.py list
  python tools/image_to_pixel.py convert "assets/com.threejsassets/thumbs/dun-treasure-chest.png" --profile jrpg-16bit --width 64 --scale 4
  python tools/image_to_pixel.py compare "assets/com.threejsassets/thumbs/dun-treasure-chest.png" --width 64
  python tools/image_to_pixel.py tileset "assets/com.threejsassets/thumbs/agora-flagstone-tile.png" --tile-size 16 --profile dark-fantasy
  python tools/image_to_pixel.py serve-editor --port 8080
"""

import re
import os
import sys
import json
import subprocess
import tempfile
import argparse
from pathlib import Path
from PIL import Image, ImageDraw

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = WORKSPACE_ROOT / "libraries" / "com.github.tezumie.image-to-pixel"
ESM_ENTRY = LIB_DIR / "dist" / "image-to-pixel.esm.js"
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.github.tezumie.image-to-pixel"

# Curated Game Art-Direction Profiles (Preserves visual consistency across an entire game)
GAME_STYLE_PROFILES = {
    "clean-sprite": {
        "label": "Clean Sprite (Zero Dither Boil)",
        "description": "Best for animated characters & small props. Crisp cel-shaded clusters, orphan cleanup, outer dark outline.",
        "settings": {
            "palette": {"source": "builtin", "id": "endesga-32", "distance": "oklab"},
            "dither": {"method": "none", "strength": 0.0},
            "cleanup": {"orphans": True, "smooth": True},
            "outline": {"mode": "outer", "color": "#14101c", "corners": False},
            "alpha": {"threshold": 128},
        },
    },
    "jrpg-16bit": {
        "label": "16-Bit SNES/GBA JRPG",
        "description": "Vibrant Endesga-32 palette with subtle Bayer-4 ordered dither, orphan cleanup, and outer outline.",
        "settings": {
            "palette": {"source": "builtin", "id": "endesga-32", "distance": "oklab"},
            "dither": {"method": "bayer4", "strength": 0.22},
            "cleanup": {"orphans": True, "smooth": False},
            "outline": {"mode": "outer", "color": "#181425", "corners": False},
            "alpha": {"threshold": 128},
        },
    },
    "dark-fantasy": {
        "label": "Dark Fantasy / Souls / Wuxia",
        "description": "Rich atmospheric 46-color Apollo palette with blue-noise dither and deep obsidian outer outline.",
        "settings": {
            "palette": {"source": "builtin", "id": "apollo", "distance": "oklab"},
            "dither": {"method": "bluenoise", "strength": 0.28},
            "cleanup": {"orphans": True, "smooth": False},
            "outline": {"mode": "outer", "color": "#0d0b14", "corners": False},
            "alpha": {"threshold": 0.25},
        },
    },
    "pico-8": {
        "label": "PICO-8 Fantasy Console",
        "description": "Strict 16-color PICO-8 palette with classic Bayer-2 checker dithering.",
        "settings": {
            "palette": {"source": "builtin", "id": "pico-8", "distance": "oklab"},
            "dither": {"method": "bayer2", "strength": 0.35},
            "cleanup": {"orphans": False, "smooth": False},
            "outline": {"mode": "outer", "color": "#000000", "corners": False},
            "alpha": {"threshold": 0.25},
        },
    },
    "retro-handheld": {
        "label": "Game Boy DMG (4-Color)",
        "description": "Authentic 4-shade olive Game Boy DMG screen with Bayer-2 ordered matrix dithering.",
        "settings": {
            "palette": {"source": "builtin", "id": "game-boy-dmg", "distance": "oklab"},
            "dither": {"method": "bayer2", "strength": 0.40},
            "cleanup": {"orphans": False, "smooth": False},
            "outline": {"mode": "none", "color": "#0f380f", "corners": False},
            "alpha": {"threshold": 0.25},
        },
    },
    "1bit-noir": {
        "label": "1-Bit Atkinson (Obra Dinn Style)",
        "description": "High-contrast 2-color 1-Bit Monitor with sharp Atkinson error diffusion.",
        "settings": {
            "palette": {"source": "builtin", "id": "1-bit-monitor", "distance": "oklab"},
            "dither": {"method": "atkinson", "strength": 0.75},
            "cleanup": {"orphans": False, "smooth": False},
            "outline": {"mode": "none", "color": "#000000", "corners": False},
            "alpha": {"threshold": 0.25},
        },
    },
    "egregore-clay": {
        "label": "RAW GODS — Kneaded Cosmos (Clay & Stop-Motion)",
        "description": "Locked 7-Color Egregore Clay Bible (Table 10) + Kiln Shadows with tactile Bayer-4 dithering and #14100E outer contour.",
        "settings": {
            "palette": {
                "source": "custom",
                "name": "Egregore Clay Bible (Table 10)",
                "colors": [
                    "#14100E",  # Deep Kiln Shadow / Contour
                    "#2B211D",  # Dark Burnt Earth
                    "#4A3B5C",  # Night Purple (Gulec Hill / Gulhin & Parasite)
                    "#6C7B8C",  # Mist Blue (Vakarhane / Sekonsa Clock Metal)
                    "#7A8C5A",  # Moss Green (Oren Pass / Kahtan Ropes)
                    "#8E6D4F",  # Dry Clay Shadow
                    "#A35C3B",  # Red Earth (Kursunhane / Mammonite / Alarm)
                    "#C9A37B",  # Raw Clay (Base Ground / Plasterer / Neutral Bodies)
                    "#E8B23A",  # Kiln Yellow (Eye Glow / Ritual Light / Gold)
                    "#EDE6D6",  # Plaster White (Plaster Square / UI / Chronicle)
                ],
                "distance": "oklab",
            },
            "dither": {"method": "bayer4", "strength": 0.22},
            "cleanup": {"orphans": False, "smooth": False},
            "outline": {"mode": "outer", "color": "#14100E", "corners": False},
            "alpha": {"threshold": 0.25},
        },
    },
    "farming-25d": {
        "label": "2.5D FARMING — 32-Color Phosphor CRT & Bayer Dither (GDD v1.0)",
        "description": "GDD Section 8.4: 32-Color Reference Palette (Soil, Foliage, Mine Ores, Phosphor Green CRT & Orange Warning) + Ordered Bayer Dither.",
        "settings": {
            "palette": {
                "source": "custom",
                "name": "2.5D Farming 32-Color Reference Palette (Section 8.4)",
                "colors": [
                    # CRT Void & Deep Shadows (4)
                    "#070B08", "#0D1610", "#142219", "#1C2F23",
                    # 3 Warm Soil & Wood Bands (6)
                    "#2E1D14", "#4A2F21", "#6B442E", "#8C5B3E", "#B37A54", "#D9A377",
                    # 5 Foliage & Crop Green Bands (7)
                    "#1A381F", "#28542E", "#3B753F", "#54994E", "#75BD64", "#9EE07E", "#C8F5A6",
                    # 4 Mine Stone & Metal Ore Bands: Stone, Copper, Iron, Silver, Gold (8)
                    "#2B3036", "#454D57", "#687382", "#94A1B2", "#C7D2E0",
                    "#C86432", "#E8994A", "#F5D042",
                    # 3 Phosphor CRT Green & K4 Crystal Accents (4)
                    "#19824C", "#28C76F", "#52FF9A", "#B8FFD6",
                    # Crop & UI Warning Accents: Radish/Tomato Red, Pumpkin/Warning Orange, Water Blue (3)
                    "#D9383A", "#FF8C24", "#3898FF"
                ],
                "distance": "oklab",
            },
            "dither": {"method": "bayer4", "strength": 0.24},
            "cleanup": {"orphans": False, "smooth": False},
            "outline": {"mode": "outer", "color": "#070B08", "corners": False},
            "alpha": {"threshold": 0.20},
        },
    },
}


NODE_RUNNER_SCRIPT = r"""
import fs from 'node:fs';
import {
  makePlan,
  runCPU,
  makeResult,
  encodePNG,
  encodeGIF,
  packSpriteSheet,
  buildTileset,
  PALETTES,
  PRESETS,
  DITHER_METHODS
} from '__ESM_PATH__';

const payloadPath = process.argv[2];
const req = JSON.parse(fs.readFileSync(payloadPath, 'utf8'));

if (req.mode === 'list') {
  console.log(JSON.stringify({
    palettes: PALETTES.map(p => ({ id: p.id, name: p.name, count: p.colors.length, author: p.author })),
    presets: PRESETS.map(p => ({ id: p.id, name: p.name, description: p.description })),
    dithers: DITHER_METHODS
  }));
  process.exit(0);
}

const rawBytes = fs.readFileSync(req.rawPath);
const frames = [];
const frameByteLen = req.frameWidth * req.frameHeight * 4;
for (let i = 0; i < req.frameCount; i++) {
  const slice = rawBytes.subarray(i * frameByteLen, (i + 1) * frameByteLen);
  frames.push({
    width: req.frameWidth,
    height: req.frameHeight,
    data: new Uint8ClampedArray(slice)
  });
}

const processedFrames = [];
for (let i = 0; i < frames.length; i++) {
  const src = frames[i];
  const plan = makePlan(req.settings, src);
  const outData = runCPU(plan, src);
  const res = makeResult(plan, outData, 'cpu', 0);
  processedFrames.push({
    name: `frame_${i}`,
    width: res.width,
    height: res.height,
    data: res.data,
    delay: req.delay || 100,
    usedColors: res.usedColors()
  });
}

if (req.mode === 'tileset') {
  const first = processedFrames[0];
  const ts = buildTileset(first, {
    tileWidth: req.tileSize || 16,
    tileHeight: req.tileSize || 16,
    columns: req.columns || 8,
    flips: true
  });
  const pngBytes = await encodePNG(ts.image, { scale: req.scale || 1 });
  fs.writeFileSync(req.outPng, pngBytes);
  fs.writeFileSync(req.outJson, JSON.stringify({
    uniqueTileCount: ts.count,
    tilesetWidth: ts.image.width,
    tilesetHeight: ts.image.height,
    map: ts.map
  }, null, 2));
  console.log(JSON.stringify({
    ok: true,
    uniqueTiles: ts.count,
    outPng: req.outPng,
    outJson: req.outJson
  }));
  process.exit(0);
}

// Single frame or multi-frame strip/sheet
if (processedFrames.length === 1) {
  const f = processedFrames[0];
  const png1x = await encodePNG(f, { scale: 1, indexed: req.indexed || false });
  fs.writeFileSync(req.out1xPng, png1x);
  if (req.outScaledPng && (req.scale || 1) > 1) {
    const pngScaled = await encodePNG(f, { scale: req.scale, grid: req.grid || false });
    fs.writeFileSync(req.outScaledPng, pngScaled);
  }
  console.log(JSON.stringify({
    ok: true,
    width: f.width,
    height: f.height,
    usedColorCount: f.usedColors.length,
    out1xPng: req.out1xPng,
    outScaledPng: req.outScaledPng || null
  }));
} else {
  // Pack horizontal GameMaker strip (_stripN.png) + JSON atlas + animated GIF
  const packed = packSpriteSheet(processedFrames, {
    columns: processedFrames.length,
    padding: 0,
    name: req.baseName || 'strip'
  });
  const stripPng = await encodePNG(packed.image, { scale: 1 });
  fs.writeFileSync(req.out1xPng, stripPng);
  if (req.outAtlasJson) {
    fs.writeFileSync(req.outAtlasJson, JSON.stringify(packed.atlas, null, 2));
  }
  if (req.outGif) {
    const gifBytes = encodeGIF(processedFrames, { scale: req.scale || 3, delay: req.delay || 100 });
    fs.writeFileSync(req.outGif, gifBytes);
  }
  console.log(JSON.stringify({
    ok: true,
    frames: processedFrames.length,
    frameWidth: processedFrames[0].width,
    frameHeight: processedFrames[0].height,
    stripWidth: packed.image.width,
    stripHeight: packed.image.height,
    out1xPng: req.out1xPng,
    outGif: req.outGif || null,
    outAtlasJson: req.outAtlasJson || null
  }));
}
"""


def _run_node_engine(payload: dict) -> dict:
    if not ESM_ENTRY.exists():
        raise FileNotFoundError(
            f"Image-to-Pixel bundle not found at {ESM_ENTRY}. "
            f"Run `npm install && npm run build` inside {LIB_DIR}."
        )
    esm_url = ESM_ENTRY.resolve().as_uri()
    script_code = NODE_RUNNER_SCRIPT.replace("__ESM_PATH__", esm_url)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        script_file = tmp / "runner.mjs"
        payload_file = tmp / "payload.json"
        script_file.write_text(script_code, encoding="utf-8")
        payload_file.write_text(json.dumps(payload), encoding="utf-8")

        proc = subprocess.run(
            ["node", str(script_file), str(payload_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Node runner failed:\n{proc.stderr}\n{proc.stdout}")
        return json.loads(proc.stdout.strip().splitlines()[-1])


def _detect_strip_frames(img_path: Path, explicit_frames: int) -> int:
    if explicit_frames > 1:
        return explicit_frames
    m = re.search(r"_strip(\d+)$", img_path.stem, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)))
    return 1


def build_settings(
    profile_id: str,
    target_width: int,
    palette_id: str | None = None,
    dither_method: str | None = None,
    dither_strength: float | None = None,
    outline_mode: str | None = None,
    brightness: int = 0,
    contrast: int = 0,
    saturation: int = 0,
) -> dict:
    prof = GAME_STYLE_PROFILES.get(profile_id, GAME_STYLE_PROFILES["jrpg-16bit"])
    cfg = json.loads(json.dumps(prof["settings"]))
    cfg["size"] = {
        "mode": "width",
        "width": target_width,
        "height": 0,
        "block": 4,
        "resample": "box",
    }
    cfg["adjust"] = {
        "brightness": brightness,
        "contrast": contrast,
        "saturation": saturation,
        "hue": 0,
        "gamma": 1.0,
    }
    if palette_id:
        if palette_id == "extract":
            cfg["palette"] = {"source": "extract", "count": 16, "distance": "oklab"}
        elif palette_id == "none":
            cfg["palette"] = {"source": "none"}
        else:
            cfg["palette"] = {"source": "builtin", "id": palette_id, "distance": "oklab"}
    if dither_method:
        cfg["dither"]["method"] = dither_method
    if dither_strength is not None:
        cfg["dither"]["strength"] = float(dither_strength)
    if outline_mode:
        cfg["outline"]["mode"] = outline_mode
    return cfg


def cmd_list():
    info = _run_node_engine({"mode": "list"})
    print("=== CURATED GAME ART-DIRECTION PROFILES (--profile) ===")
    for pid, pdata in GAME_STYLE_PROFILES.items():
        print(f"  * {pid:<16} : {pdata['label']} — {pdata['description']}")
    print("\n=== BUILT-IN LOSPEC PALETTES (--palette) ===")
    for p in info["palettes"]:
        print(f"  * {p['id']:<26} ({p['count']:>2} colors) by {p['author']}")
    print("\n=== 16 DITHERING METHODS (--dither) ===")
    for d in info["dithers"]:
        print(f"  * {d['id']:<18} [{d['kind']}] — {d['label']}")


def cmd_convert(args):
    in_path = Path(args.input).resolve()
    if not in_path.exists():
        print(f"[ERROR] Input file not found: {in_path}")
        sys.exit(1)

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    im = Image.open(in_path).convert("RGBA")
    n_frames = _detect_strip_frames(in_path, args.frames)
    frame_w = im.width // n_frames
    frame_h = im.height

    # Guard against diffusion dither boil on multi-frame animations
    dither_override = args.dither
    if n_frames > 1 and not dither_override:
        prof_dither = GAME_STYLE_PROFILES[args.profile]["settings"]["dither"]["method"]
        if prof_dither in ("floyd-steinberg", "atkinson", "sierra", "sierra-lite", "burkes", "jarvis", "stucki"):
            print(f"[ART-DIRECTION GUARD] Multi-frame strip ({n_frames} frames) detected: switching diffusion dither '{prof_dither}' -> 'bayer2' to prevent frame-to-frame pixel boiling!")
            dither_override = "bayer2"

    settings = build_settings(
        profile_id=args.profile,
        target_width=args.width,
        palette_id=args.palette,
        dither_method=dither_override,
        dither_strength=args.strength,
        outline_mode=args.outline,
        brightness=args.brightness,
        contrast=args.contrast,
        saturation=args.saturation,
    )

    stem_clean = re.sub(r"_strip\d+$", "", in_path.stem, flags=re.IGNORECASE)
    tag = f"{stem_clean}_{args.profile}_{args.width}w"

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "frames.raw"
        with open(raw_path, "wb") as f:
            for i in range(n_frames):
                crop = im.crop((i * frame_w, 0, (i + 1) * frame_w, frame_h))
                f.write(crop.tobytes())

        if n_frames == 1:
            out_1x = out_dir / f"{tag}_1x.png"
            out_scaled = out_dir / f"{tag}_{args.scale}x.png" if args.scale > 1 else None
            res = _run_node_engine({
                "mode": "convert",
                "rawPath": str(raw_path),
                "frameWidth": frame_w,
                "frameHeight": frame_h,
                "frameCount": 1,
                "settings": settings,
                "scale": args.scale,
                "grid": args.grid,
                "out1xPng": str(out_1x),
                "outScaledPng": str(out_scaled) if out_scaled else None,
            })
            print(f"[OK] Pixelated ({res['width']}x{res['height']}px, {res['usedColorCount']} colors):")
            print(f"  -> 1x Native Sprite : {res['out1xPng']}")
            if res.get("outScaledPng"):
                print(f"  -> {args.scale}x Crispy Preview: {res['outScaledPng']}")

            if args.normal_map:
                nmap_script = WORKSPACE_ROOT / "tools" / "normal_map_gen.py"
                subprocess.run([sys.executable, str(nmap_script), str(out_1x), "--preview"], check=True)
        else:
            out_strip = out_dir / f"{tag}_strip{n_frames}.png"
            out_gif = out_dir / f"{tag}_anim.gif"
            out_atlas = out_dir / f"{tag}_atlas.json"
            res = _run_node_engine({
                "mode": "convert",
                "rawPath": str(raw_path),
                "frameWidth": frame_w,
                "frameHeight": frame_h,
                "frameCount": n_frames,
                "settings": settings,
                "scale": args.scale,
                "baseName": tag,
                "out1xPng": str(out_strip),
                "outGif": str(out_gif),
                "outAtlasJson": str(out_atlas),
            })
            print(f"[OK] Pixelated {n_frames}-Frame Animation Strip ({res['frameWidth']}x{res['frameHeight']}px per frame):")
            print(f"  -> GameMaker Strip : {res['out1xPng']}")
            print(f"  -> Animated GIF    : {res['outGif']}")
            print(f"  -> JSON Atlas      : {res['outAtlasJson']}")


def cmd_compare(args):
    in_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    im = Image.open(in_path).convert("RGBA")
    profiles = list(GAME_STYLE_PROFILES.keys())
    rendered_cards = []

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "src.raw"
        raw_path.write_bytes(im.tobytes())

        for pid in profiles:
            settings = build_settings(pid, args.width)
            out_scaled = Path(tmpdir) / f"{pid}.png"
            out_1x = Path(tmpdir) / f"{pid}_1x.png"
            res = _run_node_engine({
                "mode": "convert",
                "rawPath": str(raw_path),
                "frameWidth": im.width,
                "frameHeight": im.height,
                "frameCount": 1,
                "settings": settings,
                "scale": args.scale,
                "out1xPng": str(out_1x),
                "outScaledPng": str(out_scaled),
            })
            px_im = Image.open(out_scaled).convert("RGBA")
            rendered_cards.append((pid, GAME_STYLE_PROFILES[pid]["label"], px_im, res["usedColorCount"]))

    cols = 3
    rows = (len(rendered_cards) + cols - 1) // cols
    cw, ch = rendered_cards[0][2].width, rendered_cards[0][2].height
    pad = 20
    header_h = 34
    canvas_w = cols * (cw + pad) + pad
    canvas_h = rows * (ch + header_h + pad) + pad

    sheet = Image.new("RGBA", (canvas_w, canvas_h), (18, 22, 32, 255))
    draw = ImageDraw.Draw(sheet)

    for idx, (pid, label, card_im, n_cols) in enumerate(rendered_cards):
        r = idx // cols
        c = idx % cols
        x = pad + c * (cw + pad)
        y = pad + r * (ch + header_h + pad)
        draw.rectangle([x - 2, y - 2, x + cw + 2, y + ch + header_h + 2], fill=(28, 34, 48, 255), outline=(58, 72, 102, 255))
        draw.text((x + 6, y + 4), f"{pid} ({n_cols}c)", fill=(110, 200, 255, 255))
        draw.text((x + 6, y + 18), label[:32], fill=(180, 192, 215, 255))
        sheet.alpha_composite(card_im, (x, y + header_h))

    out_matrix = out_dir / f"{in_path.stem}_style_comparison_matrix.png"
    sheet.save(out_matrix)
    print(f"[OK] Saved 6-Profile Art-Direction Comparison Matrix -> {out_matrix}")


def cmd_tileset(args):
    in_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    im = Image.open(in_path).convert("RGBA")
    settings = build_settings(args.profile, args.width, palette_id=args.palette, dither_method=args.dither)
    # No outer outline on tilesets!
    settings["outline"]["mode"] = "none"

    out_png = out_dir / f"{in_path.stem}_{args.profile}_tileset_{args.tile_size}x{args.tile_size}.png"
    out_json = out_dir / f"{in_path.stem}_{args.profile}_tilemap.json"

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = Path(tmpdir) / "src.raw"
        raw_path.write_bytes(im.tobytes())
        res = _run_node_engine({
            "mode": "tileset",
            "rawPath": str(raw_path),
            "frameWidth": im.width,
            "frameHeight": im.height,
            "frameCount": 1,
            "settings": settings,
            "tileSize": args.tile_size,
            "columns": args.columns,
            "scale": args.scale,
            "outPng": str(out_png),
            "outJson": str(out_json),
        })
    print(f"[OK] Built Deduplicated Tileset ({res['uniqueTiles']} unique {args.tile_size}x{args.tile_size} tiles):")
    print(f"  -> Tileset PNG  : {res['outPng']}")
    print(f"  -> Tilemap JSON : {res['outJson']}")


def cmd_serve_editor(args):
    serve_script = LIB_DIR / "scripts" / "serve.mjs"
    print(f"[OK] Starting Local Offline Image-to-Pixel 3.2.0 WebGL2 Studio on http://localhost:{args.port}/Image-to-Pixel/editor/")
    env = os.environ.copy()
    env["PORT"] = str(args.port)
    subprocess.run(["node", str(serve_script)], cwd=str(LIB_DIR), env=env)


def main():
    parser = argparse.ArgumentParser(description="Image-to-Pixel 3.2.0 Game Art-Direction CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List game style profiles, 24 built-in palettes, and 16 dithering methods")

    p_conv = sub.add_parser("convert", help="Convert an image, 3D render, or _stripN.png animation into pixel art")
    p_conv.add_argument("input", help="Input image path (.png, .jpg, .webp)")
    p_conv.add_argument("--profile", choices=list(GAME_STYLE_PROFILES.keys()), default="jrpg-16bit", help="Game Art-Direction Style Profile")
    p_conv.add_argument("--width", type=int, default=64, help="Pixel width per sprite/frame (default: 64)")
    p_conv.add_argument("--frames", type=int, default=1, help="Number of horizontal frames (auto-detected if named _stripN.png)")
    p_conv.add_argument("--palette", default=None, help="Override built-in palette id (e.g. pico-8, apollo, endesga-32, extract)")
    p_conv.add_argument("--dither", default=None, help="Override dither method (none, bayer2, bayer4, bluenoise, atkinson, floyd-steinberg)")
    p_conv.add_argument("--strength", type=float, default=None, help="Override dither strength (0.0 - 1.0)")
    p_conv.add_argument("--outline", choices=["none", "outer", "inner"], default=None, help="Override pixel outline mode")
    p_conv.add_argument("--brightness", type=int, default=0)
    p_conv.add_argument("--contrast", type=int, default=0)
    p_conv.add_argument("--saturation", type=int, default=0)
    p_conv.add_argument("--scale", type=int, default=4, help="Upscale factor for preview/GIF (default: 4)")
    p_conv.add_argument("--grid", action="store_true", help="Draw pixel grid on upscaled preview")
    p_conv.add_argument("--normal-map", action="store_true", help="Also generate Moonfell Faceted Normal Map (_n.png) + Lighting GIF")
    p_conv.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    p_cmp = sub.add_parser("compare", help="Render a 6-Profile Art-Direction Comparison Matrix PNG for an asset")
    p_cmp.add_argument("input", help="Input image path")
    p_cmp.add_argument("--width", type=int, default=64, help="Pixel width per card (default: 64)")
    p_cmp.add_argument("--scale", type=int, default=3, help="Display scale per card (default: 3)")
    p_cmp.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    p_ts = sub.add_parser("tileset", help="Convert an image into a deduplicated pixel tileset PNG + tilemap JSON")
    p_ts.add_argument("input", help="Input image path")
    p_ts.add_argument("--profile", choices=list(GAME_STYLE_PROFILES.keys()), default="dark-fantasy")
    p_ts.add_argument("--width", type=int, default=128, help="Target pixelated scene width before slicing")
    p_ts.add_argument("--tile-size", type=int, default=16, help="Tile width & height in pixels (default: 16)")
    p_ts.add_argument("--columns", type=int, default=8, help="Columns in output tileset PNG")
    p_ts.add_argument("--palette", default=None)
    p_ts.add_argument("--dither", default=None)
    p_ts.add_argument("--scale", type=int, default=1)
    p_ts.add_argument("--out-dir", default=str(DEFAULT_EXPORT_DIR))

    p_srv = sub.add_parser("serve-editor", help="Launch the 100%% local offline Image-to-Pixel 3.2.0 WebGL2 Editor")
    p_srv.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()
    if args.cmd == "list":
        cmd_list()
    elif args.cmd == "convert":
        cmd_convert(args)
    elif args.cmd == "compare":
        cmd_compare(args)
    elif args.cmd == "tileset":
        cmd_tileset(args)
    elif args.cmd == "serve-editor":
        cmd_serve_editor(args)


if __name__ == "__main__":
    main()
