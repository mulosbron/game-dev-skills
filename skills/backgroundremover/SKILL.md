---
name: backgroundremover
description: "AI-powered background removal for sprites, concept art, character frames, and video clips using U2-Net deep learning models. Strips backgrounds and outputs clean RGBA transparency with alpha mattes."
---

# Background Remover Skill

Eliminates backgrounds from sprite stills and animation video clips without manual rotoscoping.

## Quick Start Commands

Located in `libraries\com.github.nadermx.backgroundremover`:

```powershell
# Remove background from a single sprite image:
python -m backgroundremover.cmd.cli -i "path/to/character.jpg" -o "path/to/character_clean.png"

# Remove background from an animated video or GIF clip:
python -m backgroundremover.cmd.cli -i "path/to/animation.mp4" -mk -o "path/to/animation_transparent.mov"

# Remove background and output transparent GIF:
python -m backgroundremover.cmd.cli -i "path/to/animation.mp4" -tg -o "path/to/animation.gif"
```
