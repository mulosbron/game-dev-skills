# Pitfalls

## Bounding box instead of opaque pixels

A tree's rectangle is mostly empty corners. On the tree this was measured against, the boxes overlapped **10 px** before 3 of the 12 cover points were hidden. That is a visible window beside a character who is still in the open. Depth first, then the opaque samples. Silhouette and outline are the exception, because the mask tests the real texels.

## Dithering the whole sprite

A checkerboard over the entire canopy is hard to look at, and the player flickers: each step shows the other half of their pixels. Drop pixels only inside the window. Outside `clear_radius + soft` the sprite is solid.

## Tilemap layer

A tile layer is one drawable. Setting its alpha fades every tile on it. Setting its material opens every tile. Promote the things the player walks behind to their own sprites, and only after saying so.

## One material slot

Assigning the window shader replaces wind, palette swap, or an outline that was already there. Paste the `discard` / `clip()` block into the existing shader. The uniforms (`target`, `amount`, `radius`, `soft`, `keep`, `pixel_scale`) are extra uniforms on that shader, not a new material stack.

## Origin

The code treats the character position as the feet. With a centered origin the 3×4 points and the window sit half a body too high, so the hole opens around the head and the feet test is wrong. Y-sort wants the feet anyway. If you cannot move the origin, subtract `(0, height/2)` once (y-down) at the boundary and document it. The Godot script does not do that subtraction for you.

## Art scale

`floor(world)` is one art pixel only when one world unit is one texel. A sprite scaled up in the editor, or a camera that maps several world units onto a texel, needs `floor(world / pixel_scale)` and a target in the same space. Radii are art pixels either way. Zooming the camera does not by itself change `pixel_scale` if the world is already in art pixels.

## Ghost lifetime

`clip_children` and the duplicated sprite turn off when `amount` hits 0. Leaving them on costs a draw and, with clipping, can hide children that are not the ghost. One ghost per occluder. Silhouette ↔ outline changes `shader` and the color uniform on that ghost.

## Outline and the sprite sheet

The edge test reads the texel above, below, left, and right. If frame N touches frame N+1, the right edge samples frame N+1 and those outline pixels disappear. The guide measured about 40 missing outline pixels over one walk on a sheet with no gap. Pad every frame by at least 1 transparent pixel, then run:

```bash
python3 tools/see_through.py border-check sheet.png --frame-width W --frame-height H
```

## Fade and pixel art

Fade is a blend. The guide's scene gained more than 3,000 colors that are in none of the sprites. Dither, dithered fade, and cutout added none. Silhouette and outline add their one color. On hard pixel art, prefer a window or a silhouette unless the user asked for fade.

## Shared state

A global shader parameter for "the" tree target makes every occluder open around the player, including ones they are not behind. Set the uniform on that sprite's material.

## Half-transparent dither

`alpha = solid` is not this effect. It blends, which is fade's job, and it softens the Bayer pattern into new colors. The test is `solid <= bayer_threshold` then drop, else write the original pixel.

## Cover grid on the wrong box

The 12 points use `target_size`, the visible body (20×36 in the test), not the texture size if the texture has padding. A padded texture makes `is_pixel_opaque` correct for the tree, but the points are still spaced over `target_size`. If `target_size` is the texture size including empty rows, the points drift off the body.
