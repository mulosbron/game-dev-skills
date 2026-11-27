# Unity — atmospheric perspective for sprite layers

The same blend as Godot: `lerp` each pixel toward the sky's per-row color.
Two ways in:

## Option A — Shader Graph (no code)

Build a graph on a `Sprite Unlit` master stack:

1. **Sample Texture2D** (the layer's `MainTex`) → take RGB.
2. Sample a 1-pixel-wide **`_SkyColors`** texture with UV `(0.5, uv.y)` —
   the sky's average color on each row. Export the 1px strip with
   `tools/atmospheric_perspective.py bake-layer ... --save-sky-rows sky_rows.png` (or `bake-stack`) or compute rows once in an editor script
   and save the 1px strip as PNG (nearest filter, no srgb conversion).
3. Compute `y = saturate((uv.y - _ArtTop) / (_ArtBottom - _ArtTop))`.
4. `k = saturate(_Strength * (_Amount + _Mist * y))`.
5. `Lerp(layerRGB, skyRGB, k)` → Base Color; the sampled alpha passes
   through unchanged.

Expose `_Amount`, `_Mist`, `_Strength`, `_ArtTop`, `_ArtBottom` as material
properties. **Give every layer its own material instance** — one shared
material means one set of numbers for all layers.

## Option B — code (URP HLSL fragment)

```hlsl
TEXTURE2D(_SkyColors); SAMPLER(sampler_SkyColors);
float _Amount, _Mist, _Strength, _ArtTop, _ArtBottom;

half4 frag(Varyings IN) : SV_Target
{
    half4 c = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, IN.uv);
    half3 sky = SAMPLE_TEXTURE2D(_SkyColors, sampler_SkyColors,
                                 half2(0.5, IN.uv.y)).rgb;
    float y = saturate((IN.uv.y - _ArtTop) / (_ArtBottom - _ArtTop));
    float k = saturate(_Strength * (_Amount + _Mist * y));
    return half4(lerp(c.rgb, sky, k), c.a);
}
```

## Layer setup

- Each layer is a SpriteRenderer in a sorting order matching the existing
  back-to-front layer order; scroll speeds stay as they are (custom
  follow-camera script, Cinemachine, or whatever the project uses).
- Every layer's texture must have the **same height as the sky and sit at
  the same y**, so `uv.y` matches the sky's rows. If sprites are tightly
  cropped in an atlas, compute the row from the object's world/screen y
  instead and say so.
- `_ArtTop`/`_ArtBottom` come from the sprite's used rect
  (`SpriteMetaData`/texture packing or a one-off editor script that scans
  alpha like the Godot `get_used_rect()`).
- Ground and anything the player touches: amount 0.

If the haze never changes at runtime, skip the shader entirely and bake the
layers with `tools/atmospheric_perspective.py bake-stack` at import/export — the visuals are identical.
