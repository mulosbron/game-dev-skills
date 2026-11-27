# Acceptance

The Python and JS tests cover the rows that do not need a GPU. Rendered frames, when the engine can read them back, should match the same decisions.

| Check | Expected |
| --- | --- |
| Feet level with the base, or in front | `amount` stays 0 |
| Feet 1 px behind, and the cover test passes | eases on |
| Inside the occluder box, under no opaque texel | fade / dither / cutout stay off |
| 3 of 12 points hidden | on |
| 2 of 12 | off |
| 60 fps, frame 1 = first behind frame | `amount` 0.5 after frame 6, 1 after frame 12 |
| 12 frames not behind, from 1 | `amount` 0 |
| `ease_time` 0 | goal on that frame |
| Fade fully on | opacity 0.4 |
| Dither fully on | no occluder pixel whose cell center is closer than 18 px; every pixel farther than 34 px kept; alpha is 0 or the original |
| Dithered fade fully on | inside 18 px, exactly the texels with Bayer < 6 (6 of 16); farther than 34 px all kept; no new RGB |
| `keep` 0.4 | the same 6 Bayer values as 0.375 |
| Cutout fully on | cell centers closer than 22 px dropped; the rest kept |
| Two occluders, player behind one | only that one's `amount` moves |
| Silhouette | copy visible only where the occluder covers the player; same position, frame, and flip |
| Outline | only edge texels, only where the occluder covers them, including when the player is flipped |
| `fade_to` 1, or dither radii both 0 (even with `keep` 0.375), or `hole_radius` 0 | frame matches the game with the effect absent |
| Outline sheet | `border-check` reports no opaque texels on the 1 px frame border |

Silhouette and outline still **switch on** from box overlap when the depth test passes. Pixels under empty parts of the box stay invisible because the mask clips them. Do not "fix" that by requiring the 3-of-12 test for those two looks; the mask is the test.

Headless: `python3 tools/see_through.py self-test` and `node scripts/web/see-through.test.mjs` must pass before you call the math done. A GPU frame is extra confirmation, not a substitute for those tests.
