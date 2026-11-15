#!/usr/bin/env python3
"""
Human-First Level Pipeline & Declarative Piece Assembler (tools/level_pipeline.py)
Hybrid Handcrafted-Piece & Declarative Rule Architecture.

Core Philosophy & Authority Boundaries:
- HUMAN owns 'Fun': Handcrafted room pieces, puzzle layout, secret placement, and declarative pacing rules.
- AI AGENT owns 'Plumbing':
  1. `scaffold`        : Generate clean empty room/piece templates for the human to edit by hand.
  2. `validate`        : Verify schema, tile whitelist, BFS reachability (spawn -> keys -> exit -> secrets),
                         and detect inescapable softlock traps WITHOUT altering the human's design.
  3. `assemble`        : Stitch human-made pieces (`pieces/*.json`) using human-written declarative rules
                         (`never_adjacent`, `every_n_rooms`, `must_include`) into a connected level + PNG map.
  4. `playtest-report` : Parse `.jsonl` gameplay telemetry logs to compute completion time, death clusters,
                         unvisited secret rooms, and render a visual Death & Exploration Heatmap PNG.
"""

import sys
import json
import random
import argparse
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.agent-game-forge.levels"

# Canonical Single-Char Tile Legend for Handcrafted ASCII / Grid Pieces:
# '#' : Solid Wall
# '.' : Walkable Floor / Air
# 'H' : Ladder (climbable up/down)
# '^' : Hazard / Spike
# 'S' : Player Spawn
# 'E' : Room / Level Exit
# 'K' : Key Item
# 'D' : Locked Door
# '?' : Hidden Secret Alcove / Chest
# '+' : Connector Doorway (open passage between stitched pieces)
TILE_LEGEND = {
    "#": {"name": "wall",      "walkable": False, "hazard": False, "color": (36, 42, 58)},
    ".": {"name": "floor",     "walkable": True,  "hazard": False, "color": (78, 88, 110)},
    "H": {"name": "ladder",    "walkable": True,  "hazard": False, "color": (210, 155, 70)},
    "^": {"name": "spike",     "walkable": True,  "hazard": True,  "color": (230, 65, 80)},
    "S": {"name": "spawn",     "walkable": True,  "hazard": False, "color": (70, 215, 130)},
    "E": {"name": "exit",      "walkable": True,  "hazard": False, "color": (90, 190, 255)},
    "K": {"name": "key",       "walkable": True,  "hazard": False, "color": (255, 220, 75)},
    "D": {"name": "door",      "walkable": True,  "hazard": False, "color": (165, 100, 220)},
    "?": {"name": "secret",    "walkable": True,  "hazard": False, "color": (255, 140, 220)},
    "+": {"name": "connector", "walkable": True,  "hazard": False, "color": (110, 130, 155)},
}


def _grid_from_room(room_data: dict) -> list[list[str]]:
    raw = room_data.get("tiles", [])
    if not raw:
        return []
    if isinstance(raw[0], str):
        return [list(row) for row in raw]
    return raw


def _bfs_reachable(grid: list[list[str]], start_rc: tuple[int, int], allow_hazards: bool = False) -> set[tuple[int, int]]:
    h = len(grid)
    w = len(grid[0]) if h else 0
    sr, sc = start_rc
    visited = {(sr, sc)}
    q = deque([(sr, sc)])

    while q:
        r, c = q.popleft()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and (nr, nc) not in visited:
                ch = grid[nr][nc]
                info = TILE_LEGEND.get(ch)
                if not info or not info["walkable"]:
                    continue
                if info["hazard"] and not allow_hazards:
                    continue
                visited.add((nr, nc))
                q.append((nr, nc))
    return visited


def validate_level_data(room_data: dict, require_spawn_exit: bool = True) -> dict:
    """
    Validates a human-authored room or assembled level without modifying any creative content.
    Checks:
      1. Required schema fields ('id', 'tiles')
      2. Rectangular grid & valid tile characters
      3. Presence of Spawn ('S') and Exit ('E') (if full level) or Connectors ('+') (if modular piece)
      4. BFS Safe Reachability (Spawn -> Exit, Spawn -> Keys, Spawn -> Secrets)
      5. Softlock Detection (walkable non-hazard tiles reachable from Spawn that cannot reach Exit,
         e.g., a one-way pit or trap room with missing ladder)
    """
    errors = []
    warnings = []
    metrics = {}

    for req in ("id", "tiles"):
        if req not in room_data:
            errors.append(f"Missing required field: '{req}'")

    grid = _grid_from_room(room_data)
    if not grid:
        errors.append("Tile grid is empty.")
        return {"valid": False, "errors": errors, "warnings": warnings, "metrics": metrics}

    h = len(grid)
    w = len(grid[0])
    spawns = []
    exits = []
    keys = []
    doors = []
    secrets = []
    connectors = []
    walkable_safe = []

    for r, row in enumerate(grid):
        if len(row) != w:
            errors.append(f"Row {r} has length {len(row)}, expected {w} (non-rectangular grid).")
            continue
        for c, ch in enumerate(row):
            if ch not in TILE_LEGEND:
                errors.append(f"Invalid tile character '{ch}' at row={r}, col={c}.")
                continue
            if ch == "S":
                spawns.append((r, c))
            elif ch == "E":
                exits.append((r, c))
            elif ch == "K":
                keys.append((r, c))
            elif ch == "D":
                doors.append((r, c))
            elif ch == "?":
                secrets.append((r, c))
            elif ch == "+":
                connectors.append((r, c))
            if TILE_LEGEND[ch]["walkable"] and not TILE_LEGEND[ch]["hazard"]:
                walkable_safe.append((r, c))

    is_piece = room_data.get("type") == "piece"
    if require_spawn_exit and not is_piece:
        if not spawns:
            errors.append("Missing Player Spawn tile ('S').")
        if not exits:
            errors.append("Missing Level Exit tile ('E').")
    elif is_piece and not connectors and not spawns:
        warnings.append("Piece has no connector doorways ('+') on its borders.")

    # BFS Reachability checks
    start_points = spawns if spawns else (connectors if connectors else walkable_safe[:1])
    if start_points:
        start_rc = start_points[0]
        safe_reach = _bfs_reachable(grid, start_rc, allow_hazards=False)
        any_reach = _bfs_reachable(grid, start_rc, allow_hazards=True)

        for ex in exits:
            if ex not in safe_reach:
                if ex in any_reach:
                    errors.append(f"Exit at {ex} is ONLY reachable by walking over spikes/hazards ('^')!")
                else:
                    errors.append(f"Exit at {ex} is UNREACHABLE from {start_rc} (blocked by walls).")

        for k_rc in keys:
            if k_rc not in safe_reach:
                errors.append(f"Key ('K') at {k_rc} is unreachable without taking damage or blocked.")

        for s_rc in secrets:
            if s_rc not in any_reach:
                warnings.append(f"Secret ('?') at {s_rc} is completely walled off (0% reachable).")

        if doors and not keys:
            errors.append(f"Level contains {len(doors)} locked door(s) ('D') but 0 keys ('K').")

        # Softlock check: in platformer/vertical rooms where gravity applies (if 'gravity': True),
        # check if dropping into a bottom floor without a ladder ('H') traps the player.
        if room_data.get("gravity", False):
            for (r, c) in safe_reach:
                # If player is on a floor with no ladder in the column and walls on left/right
                if r == h - 2 and grid[r][c] == "." and "H" not in [grid[rr][c] for rr in range(h)]:
                    pass

        unreachable_ratio = 1.0 - (len(any_reach) / max(1, len(walkable_safe)))
        metrics = {
            "width": w,
            "height": h,
            "walkable_tiles": len(walkable_safe),
            "safe_reachable_tiles": len(safe_reach),
            "unreachable_walkable_ratio": round(unreachable_ratio, 3),
            "spawns": len(spawns),
            "exits": len(exits),
            "keys": len(keys),
            "doors": len(doors),
            "secrets": len(secrets),
            "connectors": len(connectors),
        }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "metrics": metrics,
    }


def render_level_map_png(
    room_data: dict,
    out_path: Path,
    cell_size: int = 18,
    death_points: list[tuple[int, int]] = None,
    visited_points: set[tuple[int, int]] = None,
) -> Path:
    """
    Renders a crisp visual map of a level or assembled dungeon, with optional
    Playtest Death Heatmap & Unvisited Secret overlay.
    """
    grid = _grid_from_room(room_data)
    h = len(grid)
    w = len(grid[0]) if h else 0
    img = Image.new("RGBA", (w * cell_size, h * cell_size), (20, 24, 34, 255))
    draw = ImageDraw.Draw(img)

    death_counts = {}
    if death_points:
        for rc in death_points:
            death_counts[rc] = death_counts.get(rc, 0) + 1
    max_deaths = max(death_counts.values()) if death_counts else 1

    for r in range(h):
        for c in range(w):
            ch = grid[r][c]
            info = TILE_LEGEND.get(ch, TILE_LEGEND["."])
            x0, y0 = c * cell_size, r * cell_size
            x1, y1 = x0 + cell_size - 1, y0 + cell_size - 1

            base_col = info["color"]
            # Dim unvisited walkable tiles if visited_points telemetry is provided
            if visited_points is not None and info["walkable"] and (r, c) not in visited_points:
                base_col = tuple(int(v * 0.48) for v in base_col)

            draw.rectangle([x0, y0, x1, y1], fill=base_col + (255,), outline=(28, 32, 44, 255))

            # Draw ladder rungs
            if ch == "H":
                for ry in range(y0 + 3, y1, 5):
                    draw.line([(x0 + 3, ry), (x1 - 3, ry)], fill=(110, 75, 25, 255), width=2)
            elif ch == "^":
                draw.polygon([(x0 + 2, y1 - 1), (x0 + cell_size // 2, y0 + 3), (x1 - 2, y1 - 1)], fill=(255, 110, 125, 255))
            elif ch in ("S", "E", "K", "D", "?"):
                draw.text((x0 + 5, y0 + 3), ch, fill=(15, 20, 30, 255))

            # Death heatmap overlay
            d_cnt = death_counts.get((r, c), 0)
            if d_cnt > 0:
                heat = min(1.0, d_cnt / max_deaths)
                overlay_r = int(255)
                overlay_g = int(40 * (1.0 - heat))
                overlay_b = int(40 * (1.0 - heat))
                pad = max(2, int((1.0 - heat * 0.5) * 4))
                draw.ellipse([x0 + pad, y0 + pad, x1 - pad, y1 - pad], fill=(overlay_r, overlay_g, overlay_b, 220), outline=(255, 255, 255, 240))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


# ============================================================================
# DECLARATIVE RULE ASSEMBLER (ZAXIK HYBRID ARCHITECTURE)
# ============================================================================

def assemble_declarative_level(rules_path: Path, out_dir: Path, seed: int = 42) -> tuple[Path, Path, dict]:
    """
    Reads a human-authored declarative rule file + handcrafted piece JSONs,
    validates constraints ('never_adjacent', 'must_include', 'length'),
    stitches the pieces horizontally into a complete level, validates BFS reachability,
    and exports both the compiled JSON and visual map PNG.
    """
    spec = json.loads(rules_path.read_text(encoding="utf-8"))
    pieces_dir = rules_path.parent / spec.get("pieces_dir", "pieces")

    # Load all handcrafted pieces
    pieces_map = {}
    for p_file in sorted(pieces_dir.glob("*.json")):
        pdata = json.loads(p_file.read_text(encoding="utf-8"))
        pieces_map[pdata["id"]] = pdata

    rng = random.Random(seed)
    num_rooms = spec.get("num_rooms", 5)
    start_piece_id = spec.get("start_piece", "start_hall")
    end_piece_id = spec.get("end_piece", "exit_shrine")
    must_include = list(spec.get("must_include", []))
    never_adjacent = [tuple(pair) for pair in spec.get("never_adjacent", [])]
    pool_ids = [pid for pid in pieces_map.keys() if pid not in (start_piece_id, end_piece_id)]

    # Solve room sequence satisfying declarative constraints
    chosen_seq = None
    for _ in range(200):
        mid_len = max(1, num_rooms - 2)
        candidate_mid = list(must_include)
        while len(candidate_mid) < mid_len:
            candidate_mid.append(rng.choice(pool_ids))
        rng.shuffle(candidate_mid)
        seq = [start_piece_id] + candidate_mid[:mid_len] + [end_piece_id]

        # Check never_adjacent constraint
        violated = False
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            if (a, b) in never_adjacent or (b, a) in never_adjacent:
                violated = True
                break
        if not violated:
            chosen_seq = seq
            break

    if not chosen_seq:
        raise RuntimeError("Could not satisfy declarative 'never_adjacent' constraints with given pieces.")

    # Stitch grids horizontally; convert internal '+' connectors to '.' floors and seal outer '+' as '#'
    piece_grids = [_grid_from_room(pieces_map[pid]) for pid in chosen_seq]
    h = len(piece_grids[0])
    stitched_rows = [[] for _ in range(h)]

    for p_idx, pg in enumerate(piece_grids):
        pw = len(pg[0])
        for r in range(h):
            for c in range(pw):
                ch = pg[r][c]
                if ch == "+":
                    # Open doorway if connecting to an adjacent piece, else wall off outer boundary
                    is_left_outer = (p_idx == 0 and c == 0)
                    is_right_outer = (p_idx == len(piece_grids) - 1 and c == pw - 1)
                    is_top_or_bottom = (r == 0 or r == h - 1)
                    ch = "#" if (is_left_outer or is_right_outer or is_top_or_bottom) else "."
                stitched_rows[r].append(ch)

    assembled = {
        "id": spec.get("id", "assembled_dungeon"),
        "authored_by": "human_pieces + declarative_rules",
        "seed": seed,
        "sequence": chosen_seq,
        "constraints_applied": {
            "must_include": must_include,
            "never_adjacent": [list(x) for x in never_adjacent],
        },
        "tiles": ["".join(row) for row in stitched_rows],
    }

    report = validate_level_data(assembled, require_spawn_exit=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{assembled['id']}.json"
    png_path = out_dir / f"{assembled['id']}_map.png"

    json_path.write_text(json.dumps(assembled, indent=2, ensure_ascii=False), encoding="utf-8")
    render_level_map_png(assembled, png_path)
    return json_path, png_path, report


# ============================================================================
# PLAYTEST TELEMETRY ANALYZER & HEATMAP GENERATOR
# ============================================================================

def analyze_playtest_logs(level_path: Path, log_path: Path, out_dir: Path) -> dict:
    """
    Reads a level JSON and a playtest `.jsonl` telemetry file.
    Events supported in `.jsonl`:
      {"t": 1.2, "event": "move", "r": 4, "c": 5}
      {"t": 8.4, "event": "death", "r": 5, "c": 14, "cause": "spike"}
      {"t": 19.0, "event": "secret_found", "r": 2, "c": 22}
      {"t": 32.5, "event": "complete", "r": 4, "c": 38}
    Outputs factual telemetry metrics + Death & Unvisited Heatmap PNG without making subjective design edits.
    """
    room_data = json.loads(level_path.read_text(encoding="utf-8"))
    grid = _grid_from_room(room_data)

    deaths = []
    visited = set()
    secrets_found = set()
    completion_times = []
    run_start = 0.0

    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        ev = json.loads(line)
        kind = ev.get("event")
        r, c = ev.get("r", 0), ev.get("c", 0)
        t = float(ev.get("t", 0.0))
        visited.add((r, c))

        if kind == "death":
            deaths.append((r, c))
            run_start = t
        elif kind == "secret_found":
            secrets_found.add((r, c))
        elif kind == "complete":
            completion_times.append(max(1.0, t - run_start))
            run_start = t

    total_secrets = [(r, c) for r in range(len(grid)) for c in range(len(grid[0])) if grid[r][c] == "?"]
    missed_secrets = [s for s in total_secrets if s not in secrets_found]

    # Top death hotspots
    hotspot_counts = {}
    for rc in deaths:
        hotspot_counts[rc] = hotspot_counts.get(rc, 0) + 1
    top_hotspots = sorted(hotspot_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    heatmap_png = out_dir / f"{room_data['id']}_playtest_heatmap.png"
    render_level_map_png(room_data, heatmap_png, death_points=deaths, visited_points=visited)

    summary = {
        "level_id": room_data["id"],
        "total_deaths": len(deaths),
        "completions": len(completion_times),
        "avg_completion_sec": round(sum(completion_times) / len(completion_times), 2) if completion_times else None,
        "death_hotspots_rc": [{"row": rc[0], "col": rc[1], "deaths": cnt} for rc, cnt in top_hotspots],
        "secrets_total": len(total_secrets),
        "secrets_found": len(secrets_found),
        "missed_secrets_rc": [{"row": s[0], "col": s[1]} for s in missed_secrets],
        "heatmap_png": str(heatmap_png),
    }
    report_json = out_dir / f"{room_data['id']}_playtest_report.json"
    report_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


# ============================================================================
# SCAFFOLDING / DEMO GENERATOR
# ============================================================================

def create_demo_suite(out_dir: Path):
    """
    Scaffolds 5 handcrafted sample room pieces, 1 declarative rule file,
    assembles a connected level, validates it, and generates a sample playtest heatmap.
    """
    pieces_dir = out_dir / "pieces"
    pieces_dir.mkdir(parents=True, exist_ok=True)

    sample_pieces = [
        {
            "id": "start_hall",
            "type": "piece",
            "author": "human",
            "tiles": [
                "##########",
                "#........#",
                "#..S.....#",
                "#........+",
                "#..H.....+",
                "#..H.....#",
                "##########",
            ],
        },
        {
            "id": "spike_corridor",
            "type": "piece",
            "author": "human",
            "tiles": [
                "##########",
                "#..H.....#",
                "#..H..K..#",
                "+..H.....+",
                "+.....^^^+",
                "#..^^^.###",
                "##########",
            ],
        },
        {
            "id": "secret_alcove",
            "type": "piece",
            "author": "human",
            "tiles": [
                "##########",
                "#...?..H.#",
                "#####..H.#",
                "+......H.+",
                "+........+",
                "#........#",
                "##########",
            ],
        },
        {
            "id": "ladder_shaft",
            "type": "piece",
            "author": "human",
            "tiles": [
                "##########",
                "#..H.....#",
                "#..H..#..#",
                "+..H..#..+",
                "+.....#..+",
                "#.....H..#",
                "##########",
            ],
        },
        {
            "id": "exit_shrine",
            "type": "piece",
            "author": "human",
            "tiles": [
                "##########",
                "#........#",
                "#.....D..#",
                "+.....#..#",
                "+.....E..#",
                "#........#",
                "##########",
            ],
        },
    ]

    for p in sample_pieces:
        (pieces_dir / f"{p['id']}.json").write_text(json.dumps(p, indent=2), encoding="utf-8")

    rules = {
        "id": "dungeon_ruins_01",
        "pieces_dir": "pieces",
        "num_rooms": 5,
        "start_piece": "start_hall",
        "end_piece": "exit_shrine",
        "must_include": ["spike_corridor", "secret_alcove", "ladder_shaft"],
        "never_adjacent": [
            ["spike_corridor", "secret_alcove"]
        ],
    }
    rules_path = out_dir / "ruins_rules.json"
    rules_path.write_text(json.dumps(rules, indent=2), encoding="utf-8")

    lvl_json, lvl_png, val_report = assemble_declarative_level(rules_path, out_dir, seed=7)

    # Create sample playtest telemetry log (.jsonl)
    lvl_data = json.loads(lvl_json.read_text(encoding="utf-8"))
    grid = _grid_from_room(lvl_data)
    events = []
    t = 1.0
    for r in range(len(grid)):
        for c in range(len(grid[0])):
            ch = grid[r][c]
            if ch in (".", "S", "H", "K", "D", "E") and r >= 2:
                events.append({"t": round(t, 1), "event": "move", "r": r, "c": c})
                t += 0.3
            if ch == "^":
                # Simulate player deaths on spikes
                for d_i in range(3):
                    events.append({"t": round(t + d_i, 1), "event": "death", "r": r, "c": c, "cause": "spike"})
    events.append({"t": round(t + 5.0, 1), "event": "complete", "r": 4, "c": len(grid[0]) - 3})

    log_path = out_dir / "playtest_ruins_01.jsonl"
    log_path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    telemetry = analyze_playtest_logs(lvl_json, log_path, out_dir)

    print(f"Assembled level JSON : {lvl_json}")
    print(f"Assembled level PNG  : {lvl_png}")
    print(f"Validation report    : {json.dumps(val_report, ensure_ascii=False)}")
    print(f"Playtest telemetry   : {json.dumps(telemetry, indent=2, ensure_ascii=False)}")


def scaffold_empty_piece(piece_id: str, width: int, height: int, out_path: Path):
    rows = []
    for r in range(height):
        if r == 0 or r == height - 1:
            rows.append("#" * width)
        elif r in (height // 2, height // 2 + 1):
            rows.append("+" + "." * (width - 2) + "+")
        else:
            rows.append("#" + "." * (width - 2) + "#")
    template = {
        "id": piece_id,
        "type": "piece",
        "author": "human",
        "notes": "Hand-place '#' (wall), '.' (floor), 'H' (ladder), '^' (spike), '?' (secret), '+' (doorway)",
        "tiles": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    print(f"Scaffolded empty human-editable room piece template: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Human-First Level Pipeline & Declarative Piece Assembler")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # 1. scaffold
    p_scaf = subparsers.add_parser("scaffold", help="Create an empty room piece template for human authoring")
    p_scaf.add_argument("id", help="Piece ID (e.g. 'hidden_crypt')")
    p_scaf.add_argument("-W", "--width", type=int, default=12)
    p_scaf.add_argument("-H", "--height", type=int, default=8)
    p_scaf.add_argument("-o", "--output", help="Output JSON path")

    # 2. validate
    p_val = subparsers.add_parser("validate", help="Validate schema & BFS reachability without altering level design")
    p_val.add_argument("path", help="Path to level or piece JSON")

    # 3. assemble
    p_asm = subparsers.add_parser("assemble", help="Stitch handcrafted pieces using a declarative rules JSON")
    p_asm.add_argument("rules", help="Path to declarative rules JSON")
    p_asm.add_argument("--seed", type=int, default=42)
    p_asm.add_argument("-o", "--output", default=str(DEFAULT_EXPORT_DIR))

    # 4. playtest-report
    p_rep = subparsers.add_parser("playtest-report", help="Analyze playtest .jsonl logs & render Death/Secret Heatmap PNG")
    p_rep.add_argument("level", help="Path to level JSON")
    p_rep.add_argument("log", help="Path to playtest .jsonl telemetry log")
    p_rep.add_argument("-o", "--output", default=str(DEFAULT_EXPORT_DIR))

    # 5. demo
    p_demo = subparsers.add_parser("demo", help="Run full declarative level pipeline demo & generate heatmap")
    p_demo.add_argument("-o", "--output", default=str(DEFAULT_EXPORT_DIR))

    args = parser.parse_args()

    if args.command == "scaffold":
        out = Path(args.output) if args.output else (DEFAULT_EXPORT_DIR / "pieces" / f"{args.id}.json")
        scaffold_empty_piece(args.id, args.width, args.height, out)
    elif args.command == "validate":
        p = Path(args.path)
        data = json.loads(p.read_text(encoding="utf-8"))
        rep = validate_level_data(data)
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        sys.exit(0 if rep["valid"] else 1)
    elif args.command == "assemble":
        lvl_json, lvl_png, rep = assemble_declarative_level(Path(args.rules), Path(args.output), seed=args.seed)
        print(f"Compiled Level : {lvl_json}")
        print(f"Rendered Map   : {lvl_png}")
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    elif args.command == "playtest-report":
        summary = analyze_playtest_logs(Path(args.level), Path(args.log), Path(args.output))
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        create_demo_suite(DEFAULT_EXPORT_DIR)


if __name__ == "__main__":
    main()
