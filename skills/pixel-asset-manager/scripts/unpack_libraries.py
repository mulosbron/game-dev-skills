#!/usr/bin/env python3
"""
Unpacks zip asset packages in libraries/ so they are ready for game development.
"""

import sys
import zipfile
from pathlib import Path

def _find_workspace_root() -> Path:
    curr = Path(__file__).resolve().parent
    for parent in [curr] + list(curr.parents):
        if (parent / "AGENTS.md").exists() or (parent / "libraries").exists():
            return parent
    return curr.parent

WORKSPACE_ROOT = _find_workspace_root()
LIBRARIES_DIR = WORKSPACE_ROOT / "libraries"

def unpack_zips(target_lib: str = "PixelSRPG-Forge", skip_large: bool = False):
    lib_path = LIBRARIES_DIR / target_lib
    if not lib_path.exists():
        print(f"Library not found: {lib_path}")
        return

    zips = list(lib_path.rglob("*.zip"))
    print(f"Found {len(zips)} zip packages in {target_lib}.")

    for z in zips:
        # Check size if skip_large
        size_mb = z.stat().st_size / (1024 * 1024)
        if skip_large and size_mb > 20:
            print(f"Skipping large pack ({size_mb:.1f} MB): {z.name}")
            continue

        out_dir = z.parent / z.stem
        if out_dir.exists() and any(out_dir.iterdir()):
            print(f"Already extracted: {z.name}")
            continue

        print(f"Extracting {z.name} ({size_mb:.1f} MB)...", end=" ", flush=True)
        try:
            with zipfile.ZipFile(z, 'r') as zip_ref:
                zip_ref.extractall(out_dir)
                print(f"Done ({len(zip_ref.namelist())} files).")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    skip = "--all" not in sys.argv
    unpack_zips(skip_large=skip)
