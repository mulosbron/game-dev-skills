#!/usr/bin/env python3
"""Jump physics calculator: derives initial velocity and gravity from target height and apex time.

Instead of guessing gravity and jump velocity by trial and error, specify two intuitive goals:
how high the jump should reach and how quickly it should hit the apex:

    v0   = 2h / t            (initial vertical velocity)
    g_up = 2h / t^2          (ascent gravity)
    g_dn = g_up * mult       (descent gravity; mult > 1 makes falling feel snappy/heavy)
    t_dn = sqrt(2h / g_dn)   (time from apex back to ground)

Usage:
  python jump_physics.py --height 96 --time-to-apex 0.28
  python jump_physics.py --height 96 --time-to-apex 0.28 --fall-multiplier 1.6 --character-height 32
  python jump_physics.py ... --json result.json
"""

import argparse
import json
import math
import sys
from pathlib import Path


def calculate(height, time_to_apex, fall_multiplier=1.0, fps=60.0, character_height=None, unit="px"):
    """Compute jump physics parameters. Raises ValueError on non-positive inputs."""
    if height <= 0:
        raise ValueError("height must be greater than zero")
    if time_to_apex <= 0:
        raise ValueError("time-to-apex must be greater than zero")
    if fall_multiplier <= 0:
        raise ValueError("fall-multiplier must be greater than zero")
    if fps <= 0:
        raise ValueError("fps must be greater than zero")
    if character_height is not None and character_height <= 0:
        raise ValueError("character-height must be greater than zero")

    v0 = 2.0 * height / time_to_apex
    g_up = 2.0 * height / time_to_apex ** 2
    g_dn = g_up * fall_multiplier
    t_dn = math.sqrt(2.0 * height / g_dn)
    result = {
        "unit": unit,
        "height": height,
        "initial_velocity": v0,
        "gravity_up": g_up,
        "gravity_down": g_dn,
        "fall_multiplier": fall_multiplier,
        "time_to_apex_sec": time_to_apex,
        "fall_time_sec": t_dn,
        "total_air_time_sec": time_to_apex + t_dn,
        "fps": fps,
        "time_to_apex_frames": time_to_apex * fps,
        "fall_time_frames": t_dn * fps,
        "total_air_time_frames": (time_to_apex + t_dn) * fps,
    }
    # Sanity check: fixed-step Euler integration as most engines execute per physics tick.
    dt = 1.0 / fps
    y, vy = 0.0, -v0
    highest = 0.0
    for _ in range(int(math.ceil(2 * (time_to_apex + t_dn) * fps))):
        vy += g_up * dt
        y += vy * dt
        highest = min(highest, y)
    result["euler_height"] = -highest
    result["euler_error_pct"] = 100.0 * (result["euler_height"] - height) / height
    if character_height:
        result["character_height"] = character_height
        result["height_in_characters"] = height / character_height
        result["initial_velocity_in_characters_sec"] = v0 / character_height
    return result


def format_table(s):
    u = s["unit"]
    lines = [
        "# Jump Physics Parameters",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Target height | {s['height']:g} {u} |",
        f"| Initial vertical velocity (v0) | {s['initial_velocity']:.1f} {u}/s |",
        f"| Gravity, rising | {s['gravity_up']:.1f} {u}/s² |",
        f"| Gravity, falling (multiplier {s['fall_multiplier']:g}) | {s['gravity_down']:.1f} {u}/s² |",
        f"| Time to apex | {s['time_to_apex_sec'] * 1000:.0f} ms ({s['time_to_apex_frames']:.1f} frames @ {s['fps']:g} fps) |",
        f"| Fall time | {s['fall_time_sec'] * 1000:.0f} ms ({s['fall_time_frames']:.1f} frames) |",
        f"| Total air time | {s['total_air_time_sec'] * 1000:.0f} ms ({s['total_air_time_frames']:.1f} frames) |",
    ]
    if "character_height" in s:
        lines += [
            f"| Height in character heights | {s['height_in_characters']:.2f}x |",
            f"| Initial velocity in character heights/s | {s['initial_velocity_in_characters_sec']:.1f}x/s |",
        ]
    lines += [
        "",
        "Euler check: fixed-step Euler integration reaches "
        f"{s['euler_height']:.1f} {u} ({abs(s['euler_error_pct']):.1f}% "
        f"{'below' if s['euler_error_pct'] < 0 else 'above'} target). This is discrete-step "
        "quantization; it shrinks at higher tick rates—fine-tune final values in-engine.",
    ]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Jump physics parameter calculator.")
    ap.add_argument("--height", type=float, required=True, help="Target apex height (in chosen unit)")
    ap.add_argument("--time-to-apex", type=float, required=True, help="Time from takeoff to apex (seconds)")
    ap.add_argument("--fall-multiplier", type=float, default=1.0, help="Falling gravity multiplier (1 = symmetric)")
    ap.add_argument("--fps", type=float, default=60.0, help="Physics tick rate for frame conversions")
    ap.add_argument("--character-height", type=float, default=None, help="Character height (same unit) for ratios")
    ap.add_argument("--unit", default="px", help="Length unit label (px, m, units, ...)")
    ap.add_argument("--json", metavar="FILE", help="Also write parameters to JSON file")
    args = ap.parse_args(argv)

    try:
        s = calculate(
            args.height,
            args.time_to_apex,
            args.fall_multiplier,
            args.fps,
            args.character_height,
            args.unit,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    sys.stdout.write(format_table(s))
    if args.json:
        Path(args.json).write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
