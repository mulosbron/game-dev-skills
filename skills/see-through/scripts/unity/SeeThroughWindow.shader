// Occluder window. Cutout is this shader with _Soft = 0 and _Keep = 0.
// Dithered fade is _Keep = 0.375. Do not use this to replace a wind or outline
// shader — paste SeeThroughClip from SeeThroughWindow.hlsl into that shader instead.
Shader "SeeThrough/Window" {
    Properties {
        [PerRendererData] _MainTex ("Sprite", 2D) = "white" {}
        _Color ("Tint", Color) = (1, 1, 1, 1)
        _Target ("Character center (world)", Vector) = (0, 0, 0, 0)
        _Amount ("Amount", Range(0, 1)) = 0
        _Radius ("Radius (art px)", Float) = 18
        _Soft ("Soft (art px)", Float) = 16
        _Keep ("Keep", Range(0, 1)) = 0
        _PixelScale ("World units per art pixel", Float) = 1
    }
    SubShader {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "CanUseSpriteAtlas" = "True" }
        Cull Off
        Lighting Off
        ZWrite Off
        Blend One OneMinusSrcAlpha
        Pass {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            #include "SeeThroughWindow.hlsl"

            sampler2D _MainTex;
            float4 _Color;
            float4 _Target;
            float _Amount;
            float _Radius;
            float _Soft;
            float _Keep;
            float _PixelScale;

            struct appdata {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
            };
            struct v2f {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
                float2 world : TEXCOORD1;
            };

            v2f vert(appdata v) {
                v2f o;
                float4 world = mul(unity_ObjectToWorld, v.vertex);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                o.color = v.color * _Color;
                o.world = world.xy;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target {
                SeeThroughClip(i.world, _Target.xy, _Amount, _Radius, _Soft, _Keep, _PixelScale);
                fixed4 c = tex2D(_MainTex, i.uv) * i.color;
                c.rgb *= c.a;
                return c;
            }
            ENDCG
        }
    }
}
