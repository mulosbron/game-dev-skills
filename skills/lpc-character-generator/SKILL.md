---
name: lpc-character-generator
description: "Universal LPC (Liberated Pixel Cup) modular character generator and animator. Assembles 89,000+ modular body parts, clothing, armor, hairstyles, and weapons into standard 64x64 pixel animation sheets and GameMaker '_stripN.png' files with 100% automated legal attribution ledgers (CREDITS.csv)."
---

# Universal LPC Character Generator Skill

The **Liberated Pixel Cup (LPC)** is the gold standard for modular, open-source 2D pixel art character animation.
The entire generator library and asset repository is installed at:
`libraries\com.github.liberatedpixelcup.universal-lpc-spritesheet-character-generator`

---

## 📐 The LPC Grid & Animation Standard (64×64)

LPC characters are drawn on strict **64×64 pixel integer grid cells**.

### 1. The Classic 832×1344 Composite Spritesheet
Contains 21 vertical rows and 13 horizontal columns:
* **Rows 0–3:** `spellcast` (7 frames per direction, rows: Up, Left, Down, Right)
* **Rows 4–7:** `thrust` (8 frames per direction, rows: Up, Left, Down, Right)
* **Rows 8–11:** `walk` (9 frames per direction, rows: Up, Left, Down, Right)
* **Rows 12–15:** `slash` (6 frames per direction, rows: Up, Left, Down, Right)
* **Rows 16–19:** `shoot` / `bow` (13 frames per direction, rows: Up, Left, Down, Right)
* **Row 20:** `hurt` / `fall` (6 frames, Down direction only)

### 2. Directional Row Ordering
In every 4-row animation sheet:
* **Row 0 (y: 0..63):** Facing **North / Up**
* **Row 1 (y: 64..127):** Facing **West / Left**
* **Row 2 (y: 128..191):** Facing **South / Down** (Default Front)
* **Row 3 (y: 192..255):** Facing **East / Right**

### 3. Extended Animations Available
* `run` (8 frames per direction, 512×256)
* `jump` (8 frames per direction, 512×256)
* `climb` (6 frames, 384×64)
* `idle` (2 frames per direction, 128×256)
* `sit` (3 frames per direction, 192×256)
* `emote` (3 frames, 192×64)

---

## 🧱 Modular Layering & Z-Ordering

Modular parts must be composited in strict back-to-front Z-order to prevent clipping:
1. `shadow` (Floor contact)
2. `cape_back` / `quiver` / `backpack_bg` (Behind body)
3. `body` (Gender: male, female, muscular, pregnant, teen, child; skin tones: light, amber, bronze, brown, dark, orc green, skeleton)
4. `eyes` (Color: blue, brown, green, gray, purple, red, yellow)
5. `facial` / `expression`
6. `legs` (Pants, skirts, plate greaves)
7. `feet` (Shoes, boots, armored sabatons)
8. `torso` (Shirts, tunics, chainmail, plate cuirass, robes)
9. `arms` (Bracers, gloves, gauntlets)
10. `beards` / `mustache`
11. `hair` (60+ hairstyles)
12. `hat` / `headwear` (Helmets, wizard hats, bandanas, crowns)
13. `weapon` (Swords, staves, bows, daggers, maces)
14. `shield` (Bucklers, kite shields, heater shields)

---

## 🛠️ CLI Builder Utility (`tools/lpc_character_builder.py`)

AI agents can search among 89,000+ modular parts and assemble characters programmatically:

### 1. Search Parts
```powershell
# Search for helmets or wizard hats
python tools/lpc_character_builder.py search "wizard" --category hat

# Search for swords or polearms
python tools/lpc_character_builder.py search "sword" --category weapon
```

### 2. Build with Ready Presets
Presets available: `warrior`, `mage`, `rogue`, `peasant`.

```powershell
# Build full classic 832x1344 sheet
python tools/lpc_character_builder.py build --preset warrior -o "exports\com.github.liberatedpixelcup.lpc\warrior.png"

# Build walk animation and export GameMaker-ready horizontal strip:
python tools/lpc_character_builder.py build --preset mage --anim walk --gamemaker-strip --direction down -o "exports\com.github.liberatedpixelcup.lpc\mage_walk.png"
```

### 3. Build Custom Layered Character
```powershell
python tools/lpc_character_builder.py build \
  --body "body/bodies/female" \
  --legs "legs/pants/thin" \
  --feet "feet/boots/basic/thin" \
  --torso "torso/armour/leather/thin" \
  --hair "hair/ponytail/adult" \
  --weapon "weapon/melee/dagger/basic/thin" \
  --anim slash \
  --gamemaker-strip \
  --direction down \
  -o "exports\com.github.liberatedpixelcup.lpc\custom_rogue.png"
```

---

## ⚖️ Commercial Clearance & Legal Attribution (Credits)

* **100% Commercial Use Allowed:** LPC assets are licensed under **CC-BY-SA 3.0/4.0**, **CC-BY 3.0/4.0**, **OGA-BY 3.0**, **CC0 1.0**, and **GPL 3.0**.
* **Automatic Attribution Ledger:** Every time `tools/lpc_character_builder.py` builds an asset, it parses `CREDITS.csv` and outputs `<character_name>_credits.txt` containing all contributing artists, licenses, URLs, and notes.
* **Game Inclusion:** Simply copy the contents of `<character_name>_credits.txt` into your game's credits screen or `CREDITS.txt` file in your distribution to be 100% legally compliant.
