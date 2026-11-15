---
name: pixelfx
description: >-
  Make, search, customize, render and export 244+ procedural code-driven pixel art effects
  and animations (fire, explosions, water, ice, lightning, sci-fi, melee, impacts, projectiles,
  spawn/death, arcane, holy, shadow, status, nature, weather, UI, pickups, transitions, critters,
  moves with wind-up/hit-stop) using the patch-gg/pixelfx engine. Exports ready-to-use GameMaker
  '_stripN.png' files, Aseprite JSON, or creates new effects from code.
---

# PixelFX - Procedural Pixel Art Effects & Animation Skill

This skill manages the **244 procedural, code-driven pixel art effects and animations** located in `libraries\com.github.patch-gg.pixelfx`. All effects are deterministic, zero-hallucination code built using Hugo Duprez and Patch.gg's two-buffer architecture (`color` + additive `light` glow).

---

## ⚡ Quick CLI Commands (GameMaker Integration)

### 1. Effect Discovery (`list`)
Search effects by keyword, category, or tag:
```powershell
# Search sword slashes and strikes
python tools/pixelfx_tool.py list "slash"

# Search magic spells and novae
python tools/pixelfx_tool.py list "nova"

# List all 244 effects
python tools/pixelfx_tool.py list
```

### 2. Exporting for GameMaker (`export`)
Renders any effect and converts it directly into a GameMaker horizontal `spr_fx_<name>_stripN.png` along with pivot and FPS metadata:
```powershell
# Export Frost Nova for GameMaker:
python tools/pixelfx_tool.py export ice/frost-nova

# Export directly into a specific project's sprites folder:
python tools/pixelfx_tool.py export melee/sword-slash -o "projects\MyGame\sprites\"

# Mirror horizontally (face left):
python tools/pixelfx_tool.py export melee/sword-slash --flip
```

### 3. Palette Swapping (Recoloring)
Change an effect's colors without touching any code by supplying a hex ramp from dark to bright:
```powershell
# Turn fire into an ice/blue flame:
python tools/pixelfx_tool.py export fire/torch -p "#102" "#215" "#43a" "#8cf" "#fff"
```

### 4. Adding 2D Dynamic Lighting (Normal Maps)
Attach a normal map to a rendered effect strip:
```powershell
python tools/normal_map_gen.py "exports\com.github.patch-gg.pixelfx\spr_fx_frost_nova_strip103.png"
```

---

## 📂 Effect Categories Catalog (244 Effects)

| Category | Count | Sample Effects |
|---|---|---|
| **moves** | 12 | arrow shot, dash strike, earth stomp, fireball throw, ground pound, holy smite |
| **fire** | 12 | campfire, candle, fire breath, fire ring, fire tornado, torch |
| **explosions** | 12 | barrel explosion, big explosion, cartoon pow, firework burst |
| **water** | 12 | bubbles, drip, fountain, geyser, rain splash, ripples |
| **ice** | 10 | blizzard vortex, freeze, frost breath, frost nova, ice crystal, ice lance |
| **lightning** | 11 | ball lightning, chain lightning, charge up, electrified, plasma ball |
| **sci-fi** | 12 | emp blast, energy core, force field, glitch, hologram, jetpack |
| **melee** | 12 | claw swipe, dagger flurry, double slash, hammer smash, heavy cleave, scythe reap |
| **impacts** | 11 | blunt hit, bullet impact, critical hit, ground slam, hit flash |
| **projectiles** | 13 | arrow, bullet tracer, cannon shot, energy disc, homing missile |
| **spawn & death** | 10 | coin drop, disintegrate, dissolve burn, egg hatch, poof, respawn beam |
| **arcane** | 12 | arcane beam, arcane missiles, arcane orb, blink in/out, magic circle cast |
| **holy** | 10 | blessing, divine shield, feather burst, halo, heal, healing ring |
| **shadow** | 12 | black hole, curse, dark explosion, eclipse, grasping hands, hex sigil |
| **status** | 13 | bleeding, burning, charmed, confused, cursed, frozen |
| **nature** | 13 | acid splash, boulder, earth spike, healing bloom, leaf storm, poison cloud |
| **weather** | 12 | aurora, blizzard, cherry blossoms, clouds, falling leaves, fireflies |
| **ui** | 12 | achievement, coin collect, combo counter, confetti, countdown, crit number |
| **pickups** | 11 | chest open, coin spin, collect burst, crystal shard, gem spin, heart pickup |
| **transitions** | 10 | blinds, burn away, crt off, diamond wipe, glitch wipe, iris |
| **critters** | 12 | bat, bird, butterfly, eyeball, fish school, flying skull |

---

## 🎨 AI Agent Workflow for Authoring New Procedural Effects

When an AI agent creates a new procedural effect from scratch:

1. **Bootstrap Template:**
   ```powershell
   python tools/pixelfx_tool.py new arcane/my-spell
   ```
2. **Implement Drawing Logic:**
   Edit `libraries\com.github.patch-gg.pixelfx\src\fx\arcane\my-spell.js` using `draw(p, t, o)` (pure math) or `create(o)` (particle simulation).
3. **Render & Inspect:**
   ```powershell
   node libraries\com.github.patch-gg.pixelfx\tools\render.mjs arcane/my-spell --gif
   ```
4. **Automated Quality Checks:**
   ```powershell
   node libraries\com.github.patch-gg.pixelfx\tools\check.mjs arcane/my-spell
   ```
