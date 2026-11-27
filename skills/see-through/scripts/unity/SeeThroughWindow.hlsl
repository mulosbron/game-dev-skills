// Paste into an existing sprite shader, then call SeeThroughClip from the fragment.
// Radii are art pixels. pixelScale is world units per art pixel (1 at art resolution).
// Dropping a pixel is clip(), never a half-transparent write.
#ifndef SEE_THROUGH_WINDOW_INCLUDED
#define SEE_THROUGH_WINDOW_INCLUDED

static const float SEE_THROUGH_BAYER[16] = {
    0.0, 8.0, 2.0, 10.0,
    12.0, 4.0, 14.0, 6.0,
    3.0, 11.0, 1.0, 9.0,
    15.0, 7.0, 13.0, 5.0
};

float SeeThroughSolid(float2 world, float2 target, float amount, float radius, float soft, float keep, float pixelScale) {
    float2 art = world / pixelScale;
    float2 cell = floor(art);
    float d = distance(cell + 0.5, target / pixelScale);
    float reach = (radius + soft) * amount;
    float solid = soft > 0.0 ? saturate((d - reach) / soft + 1.0) : step(reach, d);
    return max(solid, keep);
}

void SeeThroughClip(float2 world, float2 target, float amount, float radius, float soft, float keep, float pixelScale) {
    float2 cell = floor(world / pixelScale);
    float solid = SeeThroughSolid(world, target, amount, radius, soft, keep, pixelScale);
    float2 wrapped = cell - floor(cell / 4.0) * 4.0;
    int index = (int)wrapped.y * 4 + (int)wrapped.x;
    if (solid <= (SEE_THROUGH_BAYER[index] + 0.5) / 16.0) {
        clip(-1);
    }
}

#endif
