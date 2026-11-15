#!/usr/bin/env python3
"""
Pixel-Perfect Rendering Tool: Integer Scale Calculator, GCD Pixel-Size Detector (Mixel Finder),
Scene/Project Rule Auditor, Asset Folder Scanner, Verifier & Engine Config Exporter.

Usage:
    python tools/pixel_perfect.py verify --json
    python tools/pixel_perfect.py scale-check --base 384x216 --json
    python tools/pixel_perfect.py inspect-assets path/to/sprites --json
    python tools/pixel_perfect.py export-code --engine godot4 --out-dir exports/pixel_perfect
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")


def integer_scale(window_w: int, window_h: int, base_w: int, base_h: int) -> tuple[int, int, int]:
    """Return (scale, bar_x, bar_y) for exact whole-number scaling with centered black bars."""
    if base_w <= 0 or base_h <= 0:
        raise ValueError(f"Base resolution must be positive, got {base_w}x{base_h}")
    scale = max(1, min(window_w // base_w, window_h // base_h))
    bar_x = (window_w - base_w * scale) // 2
    bar_y = (window_h - base_h * scale) // 2
    return scale, bar_x, bar_y


def pixel_size(image: Image.Image) -> int:
    """Largest integer pixel block size dividing every horizontal and vertical color run (1 = native/irregular, 2 = 2x nearest)."""
    rgba = image.convert("RGBA")
    w, h = rgba.size
    if w == 0 or h == 0:
        return 0
    arr = np.asarray(rgba, dtype=np.uint8)
    # Pack RGBA into single uint32 per pixel for fast exact run detection
    packed = (
        arr[..., 0].astype(np.uint32)
        | (arr[..., 1].astype(np.uint32) << 8)
        | (arr[..., 2].astype(np.uint32) << 16)
        | (arr[..., 3].astype(np.uint32) << 24)
    )
    size = 0
    for grid in (packed, packed.T):
        rows, cols = grid.shape
        for r in range(rows):
            row = grid[r]
            changes = np.nonzero(row[1:] != row[:-1])[0] + 1
            starts = np.concatenate(([0], changes))
            ends = np.concatenate((changes, [cols]))
            runs = ends - starts
            for run in runs:
                size = math.gcd(size, int(run))
                if size == 1:
                    return 1
    return size


def render_integer_viewport(base_img: Image.Image, window_w: int, window_h: int) -> tuple[Image.Image, tuple[int, int, int]]:
    """Composite a base-resolution RGBA/RGB canvas into a window with Nearest integer scaling and black bars."""
    base_w, base_h = base_img.size
    scale, bar_x, bar_y = integer_scale(window_w, window_h, base_w, base_h)
    scaled = base_img.convert("RGB").resize((base_w * scale, base_h * scale), Image.NEAREST)
    out = Image.new("RGB", (window_w, window_h), (0, 0, 0))
    out.paste(scaled, (bar_x, bar_y))
    return out, (scale, bar_x, bar_y)


def audit_scene_dict(project: dict[str, Any], root: dict[str, Any]) -> list[str]:
    """Run the 8-rule project + scene graph pixel-perfect audit and return problem descriptions."""
    out: list[str] = []
    if project.get("default_texture_filter") != "Nearest":
        out.append("Project: Default Texture Filter is not Nearest")
    if project.get("stretch_mode") != "viewport":
        out.append("Project: Stretch Mode is not viewport")
    if project.get("stretch_scale_mode") != "integer":
        out.append("Project: Stretch Scale Mode is not integer")
    if not project.get("snap_2d_transforms_to_pixel", False):
        out.append("Project: Snap 2D Transforms to Pixel is off")
    if not project.get("snap_2d_vertices_to_pixel", False):
        out.append("Project: Snap 2D Vertices to Pixel is off")

    def walk(node: dict[str, Any], parent_sx: float, parent_sy: float, parent_rot: float) -> None:
        name = node.get("name", "<unnamed>")
        ntype = node.get("type", "Node")
        sx = float(node.get("scale", [1.0, 1.0])[0]) * parent_sx
        sy = float(node.get("scale", [1.0, 1.0])[1]) * parent_sy
        rot = float(node.get("rotation_deg", 0.0)) + parent_rot

        filt = node.get("texture_filter", "Inherit")
        if node.get("is_canvas_item", ntype in {"Sprite2D", "AnimatedSprite2D", "TileMapLayer", "Label", "CanvasItem"}):
            if filt not in ("Inherit", "Nearest"):
                out.append(f"{name}: its own texture filter is not Nearest ({filt})")

        if ntype in {"Sprite2D", "AnimatedSprite2D", "TileMapLayer"}:
            ax, ay = abs(sx), abs(sy)
            if not (math.isclose(ax, 1.0, abs_tol=1e-4) and math.isclose(ay, 1.0, abs_tol=1e-4)):
                out.append(f"{name}: drawn at total scale ({ax:.3g}, {ay:.3g}), so its pixels are not the size of the others")
            turn = abs(rot) % 90.0
            if min(turn, 90.0 - turn) > 0.01:
                out.append(f"{name}: rotated {round(rot)} degrees, pixel art only survives 90 degree steps")

        if ntype == "Camera2D":
            zx, zy = node.get("zoom", [1.0, 1.0])
            if not (math.isclose(zx, round(zx), abs_tol=1e-4) and math.isclose(zy, round(zy), abs_tol=1e-4)):
                out.append(f"{name}: zoom ({zx}, {zy}) is not a whole number")

        if ntype == "Label":
            if node.get("font_antialiasing", "Gray") != "None":
                out.append(f"{name}: its font is antialiased")

        for ch in node.get("children", []):
            walk(ch, sx, sy, rot)

    walk(root, 1.0, 1.0, 0.0)
    return out


def inspect_assets_path(target: Path) -> dict[str, Any]:
    """Measure pixel_size on PNG assets and flag mixels or large irregular AI grids."""
    paths = [target] if target.is_file() else sorted(target.rglob("*.png"))
    report: list[dict[str, Any]] = []
    mixels = []
    for p in paths:
        im = Image.open(p)
        ps = pixel_size(im)
        entry = {"file": str(p), "size": [im.width, im.height], "pixel_size": ps, "mixel_flag": ps > 1}
        report.append(entry)
        if ps > 1:
            mixels.append(str(p))
    return {"count": len(report), "mixel_files": mixels, "assets": report}


def run_verify() -> dict[str, Any]:
    """Run all 5 verification tests for integer_scale, pixel_size, viewport render, and scene audit."""
    checks: dict[str, dict[str, Any]] = {}

    # 1. Exact integer_scale results
    s1 = integer_scale(1920, 1080, 384, 216)
    s2 = integer_scale(2560, 1440, 384, 216)
    s3 = integer_scale(1366, 768, 384, 216)
    s4 = integer_scale(300, 200, 384, 216)
    s320 = [
        integer_scale(1920, 1080, 320, 180),
        integer_scale(2560, 1440, 320, 180),
        integer_scale(3840, 2160, 320, 180),
    ]
    checks["1_integer_scale_resolutions"] = {
        "1080p_384": list(s1),
        "1440p_384": list(s2),
        "768p_384": list(s3),
        "small_300x200": list(s4),
        "320x180_at_1080_1440_4k": [list(x) for x in s320],
        "ok": (
            s1 == (5, 0, 0)
            and s2 == (6, 128, 72)
            and s3 == (3, 107, 60)
            and s4[0] == 1
            and s320 == [(6, 0, 0), (8, 0, 0), (12, 0, 0)]
        ),
    }

    # 2. pixel_size: 1 for native sprite, 2 for 2x nearest, 1 for 1.5x nearest
    rng = np.random.default_rng(123)
    native_arr = rng.integers(0, 255, size=(16, 16, 4), dtype=np.uint8)
    native_arr[..., 3] = 255
    im_native = Image.fromarray(native_arr, "RGBA")
    im_2x = im_native.resize((32, 32), Image.NEAREST)
    im_15x = im_native.resize((24, 24), Image.NEAREST)
    ps_nat, ps_2x, ps_15x = pixel_size(im_native), pixel_size(im_2x), pixel_size(im_15x)
    checks["2_pixel_size_gcd"] = {
        "native": ps_nat,
        "scaled_2x": ps_2x,
        "scaled_1_5x": ps_15x,
        "ok": (ps_nat == 1 and ps_2x == 2 and ps_15x == 1),
    }

    # 3. Viewport render on non-multiple 1366x768 window -> pure black bars + exact 3x3 integer game pixels + no blended edge colors
    base = Image.new("RGB", (384, 216), (20, 40, 80))
    base_px = base.load()
    palette_colors = {(20, 40, 80), (220, 60, 40), (245, 220, 90)}
    for yy in range(40, 70):
        for xx in range(50, 80):
            base_px[xx, yy] = (220, 60, 40) if (xx + yy) % 2 == 0 else (245, 220, 90)
    win_img, (scale, bx, by) = render_integer_viewport(base, 1366, 768)
    win_arr = np.asarray(win_img)
    left_bar_black = bool(np.all(win_arr[:, :bx] == 0))
    top_bar_black = bool(np.all(win_arr[:by, :] == 0))
    inner = win_arr[by : by + 216 * scale, bx : bx + 384 * scale]
    # Verify every game pixel expands to a uniform 3x3 block and introduces zero blended colors
    blocks_uniform = bool(
        np.all(inner.reshape(216, scale, 384, scale, 3) == inner[::scale, ::scale][:, None, :, None, :])
    )
    unique_inner = {tuple(int(c) for c in row) for row in np.unique(inner.reshape(-1, 3), axis=0)}
    no_blended_colors = unique_inner <= palette_colors
    checks["3_viewport_render_bars_and_crisp_blocks"] = {
        "scale_bars": [scale, bx, by],
        "left_bar_black": left_bar_black,
        "top_bar_black": top_bar_black,
        "uniform_3x3_blocks": blocks_uniform,
        "no_blended_edge_colors": no_blended_colors,
        "ok": (left_bar_black and top_bar_black and blocks_uniform and no_blended_colors),
    }

    # 4. Audit test scene: 1 clean + flip + 270deg + cam zoom 2 + clean label -> PASS; exact 6 offenders -> FAIL
    good_proj = {
        "default_texture_filter": "Nearest",
        "stretch_mode": "viewport",
        "stretch_scale_mode": "integer",
        "snap_2d_transforms_to_pixel": True,
        "snap_2d_vertices_to_pixel": True,
    }
    scene = {
        "name": "Root",
        "type": "Node2D",
        "children": [
            {"name": "CleanSprite", "type": "Sprite2D", "scale": [1, 1], "rotation_deg": 0, "texture_filter": "Inherit"},
            {"name": "FlippedSprite", "type": "Sprite2D", "scale": [-1, 1], "rotation_deg": 0, "texture_filter": "Nearest"},
            {"name": "Rot270Sprite", "type": "Sprite2D", "scale": [1, 1], "rotation_deg": 270, "texture_filter": "Inherit"},
            {"name": "CleanCam", "type": "Camera2D", "zoom": [2, 2]},
            {"name": "CleanLabel", "type": "Label", "font_antialiasing": "None"},
            # Exact 6 offenders:
            {"name": "Off1_Scale2", "type": "Sprite2D", "scale": [2, 2]},
            {
                "name": "Parent15",
                "type": "Node2D",
                "scale": [1.5, 1.5],
                "children": [{"name": "Off2_UnderScaledParent", "type": "Sprite2D", "scale": [1, 1]}],
            },
            {"name": "Off3_Rot30", "type": "Sprite2D", "rotation_deg": 30},
            {"name": "Off4_LinearFilter", "type": "Sprite2D", "texture_filter": "Linear"},
            {"name": "Off5_CamZoom15", "type": "Camera2D", "zoom": [1.5, 1.5]},
            {"name": "Off6_AntialiasedLabel", "type": "Label", "font_antialiasing": "Gray"},
        ],
    }
    problems = audit_scene_dict(good_proj, scene)
    expected_prefixes = (
        "Off1_Scale2:",
        "Off2_UnderScaledParent:",
        "Off3_Rot30:",
        "Off4_LinearFilter:",
        "Off5_CamZoom15:",
        "Off6_AntialiasedLabel:",
    )
    matched_exact = len(problems) == 6 and all(any(p.startswith(pfx) for p in problems) for pfx in expected_prefixes)
    checks["4_scene_audit_exact_6_offenders"] = {
        "problem_count": len(problems),
        "problems": problems,
        "ok": matched_exact,
    }

    # 5. Default project catches all 5 project-level problems
    default_proj = {
        "default_texture_filter": "Linear",
        "stretch_mode": "disabled",
        "stretch_scale_mode": "fractional",
        "snap_2d_transforms_to_pixel": False,
        "snap_2d_vertices_to_pixel": False,
    }
    proj_problems = audit_scene_dict(default_proj, {"name": "Root", "type": "Node2D", "children": []})
    checks["5_default_project_catches_all_5_settings"] = {
        "problem_count": len(proj_problems),
        "problems": proj_problems,
        "ok": (len(proj_problems) == 5),
    }

    all_passed = all(v["ok"] for v in checks.values())
    return {"all_passed": all_passed, "passed": sum(1 for v in checks.values() if v["ok"]), "total": len(checks), "checks": checks}


GODOT_SETTINGS_SNIPPET = """# Add to project.godot (Godot 4.2+) for pixel-perfect viewport integer scaling (384x216 or 320x180)
[display]

window/size/viewport_width=384
window/size/viewport_height=216
window/size/window_width_override=1920
window/size/window_height_override=1080
window/stretch/mode="viewport"
window/stretch/scale_mode="integer"

[rendering]

textures/canvas_textures/default_texture_filter=0
2d/snap/snap_2d_transforms_to_pixel=true
2d/snap/snap_2d_vertices_to_pixel=true
"""

GODOT_AUDIT_GD = """# PixelAudit.gd — Walks a running Godot 4 scene and reports any pixel-perfect violations
# Usage: for line in PixelAudit.audit(get_tree().root): print(line)
class_name PixelAudit
extends RefCounted


static func audit(root: Node) -> PackedStringArray:
\tvar out := PackedStringArray()
\tvar window := root.get_window()
\tvar viewport := root.get_viewport()
\tif viewport.canvas_item_default_texture_filter != Viewport.DEFAULT_CANVAS_ITEM_TEXTURE_FILTER_NEAREST:
\t\tout.append("Project: Default Texture Filter is not Nearest")
\tif window.content_scale_mode != Window.CONTENT_SCALE_MODE_VIEWPORT:
\t\tout.append("Project: Stretch Mode is not viewport")
\tif window.content_scale_stretch != Window.CONTENT_SCALE_STRETCH_INTEGER:
\t\tout.append("Project: Stretch Scale Mode is not integer")
\tif not viewport.snap_2d_transforms_to_pixel:
\t\tout.append("Project: Snap 2D Transforms to Pixel is off")
\tif not viewport.snap_2d_vertices_to_pixel:
\t\tout.append("Project: Snap 2D Vertices to Pixel is off")
\t_walk(root, out)
\treturn out


static func _walk(node: Node, out: PackedStringArray) -> void:
\tif node is CanvasItem and not node.texture_filter in [CanvasItem.TEXTURE_FILTER_PARENT_NODE, CanvasItem.TEXTURE_FILTER_NEAREST]:
\t\tout.append("%s: its own texture filter is not Nearest" % node.get_path())
\tif node is Sprite2D or node is AnimatedSprite2D or node is TileMapLayer:
\t\tvar size: Vector2 = node.global_scale.abs()
\t\tif not size.is_equal_approx(Vector2.ONE):
\t\t\tout.append("%s: drawn at scale %s, so its pixels are not the size of the others" % [node.get_path(), size])
\t\tvar turn := fmod(absf(node.global_rotation_degrees), 90.0)
\t\tif minf(turn, 90.0 - turn) > 0.01:
\t\t\tout.append("%s: rotated %d degrees, pixel art only survives 90 degree steps" % [node.get_path(), roundi(node.global_rotation_degrees)])
\tif node is Camera2D and not node.zoom.is_equal_approx(node.zoom.round()):
\t\tout.append("%s: zoom %s is not a whole number" % [node.get_path(), node.zoom])
\tif node is Label:
\t\tvar font: Font = node.get_theme_font("font")
\t\tif not font is FontFile or font.antialiasing != TextServer.FONT_ANTIALIASING_NONE:
\t\t\tout.append("%s: its font is antialiased" % node.get_path())
\tfor child in node.get_children():
\t\t_walk(child, out)
"""

UNITY_AUDIT_CS = """// PixelPerfectAudit.cs — Runtime / Editor check for Unity 2D Pixel Perfect Camera + Quality AA + SpriteRenderer rules
using System.Collections.Generic;
using UnityEngine;

public static class PixelPerfectAudit
{
    public static List<string> AuditScene()
    {
        var problems = new List<string>();
        if (QualitySettings.antiAliasing != 0)
            problems.Add($"QualitySettings.antiAliasing is {QualitySettings.antiAliasing} (must be 0)");

        foreach (var sr in Object.FindObjectsByType<SpriteRenderer>(FindObjectsSortMode.None))
        {
            Vector3 s = sr.transform.lossyScale;
            if (!Mathf.Approximately(Mathf.Abs(s.x), 1f) || !Mathf.Approximately(Mathf.Abs(s.y), 1f))
                problems.Add($"{sr.name}: total scale ({s.x:F2}, {s.y:F2}) != 1 (mixels)");
            float turn = Mathf.Abs(sr.transform.eulerAngles.z) % 90f;
            if (Mathf.Min(turn, 90f - turn) > 0.01f)
                problems.Add($"{sr.name}: rotated {sr.transform.eulerAngles.z:F1} deg (only 90 deg steps allowed)");
            if (sr.sprite != null && sr.sprite.texture != null && sr.sprite.texture.filterMode != FilterMode.Point)
                problems.Add($"{sr.name}: texture filterMode is {sr.sprite.texture.filterMode} (must be Point)");
        }
        return problems;
    }
}
"""

WEB_CANVAS_TS = """// pixelViewport.ts — Integer scale offscreen target + crisp CSS canvas rendering
export function integerScale(windowW: number, windowH: number, baseW: number, baseH: number) {
  const scale = Math.max(1, Math.min(Math.floor(windowW / baseW), Math.floor(windowH / baseH)));
  const barX = Math.floor((windowW - baseW * scale) / 2);
  const barY = Math.floor((windowH - baseH * scale) / 2);
  return { scale, barX, barY };
}

export function blitPixelPerfect(
  displayCtx: CanvasRenderingContext2D,
  offscreen: HTMLCanvasElement,
  windowW: number,
  windowH: number
): void {
  const { scale, barX, barY } = integerScale(windowW, windowH, offscreen.width, offscreen.height);
  displayCtx.imageSmoothingEnabled = false;
  displayCtx.fillStyle = "#000000";
  displayCtx.fillRect(0, 0, windowW, windowH);
  displayCtx.drawImage(offscreen, barX, barY, offscreen.width * scale, offscreen.height * scale);
}
"""


def export_code(engine: str, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if engine == "godot4":
        p1 = out_dir / "PixelAudit.gd"
        p2 = out_dir / "project_pixel_perfect.ini"
        p1.write_text(GODOT_AUDIT_GD, encoding="utf-8")
        p2.write_text(GODOT_SETTINGS_SNIPPET, encoding="utf-8")
        written.extend([str(p1), str(p2)])
    elif engine == "unity":
        p1 = out_dir / "PixelPerfectAudit.cs"
        p1.write_text(UNITY_AUDIT_CS, encoding="utf-8")
        written.append(str(p1))
    elif engine == "typescript":
        p1 = out_dir / "pixelViewport.ts"
        p1.write_text(WEB_CANVAS_TS, encoding="utf-8")
        written.append(str(p1))
    else:
        raise ValueError(f"Unsupported engine: {engine}")
    return written


def _parse_wh(spec: str) -> tuple[int, int]:
    w, h = spec.lower().split("x")
    return int(w), int(h)


def main() -> int:
    parser = argparse.ArgumentParser(description="Pixel-Perfect Rendering Tool (integer_scale, pixel_size, scene audit, verify)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify", help="Run all 5 automated pixel-perfect checks")
    p_ver.add_argument("--json", action="store_true")

    p_sc = sub.add_parser("scale-check", help="Calculate integer scale & black bars across common displays")
    p_sc.add_argument("--base", default="384x216")
    p_sc.add_argument("--window", default=None, help="Optional extra WxH window to evaluate")
    p_sc.add_argument("--json", action="store_true")

    p_ins = sub.add_parser("inspect-assets", help="Measure GCD pixel_size across PNG sprites to catch mixels")
    p_ins.add_argument("target", type=Path)
    p_ins.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export PixelAudit.gd / Unity / Web Canvas templates")
    p_exp.add_argument("--engine", choices=["godot4", "unity", "typescript"], required=True)
    p_exp.add_argument("--out-dir", type=Path, default=Path("exports/pixel_perfect"))
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()
    if args.cmd == "verify":
        res = run_verify()
        print(json.dumps(res, indent=2) if args.json else f"Pixel Perfect verify: {res['passed']}/{res['total']} passed")
        return 0 if res["all_passed"] else 1

    if args.cmd == "scale-check":
        bw, bh = _parse_wh(args.base)
        windows = [(1920, 1080), (2560, 1440), (3840, 2160), (1366, 768)]
        if args.window:
            windows.append(_parse_wh(args.window))
        rows = {}
        for ww, wh in windows:
            sc, bx, by = integer_scale(ww, wh, bw, bh)
            rows[f"{ww}x{wh}"] = {"scale": sc, "bar_x": bx, "bar_y": by}
        print(json.dumps({"base": [bw, bh], "windows": rows}, indent=2) if args.json else str(rows))
        return 0

    if args.cmd == "inspect-assets":
        res = inspect_assets_path(args.target)
        print(json.dumps(res, indent=2) if args.json else f"Scanned {res['count']} files, mixels={len(res['mixel_files'])}")
        return 0

    if args.cmd == "export-code":
        files = export_code(args.engine, args.out_dir)
        print(json.dumps({"engine": args.engine, "files": files}, indent=2) if args.json else str(files))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
