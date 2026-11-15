#!/usr/bin/env python3
"""
Procedural Pixel Creatures CLI & GameMaker Bridge
Generates infinite procedural pixel art creatures in 9 families with walk, idle, run animations,
breeds/mutates genomes, and exports GameMaker-ready '_stripN.png' files and dynamic lighting normal maps.
Backed by: https://github.com/idlerunner00/procedural-pixel-creatures (com.github.idlerunner00.procedural-pixel-creatures)
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CREATURES_REPO = WORKSPACE_ROOT / "libraries" / "com.github.idlerunner00.procedural-pixel-creatures"
HARNESS_DLL = CREATURES_REPO / "tools" / "core_harness" / "bin" / "Release" / "net8.0" / "CoreHarness.dll"
HARNESS_CSPROJ = CREATURES_REPO / "tools" / "core_harness" / "CoreHarness.csproj"
DEFAULT_EXPORT_DIR = WORKSPACE_ROOT / "exports" / "com.github.idlerunner00.creatures"
NORMAL_MAP_TOOL = WORKSPACE_ROOT / "tools" / "normal_map_gen.py"

def find_dotnet() -> str:
    """Locates the .NET CLI executable across Windows, macOS, and Linux."""
    for env_var in ("DOTNET_EXE", "DOTNET_ROOT"):
        env_val = os.environ.get(env_var)
        if env_val:
            p = Path(env_val)
            if p.is_file():
                return str(p.resolve())
            exe_name = "dotnet.exe" if sys.platform == "win32" else "dotnet"
            if (p / exe_name).is_file():
                return str((p / exe_name).resolve())

    which_dotnet = shutil.which("dotnet")
    if which_dotnet:
        return which_dotnet

    exe_name = "dotnet.exe" if sys.platform == "win32" else "dotnet"
    candidates = [
        CREATURES_REPO / ".tools" / "dotnet" / exe_name,
        Path.home() / ".dotnet" / exe_name,
        Path("/usr/local/share/dotnet") / exe_name,
        Path("/usr/share/dotnet") / exe_name,
        Path("C:/Program Files/dotnet/dotnet.exe") if sys.platform == "win32" else Path("/opt/homebrew/bin/dotnet"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve())

    return "dotnet"

def ensure_built():
    """Ensures CoreHarness is built and available."""
    if not HARNESS_DLL.exists():
        print("[creature_gen] Building CoreHarness.dll...", file=sys.stderr)
        dotnet_bin = find_dotnet()
        cmd = [dotnet_bin, "build", "-c", "Release", str(HARNESS_CSPROJ)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[Error] Failed to build CoreHarness: {res.stderr}", file=sys.stderr)
            sys.exit(1)

def run_harness(args: list) -> subprocess.CompletedProcess:
    """Executes the CoreHarness CLI via dotnet exec."""
    ensure_built()
    dotnet_bin = find_dotnet()
    cmd = [dotnet_bin, "exec", str(HARNESS_DLL)] + args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

def cmd_list(args):
    """Lists all available creature families."""
    res = run_harness(["list-families"])
    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

def cmd_generate(args):
    """Generates procedural creature sprites and strips."""
    out_dir = Path(args.out) if args.out else (DEFAULT_EXPORT_DIR / (args.name or f"{args.family}_{args.seed or 'rnd'}"))
    out_dir.mkdir(parents=True, exist_ok=True)

    harness_args = [
        "generate",
        "--family", args.family,
        "--out", str(out_dir),
        "--clips", args.clips,
        "--dirs", args.dirs,
        "--fps", str(args.fps),
        "--shadow", str(args.shadow).lower(),
        "--strips", str(args.strips).lower(),
        "--sheet", str(args.sheet).lower(),
        "--still", str(args.still).lower(),
        "--preset", str(args.preset).lower()
    ]

    if args.seed is not None:
        harness_args += ["--seed", str(args.seed)]
    if args.name:
        harness_args += ["--name", args.name]
    if args.json:
        harness_args += ["--json"]

    res = run_harness(harness_args)
    if res.returncode != 0:
        print(f"[Error] Generation failed:\n{res.stderr or res.stdout}", file=sys.stderr)
        sys.exit(res.returncode)

    print(res.stdout)

    # Optional normal map generation
    if args.normal_map and NORMAL_MAP_TOOL.exists():
        for png_file in out_dir.glob("*.png"):
            if not png_file.stem.endswith("_n"):
                subprocess.run([sys.executable, str(NORMAL_MAP_TOOL), str(png_file)], capture_output=True)
        print(f"[Normal Maps] Generated 2D normal maps for sprites in: {out_dir}")

    # Optional copy to GameMaker project
    if args.project:
        target_dir = WORKSPACE_ROOT / "projects" / args.project / "sprites"
        target_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for f in out_dir.glob("spr_*.png"):
            shutil.copy2(f, target_dir / f.name)
            copied += 1
        print(f"[Project Export] Copied {copied} sprites into {target_dir}")

def cmd_mutate(args):
    """Mutates a creature genome preset into offspring."""
    out_dir = Path(args.out) if args.out else DEFAULT_EXPORT_DIR / "mutations"
    out_dir.mkdir(parents=True, exist_ok=True)

    harness_args = [
        "mutate",
        "--parent", str(args.parent),
        "--out", str(out_dir),
        "--count", str(args.count),
        "--strength", str(args.strength)
    ]
    if args.seed is not None:
        harness_args += ["--seed", str(args.seed)]

    res = run_harness(harness_args)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)

def cmd_breed(args):
    """Crossbreeds two creature genome presets."""
    out_dir = Path(args.out) if args.out else DEFAULT_EXPORT_DIR / "breeding"
    out_dir.mkdir(parents=True, exist_ok=True)

    harness_args = [
        "breed",
        "--parent-a", str(args.parent_a),
        "--parent-b", str(args.parent_b),
        "--out", str(out_dir),
        "--count", str(args.count),
        "--strength", str(args.strength)
    ]
    if args.seed is not None:
        harness_args += ["--seed", str(args.seed)]

    res = run_harness(harness_args)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)

def main():
    parser = argparse.ArgumentParser(
        description="Procedural Pixel Creatures: 9 families, infinite code-driven sprites, GameMaker strips & genetics."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List registered creature families and archetypes")
    p_list.set_defaults(func=cmd_list)

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate a procedural creature")
    p_gen.add_argument("--family", default="quadruped", help="Family ID: quadruped, biped, reptile, arthropod, winged, serpent, aquatic, amorphous, plantfolk")
    p_gen.add_argument("--seed", type=int, default=None, help="Specific RNG seed (reproducible output)")
    p_gen.add_argument("--name", default=None, help="Custom sprite/creature name")
    p_gen.add_argument("--clips", default="idle,walk", help="Comma-separated clips: idle,walk,run,action,hit,sleep,all")
    p_gen.add_argument("--dirs", default="S", help="Directions: S (front), cardinal (4-dir), all (8-dir), or 0-7")
    p_gen.add_argument("--fps", type=int, default=12, help="Animation FPS (6, 10, 12, 15, 20, 30)")
    p_gen.add_argument("--no-shadow", dest="shadow", action="store_false", default=True, help="Disable drop shadow")
    p_gen.add_argument("--no-strips", dest="strips", action="store_false", default=True, help="Disable GameMaker strips")
    p_gen.add_argument("--sheet", action="store_true", default=False, help="Export packed spritesheet atlas + json")
    p_gen.add_argument("--no-still", dest="still", action="store_false", default=True, help="Disable still PNG")
    p_gen.add_argument("--no-preset", dest="preset", action="store_false", default=True, help="Disable genome JSON")
    p_gen.add_argument("--normal-map", action="store_true", help="Automatically generate dynamic normal maps for sprites")
    p_gen.add_argument("--project", default=None, help="Target GameMaker project in 'projects/' to import sprites into")
    p_gen.add_argument("--out", default=None, help="Output directory")
    p_gen.add_argument("--json", action="store_true", help="Output summary in JSON format")
    p_gen.set_defaults(func=cmd_generate)

    # mutate
    p_mut = subparsers.add_parser("mutate", help="Mutate a creature genome preset")
    p_mut.add_argument("--parent", required=True, help="Path to parent genome.json")
    p_mut.add_argument("--count", type=int, default=4, help="Number of mutated offspring")
    p_mut.add_argument("--strength", type=float, default=0.35, help="Mutation drift (0.0 to 1.0)")
    p_mut.add_argument("--seed", type=int, default=None, help="Mutation seed")
    p_mut.add_argument("--out", default=None, help="Output directory")
    p_mut.set_defaults(func=cmd_mutate)

    # breed
    p_brd = subparsers.add_parser("breed", help="Crossbreed two creature presets")
    p_brd.add_argument("--parent-a", required=True, help="Path to parent A genome.json")
    p_brd.add_argument("--parent-b", required=True, help="Path to parent B genome.json")
    p_brd.add_argument("--count", type=int, default=4, help="Number of hybrid offspring")
    p_brd.add_argument("--strength", type=float, default=0.25, help="Mutation drift")
    p_brd.add_argument("--seed", type=int, default=None, help="Breeding seed")
    p_brd.add_argument("--out", default=None, help="Output directory")
    p_brd.set_defaults(func=cmd_breed)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
