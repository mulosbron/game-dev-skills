# Unity — unlit sprite shader / Shader Graph

Same math as the Godot reference; the differences are Unity-specific setup.

## Setup

1. Get the land as pixels at art resolution: render the land layers once into
   a camera with a solid transparent background and `ReadPixels`, or use a
   Texture2D of the merged land art if the level is authored as an image.
2. Bake the 8-bit map on load (CPU, C# or a bundled Python bake at build
   time) and upload as a `Texture2D` (R8/Alpha8, one texel per art pixel).
3. Draw the map on a SpriteRenderer **below** the Tilemap/sprites, same
   position and scale as the land art.
4. **Filter mode: Point** on the map texture — linear filtering at screen
   resolution turns the bands into thin smooth curves that ignore the art's
   pixel grid.
5. Scale everything by `tileSize / 16` if the project isn't 16 px tiles, and
   expose the settings (MAX_DIST, band edges, foam, wave numbers) in one
   serializable settings asset.

## Unlit shader (Built-in / URP-compatible HLSL)

```hlsl
Shader "Custom/WaterShoreline"
{
    Properties
    {
        _MainTex ("Distance Map", 2D) = "black" {}
        _MaxDist ("MAX_DIST (px)", Float) = 32.0
        _Deep ("Deep", Color) = (0.110, 0.290, 0.502, 1)
        _Mid ("Mid", Color) = (0.133, 0.384, 0.588, 1)
        _Shallow ("Shallow", Color) = (0.204, 0.549, 0.690, 1)
        _Shoal ("Shoal", Color) = (0.376, 0.745, 0.769, 1)
        _Wave ("Wave", Color) = (0.588, 0.839, 0.855, 1)
        _Foam ("Foam", Color) = (0.925, 0.965, 0.957, 1)
        _WaveSpacing ("Wave Spacing (px)", Float) = 11.0
        _WaveSpeed ("Wave Speed (px/s)", Float) = 4.4
    }
    SubShader
    {
        Tags { "Queue"="Transparent" "RenderType"="Transparent" }
        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            float4 _MainTex_TexelSize;
            float _MaxDist;
            fixed4 _Deep, _Mid, _Shallow, _Shoal, _Wave, _Foam;
            float _WaveSpacing, _WaveSpeed;

            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };
            v2f vert(float4 vertex : POSITION, float2 uv : TEXCOORD0)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(vertex);
                o.uv = uv;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float d = tex2D(_MainTex, i.uv).r * _MaxDist; // px to land

                fixed4 c = _Deep;
                if (d < 26.0) c = _Mid;
                if (d < 13.0) c = _Shallow;
                if (d < 5.0)  c = _Shoal;

                float phase = fmod(d + _Time.y * _WaveSpeed, _WaveSpacing);
                if (phase < 1.6 && d > 4.0 && d < 20.0) c = _Wave;

                if (d < 2.2 + 1.1 * sin(_Time.y * 2.5)) c = _Foam;

                return c;
            }
            ENDHLSL
        }
    }
}
```

`_Time.y` is Unity's time in seconds; `_Time.y * 2.5` drives the foam breath
(out and back every 2.5 s).

## Shader Graph variant

Unlit sprite graph, same nodes:

1. `Sample Texture 2D` (map, **Point** filter via the texture import or a
   Sampler State node) → `.r` × `MAX_DIST` = `d`.
2. Band colors: three `Branch`/`Step` comparisons at 26 / 13 / 5 px.
3. Waves: `Fmod(d + Time * 4.4, 11) < 1.6` AND `d > 4` AND `d < 20`.
4. Foam: `d < 2.2 + 1.1 * Sin(Time * 2.5)`.
5. Master node: Unlit, Transparent.

## C# bake note

For runtime baking in C#, port `tools/water_shorelines.py`'s two-pass
Felzenszwalb transform (it is short and exact), or bake offline with
`python tools/water_shorelines.py bake land.png -o shore_distance.png` at build time and ship the PNG. Unity's `Terrain`/async APIs
don't provide an EDT; don't approximate with per-tile distances.

## Checks in-engine

- Point filter confirmed on the actual texture import, not just the settings.
- Debug toggle that shows the raw map sprite.
- Bands at 4 / 12 / 25 / 27 px = shoal / shallow / mid / deep (wobble + foam
  off for the test).
- Effect toggle off → old flat water back.
