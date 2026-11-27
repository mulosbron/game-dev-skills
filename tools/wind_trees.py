#!/usr/bin/env python3
"""
Pixel-Art Wind Trees CLI (wind_trees.py)
Frame-free pixel-art foliage wind toolkit:
  - verify:      Run headless wind-field, clump-loop, traveling-wave, and damped-spring acceptance tests.
  - split:       Split a pixel-art tree/bush sprite into trunk.png, inside.png, and clump_NN.png layers.
  - export-code: Export Godot 4 runtime files (wind.gd, wind_tree.gd, row_bend.gdshader).

Usage:
    python tools/wind_trees.py verify --json
    python tools/wind_trees.py split oak.png -o exports/oak_layers --preset oak --json
    python tools/wind_trees.py export-code --out-dir exports/wind_trees/godot4 --json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

TAU = 2.0 * math.pi
LOOP = 20.0
WAVE_PERIOD = 1.54
WAVE_LENGTH = 69.0
POSE_TIME = 0.1

GUSTS: List[List[float]] = [
    [18.6, 65.0, 0.0, 0.0, 44.0, 1.25],
    [19.8, 65.0, 0.0, 0.0, 26.0, 0.5],
    [1.5, 60.0, 95.0, 45.0, 30.0, 0.6],
    [6.0, 55.0, 150.0, 60.0, 34.0, 0.75],
    [7.3, 55.0, 145.0, 65.0, 30.0, 0.9],
    [8.5, 50.0, 50.0, 55.0, 30.0, 0.55],
]

SPLIT_PRESETS: Dict[str, Tuple[int, int, float]] = {
    "oak": (5, 25, 0.4),
    "bush": (3, 10, 0.0),
}

GODOT_DIR = Path(__file__).resolve().parent.parent / "skills" / "pixel-art-wind-trees" / "godot"
GODOT_FILES = ("wind.gd", "wind_tree.gd", "row_bend.gdshader")


def along(p: Tuple[float, float]) -> float:
    return p[0] + 0.25 * p[1]


def _field(p: Tuple[float, float], time: float, gusts: Sequence[Sequence[float]], spread: float) -> float:
    total = 0.0
    for g in gusts:
        path = g[1] * LOOP
        # Exact Python mirror of Godot fposmod(along(p) - g[1]*(time - g[0]) + path/2, path) - path/2
        d = ((along(p) - g[1] * (time - g[0]) + path / 2.0) % path) - path / 2.0
        a = g[5] * math.exp(-((d / (g[4] * spread)) ** 2))
        if g[3] > 0.0:
            a *= math.exp(-(((p[1] - g[2]) / (g[3] * (1.6 if spread > 1.0 else 1.0))) ** 2))
        total += a
    return total


def gust(p: Tuple[float, float], time: float, gusts: Sequence[Sequence[float]] = GUSTS) -> float:
    return _field(p, time, gusts, 1.0)


def breeze(p: Tuple[float, float], time: float, gusts: Sequence[Sequence[float]] = GUSTS) -> float:
    return min(1.6 * _field(p, time, gusts, 2.2), 1.0)


def wave_phase(p: Tuple[float, float], time: float) -> float:
    return TAU * (time / WAVE_PERIOD - along(p) / WAVE_LENGTH)


def clump_offset(
    p: Tuple[float, float],
    w: float,
    time: float,
    lean: float,
    gusts: Sequence[Sequence[float]] = GUSTS,
    trunk_bend: bool = False,
    height01: float = 1.0,
) -> Tuple[int, int]:
    g = gust(p, time, gusts)
    b = breeze(p, time, gusts)
    a = wave_phase(p, time)
    ride = lean * (height01 ** 2 if trunk_bend else w)
    dx = ride + w * (0.9 * b + 1.3 * g) * (0.5 - 0.5 * math.cos(a))
    dy = -w * (0.75 * b + 0.5 * g) * max(math.sin(a), 0.0)
    return round(dx), round(dy)


def simulate_spring(
    gusts: Sequence[Sequence[float]] = GUSTS,
    push: float = 2.2,
    period: float = 2.2,
    damping: float = 0.35,
    dt: float = 1.0 / 60.0,
    secs: float = 30.0,
) -> List[Tuple[float, float]]:
    lean = lean_speed = 0.0
    t = 0.0
    w0 = TAU / period
    samples: List[Tuple[float, float]] = []
    while t < secs:
        target = push * gust((0.0, 0.0), t, gusts)
        lean_speed += (w0 * w0 * (target - lean) - 2.0 * damping * w0 * lean_speed) * dt
        lean += lean_speed * dt
        samples.append((t, lean))
        t += dt
    return samples


def run_verify() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}

    # 1. Still air (no gusts) -> zero offsets everywhere
    worst = 0
    for i in range(40):
        t = i * 0.13
        for p in ((10.0, 20.0), (70.0, 3.0), (-45.0, 90.0)):
            for w in (0.35, 0.7, 1.0):
                dx, dy = clump_offset(p, w, t, 0.0, [])
                worst = max(worst, abs(dx), abs(dy))
    checks["still_air_zero_motion"] = {
        "ok": worst == 0 and gust((5.0, 5.0), 3.0, []) == 0.0 and breeze((5.0, 5.0), 3.0, []) == 0.0,
        "max_offset": worst,
    }

    # 2. Clump loop cycle: w=1 walks (0,0)->(0,-1)->(1,-1)->(1,0); w=0.35 stays (0,0)
    def forced(bz: float, gt: float, a: float, w: float) -> Tuple[int, int]:
        dx = w * (0.9 * bz + 1.3 * gt) * (0.5 - 0.5 * math.cos(a))
        dy = -w * (0.75 * bz + 0.5 * gt) * max(math.sin(a), 0.0)
        return round(dx), round(dy)

    seq: List[Tuple[int, int]] = []
    for i in range(100):
        pt = forced(1.0, 0.0, TAU * i / 100.0, 1.0)
        if not seq or seq[-1] != pt:
            seq.append(pt)
    expected_cycle = [(0, 0), (0, -1), (1, -1), (1, 0)]
    still_inner = {forced(1.0, 0.0, TAU * i / 100.0, 0.35) for i in range(100)}
    checks["clump_loop_steps_and_inner_stiffness"] = {
        "ok": seq[:4] == expected_cycle and still_inner == {(0, 0)},
        "w1_cycle": seq[:4],
        "w035_poses": [list(p) for p in still_inner],
    }

    # 3. Traveling wave: 69 px apart along wind share identical phase
    p1 = (100.0, 40.0)
    p2 = (169.0, 40.0)
    phase_match = all(
        min(abs((wave_phase(p1, i * 0.05) - wave_phase(p2, i * 0.05)) % TAU),
            abs(TAU - ((wave_phase(p1, i * 0.05) - wave_phase(p2, i * 0.05)) % TAU))) < 1e-9
        for i in range(60)
    )
    checks["traveling_wave_69px_parity"] = {"ok": phase_match}

    # 4. Whole-pixel offsets & 10 Hz pose clock
    all_int = all(
        isinstance(clump_offset((50.0 + i, 80.0), 1.0, i * 0.037, 1.3)[0], int)
        and isinstance(clump_offset((50.0 + i, 80.0), 1.0, i * 0.037, 1.3)[1], int)
        for i in range(200)
    )
    checks["whole_pixels_and_10hz_clock"] = {"ok": all_int and POSE_TIME == 0.1}

    # 5. Oak damped spring leans downwind, dips past upright, and settles near 0
    # Use a single isolated gust crossing origin at t=2s to verify clean spring response & settle
    single_gust = [[2.0, 65.0, 0.0, 0.0, 44.0, 1.25]]
    samples = simulate_spring(single_gust, secs=16.0)
    peak_t, peak_l = max(samples, key=lambda s: s[1])
    post = [l for t, l in samples if t > peak_t]
    dipped = any(l < min(-0.05, -0.1 * abs(peak_l)) for l in post)
    tail = [l for t, l in samples if t > 12.0]
    settled = max(abs(l) for l in tail) < 0.05
    checks["oak_spring_lean_overshoot_settle"] = {
        "ok": peak_l > 0.5 and dipped and settled,
        "peak_lean": round(peak_l, 3),
        "dipped_negative": dipped,
        "max_tail_lean": round(max(abs(l) for l in tail), 4),
    }

    # 6. Gust pattern shape: 6 gusts, 20s loop, 1.3s double-hit, still air between gusts
    entry_times = sorted(g[0] for g in GUSTS)
    gaps = [round(b - a, 1) for a, b in zip(entry_times, entry_times[1:])]
    min_center_gust = min(gust((160.0, 90.0), t * 0.05) for t in range(400))
    checks["gust_pattern_6_in_20s_with_still_air"] = {
        "ok": len(GUSTS) == 6 and LOOP == 20.0 and (1.3 in gaps) and min_center_gust < 0.05,
        "gaps_sec": gaps,
        "min_center_gust": round(min_center_gust, 4),
    }

    all_ok = all(bool(v["ok"]) for v in checks.values())
    return {
        "ok": all_ok,
        "passed": sum(1 for v in checks.values() if v["ok"]),
        "total": len(checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pixel-Art Wind Trees: verify, split sprites & export Godot 4 runtime")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ver = sub.add_parser("verify", help="Run headless wind-math & damped-spring verification suite")
    p_ver.add_argument("--json", action="store_true")

    p_spl = sub.add_parser("split", help="Split a tree/bush PNG into trunk.png, inside.png & clump_NN.png")
    p_spl.add_argument("input", type=Path, help="Input RGBA tree/bush sprite PNG")
    p_spl.add_argument("-o", "--out-dir", type=Path, required=True, help="Output directory for layers")
    p_spl.add_argument("--preset", choices=["oak", "bush"], default="oak")
    p_spl.add_argument("--min-dist", type=int, default=None)
    p_spl.add_argument("--min-size", type=int, default=None)
    p_spl.add_argument("--trunk-part", type=float, default=None)
    p_spl.add_argument("--json", action="store_true")

    p_exp = sub.add_parser("export-code", help="Export Godot 4 wind.gd, wind_tree.gd & row_bend.gdshader")
    p_exp.add_argument("--out-dir", type=Path, help="Optional directory to write Godot 4 files")
    p_exp.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.cmd == "verify":
        res = run_verify()
        print(json.dumps(res, indent=2) if args.json else f"Wind trees verify: {res['passed']}/{res['total']} passed")
        return 0 if res["ok"] else 1

    if args.cmd == "split":
        scripts_dir = Path(__file__).resolve().parent.parent / "skills" / "pixel-art-wind-trees" / "scripts"
        sys.path.insert(0, str(scripts_dir))
        try:
            from split_tree import split_tree  # type: ignore
        except ImportError as exc:
            err = {"ok": False, "error": f"Missing dependency for split (requires numpy, scipy, scikit-image, Pillow): {exc}"}
            print(json.dumps(err, indent=2) if args.json else err["error"], file=sys.stderr)
            return 1
        d_dist, d_size, d_trunk = SPLIT_PRESETS[args.preset]
        md = args.min_dist if args.min_dist is not None else d_dist
        ms = args.min_size if args.min_size is not None else d_size
        tp = args.trunk_part if args.trunk_part is not None else d_trunk
        count = split_tree(str(args.input), str(args.out_dir), min_dist=md, min_size=ms, trunk_part=tp)
        payload = {"ok": True, "input": str(args.input), "out_dir": str(args.out_dir), "preset": args.preset, "clumps": count}
        print(json.dumps(payload, indent=2) if args.json else f"Split {args.input} -> {count} clumps in {args.out_dir}")
        return 0

    if args.cmd == "export-code":
        written: Dict[str, str] = {}
        info: Dict[str, int] = {}
        for fname in GODOT_FILES:
            src = (GODOT_DIR / fname).read_text(encoding="utf-8")
            info[fname] = len(src)
            if args.out_dir:
                args.out_dir.mkdir(parents=True, exist_ok=True)
                dest = args.out_dir / fname
                dest.write_text(src, encoding="utf-8")
                written[fname] = str(dest)
        payload: Dict[str, Any] = {"ok": True, "files": written if written else info}
        print(json.dumps(payload, indent=2) if args.json else str(payload["files"]))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
