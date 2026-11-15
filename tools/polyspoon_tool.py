#!/usr/bin/env python3
"""
Polyspoon Procedural 3D Model Toolkit CLI
Integrates Polyspoon (com.github.ditlied.polyspoon) into Agent Game Forge.
Allows searching 20 procedural low-poly model families, inspecting parameters,
customizing shapes/colors, and generating reproducible GLB/FBX/OBJ/USDZ models.
"""

import sys
import os
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = WORKSPACE_ROOT / "catalogs" / "polyspoon_catalog.json"
RUNTIME_PATH = WORKSPACE_ROOT / ".polyspoon" / "runtime.mjs"
EXPORTS_DIR = WORKSPACE_ROOT / "exports" / "com.github.ditlied.polyspoon"


def load_catalog() -> List[Dict[str, Any]]:
    if not CATALOG_PATH.exists():
        if not RUNTIME_PATH.exists():
            print(f"Error: Polyspoon runtime not found at {RUNTIME_PATH}", file=sys.stderr)
            sys.exit(1)
        # Generate catalog
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(["node", str(RUNTIME_PATH), "catalog"], capture_output=True, text=True, check=True)
        catalog = json.loads(res.stdout)
        with open(CATALOG_PATH, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)
        return catalog
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_search(args: argparse.Namespace) -> None:
    catalog = load_catalog()
    query = args.query.lower().strip()
    matches = []
    for item in catalog:
        cid = item.get("id", "").lower()
        title = item.get("title", "").lower()
        desc = item.get("description", "").lower()
        if not query or query in cid or query in title or query in desc:
            matches.append(item)

    print(f"\nFound {len(matches)} Polyspoon model families matching '{args.query}':\n")
    print(f"{'ID':<20} | {'Title':<24} | {'Ver':<6} | {'Presets':<8} | Description")
    print("-" * 90)
    for m in matches:
        presets_count = len(m.get("presets", []))
        desc = (m.get("description", "")[:40] + "...") if len(m.get("description", "")) > 40 else m.get("description", "")
        print(f"{m['id']:<20} | {m.get('title', m['id']):<24} | {m.get('version', '1.0'):<6} | {presets_count:<8} | {desc}")
    print()


def cmd_inspect(args: argparse.Namespace) -> None:
    catalog = load_catalog()
    family_id = args.family.strip()
    match = next((m for m in catalog if m.get("id") == family_id), None)
    if not match:
        print(f"Error: Family '{family_id}' not found in catalog.", file=sys.stderr)
        sys.exit(1)

    print(f"\n================================================================================")
    print(f"Polyspoon Model Family: {match.get('title', family_id)} ({match.get('id')}) v{match.get('version')}")
    print(f"Description: {match.get('description')}")
    print(f"================================================================================\n")

    presets = match.get("presets", [])
    if presets:
        print("Available Presets:")
        for p in presets:
            print(f"  * {p.get('id'):<16} : {p.get('name')} - {p.get('description')}")
        print()

    controls = match.get("controls", [])
    print(f"Configurable Controls ({len(controls)} total):")
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for c in controls:
        grp = c.get("group", "general")
        groups.setdefault(grp, []).append(c)

    for grp, ctrls in groups.items():
        print(f"\n  [Group: {grp.upper()}]")
        for c in ctrls:
            key = c.get("key")
            label = c.get("label", key)
            kind = c.get("kind")
            default_val = c.get("default")
            unit = c.get("unit", "")
            hint = c.get("hint", "")

            if kind == "range":
                r_min = c.get("min")
                r_max = c.get("max")
                step = c.get("step")
                print(f"    - {key:<20} ({label}): range [{r_min} .. {r_max}] (step {step} {unit}), default={default_val}")
            elif kind == "choice":
                opts = [o.get("value") for o in c.get("options", [])]
                print(f"    - {key:<20} ({label}): choice {opts}, default='{default_val}'")
            elif kind == "toggle":
                print(f"    - {key:<20} ({label}): toggle boolean, default={default_val}")
            elif kind == "color":
                print(f"    - {key:<20} ({label}): hex color, default='{default_val}'")
            else:
                print(f"    - {key:<20} ({label}): {kind}, default={default_val}")
            if hint:
                print(f"        -> {hint}")
    print()


def cmd_build(args: argparse.Namespace) -> None:
    catalog = load_catalog()
    family_id = args.family.strip()
    match = next((m for m in catalog if m.get("id") == family_id), None)
    if not match:
        print(f"Error: Family '{family_id}' not found in catalog.", file=sys.stderr)
        sys.exit(1)

    params: Dict[str, Any] = {}
    if args.preset:
        preset_obj = next((p for p in match.get("presets", []) if p.get("id") == args.preset), None)
        if not preset_obj:
            print(f"Error: Preset '{args.preset}' not found for family '{family_id}'.", file=sys.stderr)
            sys.exit(1)
        params.update(preset_obj.get("parameters", {}))

    if args.parameters:
        try:
            extra = json.loads(args.parameters)
            params.update(extra)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON parameters string: {e}", file=sys.stderr)
            sys.exit(1)

    # Determine output folder
    if args.out:
        out_path = Path(args.out).resolve()
    else:
        preset_name = f"_{args.preset}" if args.preset else ""
        out_path = EXPORTS_DIR / f"{family_id}{preset_name}"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["node", str(RUNTIME_PATH), "build", "--family", family_id]
    if params:
        cmd.extend(["--parameters", json.dumps(params)])
    if args.formats:
        cmd.extend(["--formats", args.formats])
    cmd.extend(["--out", str(out_path)])

    print(f"Building Polyspoon asset '{family_id}' -> {out_path}...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Build failed with error:\n{res.stderr}\n{res.stdout}", file=sys.stderr)
        sys.exit(res.returncode)

    try:
        data = json.loads(res.stdout)
        geom = data.get("geometry", {})
        print(f"\nBuild Successful!")
        print(f"Output Directory : {data.get('output')}")
        print(f"Triangles        : {geom.get('triangles')}")
        print(f"Vertices         : {geom.get('vertices')}")
        print(f"Dimensions (m)   : {data.get('dimensions')}")
        print(f"GLB Hash         : {data.get('glbSha256')}")
        print(f"Files Generated  :")
        for f in out_path.iterdir():
            print(f"  * {f.name} ({f.stat().st_size:,} bytes)")
    except Exception:
        print(res.stdout)


def main():
    parser = argparse.ArgumentParser(description="Polyspoon Procedural 3D Asset Toolkit CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # search
    p_search = subparsers.add_parser("search", help="Search procedural model families")
    p_search.add_argument("query", nargs="?", default="", help="Keyword to search in families")

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect controls and presets for a model family")
    p_inspect.add_argument("family", help="Family identifier (e.g. cottage, bench, stylized-fox)")

    # build
    p_build = subparsers.add_parser("build", help="Build a customized 3D model")
    p_build.add_argument("--family", required=True, help="Family identifier")
    p_build.add_argument("--preset", default=None, help="Preset identifier")
    p_build.add_argument("--parameters", default=None, help="JSON string of parameter overrides")
    p_build.add_argument("--formats", default=None, help="Additional formats (obj, fbx, usdz, or all)")
    p_build.add_argument("--out", default=None, help="Output destination folder")

    args = parser.parse_args()
    if args.command == "search":
        cmd_search(args)
    elif args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "build":
        cmd_build(args)


if __name__ == "__main__":
    main()
