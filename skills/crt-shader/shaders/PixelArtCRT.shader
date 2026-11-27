// CRT look for pixel art, one pass. Unity URP fullscreen blit (HLSL / ShaderLab).
// UNTESTED port: rename rules from the SpriteCook guide applied to the GLSL source.
//   vec3 -> float3, mat3 -> float3x3, mix -> lerp, mod -> fmod,
//   texelFetch(game, p, 0) -> game.Load(int3(p, 0)), M * v -> mul(M, v).
// Blit your game RenderTexture through this at a whole-number scale.
// Keep the RenderTexture filter mode = Point. Color in and out is gamma-encoded:
// if your pipeline passes linear values, convert once (see notes.md).

Shader "Hidden/CRT/PixelArtCRT"
{
    Properties
    {
        _MainTex ("Game (native size)", 2D) = "black" {}
    }

    HLSLINCLUDE
    #include "Packages/com.unity.render-pipelines.core/ShaderLibrary/Common.hlsl"
    #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

    TEXTURE2D(_MainTex);
    SAMPLER(sampler_MainTex);   // set point filtering on the RenderTexture itself

    // ---- Settings (the knobs). Distances are in game pixels unless noted. ----
    static const float LUMA_BLUR = 0.45;
    static const float CHROMA_BLUR = 1.2;
    static const float BEAM_MIN = 0.21;
    static const float BEAM_MAX = 0.40;
    static const float MASK_PX = 2.0;
    static const float MASK_DARK = 0.62;
    static const float MASK_LIGHT = 1.22;
    static const float GLOW = 0.26;
    static const float BOOST = 1.5;
    static const float2 WARP = float2(0.031, 0.041);

    // NTSC YIQ. Rows here so you can write mul(rgb, RGB_TO_YIQ).
    static const float3x3 RGB_TO_YIQ = float3x3(
        0.299, 0.587, 0.114,
        0.596, -0.274, -0.322,
        0.211, -0.523, 0.312);
    static const float3x3 YIQ_TO_RGB = float3x3(
        1.0, 0.956, 0.621,
        1.0, -0.272, -0.647,
        1.0, -1.106, 1.703);

    int3 GameSize()
    {
        int w, h;
        _MainTex.GetDimensions(w, h);
        return int3(w, h, 0);
    }

    float3 GamePx(int2 p)
    {
        int3 s = GameSize();
        int2 c = clamp(p, int2(0, 0), int2(s.x - 1, s.y - 1));
        return _MainTex.Load(int3(c, 0)).rgb;
    }

    // 1. The signal: one row blurred sideways only, read at x.
    float3 SignalRow(int row, float x)
    {
        int x0 = int(floor(x));
        float3 t[9];
        for (int k = 0; k < 9; k++)
            t[k] = mul(GamePx(int2(x0 - 4 + k, row)), RGB_TO_YIQ);
        float3 sum = float3(0.0, 0.0, 0.0);
        float3 weight = float3(0.0, 0.0, 0.0);
        for (int k = 1; k < 8; k++)
        {
            float luma = 0.25 * t[k - 1].x + 0.5 * t[k].x + 0.25 * t[k + 1].x;
            float d = float(x0 - 4 + k) + 0.5 - x;
            float wl = exp(-0.5 * d * d / (LUMA_BLUR * LUMA_BLUR));
            float wc = exp(-0.5 * d * d / (CHROMA_BLUR * CHROMA_BLUR));
            sum += float3(luma * wl, t[k].y * wc, t[k].z * wc);
            weight += float3(wl, wc, wc);
        }
        return saturate(mul(sum / weight, YIQ_TO_RGB));
    }

    // 2. The beam: soft band per row, thicker on bright pixels.
    float3 Beam(float3 lin, float dist)
    {
        float3 sigma = lerp(float3(BEAM_MIN, BEAM_MIN, BEAM_MIN),
                            float3(BEAM_MAX, BEAM_MAX, BEAM_MAX),
                            pow(lin, float3(0.6, 0.6, 0.6)));
        return lin * exp(-0.5 * dist * dist / (sigma * sigma));
    }

    // 4. Glow: wide soft blur of the game, added on top. Shrink to 3x3 on mobile.
    float3 Glow(float2 p)
    {
        int2 c = int2(floor(p));
        float3 sum = float3(0.0, 0.0, 0.0);
        float weight = 0.0;
        for (int j = -2; j <= 2; j++)
        for (int i = -2; i <= 2; i++)
        {
            float2 d = float2(c + int2(i, j)) + 0.5 - p;
            float w = exp(-0.5 * dot(d, d) / 2.56);
            sum += w * pow(GamePx(c + int2(i, j)), float3(2.4, 2.4, 2.4));
            weight += w;
        }
        return sum / weight;
    }

    // uv: 0..1, top-left origin. screen_px: position in real output pixels.
    float3 Crt(float2 uv, float2 screen_px)
    {
        // 5. Curvature first, black outside the glass.
        float2 c = uv * 2.0 - 1.0;
        c *= float2(1.0 + c.y * c.y * WARP.x, 1.0 + c.x * c.x * WARP.y);
        uv = c * 0.5 + 0.5;
        if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0)
            return float3(0.0, 0.0, 0.0);

        int3 gs = GameSize();
        float2 p = uv * float2(gs.x, gs.y);   // position in game pixels
        float y = p.y - 0.5;
        int r0 = int(floor(y));
        float3 col = float3(0.0, 0.0, 0.0);
        for (int k = 0; k < 2; k++)
        {
            float3 lin = pow(SignalRow(r0 + k, p.x), float3(2.4, 2.4, 2.4));
            col += Beam(lin, y - float(r0 + k));
        }
        col *= 1.32;
        // 3. Phosphor mask: R/G/B stripes on the glass.
        int stripe = int(fmod(floor(screen_px.x / MASK_PX), 3.0));
        float3 on = float3(stripe == 0 ? 1.0 : 0.0,
                           stripe == 1 ? 1.0 : 0.0,
                           stripe == 2 ? 1.0 : 0.0);
        col *= lerp(float3(MASK_DARK, MASK_DARK, MASK_DARK),
                    float3(MASK_LIGHT, MASK_LIGHT, MASK_LIGHT), on);
        col += GLOW * Glow(p);
        col *= 1.0 - 0.22 * pow(saturate(dot(c, c) * 0.5), 1.5);
        return pow(saturate(col * BOOST), float3(1.0 / 2.2, 1.0 / 2.2, 1.0 / 2.2));
    }

    struct Varyings
    {
        float4 pos : SV_POSITION;
        float2 uv  : TEXCOORD0;
    };

    Varyings VertBlit(Attributes input)
    {
        Varyings o;
        o.pos = TransformObjectToHClip(input.positionOS.xyz);
        o.uv = input.uv;   // with a standard fullscreen tri, uv is 0..1 bottom-left
        return o;
    }

    float4 FragBlit(Varyings i) : SV_Target
    {
        // Flip to top-left origin like the GLSL version.
        float2 uv = float2(i.uv.x, 1.0 - i.uv.y);
        return float4(Crt(uv, i.pos.xy), 1.0);
    }
    ENDHLSL

    SubShader
    {
        Tags { "RenderType" = "Opaque" "RenderPipeline" = "UniversalPipeline" }
        Cull Off ZWrite Off ZTest Always

        Pass
        {
            Name "PixelArtCRT"
            HLSLPROGRAM
            #pragma vertex VertBlit
            #pragma fragment FragBlit
            ENDHLSL
        }
    }
}
