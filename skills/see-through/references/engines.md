# Engines

The math in `tools/see_through_lib.py` is the spec. `scripts/web/see-through.mjs` is the same functions. Ports below call that math; they do not invent a second rule.

## Godot 4

Files in `scripts/godot/`:

| File | Role |
| --- | --- |
| `see_through.gd` | On the occluder `Sprite2D`. Exports are the settings. |
| `see_through.gdshader` | Tested window. `discard`. Scale 1 only. |
| `see_through_scaled.gdshader` | Same rule divided by `pixel_scale`. The script preloads it when `pixel_scale != 1`. |
| `flat_color.gdshader` | Silhouette ghost. |
| `outline.gdshader` | Outline ghost. |
| `see_through_math.gd` | `godot --headless --script see_through_math.gd` |

`target` and this sprite: origin at the feet. `target_sprite` is the `Sprite2D` or `AnimatedSprite2D` the ghost copies. Dithered fade: `mode = DITHER`, `keep = 0.375`.

Debug: call `cycle_mode()` from input. Order: fade, dither (`keep` 0), dithered fade (`keep` 0.375), cutout, silhouette, outline.

`pixel_scale` is read in `_ready`. Set it in the inspector before play.

Existing shader: copy the `fragment()` discard from `see_through.gdshader` (or the scaled variant) into that shader. Keep its wind or outline code. Do not assign `_window` on top of it.

## Unity

Files in `scripts/unity/`. Y grows **up**. "Behind" is a greater feet Y. The center is `feet + (0, height/2)`.

`SeeThroughOccluder` on each scenery sprite. Assign `windowShader`, `flatShader`, `outlineShader` to the three shaders in this folder. Pivot of the occluder and the character: **bottom center**. `OpaqueAt` assumes that pivot; if the pivot is elsewhere, fix the sample before trusting the cover test.

The window material is an instance. Accessing `renderer.material` just to compare it would clone the default material, so the script tracks `_windowOn` and restores `sharedMaterial`.

Silhouette: a `SpriteMask` with a custom back/front range of `sortingOrder` .. `sortingOrder + 1`. The ghost sits at `sortingOrder + 1` and is `VisibleInsideMask`. Other sprites stay outside that range.

Dithered fade: `mode = Dither`, `keep = 0.375`.

If the sprite already has a shader, do not assign `SeeThrough/Window`. `#include "SeeThroughWindow.hlsl"` and call `SeeThroughClip(...)` at the top of the fragment, then keep the rest of the shader. `clip(-1)` drops the pixel.

`OpaqueAt` blits a non-readable texture once. A tree does not change atlases. If the occluder is animated, drop the cached `Texture2D` when the sprite changes.

## Canvas and Phaser

Import `scripts/web/see-through.mjs`.

```js
import { createOccluder, Look, characterCenter, applyWindowToRgba, defaultSettings } from "./see-through.mjs";

const tree = createOccluder({
  name: "tree",
  baseY: treeFeetY,
  look: Look.DITHERED_FADE,
  bounds: [treeX, treeY, treeW, treeH],
  opaqueAt: (x, y) => mask.isOpaque(x, y),
  settings: defaultSettings(),
});

function frame(dt) {
  tree.step(dt, player.feetX, player.feetY);
  const [cx, cy] = characterCenter(player.feetX, player.feetY, tree.settings.charHeight, true);
  if (tree.look === Look.FADE) {
    ctx.globalAlpha = tree.opacity();
    ctx.drawImage(treeImage, treeX, treeY);
    ctx.globalAlpha = 1;
  } else if (tree.amount > 0 && tree.look !== Look.SILHOUETTE && tree.look !== Look.OUTLINE) {
    const copy = new ImageData(new Uint8ClampedArray(treePixels.data), width, height);
    applyWindowToRgba(copy.data, width, height, treeX, treeY, cx, cy, tree.look, tree.amount, tree.settings);
    ctx.putImageData(copy, treeX, treeY);
  } else {
    ctx.drawImage(treeImage, treeX, treeY);
  }
}
```

Build `opaqueAt` from `getImageData` once, at art resolution, using the feet anchor (`texel_from_feet_anchor` in the Python tool describes the mapping). Do not call `getImageData` on the whole canvas every frame if the bitmap is static.

Cache the dropped `ImageData` only if the target cell and `amount` did not change. The player moves, so expect to rebuild while `amount > 0`.

Silhouette in Canvas: draw the player to an offscreen canvas, `destination-in` with the occluder image, then `source-in` a flat fill. Outline: run `outlineFromGrid` on that masked alpha and draw only those texels. Follow the player's frame and `flip`. Skip the offscreen work when `amount` is 0.

Phaser: same functions inside the sprite's render, or a WebGL pipeline that uses `SEE_THROUGH_FRAG` from the module. One pipeline **uniform set per sprite**. A shared uniform opens every tree.

`pixelScale` on `defaultSettings` must match the game, not the camera zoom.

## Custom engine

- Fade: vertex color or material alpha.
- Window: fragment discard / `clip()`. Pass the center in the same space as the interpolated world position. Divide by the art scale before `floor`.
- Silhouette: write the occluder into the stencil, draw the flat copy where the stencil is set. Or a sprite mask.
- Outline: that copy with the neighbor test, not a second stencil.

There is no tested port outside the math. The Godot shaders are the ones that were compared to a software raster of this rule. Treat Unity and the web shader strings as faithful translations of that rule, and run `self-test` plus one rendered frame if the engine can read it back.
