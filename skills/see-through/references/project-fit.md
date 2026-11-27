# Fit the project

Read the scene before adding files. The wrong default is a second component that ignores how the game already draws.

## What to find

| Question | Why it changes the patch |
| --- | --- |
| What sorts sprites? | The feet test must use that axis. If the project sorts by `y` ascending in a y-down world, `base_y` is the sprite origin and the origin is already the feet. |
| Is the origin the feet, the center, or the top-left? | Cover points and the window are computed from the feet. If the origin is the center, either move it (Y-sort usually wants the feet) or convert before the test. Do not convert twice. |
| Is each occluder a node/sprite? | Attach the script to that sprite. One `amount`, one material. |
| Are they tiles of one tilemap? | Stop. Tell the user a layer shares opacity and material. Ask before promoting trees to sprites. |
| Is there already a material? | Paste the discard into it. A sprite has one material. |
| What is `pixel_scale`? | Camera zoom is not the art scale. The scale is how many world units one texel of the texture covers in game space. Pixel-perfect at 1 texel = 1 world unit → `pixel_scale` 1. A sprite scaled 4× in the scene → `pixel_scale` 4, radii still 18 / 16 / 22 in art pixels. |
| How big is the character, in art pixels? | Scale radii by `height / 36`. The 20×36 numbers are not universal. |
| Does the sheet have a 1 px gap per frame? | Only the outline look needs it. Run the border check before relying on the edge shader. |

## What not to add

- A second Y-sort.
- A fullscreen post process. The window is per occluder, in that occluder's pixels.
- A shared `ShaderMaterial` resource. In Godot, `ShaderMaterial.new()` per sprite. In Unity, one `Material` instance per occluder. A shared asset opens every tree together.
- A new opacity on the tilemap layer.

## Asking for the look

One question, the six names, and the note that each sprite can differ:

> fade (40% opacity, blends), dither (hard hole that feathers with a Bayer pattern), dithered fade (same window, 6 of 16 pixels stay), cutout (hard hole, 22 px), silhouette (flat color on top of the scenery), outline (1 px edge). Which ones, and on which objects?

If they already named one, use it. Do not ask again.

## Per-object looks

The same script, a different `mode` / `keep` on each sprite. A large canopy can be dithered fade while a sign is a silhouette. That is the intended setup, not a special case.
