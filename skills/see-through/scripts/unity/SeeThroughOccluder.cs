// One component per scenery sprite the player can walk behind.
// Unity Y grows up. This transform and the target both use the feet as origin.
// Each occluder has its own amount and its own material instance.
// Fade at 1, or a radius of 0, leaves the sprite unchanged.
// Dithered fade is Mode.Dither with keep = 0.375 (not a separate mode).
//
// Silhouette / outline: this object needs a SpriteMask using its sprite, and
// the ghost renderer is set to VisibleInsideMask. The mask's custom range
// covers only the ghost's sorting order, so other sprites are not masked.
// Switching between silhouette and outline swaps the ghost's shader. It does
// not create a second ghost. Both turn off when amount hits 0.

using UnityEngine;

[RequireComponent(typeof(SpriteRenderer))]
public class SeeThroughOccluder : MonoBehaviour {
    public enum Mode { Fade, Dither, Cutout, Silhouette, Outline }

    public Mode mode = Mode.Dither;
    public Transform target;
    public SpriteRenderer targetSprite;
    public Vector2 targetSize = new Vector2(20f, 36f);
    public float easeTime = 0.2f;
    public Vector2Int coverGrid = new Vector2Int(3, 4);
    [Range(0f, 1f)] public float coverNeeded = 0.25f;

    [Range(0f, 1f)] public float fadeTo = 0.4f;
    public float clearRadius = 18f;
    public float soft = 16f;
    public float keep = 0f;
    public float holeRadius = 22f;
    public Color silhouette = new Color(118f / 255f, 214f / 255f, 255f / 255f, 1f);
    public Color outline = new Color(250f / 255f, 250f / 255f, 240f / 255f, 1f);
    public float pixelScale = 1f;

    public Shader windowShader;
    public Shader flatShader;
    public Shader outlineShader;

    [System.NonSerialized] public float amount;

    SpriteRenderer _renderer;
    SpriteRenderer _ghost;
    SpriteMask _mask;
    Material _window;
    Material _shared;
    bool _windowOn;
    Texture2D _readable;

    static readonly int TargetId = Shader.PropertyToID("_Target");
    static readonly int AmountId = Shader.PropertyToID("_Amount");
    static readonly int RadiusId = Shader.PropertyToID("_Radius");
    static readonly int SoftId = Shader.PropertyToID("_Soft");
    static readonly int KeepId = Shader.PropertyToID("_Keep");
    static readonly int PixelScaleId = Shader.PropertyToID("_PixelScale");

    void Awake() {
        _renderer = GetComponent<SpriteRenderer>();
        _shared = _renderer.sharedMaterial;
        if (windowShader != null) {
            _window = new Material(windowShader);
            _window.mainTexture = _renderer.sprite != null ? _renderer.sprite.texture : null;
        }
    }

    void OnDestroy() {
        if (_window != null) Destroy(_window);
        if (_readable != null) Destroy(_readable);
    }

    void Update() {
        bool behind = target != null && IsBehind();
        float goal = behind ? 1f : 0f;
        amount = easeTime > 0f ? Mathf.MoveTowards(amount, goal, Time.deltaTime / easeTime) : goal;

        var color = _renderer.color;
        color.a = mode == Mode.Fade ? Mathf.Lerp(1f, fadeTo, amount) : 1f;
        _renderer.color = color;

        bool window = mode == Mode.Dither || mode == Mode.Cutout;
        bool windowOff = (mode == Mode.Dither && clearRadius == 0f && soft == 0f)
            || (mode == Mode.Cutout && holeRadius == 0f)
            || _window == null;
        if (window && !windowOff) {
            if (!_windowOn) {
                _renderer.material = _window;
                _windowOn = true;
            }
            float radius = mode == Mode.Dither ? clearRadius : holeRadius;
            float softNow = mode == Mode.Dither ? soft : 0f;
            float keepNow = mode == Mode.Dither ? keep : 0f;
            _window.SetVector(TargetId, Center());
            _window.SetFloat(AmountId, amount);
            _window.SetFloat(RadiusId, radius);
            _window.SetFloat(SoftId, softNow);
            _window.SetFloat(KeepId, keepNow);
            _window.SetFloat(PixelScaleId, pixelScale);
        } else if (_windowOn) {
            _renderer.sharedMaterial = _shared;
            _windowOn = false;
        }

        ShowGhost(amount > 0f && (mode == Mode.Silhouette || mode == Mode.Outline));
    }

    public Vector2 Center() {
        // Y grows up. Feet plus half the height.
        return target != null
            ? (Vector2)target.position + new Vector2(0f, targetSize.y * 0.5f)
            : Vector2.zero;
    }

    public bool IsBehind() {
        Vector2 feet = target.position;
        // Level with the base, or in front of it (smaller y): never on.
        if (feet.y <= transform.position.y) return false;
        if (mode == Mode.Silhouette || mode == Mode.Outline) {
            var box = new Rect(feet.x - targetSize.x * 0.5f, feet.y, targetSize.x, targetSize.y);
            return WorldBounds().Overlaps(box);
        }
        int hidden = 0;
        for (int ix = 0; ix < coverGrid.x; ix++) {
            for (int iy = 0; iy < coverGrid.y; iy++) {
                float atX = ((ix + 0.5f) / coverGrid.x - 0.5f) * targetSize.x;
                float atY = -((iy + 0.5f) / coverGrid.y - 1f) * targetSize.y;
                if (OpaqueAt(feet + new Vector2(atX, atY))) hidden++;
            }
        }
        return hidden > 0 && hidden >= coverNeeded * coverGrid.x * coverGrid.y;
    }

    Rect WorldBounds() {
        var b = _renderer.bounds;
        return new Rect(b.min.x, b.min.y, b.size.x, b.size.y);
    }

    bool OpaqueAt(Vector2 world) {
        var sprite = _renderer.sprite;
        if (sprite == null || sprite.texture == null) return false;
        var local = transform.InverseTransformPoint(world);
        // Origin at the feet, sprite centered on X, texture y-up so the feet
        // are the bottom of the sprite rect in local space only after the
        // import pivot is the bottom center. Sample in sprite texel space.
        Rect rect = sprite.textureRect;
        float px = (local.x / pixelScale) + rect.width * 0.5f;
        float py = (local.y / pixelScale);
        int x = Mathf.FloorToInt(rect.x + px);
        int y = Mathf.FloorToInt(rect.y + py);
        var tex = Readable(sprite.texture);
        if (x < 0 || y < 0 || x >= tex.width || y >= tex.height) return false;
        return tex.GetPixel(x, y).a >= 0.5f;
    }

    Texture2D Readable(Texture2D source) {
        if (source.isReadable) return source;
        if (_readable != null && _readable.width == source.width && _readable.height == source.height) return _readable;
        var rt = RenderTexture.GetTemporary(source.width, source.height, 0, RenderTextureFormat.ARGB32);
        Graphics.Blit(source, rt);
        var prev = RenderTexture.active;
        RenderTexture.active = rt;
        _readable = new Texture2D(source.width, source.height, TextureFormat.RGBA32, false);
        _readable.ReadPixels(new Rect(0, 0, source.width, source.height), 0, 0);
        _readable.Apply();
        RenderTexture.active = prev;
        RenderTexture.ReleaseTemporary(rt);
        return _readable;
    }

    void ShowGhost(bool on) {
        if (on && _ghost == null && targetSprite != null) {
            var go = new GameObject(name + " see-through ghost");
            _ghost = go.AddComponent<SpriteRenderer>();
            _mask = gameObject.GetComponent<SpriteMask>();
            if (_mask == null) _mask = gameObject.AddComponent<SpriteMask>();
            _mask.sprite = _renderer.sprite;
            _mask.isCustomRangeActive = true;
            _mask.backSortingOrder = _renderer.sortingOrder;
            _mask.frontSortingOrder = _renderer.sortingOrder + 1;
            _ghost.sortingLayerID = _renderer.sortingLayerID;
            _ghost.sortingOrder = _renderer.sortingOrder + 1;
            _ghost.maskInteraction = SpriteMaskInteraction.VisibleInsideMask;
        }
        if (_ghost == null) return;
        _ghost.enabled = on;
        if (_mask != null) _mask.enabled = on;
        if (!on) return;
        bool edge = mode == Mode.Outline;
        var shader = edge ? outlineShader : flatShader;
        if (shader != null && (_ghost.material == null || _ghost.material.shader != shader)) {
            _ghost.material = new Material(shader);
        }
        _ghost.color = edge ? outline : silhouette;
        _ghost.sprite = targetSprite.sprite;
        _ghost.flipX = targetSprite.flipX;
        _ghost.flipY = targetSprite.flipY;
        _ghost.transform.SetPositionAndRotation(targetSprite.transform.position, targetSprite.transform.rotation);
        _ghost.transform.localScale = targetSprite.transform.lossyScale;
    }

    // Bind this to a debug key when you cannot render-test. Order matches LOOK_CYCLE
    // minus a separate dithered-fade enum: Dither is visited twice, keep 0 then 0.375.
    public void CycleMode() {
        switch (mode) {
            case Mode.Fade:
                mode = Mode.Dither;
                keep = 0f;
                break;
            case Mode.Dither:
                if (keep <= 0f) keep = 0.375f;
                else { mode = Mode.Cutout; keep = 0f; }
                break;
            case Mode.Cutout:
                mode = Mode.Silhouette;
                break;
            case Mode.Silhouette:
                mode = Mode.Outline;
                break;
            default:
                mode = Mode.Fade;
                break;
        }
    }
}
