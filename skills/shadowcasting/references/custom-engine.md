# Custom engine — shadowcasting on your collision grid

For a hand-rolled engine (SDL, raylib, LOVE2D, Pygame, monogame, whatever):
your collision grid IS the walls grid. One scan function serves all three
features; light/fog rendering is a multiply-blended texture or a per-pixel
CPU composite.

## Walls grid

- Use whatever boolean collision grid the engine already keeps, but decide
  per case: `walls` means "blocks light", not "blocks movement". A
  half-height barrier blocks movement but not light; a solid wall blocks
  both. If the engine has only one grid, ask the user which tiles block
  light before guessing.
- Rebuild/patch the grid when doors open or destructible walls change,
  then recast the affected lights.
- Per pixel: derive the grid from the wall layer's opaque pixels instead
  (see `scripts/shadowcast.py::walls_from_image`).

## The scan

Port `scripts/shadowcast.py::_shadowcast_flat` line for line — it is the
tested reference (29/29 checks pass). Copy the slope lines exactly, with
float division; rewritten from memory the slopes go wrong. Key properties
to preserve:

- A cell exactly `radius` away is NOT seen (`dx*dx + dy*dy < radius*radius`,
  strict), so sight range 10 reaches 9 cells straight ahead.
- `radius <= 0` or an origin outside the grid → all-false result, no crash.
- Origin inside a wall → only its 8 neighbors (thick wall) or leak both
  sides (1-cell-thin wall). Move the origin to the nearest open cell first
  (`resolve_origin`), on a tie picking the holder's side.

## Use 1 — torchlight

1. Recast when the light's cell changes (per tile it is cheap enough for
   every frame; per pixel at 368 x 176 / radius 92 it is ~4 ms in plain
   Python, ~1.6 ms in GDScript, sub-ms in compiled languages).
2. Build the light buffer, per cell/pixel: `seen` AND falloff
   `t = clamp(1 - dist/radius, 0, 1) ** 0.8`, quantized with
   `ceil(t * 6) / 6` (clamp the ceil to 1 — float `1/6` error can mint a
   phantom 7th band). Per pixel, spread the light `5 px` (per 16 px tile,
   scale with tile size) into wall cells touching a seen cell
   (`dilate_walls_top`), or wall tops facing the light stay 1 px edges.
3. Composite: `out = scene * (ambient + light * torch_color)` with the
   guide defaults ambient `(0.045, 0.05, 0.09)`, torch
   `(1.0, 0.80, 0.55) * 1.15` — or the project's own. Software renderer:
   do it per pixel in the final pass. GPU: upload the light buffer as a
   texture and multiply in a shader (`Blend DstColor Zero`, or a fragment
   multiply).

## Use 2 — fog of war

`explored` grid allocated once at level load, `explored |= seen` after
every recast. Colors: seen → lit; explored & !seen →
`gray(scene) * (0.30, 0.32, 0.40)` with `gray = (r+g+b)/3`; else black.
Save `explored` with the level (savegames); it only ever grows.

## Use 3 — enemy line of sight

Cast from the enemy's cell with its sight range; `seen[player_cell]` is the
answer. The scan is not symmetric (16% of per-tile pairs one-way on the
guide's map), so always cast from the observer; if stealth needs to be fair
both ways, ask the user about symmetric shadowcasting (Albert Ford).

## Settings to expose

`light_radius`, `sight_range` (cells or pixels), falloff `power` 0.8,
`bands` 6, `wall_dilation` 5 px per 16 px tile, fog tint
`(0.30, 0.32, 0.40)`, ambient, torch color. Tell the user where they live.

## Verify

Run `python scripts/verify_shadowcast.py` on the same grids your engine
uses (write the grid out as text, load it in the script), and add a debug
view that draws `seen` in-engine plus a toggle that restores the old light.
