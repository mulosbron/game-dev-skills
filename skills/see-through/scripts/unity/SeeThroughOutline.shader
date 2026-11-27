Shader "SeeThrough/Outline" {
    Properties {
        [PerRendererData] _MainTex ("Sprite", 2D) = "white" {}
        _Color ("Outline", Color) = (0.980, 0.980, 0.941, 1)
    }
    SubShader {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" }
        Cull Off
        Lighting Off
        ZWrite Off
        Blend One OneMinusSrcAlpha
        Pass {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"
            sampler2D _MainTex;
            float4 _MainTex_TexelSize;
            float4 _Color;
            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct v2f { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };
            v2f vert(appdata v) {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }
            fixed4 frag(v2f i) : SV_Target {
                float2 px = _MainTex_TexelSize.xy;
                float inside = step(0.5, tex2D(_MainTex, i.uv).a);
                float around = min(
                    min(tex2D(_MainTex, i.uv + float2(px.x, 0)).a, tex2D(_MainTex, i.uv - float2(px.x, 0)).a),
                    min(tex2D(_MainTex, i.uv + float2(0, px.y)).a, tex2D(_MainTex, i.uv - float2(0, px.y)).a));
                float a = inside * (1.0 - step(0.5, around)) * _Color.a;
                return float4(_Color.rgb * a, a);
            }
            ENDCG
        }
    }
}
