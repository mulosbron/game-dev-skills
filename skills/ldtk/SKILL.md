---
name: ldtk
description: "Modern 2D level design tool (Level Designer Toolkit) for grid-based tilemaps, rule-based auto-tiling, entity metadata, collision layers, and multi-world layouts. Exports structured JSON maps readable by Godot, GameMaker, Phaser, and Unity."
---

# LDtk (2D Level Designer Toolkit) Skill

LDtk is located at `libraries\com.github.deepnight.ldtk`.

## Game Engine Integration

1. **Format:**
   LDtk saves all projects in clean, human-readable JSON `.ldtk` files with optional external level files.
2. **GameMaker Integration:**
   GameMaker projects can parse `.ldtk` files directly using GML `json_parse()` to instantiate tile layers, collision grids, and object entities automatically.
3. **Godot Integration:**
   Compatible with the official Godot LDtk importer plugin (`godot-ldtk-importer`) to convert LDtk files into TileMap and Node2D hierarchies at build time.
