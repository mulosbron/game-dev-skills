#!/usr/bin/env python3
"""
Enemy & Boss Sprite Generator for 'Aestra: The Last Wish'
Generates 32 game-ready pixel-art animation strips (_stripN.png),
dynamic normal maps (_n.png), Godot 4 SpriteFrames (.tres), and .import files.
"""

import os
import sys
import math
import random
from pathlib import Path
from typing import List, Tuple, Dict, Any
import numpy as np
from PIL import Image, ImageDraw

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
ENEMIES_DIR = WORKSPACE_ROOT / "projects" / "nos" / "assets" / "enemies"
NORMALS_DIR = ENEMIES_DIR / "normals"
NORMAL_MAP_TOOL = WORKSPACE_ROOT / "tools" / "normal_map_gen.py"

# Ensure output directories exist
ENEMIES_DIR.mkdir(parents=True, exist_ok=True)
NORMALS_DIR.mkdir(parents=True, exist_ok=True)

print(f"[Init] Output directory: {ENEMIES_DIR}")
print(f"[Init] Normals directory: {NORMALS_DIR}")
