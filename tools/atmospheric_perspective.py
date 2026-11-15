#!/usr/bin/env python3
"""
Atmospheric Perspective Tool for 2D Parallax & 2.5D Layered Scenes (atmospheric_perspective.py)
Blends background/depth layers pixel-by-pixel toward the matching vertical row color of the sky
behind them, with extra base mist for mountain ridge separation, global strength control,
edge-outline cleanup, 2D/2.5D Limbo-style demos, 6-point verification, and Godot/Unity/TS exports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCROLL_SPEED_PRESETS: List[Dict[str, Any]] = [
    {"layer": "sky", "scroll_speed": 0.03, "amount": 0.00, "mist": 0.00},
    {"layer": "far_peaks", "scroll_speed": 0.08, "amount": 0.80, "mist": 0.20},
    {"layer": "high_clouds", "scroll_speed": 0.10, "amount": 0.74, "mist": 0.00},
    {"layer": "jagged_range", "scroll_speed": 0.13, "amount": 0.66, "mist": 0.22},
    {"layer": "lower_range", "scroll_speed": 0.19, "amount": 0.52, "mist": 0.22},
    {"layer": "cloud_bank", "scroll_speed": 0.23, "amount": 0.46, "mist": 0.00},
    {"layer": "forested_ridge", "scroll_speed": 0.27, "amount": 0.40, "mist": 0.20},
    {"layer": "hills", "scroll_speed": 0.38, "amount": 0.28, "mist": 0.00},
    {"layer": "near_trees", "scroll_speed": 0.60, "amount": 0.04, "mist": 0.00},
    {"layer": "ground", "scroll_speed": 1.00, "amount": 0.00, "mist": 0.00},
]


# ---------------------------------------------------------------------------
# Core Atmospheric Perspective Math (Exact Godot 4 Shader/Script Parity)
# ---------------------------------------------------------------------------

def sky_row_colors(sky_img: Image.Image) -> np.ndarray:
    """
    Compute average RGB of each sky row rounded like Godot's roundi:
    floor(mean + 0.5) -> uint8 shape (H, 3).
    """
    rgb = np.asarray(sky_img.convert("RGB"), dtype=np.float32)
    return np.floor(rgb.mean(axis=1) + 0.5).astype(np.uint8)


def find_art_bounds(alpha: np.ndarray) -> Tuple[int, int]:
    """Return (art_top, art_bottom) where art_bottom is last opaque row + 1."""
    rows = np.flatnonzero(alpha.max(axis=1) > 0)
    if len(rows) == 0:
        return 0, alpha.shape[0]
    return int(rows[0]), int(rows[-1]) + 1


def apply_atmospheric_haze(
    layer_img: Image.Image,
    sky_rows: np.ndarray,
    amount: float,
    mist: float = 0.0,
    strength: float = 1.0,
) -> Image.Image:
    """
    Blend a layer toward sky_rows on each matching row while preserving alpha exactly.
    If amount == 0 and mist == 0 (or strength == 0), returns an exact copy of layer_img.
    """
    rgba = np.asarray(layer_img.convert("RGBA"), dtype=np.uint8)
    if strength <= 0.0 or (amount <= 0.0 and mist <= 0.0):
        return Image.fromarray(rgba.copy(), mode="RGBA")

    h = rgba.shape[0]
    if sky_rows.shape[0] != h:
        raise ValueError(f"Layer height ({h}) must match sky height ({sky_rows.shape[0]}) for row-aligned lookup.")

    a_f = rgba.astype(np.float32)
    art_top, art_bottom = find_art_bounds(rgba[:, :, 3])
    span = max(1, art_bottom - art_top)
    y = np.clip((np.arange(h, dtype=np.float32) + 0.5 - art_top) / float(span), 0.0, 1.0)
    k = float(strength) * np.clip(float(amount) + float(mist) * y, 0.0, 1.0)
    k3 = k[:, None, None]

    sky_f = np.asarray(sky_rows, dtype=np.float32)[:, None, :]
    blended_rgb = a_f[:, :, :3] * (1.0 - k3) + sky_f * k3

    out = rgba.copy()
    out[:, :, :3] = np.clip(np.round(blended_rgb), 0, 255).astype(np.uint8)
    # Alpha stays 100% unchanged
    return Image.fromarray(out, mode="RGBA")


def clean_patchy_outline(layer_img: Image.Image, luma_drop_threshold: float = 24.0) -> Tuple[Image.Image, int]:
    """
    Replace dark patchy 1px outline pixels on the outer silhouette of a far layer
    with the average RGB of their interior non-edge opaque neighbors, preventing
    dotted outline artifacts in the distance.
    """
    rgba = np.asarray(layer_img.convert("RGBA"), dtype=np.uint8).copy()
    h, w = rgba.shape[:2]
    opaque = rgba[:, :, 3] > 0

    # Identify 4-connected exterior edge pixels (opaque pixel touching at least one transparent pixel)
    up = np.pad(opaque[:-1, :], ((1, 0), (0, 0)), constant_values=False)
    down = np.pad(opaque[1:, :], ((0, 1), (0, 0)), constant_values=False)
    left = np.pad(opaque[:, :-1], ((0, 0), (1, 0)), constant_values=False)
    right = np.pad(opaque[:, 1:], ((0, 0), (0, 1)), constant_values=False)
    interior = opaque & up & down & left & right
    edge = opaque & ~interior

    rgb_f = rgba[:, :, :3].astype(np.float32)
    luma = 0.299 * rgb_f[:, :, 0] + 0.587 * rgb_f[:, :, 1] + 0.114 * rgb_f[:, :, 2]

    ey, ex = np.where(edge)
    fixed = 0
    for y, x in zip(ey, ex):
        y0, y1 = max(0, y - 1), min(h, y + 2)
        x0, x1 = max(0, x - 1), min(w, x + 2)
        patch_int = interior[y0:y1, x0:x1]
        if not np.any(patch_int):
            patch_int = opaque[y0:y1, x0:x1] & ~edge[y0:y1, x0:x1]
        if not np.any(patch_int):
            continue
        mean_rgb = rgb_f[y0:y1, x0:x1][patch_int].mean(axis=0)
        mean_luma = float(0.299 * mean_rgb[0] + 0.587 * mean_rgb[1] + 0.114 * mean_rgb[2])
        if mean_luma - float(luma[y, x]) >= luma_drop_threshold:
            rgba[y, x, :3] = np.round(mean_rgb).astype(np.uint8)
            fixed += 1

    return Image.fromarray(rgba, mode="RGBA"), fixed


# ---------------------------------------------------------------------------
# Demo Parallax Stack (Daylight & 2.5D Limbo-Style Twilight Presets)
# ---------------------------------------------------------------------------

def synthesize_demo_stack(width: int = 320, height: int = 180, style: str = "daylight") -> Dict[str, Any]:
    """
    Build a 6-layer pixel-art platformer stack sharing one (width x height) canvas:
      sky, far_peaks, jagged_range, forested_ridge, hills, ground
    Supports 'daylight' (classic sky-blue atmospheric perspective) and
    'limbo' (moody 2.5D twilight silhouette gradient).
    """
    yy, xx = np.mgrid[:height, :width]
    t_y = yy / float(max(1, height - 1))

    # 1. Sky gradient
    sky_arr = np.zeros((height, width, 4), dtype=np.uint8)
    if style == "limbo":
        top_c = np.array([22, 26, 34], dtype=np.float32)
        bot_c = np.array([154, 166, 176], dtype=np.float32)
    else:
        top_c = np.array([64, 134, 212], dtype=np.float32)
        bot_c = np.array([196, 226, 246], dtype=np.float32)
    sky_rgb = top_c[None, None, :] * (1.0 - t_y[:, :, None]) + bot_c[None, None, :] * t_y[:, :, None]
    sky_arr[:, :, :3] = np.round(sky_rgb).astype(np.uint8)
    sky_arr[:, :, 3] = 255

    def _mountain(ridge_y: np.ndarray, fill_top: Tuple[int, int, int], fill_bot: Tuple[int, int, int], snow: bool = False) -> np.ndarray:
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        mask = yy >= ridge_y[None, :]
        denom = np.maximum(1.0, (height - 1) - ridge_y[None, :])
        rel = np.clip((yy - ridge_y[None, :]) / denom, 0.0, 1.0)
        for c_idx in range(3):
            arr[:, :, c_idx] = np.where(
                mask,
                np.round(fill_top[c_idx] * (1.0 - rel) + fill_bot[c_idx] * rel),
                0,
            ).astype(np.uint8)
        if snow:
            snow_cap = mask & ((yy - ridge_y[None, :]) < 12) & (ridge_y[None, :] < height * 0.44)
            arr[snow_cap, :3] = (238, 242, 246) if style == "daylight" else (180, 188, 196)
        arr[mask, 3] = 255
        return arr

    # 2. Far peaks (0.08 -> amount 0.80, mist 0.20)
    r_far = 52 + 24 * np.sin(xx[0] * 0.032) + 14 * np.cos(xx[0] * 0.085)
    far_peaks = _mountain(r_far, (112, 92, 86), (78, 66, 62), snow=True)

    # 3. Jagged range (0.13 -> amount 0.66, mist 0.22)
    r_jag = 76 + 18 * np.sin(xx[0] * 0.05 + 1.2) + 10 * np.abs(np.sin(xx[0] * 0.14))
    jagged_range = _mountain(r_jag, (94, 78, 68), (58, 52, 48), snow=False)

    # 4. Forested ridge (0.27 -> amount 0.40, mist 0.20)
    r_for = 104 + 12 * np.sin(xx[0] * 0.04 + 2.4) + 5 * np.sin(xx[0] * 0.22)
    forested_ridge = _mountain(r_for, (46, 102, 56), (32, 72, 44)) if style == "daylight" else _mountain(r_for, (46, 52, 60), (28, 32, 38))

    # 5. Hills (0.38 -> amount 0.28)
    r_hill = 128 + 9 * np.sin(xx[0] * 0.028 + 0.6)
    hills = _mountain(r_hill, (68, 134, 62), (48, 98, 48)) if style == "daylight" else _mountain(r_hill, (28, 32, 38), (18, 20, 24))

    # 6. Playable Ground + Hero Silhouette (1.0 -> amount 0.0, mist 0.0)
    ground = np.zeros((height, width, 4), dtype=np.uint8)
    g_mask = yy >= 152
    ground[g_mask] = (88, 64, 44, 255) if style == "daylight" else (10, 12, 14, 255)
    ground[(yy >= 152) & (yy < 157)] = (72, 148, 60, 255) if style == "daylight" else (14, 16, 20, 255)
    # Hero standing on ground (never hazed)
    ground[132:152, 154:166] = (214, 84, 72, 255) if style == "daylight" else (235, 240, 245, 255)
    ground[124:132, 156:164] = (232, 188, 146, 255) if style == "daylight" else (235, 240, 245, 255)

    return {
        "sky": Image.fromarray(sky_arr, mode="RGBA"),
        "layers": [
            {"name": "far_peaks", "image": Image.fromarray(far_peaks, mode="RGBA"), "scroll_speed": 0.08, "amount": 0.80, "mist": 0.20},
            {"name": "jagged_range", "image": Image.fromarray(jagged_range, mode="RGBA"), "scroll_speed": 0.13, "amount": 0.66, "mist": 0.22},
            {"name": "forested_ridge", "image": Image.fromarray(forested_ridge, mode="RGBA"), "scroll_speed": 0.27, "amount": 0.40, "mist": 0.20},
            {"name": "hills", "image": Image.fromarray(hills, mode="RGBA"), "scroll_speed": 0.38, "amount": 0.28, "mist": 0.00},
            {"name": "ground", "image": Image.fromarray(ground, mode="RGBA"), "scroll_speed": 1.00, "amount": 0.00, "mist": 0.00},
        ],
    }


def composite_stack(sky_img: Image.Image, layers: Sequence[Image.Image]) -> Image.Image:
    """Alpha-composite layers back-to-front over sky_img."""
    canvas = sky_img.convert("RGBA")
    for layer in layers:
        canvas = Image.alpha_composite(canvas, layer.convert("RGBA"))
    return canvas


# ---------------------------------------------------------------------------
# 6-Point Automated Verification Suite
# ---------------------------------------------------------------------------

def run_verification_suite() -> Dict[str, Any]:
    """
    Verify all 6 requirements from the Atmospheric Perspective specification:
      1. Amount 0, mist 0 -> equals source art exactly.
      2. Amount 1 -> every opaque pixel equals sky row color behind it.
      3. Amount 0.80, mist 0.20 -> top row of art satisfies k = 0.80 + 0.20 * 0.5 / (art_bottom - art_top) within 1/255.
      4. Alpha channel is identical before and after.
      5. Ground and player stay identical with effect on vs off.
      6. Strength 0 returns exact original background.
    """
    stack = synthesize_demo_stack(160, 120, style="daylight")
    sky = stack["sky"]
    rows = sky_row_colors(sky)
    far = stack["layers"][0]["image"]
    far_arr = np.asarray(far, dtype=np.uint8)
    ground = stack["layers"][-1]["image"]
    ground_arr = np.asarray(ground, dtype=np.uint8)

    checks: Dict[str, Any] = {}

    # 1. Amount 0, mist 0 -> exact source match
    z_img = apply_atmospheric_haze(far, rows, amount=0.0, mist=0.0, strength=1.0)
    checks["amount_0_mist_0_exact"] = {"ok": bool(np.array_equal(np.asarray(z_img), far_arr))}

    # 2. Amount 1 -> opaque pixels match sky_rows[row]
    full_img = apply_atmospheric_haze(far, rows, amount=1.0, mist=0.0, strength=1.0)
    full_arr = np.asarray(full_img, dtype=np.uint8)
    opaque_mask = far_arr[:, :, 3] > 0
    expected_sky_grid = np.broadcast_to(rows[:, None, :], far_arr[:, :, :3].shape)
    max_sky_diff = int(np.max(np.abs(full_arr[:, :, :3][opaque_mask].astype(np.int32) - expected_sky_grid[opaque_mask].astype(np.int32))))
    checks["amount_1_matches_sky_row"] = {"ok": max_sky_diff == 0, "max_diff": max_sky_diff}

    # 3. Amount 0.80, mist 0.20 -> top art row k check within 1/255 per channel
    hazed_img = apply_atmospheric_haze(far, rows, amount=0.80, mist=0.20, strength=1.0)
    hazed_arr = np.asarray(hazed_img, dtype=np.uint8)
    art_top, art_bottom = find_art_bounds(far_arr[:, :, 3])
    k_expected = 0.80 + 0.20 * 0.5 / float(art_bottom - art_top)
    top_opaque = far_arr[art_top, :, 3] > 0
    src_top = far_arr[art_top, top_opaque, :3].astype(np.float32)
    sky_top = rows[art_top].astype(np.float32)
    exp_top = np.round(src_top * (1.0 - k_expected) + sky_top[None, :] * k_expected)
    obs_top = hazed_arr[art_top, top_opaque, :3].astype(np.float32)
    max_top_err = int(np.max(np.abs(obs_top - exp_top)))
    checks["amount_080_mist_020_top_row"] = {
        "ok": max_top_err <= 1,
        "k_top": round(k_expected, 6),
        "max_channel_diff": max_top_err,
    }

    # 4. Alpha unchanged
    alpha_diff = int(np.max(np.abs(hazed_arr[:, :, 3].astype(np.int32) - far_arr[:, :, 3].astype(np.int32))))
    checks["alpha_preserved"] = {"ok": alpha_diff == 0, "max_alpha_diff": alpha_diff}

    # 5. Ground + player unchanged
    ground_out = apply_atmospheric_haze(ground, rows, amount=0.0, mist=0.0, strength=1.0)
    checks["ground_and_player_untouched"] = {"ok": bool(np.array_equal(np.asarray(ground_out), ground_arr))}

    # 6. Strength 0 -> exact original background
    s0 = apply_atmospheric_haze(far, rows, amount=0.80, mist=0.20, strength=0.0)
    checks["strength_0_restores_original"] = {"ok": bool(np.array_equal(np.asarray(s0), far_arr))}

    return {"ok": all(bool(v["ok"]) for v in checks.values()), "checks": checks}


# ---------------------------------------------------------------------------
# Engine Code & Shader Exports (2D Parallax + 2.5D Limbo-Style Depth Cards)
# ---------------------------------------------------------------------------

SNIPPETS: Dict[str, Tuple[str, str]] = {
    "godot4-2d-shader": (
        "atmospheric_perspective.gdshader",
        """// atmospheric_perspective.gdshader — 2D Parallax layer blend toward sky row color (Godot 4.x)
shader_type canvas_item;

uniform sampler2D sky_colors : filter_nearest; // 1 px wide, sky average RGB per row
uniform float global_strength : hint_range(0.0, 1.0) = 1.0;
uniform float amount : hint_range(0.0, 1.0) = 0.0;
uniform float mist : hint_range(0.0, 1.0) = 0.0;
uniform float art_top = 0.0;
uniform float art_bottom = 1.0;
uniform bool use_screen_uv = false; // Enable if layer is cropped/atlas-packed or shifts vertically

void fragment() {
\tvec4 c = texture(TEXTURE, UV);
\tfloat lookup_y = use_screen_uv ? SCREEN_UV.y : UV.y;
\tvec3 sky = texture(sky_colors, vec2(0.5, lookup_y)).rgb;
\tfloat denom = max(art_bottom - art_top, 0.0001);
\tfloat y = clamp((UV.y - art_top) / denom, 0.0, 1.0);
\tfloat k = global_strength * clamp(amount + mist * y, 0.0, 1.0);
\tCOLOR = vec4(mix(c.rgb, sky, k), c.a);
}
""",
    ),
    "godot4-2d-script": (
        "hazed_layer.gd",
        """# hazed_layer.gd — Attach to each Parallax2D Sprite2D with atmospheric_perspective.gdshader
extends Sprite2D

@export var sky: Texture2D
@export_range(0.0, 1.0) var global_strength := 1.0
@export_range(0.0, 1.0) var amount := 0.0
@export_range(0.0, 1.0) var mist := 0.0
@export var use_screen_uv := false

func _ready() -> void:
\tvar art := texture.get_image().get_used_rect()
\tvar h := float(texture.get_height())
\tmaterial = material.duplicate() # Per-layer instance so each depth keeps its own numbers
\tmaterial.set_shader_parameter("sky_colors", sky_colors(sky.get_image()))
\tmaterial.set_shader_parameter("global_strength", global_strength)
\tmaterial.set_shader_parameter("amount", amount)
\tmaterial.set_shader_parameter("mist", mist)
\tmaterial.set_shader_parameter("art_top", art.position.y / h)
\tmaterial.set_shader_parameter("art_bottom", art.end.y / h)
\tmaterial.set_shader_parameter("use_screen_uv", use_screen_uv)

static func sky_colors(img: Image) -> ImageTexture:
\tvar rows := Image.create(1, img.get_height(), false, Image.FORMAT_RGB8)
\tfor y in img.get_height():
\t\tvar sum := Vector3.ZERO
\t\tfor x in img.get_width():
\t\t\tvar c := img.get_pixel(x, y)
\t\t\tsum += Vector3(c.r8, c.g8, c.b8)
\t\tsum /= img.get_width()
\t\trows.set_pixel(0, y, Color8(roundi(sum.x), roundi(sum.y), roundi(sum.z)))
\treturn ImageTexture.create_from_image(rows)
""",
    ),
    "godot4-25d-limbo-shader": (
        "atmospheric_25d_card.gdshader",
        """// atmospheric_25d_card.gdshader — Spatial shader for 2.5D / Limbo-style depth cards (Sprite3D / QuadMesh)
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

uniform sampler2D albedo_tex : source_color, filter_nearest;
uniform sampler2D sky_colors : source_color, filter_nearest; // 1 px wide vertical gradient
uniform float global_strength : hint_range(0.0, 1.0) = 1.0;
uniform float amount : hint_range(0.0, 1.0) = 0.4;
uniform float mist : hint_range(0.0, 1.0) = 0.2;
uniform float art_top = 0.0;
uniform float art_bottom = 1.0;
uniform float alpha_scissor = 0.5;

void fragment() {
\tvec4 c = texture(albedo_tex, UV);
\tif (c.a < alpha_scissor) discard;
\tvec3 sky = texture(sky_colors, vec2(0.5, SCREEN_UV.y)).rgb;
\tfloat y = clamp((UV.y - art_top) / max(art_bottom - art_top, 0.0001), 0.0, 1.0);
\tfloat k = global_strength * clamp(amount + mist * y, 0.0, 1.0);
\tALBEDO = mix(c.rgb, sky, k);
}
""",
    ),
    "unity-shader": (
        "AtmosphericParallax2D.shader",
        """// AtmosphericParallax2D.shader — Unity Sprite atmospheric perspective shader
Shader "Custom/AtmosphericParallax2D"
{
    Properties
    {
        [PerRendererData] _MainTex ("Layer Texture", 2D) = "white" {}
        _SkyColors ("Sky Row Colors (1px wide, Point)", 2D) = "white" {}
        _GlobalStrength ("Global Strength", Range(0,1)) = 1
        _Amount ("Layer Amount", Range(0,1)) = 0
        _Mist ("Base Mist", Range(0,1)) = 0
        _ArtTop ("Art Top UV.y", Float) = 0
        _ArtBottom ("Art Bottom UV.y", Float) = 1
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Off ZWrite Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex, _SkyColors;
            float _GlobalStrength, _Amount, _Mist, _ArtTop, _ArtBottom;

            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };

            v2f vert(appdata v) {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target {
                fixed4 c = tex2D(_MainTex, i.uv);
                // Note: Unity UV.y=0 is bottom; pass _SkyColors oriented bottom->top or flip (1 - i.uv.y)
                fixed3 sky = tex2D(_SkyColors, float2(0.5, i.uv.y)).rgb;
                float y = saturate((1.0 - i.uv.y - _ArtTop) / max(_ArtBottom - _ArtTop, 0.0001));
                float k = _GlobalStrength * saturate(_Amount + _Mist * y);
                return fixed4(lerp(c.rgb, sky, k), c.a);
            }
            ENDCG
        }
    }
}
""",
    ),
}


# ---------------------------------------------------------------------------
# CLI Commands
# ---------------------------------------------------------------------------

def _cmd_bake_layer(args: argparse.Namespace) -> int:
    sky_img = Image.open(args.sky)
    layer_img = Image.open(args.layer)
    fixed_pixels = 0
    if args.clean_outline:
        layer_img, fixed_pixels = clean_patchy_outline(layer_img, luma_drop_threshold=args.outline_threshold)

    rows = sky_row_colors(sky_img)
    out_img = apply_atmospheric_haze(
        layer_img,
        rows,
        amount=args.amount,
        mist=args.mist,
        strength=args.strength,
    )
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out_path)

    res: Dict[str, Any] = {
        "ok": True,
        "output_path": str(out_path),
        "size": [out_img.width, out_img.height],
        "amount": args.amount,
        "mist": args.mist,
        "strength": args.strength,
        "outline_pixels_cleaned": fixed_pixels,
    }
    if args.save_sky_rows:
        sp = Path(args.save_sky_rows)
        sp.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rows[:, None, :], mode="RGB").save(sp)
        res["sky_rows_path"] = str(sp)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"Baked atmospheric layer (amount={args.amount}, mist={args.mist}) -> {out_path}")
    return 0


def _cmd_clean_outline(args: argparse.Namespace) -> int:
    layer_img = Image.open(args.layer)
    cleaned, count = clean_patchy_outline(layer_img, luma_drop_threshold=args.threshold)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned.save(out_path)
    res = {"ok": True, "output_path": str(out_path), "pixels_cleaned": count}
    print(json.dumps(res, indent=2) if args.json else f"Cleaned {count} dark outline pixels -> {out_path}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    stack = synthesize_demo_stack(style=args.style)
    sky = stack["sky"]
    rows = sky_row_colors(sky)

    before_layers = [entry["image"] for entry in stack["layers"]]
    after_layers = [
        apply_atmospheric_haze(entry["image"], rows, amount=entry["amount"], mist=entry["mist"], strength=args.strength)
        for entry in stack["layers"]
    ]

    before_img = composite_stack(sky, before_layers)
    after_img = composite_stack(sky, after_layers)
    side_by_side = Image.fromarray(np.hstack([np.asarray(before_img), np.asarray(after_img)]), mode="RGBA")
    if args.upscale > 1:
        side_by_side = side_by_side.resize(
            (side_by_side.width * args.upscale, side_by_side.height * args.upscale),
            resample=Image.Resampling.NEAREST,
        )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    b_path = out_dir / f"demo_{args.style}_before.png"
    a_path = out_dir / f"demo_{args.style}_after.png"
    c_path = out_dir / f"demo_{args.style}_compare.png"
    before_img.save(b_path)
    after_img.save(a_path)
    side_by_side.save(c_path)

    res = {
        "ok": True,
        "style": args.style,
        "strength": args.strength,
        "before_path": str(b_path),
        "after_path": str(a_path),
        "compare_path": str(c_path),
    }
    print(json.dumps(res, indent=2) if args.json else f"Saved {args.style} comparison -> {c_path}")
    return 0


def _cmd_presets(args: argparse.Namespace) -> int:
    print(json.dumps({"ok": True, "presets": SCROLL_SPEED_PRESETS}, indent=2))
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    res = run_verification_suite()
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


def _cmd_export_code(args: argparse.Namespace) -> int:
    targets = list(SNIPPETS.keys()) if args.target == "all" else [args.target]
    written: Dict[str, str] = {}
    if args.out_dir:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for t in targets:
            fname, code = SNIPPETS[t]
            fp = out_dir / fname
            fp.write_text(code, encoding="utf-8")
            written[t] = str(fp)

    if args.json:
        payload: Dict[str, Any] = {"ok": True, "targets": targets}
        if written:
            payload["written"] = written
        else:
            payload["code"] = {t: {"filename": SNIPPETS[t][0], "source": SNIPPETS[t][1]} for t in targets}
        print(json.dumps(payload, indent=2))
    else:
        if written:
            for t, p in written.items():
                print(f"Exported {t} -> {p}")
        else:
            for t in targets:
                fname, code = SNIPPETS[t]
                print(f"=== {fname} ===\n{code}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atmospheric perspective pipeline for 2D parallax & 2.5D layered games."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_bake = sub.add_parser("bake-layer", help="Blend one parallax layer toward sky_rows with optional mist & outline fix.")
    p_bake.add_argument("--sky", required=True, help="Sky layer PNG (same height as layer).")
    p_bake.add_argument("--layer", required=True, help="Parallax layer PNG with transparent background.")
    p_bake.add_argument("-o", "--output", required=True, help="Output hazed layer PNG.")
    p_bake.add_argument("--amount", type=float, required=True, help="Base haze amount [0..1].")
    p_bake.add_argument("--mist", type=float, default=0.0, help="Extra base mist [0..1] toward art bottom.")
    p_bake.add_argument("--strength", type=float, default=1.0, help="Global atmospheric strength [0..1].")
    p_bake.add_argument("--clean-outline", action="store_true", help="Match dark exterior outline pixels to interior fill.")
    p_bake.add_argument("--outline-threshold", type=float, default=24.0, help="Luma drop threshold for outline cleaning.")
    p_bake.add_argument("--save-sky-rows", help="Optional 1xH sky_colors lookup PNG output path.")
    p_bake.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_bake.set_defaults(func=_cmd_bake_layer)

    p_clean = sub.add_parser("clean-outline", help="Fix patchy dark outlines on generated far parallax silhouettes.")
    p_clean.add_argument("layer", help="Input layer PNG.")
    p_clean.add_argument("-o", "--output", required=True, help="Cleaned output PNG.")
    p_clean.add_argument("--threshold", type=float, default=24.0, help="Luma drop threshold (default: 24.0).")
    p_clean.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_clean.set_defaults(func=_cmd_clean_outline)

    p_demo = sub.add_parser("demo", help="Render before/after atmospheric perspective comparison (daylight or limbo 2.5D).")
    p_demo.add_argument("--style", choices=["daylight", "limbo"], default="daylight", help="Visual style preset.")
    p_demo.add_argument("--strength", type=float, default=1.0, help="Global atmospheric strength [0..1].")
    p_demo.add_argument("--out-dir", default="exports/atmospheric_perspective", help="Output directory.")
    p_demo.add_argument("--upscale", type=int, default=2, help="Nearest upscale factor.")
    p_demo.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_demo.set_defaults(func=_cmd_demo)

    p_pre = sub.add_parser("presets", help="Print tested scroll_scale -> (amount, mist) table as JSON.")
    p_pre.set_defaults(func=_cmd_presets)

    p_ver = sub.add_parser("verify", help="Run the 6-point atmospheric perspective verification suite.")
    p_ver.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_ver.set_defaults(func=_cmd_verify)

    p_exp = sub.add_parser("export-code", help="Export Godot 4 (2D + 2.5D Limbo card) & Unity shaders/scripts.")
    p_exp.add_argument("--target", choices=sorted(list(SNIPPETS.keys()) + ["all"]), default="all", help="Export target.")
    p_exp.add_argument("--out-dir", help="Optional directory to write files.")
    p_exp.add_argument("--json", action="store_true", help="Output machine-readable JSON.")
    p_exp.set_defaults(func=_cmd_export_code)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
