# Algorithm

Y grows downward unless the engine is y-up. The character position is the **feet**. `pixel_scale` is world units per art pixel.

## Ease

```
goal   = 1 if is_behind() else 0
amount = move amount toward goal by dt / ease_time    # ease_time <= 0: amount = goal
```

`move` does not overshoot. At `dt = 1/60` and `ease_time = 0.2` the step is `1/12`.

## Center

```
y-down: center = feet - (0, char_height / 2)
y-up:   center = feet + (0, char_height / 2)
```

## is_behind

```
y-down: if feet.y >= base_y: return false
y-up:   if feet.y <= base_y: return false

if look is silhouette or outline:
    return boxes_overlap(occluder, character)

hidden = 0
for ix in 0..grid_x-1:          # default 3
    for iy in 0..grid_y-1:      # default 4
        at = ((ix + 0.5) / grid_x - 0.5,  (iy + 0.5) / grid_y - 1) * char_size
        if not y_down: at.y = -at.y
        if opaque(feet + at): hidden += 1
return hidden > 0 and hidden >= cover_needed * grid_x * grid_y
```

`cover_needed` 0.25 and a 3×4 grid → threshold 3. The `hidden > 0` term still applies if `cover_needed` is 0.

## Fade

```
opacity = lerp(1, fade_to, amount)     # fully on, fade_to 0.4 → 0.4
```

## Pixel drop (dither, dithered fade, cutout)

Shared fragment rule. Cutout is `soft = 0`, `keep = 0`, `radius = hole_radius`. Dithered fade is `keep = 0.375`.

```
BAYER = [
   0,  8,  2, 10,
  12,  4, 14,  6,
   3, 11,  1,  9,
  15,  7, 13,  5
]

cell  = floor(world / pixel_scale)
d     = distance(cell + 0.5, target / pixel_scale)     # art pixels
reach = (radius + soft) * amount
solid = soft > 0 ? clamp((d - reach) / soft + 1, 0, 1) : (d >= reach ? 1 : 0)
solid = max(solid, keep)
# negative cells: mod is the positive remainder (GLSL mod, Python %)
if solid <= (BAYER[(cell.y mod 4) * 4 + (cell.x mod 4)] + 0.5) / 16:
    discard
```

Inside the clear radius with `keep` 0.375, `solid` is 0.375, so a pixel drops when its Bayer value is **>= 6**. Values 0, 1, 2, 3, 4, 5 stay. That is 6 of 16. `keep` 0.4 crosses the same step (`0.4 * 16 = 6.4`, Bayer >= 6).

With amount 1, dither radii 18 and 16:

- `d <= 18` → solid 0 → every pixel drops
- `d >= 34` → solid 1 → every pixel stays (the highest Bayer threshold is 15.5/16)
- between them, the Bayer pattern thins the sprite

Cutout, amount 1, radius 22, soft 0: drop when `d < 22`, keep when `d >= 22`. Distance is measured from the **cell center**, not the fragment corner.

Radius 0 and soft 0: `reach` is 0, `solid` is 1 for every `d >= 0`, then `max(1, keep)` is 1. Nothing drops, including when `keep` is 0.375.

## Apply

```
fade:            alpha = source_alpha * opacity          # blends
dither / cutout: alpha = drop ? 0 : source_alpha         # RGB unchanged
silhouette / outline: occluder unchanged
```

## Outline copy

```
inside = center_alpha >= 0.5
around = min(up, down, left, right)          # missing neighbors are 0
draw outline color if inside and around < 0.5, else nothing
```

## Silhouette copy

```
draw flat color if alpha >= 0.5, else nothing
```

The copy is clipped to the occluder's opaque texels by the engine (Godot clip children, Unity sprite mask, stencil, or destination-in).

## Two occluders

Step each occluder's `amount` on its own. The player standing behind one tree must not open the other. Do not write a global "player is hidden" flag that every tree reads.
