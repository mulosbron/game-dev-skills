#!/usr/bin/env python3
"""
2D-Native Top-Down Procedural VFX Forge (tools/vfx_forge.py)
Inspired by Nenly's Wuxia Survivors (《群侠传：幸存者》) 2D-Native SDF VFX Architecture.

Core Architectural Pillars:
1. 2D-Native Orthographic Top-Down SDFs (y_scale=0.65 ground projection so hitboxes/ranges are 100% readable).
2. Five Canonical Effect Families with Spawn -> Sustain -> Decay lifecycles:
   - blade_arc  (刀光 — Sweeping crescent blade light)
   - shockwave  (冲击波 — Expanding ground ring + FBM edge distortion)
   - qi_burst   (气爆 — Radial implosion-to-explosion energy burst)
   - aoe_zone   (驻留场 — Persistent ground formation/sigil + rising motes)
   - projectile (飞行体 — Directed energy bolt/blade + vortex wake trail)
3. Dual-Buffer Selective Glow (Separate Crisp Pixel Base + Selective Emission Glow Buffer):
   - Supports Pure Pixel Mode, HD Selective Bloom Mode, and separate '_base' / '_glow' strip exports.
4. Menpai (Sect / School) Visual Language Presets + Rarity Scaling (common, rare, epic, legendary).
5. Native Godot 4 (.gdshader) & GameMaker GLSL Shader Generator + Interactive HTML Visual Studio.
"""

import sys
import json
import math
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.agent-game-forge.vfx"

# ============================================================================
# 1. MENPAI (SECT / SCHOOL) VISUAL LANGUAGE PRESETS
# ============================================================================
# Each Menpai defines:
# - palette: 5 hex stops [shadow, dark, mid, bright, core]
# - glow_color: RGB tuple for selective emission bloom
# - noise_amp: SDF edge distortion intensity (0.0 = geometric, 1.0 = chaotic)
# - angular_facets: 0 = smooth/organic, N = quantized polygonal symmetry
# - sharpness: SDF edge falloff tightness
# - particle_style: 'sparks', 'embers', 'petals', 'lightning', 'bubbles', 'runes'
MENPAI_PRESETS = {
    "azure_sword": {
        "name": "Azure Cloud Sword Sect (青云剑派)",
        "palette": ["#091526", "#163e5c", "#3ca3c9", "#98e6f5", "#ffffff"],
        "glow_color": (80, 210, 255),
        "noise_amp": 0.15,
        "angular_facets": 8,
        "sharpness": 0.90,
        "particle_style": "sparks",
        "desc": "Razor-sharp geometric arcs, cold cyan-silver palette, high velocity, clean edges.",
    },
    "crimson_demon": {
        "name": "Crimson Blood Demon Sect (血魔宗)",
        "palette": ["#1a040a", "#59091e", "#ad1136", "#ff3b5c", "#fff0f3"],
        "glow_color": (255, 55, 85),
        "noise_amp": 0.78,
        "angular_facets": 0,
        "sharpness": 0.72,
        "particle_style": "embers",
        "desc": "Jagged chaotic flame/blood edges, high FBM turbulence, aggressive explosive decay.",
    },
    "golden_buddha": {
        "name": "Shaolin Golden Dharma Sect (少林金光)",
        "palette": ["#241605", "#6e4711", "#d49424", "#ffe169", "#ffffff"],
        "glow_color": (255, 205, 70),
        "noise_amp": 0.12,
        "angular_facets": 8,
        "sharpness": 0.88,
        "particle_style": "runes",
        "desc": "Sacred octagonal/lotus symmetry, heavy impact hit-stop, warm golden radiance.",
    },
    "jade_poison": {
        "name": "Tangmen Thousand Venom Sect (唐门万毒)",
        "palette": ["#120524", "#240e42", "#1b5e3c", "#52d185", "#e3ffe8"],
        "glow_color": (75, 235, 135),
        "noise_amp": 0.62,
        "angular_facets": 5,
        "sharpness": 0.65,
        "particle_style": "bubbles",
        "desc": "Swirling purple-to-emerald venom gradients, cellular bubbling distortion, lingering mist.",
    },
    "frost_lotus": {
        "name": "Mystic Frost Lotus Palace (玄冰宫)",
        "palette": ["#080e24", "#192d59", "#3a86ff", "#a2d6f9", "#ffffff"],
        "glow_color": (120, 195, 255),
        "noise_amp": 0.25,
        "angular_facets": 6,
        "sharpness": 0.94,
        "particle_style": "sparks",
        "desc": "Hexagonal crystalline facets, shattering ice geometry, crisp diamond highlights.",
    },
    "void_thunder": {
        "name": "Purple Firmament Thunder Sect (紫霄雷法)",
        "palette": ["#10002b", "#3c096c", "#7b2cbf", "#d08fff", "#ffffff"],
        "glow_color": (195, 110, 255),
        "noise_amp": 0.88,
        "angular_facets": 12,
        "sharpness": 0.92,
        "particle_style": "lightning",
        "desc": "High-frequency jagged plasma arcs, electric violet-white contrast, rapid flicker.",
    },
}

RARITY_TIERS = {
    "common":    {"scale": 0.80, "sub_layers": 1, "particles": 6,  "glow_mult": 0.70, "rings": 1},
    "rare":      {"scale": 0.92, "sub_layers": 2, "particles": 14, "glow_mult": 1.00, "rings": 2},
    "epic":      {"scale": 1.02, "sub_layers": 3, "particles": 24, "glow_mult": 1.35, "rings": 3},
    "legendary": {"scale": 1.12, "sub_layers": 4, "particles": 36, "glow_mult": 1.75, "rings": 4},
}

EFFECT_FAMILIES = ["blade_arc", "shockwave", "qi_burst", "aoe_zone", "projectile"]


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _fbm_noise_2d(x: np.ndarray, y: np.ndarray, seed: float = 0.0) -> np.ndarray:
    """
    Fast deterministic 3-octave trigonometric value/wave FBM for 2D SDF distortion.
    """
    n1 = np.sin(x * 3.7 + seed) * np.cos(y * 3.7 - seed * 0.7)
    n2 = 0.5 * np.sin(x * 7.9 - y * 5.3 + seed * 1.9)
    n3 = 0.25 * np.cos(x * 15.1 + y * 13.7 - seed * 3.1)
    return (n1 + n2 + n3) / 1.75


def _quantize_palette(intensity: np.ndarray, alpha: np.ndarray, palette_hex: list) -> np.ndarray:
    """
    Maps scalar intensity [0..1] into discrete indexed pixel-art color bands from the 5-stop Menpai palette.
    """
    h, w = intensity.shape
    out = np.zeros((h, w, 4), dtype=np.uint8)
    colors = [_hex_to_rgb(c) for c in palette_hex]

    # 5 discrete pixel-art shading bands
    bands = [
        (0.08, colors[0]),
        (0.24, colors[1]),
        (0.46, colors[2]),
        (0.72, colors[3]),
        (0.90, colors[4]),
    ]
    for thresh, rgb in bands:
        mask = (intensity >= thresh) & (alpha > 0.08)
        out[mask, 0] = rgb[0]
        out[mask, 1] = rgb[1]
        out[mask, 2] = rgb[2]

    # Crisp pixel-art alpha threshold (2-tier alpha for clean sprites)
    out[:, :, 3] = np.where(alpha > 0.45, 255, np.where(alpha > 0.12, 160, 0)).astype(np.uint8)
    return out


# ============================================================================
# 2. THE 5 CANONICAL 2D TOP-DOWN SDF EFFECT FAMILIES
# ============================================================================

def _eval_family_sdf(
    family: str,
    t: float,
    xx: np.ndarray,
    yy: np.ndarray,
    menpai: dict,
    rarity: dict,
    y_scale: float = 0.65,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Evaluates one frame at normalized lifecycle time t in [0, 1] on a normalized [-1, 1] grid.
    Returns:
      - intensity: [0..1] indexed color ramp value
      - alpha:     [0..1] pixel opacity
      - glow:      [0..1] selective emission mask (ONLY high-energy cores/edges!)
    """
    # Lifecycle phases: Spawn [0..0.2], Sustain [0.2..0.7], Decay [0.7..1.0]
    spawn_t = min(1.0, t / 0.20) if t < 0.20 else 1.0
    decay_t = max(0.0, (1.0 - t) / 0.32) if t > 0.68 else 1.0
    env = spawn_t * decay_t

    # Top-down orthographic ground plane projection (stretch Y so ground circles are ellipses)
    gx = xx / rarity["scale"]
    gy = (yy / y_scale) / rarity["scale"]
    r_ground = np.sqrt(gx * gx + gy * gy)
    theta = np.arctan2(gy, gx)

    # Polygonal facet quantization for sects like Frost Lotus / Golden Buddha
    facets = menpai["angular_facets"]
    if facets > 0:
        sector = (2.0 * math.pi) / facets
        rel_a = ((theta + math.pi) % sector) - (sector * 0.5)
        poly_factor = np.cos(rel_a) / math.cos(sector * 0.35)
        r_shaped = r_ground / np.maximum(0.75, poly_factor)
    else:
        r_shaped = r_ground

    noise = _fbm_noise_2d(gx * 2.5, gy * 2.5, seed=t * 9.0) * menpai["noise_amp"]
    sharp = menpai["sharpness"]

    intensity = np.zeros_like(xx)
    alpha = np.zeros_like(xx)
    glow = np.zeros_like(xx)

    if family == "blade_arc":
        # 刀光 (Sweeping Crescent Blade Light)
        # Sweeps from -145 deg to +115 deg with fast ease-out
        sweep_progress = 1.0 - (1.0 - t) ** 2.4
        head_angle = -2.4 + sweep_progress * 4.2
        arc_span = 1.65 + 0.35 * rarity["sub_layers"]

        for layer_idx in range(rarity["sub_layers"]):
            r_target = 0.68 - layer_idx * 0.14
            lag = layer_idx * 0.18
            cur_head = head_angle - lag
            # Angular distance behind the leading blade tip
            ang_diff = (cur_head - theta + math.pi * 3) % (2.0 * math.pi) - math.pi
            in_arc = (ang_diff >= 0.0) & (ang_diff <= arc_span)
            arc_u = np.clip(1.0 - (ang_diff / arc_span), 0.0, 1.0)  # 1 at tip, 0 at tail

            # Tapered crescent thickness
            thickness = (0.14 - layer_idx * 0.025) * (arc_u ** 0.55) * (1.0 + 0.25 * noise)
            dist_ring = np.abs(r_shaped - r_target + 0.04 * noise)
            blade_val = np.clip(1.0 - (dist_ring / np.maximum(0.015, thickness)), 0.0, 1.0)
            blade_val = (blade_val ** (1.5 - 0.8 * sharp)) * in_arc * (arc_u ** 0.35) * decay_t

            # Leading tip flash
            tip_dist = np.sqrt((gx - r_target * np.cos(cur_head)) ** 2 + (gy - r_target * np.sin(cur_head)) ** 2)
            tip_flash = np.clip(1.0 - tip_dist / 0.18, 0.0, 1.0) ** 2 * decay_t

            layer_int = np.maximum(blade_val * (0.65 + 0.45 * arc_u), tip_flash)
            intensity = np.maximum(intensity, layer_int)
            alpha = np.maximum(alpha, np.clip(blade_val * 1.4 + tip_flash, 0.0, 1.0))
            # Selective glow ONLY on the leading outer edge & tip
            glow = np.maximum(glow, np.clip((blade_val ** 2) * arc_u * 1.2 + tip_flash * 1.4, 0.0, 1.0))

    elif family == "shockwave":
        # 冲击波 (Top-Down Expanding Ground Shockwave Ring)
        ease_t = 1.0 - (1.0 - t) ** 2.1
        for ring_i in range(rarity["rings"]):
            ring_t = np.clip((ease_t - ring_i * 0.12) / (1.0 - ring_i * 0.10), 0.0, 1.0)
            if ring_t <= 0.0:
                continue
            r_cur = 0.12 + ring_t * 0.76
            ring_w = (0.13 - ring_i * 0.02) * (1.0 - 0.55 * ring_t)
            dist = np.abs(r_shaped + noise * 0.09 - r_cur)
            ring_val = np.clip(1.0 - dist / np.maximum(0.015, ring_w), 0.0, 1.0) * (1.0 - ring_t ** 1.6)

            # Crisp outer ground telegraph line (so player clearly sees hitbox boundary!)
            outer_edge = np.clip(1.0 - np.abs(r_ground - r_cur) / 0.035, 0.0, 1.0) * (1.0 - ring_t)
            combined = np.maximum(ring_val, outer_edge * 0.95)
            intensity = np.maximum(intensity, combined)
            alpha = np.maximum(alpha, np.clip(combined * 1.5, 0.0, 1.0))
            glow = np.maximum(glow, (ring_val ** 2.2) + outer_edge * 0.9)

        # Center impact crack during initial frames
        if t < 0.45:
            core_fade = 1.0 - (t / 0.45)
            ray_wave = 0.5 + 0.5 * np.cos(theta * 8.0 + noise * 4.0)
            core = np.clip(1.0 - r_ground / (0.28 + 0.12 * ray_wave), 0.0, 1.0) * core_fade
            intensity = np.maximum(intensity, core)
            alpha = np.maximum(alpha, core)
            glow = np.maximum(glow, core ** 1.5)

    elif family == "qi_burst":
        # 气爆 (Radial Implosion -> Explosion Qi Burst)
        if t < 0.22:
            # Phase 1: Charge / Gather inward
            ct = t / 0.22
            r_in = 0.65 * (1.0 - ct)
            gather = np.clip(1.0 - np.abs(r_shaped - r_in) / 0.12, 0.0, 1.0) * ct
            core = np.clip(1.0 - r_ground / (0.15 + 0.15 * ct), 0.0, 1.0)
            intensity = np.maximum(gather * 0.85, core)
            alpha = np.clip(intensity * 1.4, 0.0, 1.0)
            glow = np.maximum(core, gather * 0.7)
        else:
            # Phase 2 & 3: Starburst explosion + directional spikes
            bt = (t - 0.22) / 0.78
            n_spikes = 6 + rarity["sub_layers"] * 2
            spike_pattern = np.abs(np.cos(theta * (n_spikes * 0.5) + noise * 1.8)) ** 1.8
            max_r = (0.38 + 0.52 * spike_pattern) * (1.0 - (1.0 - bt) ** 3.0)
            burst_body = np.clip(1.0 - r_shaped / np.maximum(0.05, max_r), 0.0, 1.0)
            # Hollow out center as it decays
            hollow = np.clip((r_ground - bt * 0.42) / 0.25, 0.0, 1.0) if bt > 0.35 else 1.0
            val = burst_body * hollow * (1.0 - bt ** 1.5)

            intensity = np.clip(val * 1.25 + (burst_body ** 3) * (1.0 - bt), 0.0, 1.0)
            alpha = np.clip(val * 1.6, 0.0, 1.0)
            glow = np.clip((intensity ** 1.8) * (1.2 - bt), 0.0, 1.0)

    elif family == "aoe_zone":
        # 驻留场 (Persistent Ground Formation / Sigil Zone)
        rot = t * math.pi * 1.5
        r_bound = 0.78 * spawn_t
        # Outer formation boundary ring (100% readable ground AoE radius)
        outer_ring = np.clip(1.0 - np.abs(r_ground - r_bound) / 0.045, 0.0, 1.0)
        inner_ring = np.clip(1.0 - np.abs(r_ground - r_bound * 0.62) / 0.035, 0.0, 1.0)

        # Rotating geometric sigil spokes & star inside the circle
        n_sym = max(4, facets if facets > 0 else 6)
        star_r = r_bound * (0.52 + 0.22 * np.cos(n_sym * (theta + rot)))
        star_line = np.clip(1.0 - np.abs(r_ground - star_r) / 0.04, 0.0, 1.0) * (r_ground <= r_bound)
        spokes = (np.abs(np.sin((theta - rot * 0.5) * (n_sym * 0.5))) > 0.94) & (r_ground < r_bound) & (r_ground > r_bound * 0.22)

        # Pulsing ground fill
        pulse = 0.55 + 0.45 * math.sin(t * math.pi * 4.0)
        ground_fill = np.clip(1.0 - r_ground / np.maximum(0.05, r_bound), 0.0, 1.0) * 0.32 * pulse

        # Vertical rising energy pillars/motes (in screen space yy above ground)
        mote_x = np.sin(xx * 14.0 + rot) * np.cos((yy + t * 2.2) * 10.0)
        motes = np.clip((mote_x - 0.72) * 3.5, 0.0, 1.0) * (r_ground < r_bound * 0.85)

        sigil = np.maximum.reduce([outer_ring, inner_ring * 0.85, star_line * 0.9, spokes.astype(np.float32) * 0.75, motes])
        intensity = np.clip((sigil + ground_fill) * decay_t, 0.0, 1.0)
        alpha = np.clip((sigil * 1.3 + ground_fill * 1.1) * decay_t, 0.0, 1.0)
        glow = np.clip((outer_ring + star_line * 0.8 + motes * 1.2) * decay_t, 0.0, 1.0)

    elif family == "projectile":
        # 飞行体 (Directed Energy Projectile moving left -> right with wake trail)
        px = -0.65 + t * 1.30
        dx = xx - px
        dy = yy
        # Projectile spearhead / crescent head
        head_r = np.sqrt((dx * 1.4) ** 2 + (dy * 2.2) ** 2)
        head = np.clip(1.0 - head_r / (0.24 * rarity["scale"]), 0.0, 1.0)
        crescent = np.clip(1.0 - np.abs( np.sqrt((dx + 0.08) ** 2 + (dy * 1.4) ** 2) - 0.18 ) / 0.05, 0.0, 1.0) * (dx > -0.12)

        # Wake trail behind head (dx < 0)
        trail_len = 0.55 + 0.15 * rarity["sub_layers"]
        trail_u = np.clip(1.0 + dx / trail_len, 0.0, 1.0) * (dx <= 0.05)
        wave_y = dy + 0.07 * np.sin(dx * 14.0 - t * 18.0) * (1.0 - trail_u)
        trail_w = 0.14 * rarity["scale"] * (trail_u ** 0.7) * (1.0 + 0.35 * noise)
        trail = np.clip(1.0 - np.abs(wave_y) / np.maximum(0.015, trail_w), 0.0, 1.0) * trail_u

        combined = np.maximum.reduce([head, crescent * 0.95, trail * 0.82]) * decay_t
        intensity = np.clip(combined + (head ** 2) * 0.35, 0.0, 1.0)
        alpha = np.clip(combined * 1.5, 0.0, 1.0)
        glow = np.clip((head ** 1.5) + crescent * 0.9 + (trail ** 2) * 0.6, 0.0, 1.0) * decay_t

    # Deterministic procedural particles (sparks / embers / runes) scaled by rarity
    n_parts = rarity["particles"]
    for p_idx in range(n_parts):
        p_seed = p_idx * 1.6180339
        p_ang = (p_seed * 7.13) % (2.0 * math.pi)
        p_speed = 0.25 + 0.55 * ((p_seed * 3.7) % 1.0)
        p_life = ((t * 1.25 - ((p_seed * 0.41) % 0.45)) % 1.0)
        if 0.0 < p_life < 0.85:
            pr = (0.12 + p_life * p_speed) * rarity["scale"]
            px_p = math.cos(p_ang + t * 0.8) * pr
            py_p = math.sin(p_ang + t * 0.8) * pr * y_scale
            p_dist = np.sqrt((xx - px_p) ** 2 + (yy - py_p) ** 2)
            p_size = 0.032 * (1.0 - p_life)
            p_val = np.clip(1.0 - p_dist / max(0.012, p_size), 0.0, 1.0) * decay_t
            intensity = np.maximum(intensity, p_val * 0.95)
            alpha = np.maximum(alpha, p_val)
            glow = np.maximum(glow, p_val)

    return intensity, alpha, np.clip(glow * rarity["glow_mult"], 0.0, 1.0)


def render_vfx_sequence(
    family: str = "blade_arc",
    menpai_id: str = "azure_sword",
    rarity_id: str = "epic",
    canvas_size: int = 96,
    pixel_scale: int = 1,
    num_frames: int = 12,
    y_scale: float = 0.65,
    mode: str = "hd-bloom",
) -> tuple[list[Image.Image], list[Image.Image], list[Image.Image]]:
    """
    Renders a full 30-FPS animation sequence for (family, menpai, rarity).
    Returns (combined_frames, base_pixel_frames, selective_glow_frames).
    """
    menpai = MENPAI_PRESETS.get(menpai_id, MENPAI_PRESETS["azure_sword"])
    rarity = RARITY_TIERS.get(rarity_id, RARITY_TIERS["epic"])

    grid_res = max(24, canvas_size // max(1, pixel_scale))
    lin = np.linspace(-1.0, 1.0, grid_res, dtype=np.float32)
    yy, xx = np.meshgrid(lin, lin, indexing="ij")

    combined_frames = []
    base_frames = []
    glow_frames = []
    glow_rgb = menpai["glow_color"]

    for f_idx in range(num_frames):
        # Step-quantized time t in [0.05 .. 0.95]
        t = (f_idx + 0.5) / num_frames
        intensity, alpha, glow_mask = _eval_family_sdf(
            family=family,
            t=t,
            xx=xx,
            yy=yy,
            menpai=menpai,
            rarity=rarity,
            y_scale=y_scale,
        )

        # 1. Base Crisp Pixel Buffer (Indexed Palette)
        base_rgba = _quantize_palette(intensity, alpha, menpai["palette"])
        base_img = Image.fromarray(base_rgba, mode="RGBA")
        if pixel_scale > 1:
            base_img = base_img.resize((canvas_size, canvas_size), Image.Resampling.NEAREST)

        # 2. Selective Glow Buffer (ONLY glowing elements!)
        glow_rgba = np.zeros((grid_res, grid_res, 4), dtype=np.uint8)
        g_norm = np.clip(glow_mask, 0.0, 1.0)
        glow_rgba[:, :, 0] = np.clip(glow_rgb[0] * g_norm + 255 * (g_norm ** 3) * 0.5, 0, 255).astype(np.uint8)
        glow_rgba[:, :, 1] = np.clip(glow_rgb[1] * g_norm + 255 * (g_norm ** 3) * 0.5, 0, 255).astype(np.uint8)
        glow_rgba[:, :, 2] = np.clip(glow_rgb[2] * g_norm + 255 * (g_norm ** 3) * 0.5, 0, 255).astype(np.uint8)
        glow_rgba[:, :, 3] = np.clip(g_norm * 235.0, 0, 255).astype(np.uint8)

        glow_img = Image.fromarray(glow_rgba, mode="RGBA")
        if pixel_scale > 1:
            glow_img = glow_img.resize((canvas_size, canvas_size), Image.Resampling.BILINEAR)
        glow_blurred = glow_img.filter(ImageFilter.GaussianBlur(radius=max(2.0, canvas_size * 0.045)))

        # 3. Composite according to mode ('pixel' vs 'hd-bloom')
        if mode == "pixel":
            comp_img = base_img.copy()
        else:
            # Additive Selective Glow under + over crisp pixel layer (preserves 100% pixel sharpness!)
            b_arr = np.array(base_img, dtype=np.float32)
            g_arr = np.array(glow_blurred, dtype=np.float32)
            g_alpha = (g_arr[:, :, 3:4] / 255.0) * 0.85
            b_alpha = b_arr[:, :, 3:4] / 255.0

            out_rgb = np.clip(b_arr[:, :, :3] * b_alpha + g_arr[:, :, :3] * g_alpha, 0, 255).astype(np.uint8)
            out_a = np.clip(np.maximum(b_arr[:, :, 3], g_arr[:, :, 3] * 0.85), 0, 255).astype(np.uint8)
            comp_img = Image.fromarray(np.dstack([out_rgb, out_a]), mode="RGBA")

        combined_frames.append(comp_img)
        base_frames.append(base_img)
        glow_frames.append(glow_blurred)

    return combined_frames, base_frames, glow_frames


def save_strip_and_gif(
    frames: list[Image.Image],
    out_dir: Path,
    stem: str,
    fps: int = 30,
    save_gif: bool = True,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(frames)
    w, h = frames[0].size
    strip = Image.new("RGBA", (w * n, h), (0, 0, 0, 0))
    for i, fr in enumerate(frames):
        strip.paste(fr, (i * w, 0))

    strip_path = out_dir / f"{stem}_strip{n}.png"
    strip.save(strip_path)

    if save_gif:
        # Dark slate preview background so selective glow is clearly visible
        gif_frames = []
        for fr in frames:
            bg = Image.new("RGBA", (w, h), (14, 17, 26, 255))
            bg.alpha_composite(fr)
            gif_frames.append(bg.convert("RGB"))
        gif_path = out_dir / f"{stem}.gif"
        gif_frames[0].save(
            gif_path,
            save_all=True,
            append_images=gif_frames[1:],
            duration=max(20, int(1000 / fps)),
            loop=0,
        )
    return strip_path


# ============================================================================
# 3. ENGINE SHADER EXPORTER (GODOT 4 .gdshader & GAMEMAKER GLSL ES)
# ============================================================================

GODOT4_SHADER_TEMPLATE = """shader_type canvas_item;
// 2D-Native Top-Down Procedural Pixel VFX Shader (Nenly Architecture)
// Family: {family} | Default Menpai: {menpai_id}
// Attach to a ColorRect / Sprite2D. Supports Pixel Grid Quantization + Selective Glow output!

uniform int effect_family : hint_range(0, 4) = {family_idx}; // 0:blade_arc, 1:shockwave, 2:qi_burst, 3:aoe_zone, 4:projectile
uniform float progress : hint_range(0.0, 1.0) = 0.35;
uniform float y_perspective : hint_range(0.35, 1.0) = 0.65;
uniform float pixel_grid : hint_range(16.0, 256.0) = 96.0;
uniform float noise_amp : hint_range(0.0, 1.0) = {noise_amp};
uniform float glow_intensity : hint_range(0.0, 3.0) = 1.35;

uniform vec4 col_shadow : source_color = vec4({c0}, 1.0);
uniform vec4 col_dark   : source_color = vec4({c1}, 1.0);
uniform vec4 col_mid    : source_color = vec4({c2}, 1.0);
uniform vec4 col_bright : source_color = vec4({c3}, 1.0);
uniform vec4 col_core   : source_color = vec4({c4}, 1.0);

float fbm2(vec2 p, float t) {{
    float n1 = sin(p.x * 3.7 + t) * cos(p.y * 3.7 - t * 0.7);
    float n2 = 0.5 * sin(p.x * 7.9 - p.y * 5.3 + t * 1.9);
    return (n1 + n2) / 1.5;
}}

vec3 sample_menpai_palette(float v) {{
    if (v >= 0.88) return col_core.rgb;
    if (v >= 0.68) return col_bright.rgb;
    if (v >= 0.42) return col_mid.rgb;
    if (v >= 0.20) return col_dark.rgb;
    return col_shadow.rgb;
}}

void fragment() {{
    // 1. Snap UV to crisp integer pixel grid
    vec2 snapped_uv = floor(UV * pixel_grid) / pixel_grid;
    vec2 p = snapped_uv * 2.0 - 1.0;

    // 2. Top-Down 2D Orthographic Ground Projection
    vec2 gp = vec2(p.x, p.y / y_perspective);
    float r = length(gp);
    float theta = atan(gp.y, gp.x);
    float n = fbm2(gp * 2.5, progress * 9.0) * noise_amp;

    float decay = clamp((1.0 - progress) / 0.32, 0.0, 1.0);
    float intensity = 0.0;
    float alpha = 0.0;
    float selective_glow = 0.0;

    if (effect_family == 0) {{
        // 刀光 Blade Arc Sweep
        float sweep = 1.0 - pow(1.0 - progress, 2.4);
        float head_a = -2.4 + sweep * 4.2;
        float ang_diff = mod(head_a - theta + 9.42477, 6.28318) - 3.14159;
        float arc_u = clamp(1.0 - ang_diff / 1.85, 0.0, 1.0) * step(0.0, ang_diff);
        float thick = 0.14 * pow(arc_u, 0.55) * (1.0 + 0.25 * n);
        float blade = clamp(1.0 - abs(r - 0.65 + 0.04 * n) / max(0.015, thick), 0.0, 1.0) * arc_u * decay;
        intensity = blade;
        alpha = step(0.12, blade);
        selective_glow = pow(blade, 2.0) * arc_u * glow_intensity;
    }} else if (effect_family == 1) {{
        // 冲击波 Shockwave Ring
        float rt = 1.0 - pow(1.0 - progress, 2.1);
        float r_cur = 0.12 + rt * 0.76;
        float ring_w = 0.12 * (1.0 - 0.55 * rt);
        float ring = clamp(1.0 - abs(r + n * 0.08 - r_cur) / max(0.015, ring_w), 0.0, 1.0) * (1.0 - rt);
        intensity = ring;
        alpha = step(0.12, ring);
        selective_glow = pow(ring, 2.0) * glow_intensity;
    }} else {{
        // 气爆 / 驻留场 Radial Burst & Sigil
        float spikes = pow(abs(cos(theta * 5.0 + n * 1.8)), 1.8);
        float max_r = (0.38 + 0.45 * spikes) * (1.0 - pow(1.0 - progress, 3.0));
        float burst = clamp(1.0 - r / max(0.05, max_r), 0.0, 1.0) * decay;
        intensity = burst;
        alpha = step(0.12, burst);
        selective_glow = pow(burst, 1.8) * glow_intensity;
    }}

    vec3 base_col = sample_menpai_palette(intensity);
    vec3 final_col = base_col + col_bright.rgb * selective_glow * 0.65;
    COLOR = vec4(final_col, alpha);
}}
"""


def export_engine_shader(family: str, menpai_id: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    menpai = MENPAI_PRESETS.get(menpai_id, MENPAI_PRESETS["azure_sword"])
    fam_idx = EFFECT_FAMILIES.index(family) if family in EFFECT_FAMILIES else 0

    def rgb_str(hex_c: str) -> str:
        r, g, b = _hex_to_rgb(hex_c)
        return f"{r/255.0:.3f}, {g/255.0:.3f}, {b/255.0:.3f}"

    pal = menpai["palette"]
    shader_code = GODOT4_SHADER_TEMPLATE.format(
        family=family,
        menpai_id=menpai_id,
        family_idx=fam_idx,
        noise_amp=menpai["noise_amp"],
        c0=rgb_str(pal[0]),
        c1=rgb_str(pal[1]),
        c2=rgb_str(pal[2]),
        c3=rgb_str(pal[3]),
        c4=rgb_str(pal[4]),
    )
    shader_path = out_dir / f"shd_vfx_{family}_{menpai_id}.gdshader"
    shader_path.write_text(shader_code, encoding="utf-8")
    print(f"Exported Godot 4 2D-native SDF shader: {shader_path}")
    return shader_path


# ============================================================================
# 4. INTERACTIVE HTML VISUAL STUDIO & ENCYCLOPEDIA GENERATOR
# ============================================================================

def build_comparison_sheet(
    family: str = "blade_arc",
    out_dir: Path = DEFAULT_EXPORT_DIR,
    canvas_size: int = 88,
) -> Path:
    """
    Renders a side-by-side comparison matrix of all 6 Menpai presets for a given family
    so the developer/agent can visually compare style grammar at a glance.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    sect_ids = list(MENPAI_PRESETS.keys())
    cols = len(sect_ids)
    rows = 2  # Row 0: Pure Pixel Mode, Row 1: HD Selective Glow Mode
    pad = 8
    header_h = 24
    sheet_w = cols * (canvas_size + pad) + pad
    sheet_h = rows * (canvas_size + pad) + header_h + pad

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (14, 17, 26, 255))
    draw = ImageDraw.Draw(sheet)

    for c_idx, m_id in enumerate(sect_ids):
        x0 = pad + c_idx * (canvas_size + pad)
        draw.text((x0 + 4, 5), m_id[:12], fill=(210, 225, 245, 255))

        comp_frames, base_frames, _ = render_vfx_sequence(
            family=family,
            menpai_id=m_id,
            rarity_id="epic",
            canvas_size=canvas_size,
            num_frames=9,
            mode="hd-bloom",
        )
        peak_idx = 3 if family != "qi_burst" else 4
        # Row 0: Pure Pixel Base
        sheet.alpha_composite(base_frames[peak_idx], (x0, header_h))
        # Row 1: HD Selective Glow
        sheet.alpha_composite(comp_frames[peak_idx], (x0, header_h + canvas_size + pad))

    out_path = out_dir / f"vfx_compare_{family}_menpai_matrix.png"
    sheet.save(out_path)
    print(f"Saved Menpai comparison matrix (Row 1: Pure Pixel, Row 2: Selective Glow): {out_path}")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="2D-Native Top-Down Procedural VFX Forge (Nenly Architecture)")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # 1. presets
    subparsers.add_parser("presets", help="List all 5 Effect Families, 6 Menpai Sects, and 4 Rarity Tiers")

    # 2. render
    p_render = subparsers.add_parser("render", help="Render a 2D-native procedural VFX strip & preview GIF")
    p_render.add_argument("--family", "-f", choices=EFFECT_FAMILIES, default="blade_arc", help="Effect family")
    p_render.add_argument("--menpai", "-m", choices=list(MENPAI_PRESETS.keys()), default="azure_sword", help="Menpai visual language preset")
    p_render.add_argument("--rarity", "-r", choices=list(RARITY_TIERS.keys()), default="epic", help="Rarity tier scaling")
    p_render.add_argument("--mode", choices=["hd-bloom", "pixel", "both"], default="both", help="Render mode: pure pixel, hd selective bloom, or both")
    p_render.add_argument("--frames", "-n", type=int, default=12, help="Frame count (default: 12 at 30 FPS)")
    p_render.add_argument("--size", "-s", type=int, default=96, help="Canvas size in pixels (default: 96)")
    p_render.add_argument("--y-scale", type=float, default=0.65, help="Top-down orthographic Y compression (default: 0.65)")
    p_render.add_argument("-o", "--output", default=str(DEFAULT_EXPORT_DIR), help="Output directory")

    # 3. compare
    p_comp = subparsers.add_parser("compare", help="Generate a visual comparison matrix across all 6 Menpai sects (Pixel vs Selective Bloom)")
    p_comp.add_argument("--family", "-f", choices=EFFECT_FAMILIES, default="blade_arc", help="Effect family to compare")
    p_comp.add_argument("-o", "--output", default=str(DEFAULT_EXPORT_DIR), help="Output directory")

    # 4. shader
    p_shd = subparsers.add_parser("shader", help="Export a 2D-native SDF Godot 4 .gdshader for a family & Menpai")
    p_shd.add_argument("--family", "-f", choices=EFFECT_FAMILIES, default="blade_arc")
    p_shd.add_argument("--menpai", "-m", choices=list(MENPAI_PRESETS.keys()), default="azure_sword")
    p_shd.add_argument("-o", "--output", default=str(DEFAULT_EXPORT_DIR))

    args = parser.parse_args()

    if args.command == "presets" or not args.command:
        print("=== 5 CANONICAL 2D TOP-DOWN EFFECT FAMILIES ===")
        for f in EFFECT_FAMILIES:
            print(f"  • {f}")
        print("\n=== 6 MENPAI (SECT) VISUAL LANGUAGE PRESETS ===")
        for k, v in MENPAI_PRESETS.items():
            print(f"  • {k:15s} | {v['name']} | {v['desc']}")
        print("\n=== 4 RARITY TIERS ===")
        for k, v in RARITY_TIERS.items():
            print(f"  • {k:10s} | scale={v['scale']}, sub_layers={v['sub_layers']}, particles={v['particles']}, glow={v['glow_mult']}")
        return

    out_dir = Path(args.output)

    if args.command == "render":
        comp_frames, base_frames, glow_frames = render_vfx_sequence(
            family=args.family,
            menpai_id=args.menpai,
            rarity_id=args.rarity,
            canvas_size=args.size,
            num_frames=args.frames,
            y_scale=args.y_scale,
            mode="hd-bloom",
        )
        stem = f"spr_vfx_{args.family}_{args.menpai}_{args.rarity}"
        if args.mode in ("pixel", "both"):
            p_base = save_strip_and_gif(base_frames, out_dir, f"{stem}_pixel", fps=30)
            print(f"Exported Pure Pixel strip: {p_base}")
        if args.mode in ("hd-bloom", "both"):
            p_hd = save_strip_and_gif(comp_frames, out_dir, f"{stem}_hd", fps=30)
            p_glow = save_strip_and_gif(glow_frames, out_dir, f"{stem}_glow", fps=30, save_gif=False)
            print(f"Exported HD Selective Bloom strip: {p_hd}")
            print(f"Exported Selective Glow additive strip: {p_glow}")

    elif args.command == "compare":
        build_comparison_sheet(family=args.family, out_dir=out_dir)

    elif args.command == "shader":
        export_engine_shader(args.family, args.menpai, out_dir)


if __name__ == "__main__":
    main()
