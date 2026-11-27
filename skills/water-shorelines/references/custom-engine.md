# Custom engine — integration recipe

For any engine with a fragment shader and sprite/texture drawing. The
pipeline is engine-agnostic; the Godot and Unity references show the same
math in concrete dialects.

## Pipeline

1. **Land mask** — the land layer's own pixels (alpha > 0) at art resolution.
   One bool per pixel. Never per tile.
2. **Bake at load** (once, not per frame):
   - Exact Euclidean distance transform: set land px to 0, water to 1e20,
     run the Felzenszwalb & Huttenlocher 1D pass down every column and along
     every row (see below), sqrt. This matches scipy's
     `distance_transform_edt(~land)` exactly.
   - Add smooth static noise: Gaussian-blurred white noise (sigma 8 px)
     rescaled to std dev 2 px (about ±3 px of wobble), taken from **world
     position** in chunked worlds.
   - Clamp to MAX_DIST and store 8-bit grayscale, same size and origin as the
     land layer: `map8 = clamp(d / MAX_DIST, 0, 1) * 255`.
   - Reference implementation: `tools/water_shorelines.py` (scipy path and pure-NumPy Felzenszwalb-Huttenlocher fallback; export GLSL or header-only C++ CPU evaluator via `python tools/water_shorelines.py export-code --target glsl-shader` or `--target cpp-software`). Port that, don't re-derive.
3. **Draw** the map textured quad **under** the land, world-aligned with the
   land art. One texel per art pixel. Sampler: **nearest** — linear filtering
   at screen resolution is the most common way this effect breaks.
4. **Shader** (GLSL fragment):

```glsl
uniform sampler2D u_map;      // 8-bit baked distance map
uniform float u_max_dist;     // MAX_DIST, same as the bake (32.0)
uniform float u_time;         // seconds

const vec3 DEEP    = vec3(0.110, 0.290, 0.502);
const vec3 MID     = vec3(0.133, 0.384, 0.588);
const vec3 SHALLOW = vec3(0.204, 0.549, 0.690);
const vec3 SHOAL   = vec3(0.376, 0.745, 0.769);
const vec3 WAVE    = vec3(0.588, 0.839, 0.855);
const vec3 FOAM    = vec3(0.925, 0.965, 0.957);

void main() {
    float d = texture(u_map, v_uv).r * u_max_dist;   // px to nearest land

    vec3 c = DEEP;
    if (d < 26.0) c = MID;
    if (d < 13.0) c = SHALLOW;
    if (d < 5.0)  c = SHOAL;

    float phase = mod(d + u_time * 4.4, 11.0);       // rings 11 px apart,
    if (phase < 1.6 && d > 4.0 && d < 20.0) c = WAVE; // sliding toward the coast

    if (d < 2.2 + 1.1 * sin(u_time * 2.5)) c = FOAM; // breathing foam line

    fragColor = vec4(c, 1.0);
}
```

## The 1D distance pass (Felzenszwalb & Huttenlocher)

```
pass_1d(f):                       # squared distance along one line of n values
    v = [0]; z = [-INF, +INF]; k = 0
    for q in 1..n-1:
        loop:
            p = v[k]
            s = ((f[q] + q*q) - (f[p] + p*p)) / (2*(q - p))
            if s > z[k]: break
            k -= 1
        k += 1; v[k] = q; z[k] = s; z[k+1] = +INF
    k = 0
    for q in 0..n-1:
        while z[k+1] < q: k += 1
        out[q] = (q - v[k])^2 + f[v[k]]
    f = out
```

Run it on every column, then every row, of the squared-distance field, then
sqrt. O(area) total.

## Settings to expose

MAX_DIST (32), wobble amplitude/sigma, band edges (5/13/26), foam
(2.2 / 1.1 / 2.5 Hz), wave spacing (11), speed (4.4), thickness (1.6), band
(4–20), and the six colors. Scale all distances by `tile_size / 16`.

## Dynamic coasts and chunks

- Coast edit: recompute a window around the edit with `2 × MAX_DIST` margin,
  copy back only the part within `MAX_DIST`.
- Chunks: bake each chunk with `MAX_DIST` of neighbors' land around it;
  wobble from world position, or the bands break at chunk borders.

## Checks

Mirror `tools/water_shorelines.py verify`'s battery in the engine's test system:
transform vs brute force, band colors at 4/12/25/27 px, wave band/period/
direction, foam width 1–3 px, six-color palette, debug view of the raw map,
and an effect-off toggle.
