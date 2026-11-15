---
name: pixelorama
description: "Open-source pixel art and animation studio built with Godot Engine. Supports layers, cel animations, palette management, timeline scrubbing, tile creation, and batch spritesheet exporting."
---

# Pixelorama Skill

Pixelorama is an open-source 2D pixel editor and animation workstation located at `libraries\com.github.orama-interactive.pixelorama`.

## Usage & Integration

- **Run in Godot Engine:**
  Open `libraries\com.github.orama-interactive.pixelorama\project.godot` with Godot Engine 4.x or launch headlessly:
  ```powershell
  godot --path "libraries\com.github.orama-interactive.pixelorama"
  ```
- **Features for Game Pipelines:**
  - Layer-based non-destructive editing
  - Animation timeline with cel manipulation
  - Custom palette importation (.gpl, .pal, .png)
  - Seamless horizontal spritesheet exports (`_stripN.png`) for GameMaker compatibility
