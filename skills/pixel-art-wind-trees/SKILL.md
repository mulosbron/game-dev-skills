---
name: pixel-art-wind-trees
description: Animate pixel art trees/bushes/pines with hand-animated-looking wind in a 2D game. Keep the trunk still, move leaf clumps by whole pixels in a traveling wave, add gust patches that cross the map with still air between them. No animation frames needed. Includes an offline Python sprite splitter (watershed-based), a Godot 4 runtime (autoload wind + tree node + row-bend shader), and verification tests. Use when foliage only sways by bending the whole sprite, when asked to "add wind to trees", or when pixel art needs frame-free foliage animation.
source: https://www.spritecook.ai/blog/pixel-art-trees-wind-animation (SpriteCook, Nov 10 2026)
---

# Pixel Art Trees: Frame-Free Wind Animation

**Goal:** trees move like hand-animated pixel art — trunk stays put, leaf clumps step
by whole pixels, gusts roll across the map with still air between them.

**Before writing any code, inspect the user's project:**
engine + language, how trees are drawn and depth-sorted, texture filter
(must be nearest/point), any existing wind system, and the tree sprites themselves.
Fit into what exists; do not add a second parallel system. **Ask which trees to split first.**

## How it works

1. **Asset step (offline):** cut each tree into
   - a **trunk layer** (wood, roots, anything that must not move),
   - **one sprite per leaf clump** (each bright ball of leaves),
   - an **inside layer** (darker canopy copy, `color x 0.55`, eroded 2 px from the outline)
     that shows through gaps between clumps so lifted clumps never reveal the ground.
   All layers share the tree's canvas → they stack pixel-perfect at one position.
2. **Loop:** each clump walks a loop in whole pixels: rest → up → up+right → right → back.
3. **Traveling wave:** loop phase comes from the clump's world position along the wind,
   so a wave runs through the canopy and from tree to tree.
4. **Gusts:** a few gust patches cross the map. In a gust the loop widens 1→2-3 px and the
   tree leans downwind on a damped spring, then swings back past upright and settles.
   Away from gusts every offset is exactly zero.
5. **Pines/conifers:** cut into branch tiers at the narrowest rows (count leaf pixels per row).
   The thin trunk bends by sliding rows: `shift = round(lean * up^2)` px per row
   (up = 0 at foot, 1 at top) via a sprite shader. Tiers ride the trunk at their own height.

## Numbers that matter

Tested at 320x180 px, trees ~100 px tall. **Scale pixel distances with the user's art.**

| Parameter | Value |
|---|---|
| Pose rate | clumps change pose 10x/second (spring runs every frame) |
| Wave | 1.54 s per loop, 69 px between crests (~45 px/s travel) |
| push / seconds-per-swing / damping | oak 2.2 / 2.2 / 0.35 · bush 1.4 / 1.0 / 0.35 · pine 3.6 / 2.8 / 0.22 |
| Gusts | 6 in a 20 s pattern; speed 50–65 px/s; length 26–44 px; strength 0.5–1.25; half-height 45–65 px (0 = whole map); two come 1.3 s apart |
| Split params | oak: min_dist 5, min_size 25, trunk_part 0.4 · bush: 3, 10, 0 |

## Pseudocode

```
# SPLIT, offline, per tree
leaves = opaque pixels, not wood/bark colored, in the top 78% of the sprite
bright = gaussian_blur(luminance, sigma = 1.6)
seeds  = local maxima of bright inside leaves, >= min_dist px apart
clump  = watershed(-bright, seeds, mask = leaves)
drop clumps < min_size px or centered in the bottom trunk_part of the sprite
trunk  = opaque pixels in no clump
inside = clump pixels eroded 2 px from the outline, colors x 0.55

# WIND, gust g = (enter_time, speed, center_y, half_height, length, strength)
along(p) = p.x + 0.25 * p.y
field(p, spread) = sum over gusts g of a, where:
    path = g.speed * 20
    d = wrap(along(p) - g.speed * (time - g.enter_time), -path/2, path/2)
    a = g.strength * exp(-(d / (g.length * spread))^2)
    if g.half_height > 0:
        a *= exp(-((p.y - g.center_y) / (g.half_height * (1.6 if spread > 1 else 1)))^2)
gust(p)   = field(p, 1)
breeze(p) = min(1.6 * field(p, 2.2), 1)
phase(p)  = 2*PI * (time / 1.54 - along(p) / 69)

# TREE, every frame
k = 2*PI / spring_period
lean_speed += (k*k * (push * gust(foot) - lean) - 2 * damping * k * lean_speed) * dt
lean += lean_speed * dt
every 0.1 s, for each clump, p = its center in the world:
    w  = lerp(inner_stiffness, 1, distance_of_center_from_canopy_center normalized)
    a  = phase(p)
    dx = lean*w + w * (0.9*breeze(p) + 1.3*gust(p)) * (0.5 - 0.5*cos(a))
    dy = -w * (0.75*breeze(p) + 0.5*gust(p)) * max(sin(a), 0)
    clump.position = rest + (round(dx), round(dy))
```

## Files in this skill

- `tools/wind_trees.py` — unified CLI wrapper (`verify --json`, `split <sprite.png> -o <dir> --preset oak|bush --json`, `export-code --out-dir <dir> --json`).
- `scripts/split_tree.py` — offline splitter (numpy/scipy/scikit-image/Pillow).
  Usage: `python tools/wind_trees.py split oak.png -o oak_layers --preset oak --json` · bush: `--preset bush`
- `scripts/test_wind.py` — headless checks of the wind math + clump loop (pure Python mirrors).
- `godot/wind.gd` — autoload singleton named `Wind` (gust list lives here).
- `godot/wind_tree.gd` — on the tree Node2D, origin at the trunk foot. Per-tree settings live here as `@export`s.
- `godot/row_bend.gdshader` — whole-pixel row slide for bending trunks (pine), grass, reeds.

## Engine setup (Godot 4)

1. Add `wind.gd` as an autoload named **Wind**.
2. Node2D per tree, origin at the foot of the trunk, `wind_tree.gd` attached.
3. Children: `inside.png` Sprite2D, `trunk.png` Sprite2D, then a Node2D named **Clumps**
   with one Sprite2D per `clump_NN.png`. All share the same position (same canvas).
4. **Texture filter: Nearest** (project default or per-sprite).
5. Draw order: inside → trunk → clumps. Pine tiers bottom-up.
6. Bending trunks (pine): material with `row_bend.gdshader` on trunk + inside sprites,
   `trunk_bend = 1`, assign `trunk` in the inspector.

Per-plant settings:

| Plant | push | spring_period | damping | trunk_bend |
|---|---|---|---|---|
| Oak | 2.2 | 2.2 | 0.35 | 0 |
| Pine | 3.6 | 2.8 | 0.22 | 1 |
| Bush | 1.4 | 1.0 | 0.35 | 0 |

## Other engines (Unity / custom)

Not tied to Godot. You need: one sprite per clump (child SpriteRenderer / draw call),
a function giving wind at a point (port `wind.gd` ~40 lines), and a 0.1 s timer applying
rounded offsets. **In Unity y points up: flip `dy` and the y term of `along`.**

## Pitfalls

- Inside layer must reach everywhere clumps meet the trunk, or a lifted clump leaves a line of missing pixels.
- Constant small movement, random timing, or a new pose every frame all read as jitter. Loop shrinks to zero in still air; time by position; 10 poses/s.
- Round every offset to whole art pixels; nearest filtering only.
- One band of wind over the whole map moves everything at once — use several gusts on different paths.
- Dark brown outlines fail the wood color test and stay behind on the trunk layer — `add_outline()` in the script assigns outline pixels to the neighboring clump.
- y points down (Godot). Unity: flip dy and the y term in `along`.

## Check that it works (acceptance tests)

Run `python scripts/test_wind.py` for the math-level checks. In-engine debug view:

- [ ] All layers stacked at rest == original sprite, pixel for pixel.
- [ ] breeze=1, gust=0, w=1 clump steps through (0,0), (0,-1), (1,-1), (1,0); w=0.35 stays at (0,0).
- [ ] Two clumps 69 px apart along the wind show the same pose simultaneously.
- [ ] Every offset integer; no clump changes pose more than 10x/s.
- [ ] After a gust passes an oak, lean dips below zero, then settles at 0 with all clumps at (0,0).
- [ ] With no gusts, every tree matches its original sprite exactly.

## Where things live (tell the user)

- **Gust list:** `godot/wind.gd` → `var gusts` (also mirrored in `scripts/test_wind.py`).
- **Tree settings:** `godot/wind_tree.gd` `@export`s (per node in the Inspector) + the table above;
  split parameters live in the `split_tree.py` command line.

## Optional extras (from the source article)

Shadows (tree's current pose projected onto ground, sways with it), falling leaves
(2 px, shed only while a gust is on, carried by the same wind, flip flat/edge-on),
meadow streaks (grass turns one flat shade lighter where a gust passes).
