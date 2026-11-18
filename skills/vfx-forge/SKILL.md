---
name: vfx-forge
description: "Author, customize, compare, and export 2D-native top-down procedural pixel VFX and Godot 4 / GameMaker shaders using Nenly's Wuxia Survivors 5-Family SDF + Selective Glow + Menpai Preset architecture (blade_arc, shockwave, qi_burst, aoe_zone, projectile)."
---

# 2D-Native Top-Down Procedural VFX Forge (`vfx-forge`)

This skill implements the **2D-Native Procedural SDF VFX Architecture** pioneered in top-down Wuxia action/survivor games (*《群侠传：幸存者》 / Nenly's VFX Studio*). Instead of squashing 3D shaders onto a 2D plane (which ruins attack range readability and makes every skill look like a recolored template), this system authors VFX natively in **2D Top-Down Orthographic Ground Coordinates (`y_scale = 0.65`)** with **Dual-Buffer Selective Glow** and **Menpai (Sect) Visual Language Presets**.

---

## 🏛️ The 4 Architectural Pillars

### 1. Five Canonical 2D Effect Families (`Spawn → Sustain → Decay`)
Never cram unrelated motion mechanics into one monolithic shader. Every skill belongs to one of 5 dedicated 2D SDF families:

| Family ID | Wuxia Archetype | 2D SDF & Lifecycle Mechanics |
| :--- | :--- | :--- |
| `blade_arc` | **刀光 (Blade / Sword Light)** | Parametric crescent ring swept along $\theta(t)$ with ease-out velocity, white-hot tip flash, and tapered angular trail. |
| `shockwave` | **冲击波 (Shockwave Ring)** | Elliptical ground-plane ring expanding from center with FBM edge distortion and a **crisp outer telegraph ring** for 100% hitbox readability. |
| `qi_burst` | **气爆 (Radial Qi Burst)** | Two-stage lifecycle: rapid inward implosion (`t < 0.22`) followed by a multi-spike radial starburst that hollows out as it decays. |
| `aoe_zone` | **驻留场 (Persistent Ground Zone)** | Rotating polygonal/runic formation projected onto the 2D ground plane (`y_scale`) with pulsing boundary rings and rising screen-space motes. |
| `projectile` | **飞行体 (Flying Projectile)** | Directed spearhead/crescent SDF with sinusoidal/vortex wake trail and rarity-scaled particles. |

### 2. Dual-Buffer Selective Glow (No Full-Screen Bloom Washout!)
Full-screen post-process bloom destroys pixel art contrast. `tools/vfx_forge.py` renders **two separate buffers per frame** at **30 FPS**:
1. **`_pixel_stripN.png` (Crisp Indexed Base):** Quantized to a strict 5-band palette and 2-tier alpha.
2. **`_glow_stripN.png` (Selective Emission Layer):** Only high-energy regions (blade leading edge, burst core, runic nodes) emit into the glow buffer.
3. **`_hd_stripN.png` (Hybrid HD + Pixel Composite):** Combines the 100% sharp pixel base with the soft selective glow layer—allowing **Pure Pixel Mode** and **HD Light Mode** from the exact same code!

### 3. Menpai (Sect / School) Visual Language Presets
A sect's identity is defined by **Palette + Shape Grammar (Polygonal Symmetry + FBM Noise) + Particle Character**, not just a color tint:
* `azure_sword` (**青云剑派**): Cold cyan-silver, 8-fold symmetry, razor-low noise (`0.15`), high sharpness (`0.90`).
* `crimson_demon` (**血魔宗**): Black-red to molten crimson, chaotic FBM flame turbulence (`0.78`), jagged edges.
* `golden_buddha` (**少林金光**): Sacred bronze-gold, octagonal lotus geometry (`facets=8`), low noise (`0.12`).
* `jade_poison` (**唐门万毒**): Swamp violet to acid emerald, organic cellular bubbling (`0.62`), 5-fold symmetry.
* `frost_lotus` (**玄冰宫**): Deep navy to diamond cyan, hexagonal ice crystal facets (`facets=6`), ultra-crisp (`0.94`).
* `void_thunder` (**紫霄雷法**): Void purple to electric magenta, high-frequency jagged plasma noise (`0.88`).

### 4. Iterative Visual Language Dictionary (Prompt → Parameter Mapping)
When the user critiques a visual preview using natural language, translate directly to SDF parameters:
* *"Make it more pixelated / retro"* → Use `--mode pixel` or increase `pixel_scale` / lower `pixel_grid`.
* *"Make the edges harder / sharper"* → Increase `sharpness` (`0.90+`) and lower `noise_amp` (`0.10–0.20`).
* *"Make it more chaotic / wild / fiery"* → Increase `noise_amp` (`0.75+`) and set `angular_facets = 0`.
* *"The range / area on the ground isn't clear enough"* → Adjust `--y-scale 0.65` and boost outer telegraph ring contrast.
* *"Make the center denser / more explosive"* → Upgrade `--rarity legendary` or boost `glow_mult`.

---

## ⚡ CLI Usage (`tools/vfx_forge.py`)

### 1. List All Families, Menpai Presets & Rarity Tiers
```powershell
python tools/vfx_forge.py presets
```

### 2. Render an Effect (Outputs Pure Pixel Strip, Selective Glow Strip, HD Hybrid Strip & 30fps GIF)
```powershell
# Render an Epic Azure Sword Blade Arc:
python tools/vfx_forge.py render --family blade_arc --menpai azure_sword --rarity epic

# Render a Legendary Crimson Demon Shockwave:
python tools/vfx_forge.py render --family shockwave --menpai crimson_demon --rarity legendary

# Render a Persistent Golden Buddha AoE Zone:
python tools/vfx_forge.py render --family aoe_zone --menpai golden_buddha --rarity epic
```

### 3. Visual Studio Matrix Comparison (`compare`)
Renders all 6 Menpai sects side-by-side (Row 1: Pure Pixel Mode, Row 2: HD Selective Bloom Mode) so you and the user can compare variants visually before picking one:
```powershell
python tools/vfx_forge.py compare --family blade_arc
python tools/vfx_forge.py compare --family shockwave
```

### 4. Export Native Engine Shaders (`shader`)
Generates a standalone **Godot 4 `.gdshader`** with pixel-grid UV snapping, 2D orthographic ground projection, Menpai 5-band palette quantization, and selective glow:
```powershell
python tools/vfx_forge.py shader --family blade_arc --menpai azure_sword
```
