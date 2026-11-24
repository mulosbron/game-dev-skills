#!/usr/bin/env python3
"""Coyote time and input buffering simulator: shows exact frame-by-frame behavior.

Two edge-case scenarios are simulated frame by frame:
  ledge    Player presses jump LATE after walking off a platform edge.
  landing  Player presses jump EARLY before touching the ground.

Each late/early offset is swept and tabulated so you can see the exact millisecond
window and verify there are no off-by-one boundaries.

The `simulate` function mirrors assets/coyote_buffer.gd step-for-step and is verified
by tests/test_game_feel.py.

Usage:
  python feel_sim.py                                    # 6 coyote, 6 buffer, 60 fps
  python feel_sim.py --coyote-frames 4 --buffer-frames 8 --fps 30
  python feel_sim.py --json result.json
"""

import argparse
import json
import sys
from pathlib import Path

LAST_GROUND_FRAME = 9   # ledge scenario: grounded on frames 0..9, airborne after
LANDING_FRAME = 20      # landing scenario: touches ground on frame 20


def simulate(ground, press_frames, coyote_frames, buffer_frames):
    """Frame-by-frame input simulation. Returns frame indices where jumps trigger.

    ground: list[bool] indicating whether the character starts each frame on ground.
    press_frames: set[int] of frame indices where jump was pressed.
    Order matches assets/coyote_buffer.gd: record input, jump, update coyote, tick buffer.
    """
    jumps = []
    coyote = 0
    buffer = 0
    for i, on_ground in enumerate(ground):
        if i in press_frames:
            # +1 because buffer decrements at the end of the same frame.
            buffer = buffer_frames + 1
        if buffer > 0 and (on_ground or coyote > 0):
            jumps.append(i)
            buffer = 0
            coyote = 0
        coyote = coyote_frames if on_ground else max(coyote - 1, 0)
        buffer = max(buffer - 1, 0)
    return jumps


def sweep_ledge(coyote_frames, buffer_frames):
    """Late jump presses after stepping off a ledge."""
    rows = []
    max_late = coyote_frames + 3
    ground = [True] * (LAST_GROUND_FRAME + 1) + [False] * (max_late + 2)
    for delay in range(0, max_late + 1):
        frame = LAST_GROUND_FRAME + delay
        rows.append({"offset": delay, "jumped": bool(simulate(ground, {frame}, coyote_frames, buffer_frames))})
    return rows


def sweep_landing(coyote_frames, buffer_frames):
    """Early jump presses before touching the ground."""
    rows = []
    max_early = buffer_frames + 3
    ground = [False] * LANDING_FRAME + [True] * (max_early + 2)
    for early in range(0, max_early + 1):
        frame = LANDING_FRAME - early
        triggered = simulate(ground, {frame}, coyote_frames, buffer_frames)
        rows.append({
            "offset": early,
            "jumped": bool(triggered),
            "jump_frame": triggered[0] if triggered else None,
        })
    return rows


def run_sim(coyote_frames, buffer_frames, fps):
    """Run both sweeps and return structured summary dict."""
    ledge = sweep_ledge(coyote_frames, buffer_frames)
    landing = sweep_landing(coyote_frames, buffer_frames)
    coyote_window = sum(1 for r in ledge if r["offset"] >= 1 and r["jumped"])
    buffer_window = sum(1 for r in landing if r["offset"] >= 1 and r["jumped"])
    return {
        "fps": fps,
        "frame_sec": 1.0 / fps,
        "coyote_frames": coyote_frames,
        "buffer_frames": buffer_frames,
        "ledge": ledge,
        "landing": landing,
        "coyote_window_frames": coyote_window,
        "buffer_window_frames": buffer_window,
        "consistent": coyote_window == coyote_frames and buffer_window == buffer_frames,
    }


def _yes_no(ok):
    return "yes" if ok else "no"


def format_report(s):
    ms = 1000.0 / s["fps"]
    out = [
        "# Coyote Time and Input Buffering Simulation",
        "",
        f"Settings: coyote time {s['coyote_frames']} frames, input buffer {s['buffer_frames']} frames, "
        f"{s['fps']:g} fps (1 frame = {ms:.1f} ms).",
        "",
        "## Ledge Scenario: Player Presses Jump AFTER Leaving Platform",
        "",
        f"Character leaves the platform at the end of frame {LAST_GROUND_FRAME}. 'Delay' is frames after leaving.",
        "",
        "| Delay (frames) | Delay (ms) | Jumped? |",
        "|---|---|---|",
    ]
    for r in s["ledge"]:
        out.append(f"| {r['offset']} | {r['offset'] * ms:.0f} | {_yes_no(r['jumped'])} |")
    out += [
        "",
        "## Landing Scenario: Player Presses Jump BEFORE Touching Ground",
        "",
        f"Character lands on frame {LANDING_FRAME}. 'Early' is frames before landing.",
        "",
        "| Early (frames) | Early (ms) | Jumped? | Jump Frame |",
        "|---|---|---|---|",
    ]
    for r in s["landing"]:
        out.append(
            f"| {r['offset']} | {r['offset'] * ms:.0f} | {_yes_no(r['jumped'])} | "
            f"{'—' if r['jump_frame'] is None else r['jump_frame']} |"
        )
    out += ["", "## Summary", ""]
    if s["coyote_frames"] == 0:
        out.append("- Coyote time disabled: only jumps pressed while grounded trigger.")
    else:
        out.append(
            f"- Coyote time: jumps pressed within {s['coyote_window_frames']} frames "
            f"({s['coyote_window_frames'] * ms:.0f} ms) after leaving a ledge succeed; one frame later falls."
        )
    if s["buffer_frames"] == 0:
        out.append("- Input buffer disabled: only jumps pressed on the exact landing frame trigger.")
    else:
        out.append(
            f"- Input buffer: jumps pressed up to {s['buffer_window_frames']} frames "
            f"({s['buffer_window_frames'] * ms:.0f} ms) before landing trigger on the landing frame."
        )
    out.append("- Presses earlier than the buffer window expire cleanly and never cause double jumps.")
    if not s["consistent"]:
        out.append("- WARNING: effective window does not match configured frames; check simulation logic.")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Coyote time and input buffering simulator.")
    ap.add_argument("--coyote-frames", type=int, default=6, help="Frames after leaving ledge where jump is valid")
    ap.add_argument("--buffer-frames", type=int, default=6, help="Frames before landing to buffer jump input")
    ap.add_argument("--fps", type=int, default=60, help="Physics frame rate")
    ap.add_argument("--json", metavar="FILE", help="Also write results to JSON file")
    args = ap.parse_args(argv)

    if args.coyote_frames < 0 or args.buffer_frames < 0:
        print("ERROR: frame counts cannot be negative", file=sys.stderr)
        return 2
    if args.fps <= 0:
        print("ERROR: fps must be greater than zero", file=sys.stderr)
        return 2
    s = run_sim(args.coyote_frames, args.buffer_frames, args.fps)
    sys.stdout.write(format_report(s))
    if args.json:
        Path(args.json).write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if s["consistent"] else 1


if __name__ == "__main__":
    sys.exit(main())
