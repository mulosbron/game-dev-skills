# Unity — shadowcasting, light, fog of war and enemy sight

Two pieces: a static `Shadowcast` C# class and a `Texture2D` light/fog
texture multiplied over the scene with an unlit multiply material.
(Tested logic only — mirror the Python reference `scripts/shadowcast.py`,
whose test battery passes; the C# below is a direct port of the same scan.)

## Deciding what to cast on

- Walls on a `Tilemap` aligned to cells → per tile: `w`/`h` are tilemap
  dimensions, wall = `tilemap.HasTile(cell)`.
- Freehand wall sprites / art not on the tile grid → per pixel: read the
  wall layer's `Texture2D` pixels (`GetPixels32()`), alpha > 0 = wall.
- If the project already uses Unity 2D lights with shadow casters
  (`Light` + composite/caster colliders), STOP and ask the user first.

## Walls grid

```csharp
// From a Tilemap:
bool WallAt(Tilemap map, Vector3Int c) => map.HasTile(c);

// From a wall sprite:
var pixels = wallTexture.GetPixels32();          // row-major, bottom-up!
// Unity textures start at the BOTTOM-left; flip the row index:
// walls[(h - 1 - y) * w + x] = pixels[y * w + x].a > 0
```

Watch the row order — a flipped grid makes the light obey mirrored walls.
`walls` means "blocks light", not "blocks movement": update it when a door
opens, then recast.

## Shadowcast.cs (direct port of the tested scan — copy, don't rewrite)

```csharp
using System.Collections.Generic;
using UnityEngine;

public static class Shadowcast {
    // The 8 slices around the origin, as (xx, xy, yx, yy).
    static readonly int[,] OCTANTS = {
        { 1, 0, 0,  1}, { 0,  1, 1, 0}, { 0, -1, 1, 0}, {-1, 0, 0,  1},
        {-1, 0, 0, -1}, { 0, -1, -1, 0}, { 0,  1, -1, 0}, { 1, 0, 0, -1}
    };

    // walls[y * w + x] == true where light can't pass. Returns the same
    // layout, true where the origin can see. Copy EXACTLY, float division
    // included — rewritten from memory, the slopes go wrong.
    public static bool[] Visible(bool[] walls, int w, int h, int cx, int cy, int radius) {
        var seen = new bool[w * h];
        if (radius <= 0 || cx < 0 || cy < 0 || cx >= w || cy >= h) return seen;
        seen[cy * w + cx] = true;
        for (int o = 0; o < 8; o++) {
            var open = new Stack<(int row, double start, double end)>();
            open.Push((1, 1.0, 0.0));
            while (open.Count > 0) {
                var (row, start, end) = open.Pop();
                if (start < end) continue;
                double newStart = 0.0;
                for (int j = row; j <= radius; j++) {   // rows, moving away
                    int dy = -j;
                    bool blocked = false;
                    for (int dx = -j; dx <= 0; dx++) {  // cells, outer edge first
                        double left  = (dx - 0.5) / (dy + 0.5);
                        double right = (dx + 0.5) / (dy - 0.5);
                        if (start < right) continue;
                        if (end > left) break;
                        int x = cx + dx * OCTANTS[o, 0] + dy * OCTANTS[o, 1];
                        int y = cy + dx * OCTANTS[o, 2] + dy * OCTANTS[o, 3];
                        bool inside = x >= 0 && x < w && y >= 0 && y < h;
                        if (inside && dx * dx + dy * dy < radius * radius)
                            seen[y * w + x] = true;
                        bool wall = !inside || walls[y * w + x];
                        if (blocked) {
                            if (wall) newStart = right;
                            else { blocked = false; start = newStart; }
                        } else if (wall && j < radius) {
                            blocked = true;
                            open.Push((j + 1, start, left));
                            newStart = right;
                        }
                    }
                    if (blocked) break;
                }
            }
        }
        return seen;
    }

    // Move an origin inside a wall to the nearest open cell.
    public static Vector2Int ResolveOrigin(bool[] walls, int w, int h, Vector2Int o) {
        if (o.x >= 0 && o.y >= 0 && o.x < w && o.y < h && !walls[o.y * w + o.x]) return o;
        for (int r = 1; r <= 2; r++)
            for (int dy = -r; dy <= r; dy++)
                for (int dx = -r; dx <= r; dx++) {
                    var p = new Vector2Int(o.x + dx, o.y + dy);
                    if (p.x >= 0 && p.y >= 0 && p.x < w && p.y < h && !walls[p.y * w + p.x])
                        return p;
                }
        return o;
    }
}
```

## Use 1 — torchlight

1. Recast only when the light's cell changes (per pixel at 368 x 176 /
   radius 92 this scan is ~1.6 ms even in optimized code; per tile it is
   negligible).
2. Write the result into a `Texture2D` (one pixel per cell or per art
   pixel), `filterMode = FilterMode.Point`, per seen pixel
   `t = Mathf.Pow(Mathf.Clamp01(1f - dist / radius), 0.8f)`,
   `v = Mathf.Ceil(t * 6f) / 6f` — clamp `v` to 1: `1f * 6f` can evaluate
   to `6.000001f` and produce a phantom 7th band. Per pixel, dilate wall
   tops 5 px (scaled: `5 * tilePixels / 16`) into wall cells touching a
   seen cell, or a wall facing the light keeps a 1 px lit edge.
3. Multiply over the scene: a full-screen quad (or UI `Image`) with
   material `Shader "Unlit/Multiply"`:

```shaderlab
Shader "Unlit/Multiply" {
    Properties { _MainTex ("Light", 2D) = "black" {} }
    SubShader {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Pass {
            Blend DstColor Zero          // destination * source
            SetTexture [_MainTex] { combine texture }
        }
    }
}
```

Keep the project's existing ambient/torch colors if it has them; the
guide's defaults are ambient `(0.045, 0.05, 0.09)` (additive pass) and
torch `(1.0, 0.80, 0.55) * 1.15` — with a pure multiply blend, fold ambient
in on the CPU when building the texture instead.

## Use 2 — fog of war

A second `bool[]` `explored`, allocated once when the level loads; after
every recast: `for (int i = 0; i < explored.Length; i++) explored[i] |= seen[i];`
Draw: seen → lit; explored & !seen → gray `(r+g+b)/3` scaled by
`(0.30, 0.32, 0.40)`; else black. Save `explored` with the level; never
clear it on a recast.

## Use 3 — enemy line of sight

```csharp
var sight = Shadowcast.Visible(walls, w, h, enemy.x, enemy.y, sightRange);
bool seesPlayer = sight[player.y * w + player.x];
```

Cast **from the enemy** — this scan is not symmetric (16% of per-tile pairs
that see each other only see one way). If stealth must be fair both ways,
ask the user and use symmetric shadowcasting (Albert Ford).

## Settings to expose

`lightRadius`, `sightRange` (cells), falloff `power` 0.8, `bands` 6,
`wallDilation` 5 px per 16 px tile, fog tint `(0.30, 0.32, 0.40)`, ambient,
torch color. Tell the user where they live (a `[Range]`-attributed config
ScriptableObject works well).

## Verify in-engine

Mirror `scripts/verify_shadowcast.py` (all 29 checks pass there) and add a
debug view of the raw `seen` grid plus a toggle that restores the old
radial light.
