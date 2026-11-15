# Godot 4.x Pixel Texture Rehberi
### 2D • 3D • 2.5D FPS • 2.5D Top-Down oyunlarda pixel-art texture pipeline'ı — eksiksiz referans dokümanı

| Hedef Sürüm | Godot 4.3+ (4.0–4.2 için farklar notlarıyla verilmiştir) |
| :--- | :--- |
| **Format** | Referans doküman: ayar tabloları + tam kod örnekleri |
| **Seviye** | Temeller hızlı, ileri kutular (PSX shader, SubViewport render) detaylı |

---

## İçindekiler
0. [Hızlı Karar Tablosu](#0-hızlı-karar-tablosu)
1. [Ortak Temel: Üç Altın Kural](#1-ortak-temel-üç-altın-kural)
2. [2D Oyunlar](#2-2d-oyunlar)
3. [3D Oyunlar (Low-Poly + Pixel Texture)](#3-3d-oyunlar-low-poly--pixel-texture)
4. [2.5D FPS (Doom/Wolfenstein Tarzı)](#4-25d-fps-doomwolfenstein-tarzı)
5. [2.5D Top-Down](#5-25d-top-down)
6. [Shader Referansı](#6-shader-referansı)
7. [Otomasyon ve Batch İşleme](#7-otomasyon-ve-batch-işleme)
8. [Dış Araç Export Ayarları (Aseprite / Blender)](#8-dış-araç-export-ayarları-aseprite--blender)
9. [Sorun Giderme](#9-sorun-giderme)
10. [Hızlı Kontrol Listesi](#10-hızlı-kontrol-listesi)

---

## 0. Hızlı Karar Tablosu
Her oyun türü için "piksel görüntüsü"nü üreten katman farklıdır. Rehbere girmeden önce kendi projenizin satırını bulun:

| Oyun türü | Sahne kökü | Piksel görünümü nereden gelir? | Kritik 3 ayar |
| :--- | :--- | :--- | :--- |
| **2D** | `Node2D` | Canvas filtresi + stretch ayarları | Default Filter = Nearest, Stretch Mode = canvas_items, Scale Mode = integer |
| **3D (low-poly)** | `Node3D` | Materyal filtresi + texel density | Material Texture Filter = Nearest, Mipmaps = Off, Shading = Per-vertex |
| **2.5D FPS** | `Node3D` + `CanvasLayer` | Sprite3D billboard + düşük çözünürlüklü render | Billboard = Enabled, Alpha Cut = Discard, SubViewport stretch_shrink |
| **2.5D Top-Down** | `Node2D` (Y-sort) veya `Node3D` (HD-2D) | Y-sort sıralama veya Sprite3D billboard | y_sort_enabled, Sprite3D Billboard = Fixed Y, pivot = ayak noktası |

---

## 1. Ortak Temel: Üç Altın Kural
Dört oyun türü de aynı üç temel üzerine kurulur. Bunlar bozulursa ne yaparsanız görünüm bozulur; doğru kurulunca geri kalan her şey detaydır.

### 1.1 Kural 1 — Palette her yerde aynı
* Tüm texture'lar tek bir palette (16–64 renk) üretilsin. Lospec'ten hazır palet alın veya Aseprite'te sabitleyin.
* Palette "yaklaşık" benzer renkler değil, birebir aynı renk değerleri kullanın. Farklı sprite'larda iki ton mavi varsa zemin ve karakter birbirine karışır.
* Araçlar arasında renk kayması olmaması için PNG export edin; JPG kullanmayın (kayıplı sıkıştırma pikselleri bozar).
* Oyun içi post-process ile renk azaltma gerekiyorsa §6.2'deki posterize + dither shader'ını kullanın; ama hedefiniz asset üretiminde palette sabitlemek olmalı (§7.1).

### 1.2 Kural 2 — Pixel density (PPU) tutarlı olsun
PPU (Pixels Per Unit): dünyada 1 birime kaç texture pikseli düştüğü. Projeye başlarken bir kez belirleyin (yaygın seçimler: 16, 32, 48) ve asla karıştırmayın. Aynı sahnede 16 PPU'lu karakter ile 32 PPU'lu kasa yan yana gelirse birinin pikselleri diğerinden iri görünür — retro projelerde en sık yapılan hata budur.

| Bağlam | PPU karşılığı | Örnek (PPU = 32) |
| :--- | :--- | :--- |
| **2D** | 1 texture pikseli = 1 canvas birimi; büyütme `Camera2D.zoom` ile yapılır | `zoom = Vector2(4, 4)` → ekranda 4× |
| **3D** | `pixel_size = 1 / PPU` (metre/piksel) | `pixel_size = 0.03125` |
| **Sprite3D (2.5D)** | 32 px texture → 1 metre yükseklik | `pixel_size = 0.03125` |
| **3D duvar tiling** | metres/texel = mesh boyu / texture çözünürlüğü | 3 m duvar, 96 px texture → 1 texel = 3.125 cm |

### 1.3 Kural 3 — Filtering: Nearest, her katmanda
Texture'lar herhangi bir katmanda "Linear" ile örneklenirse pikseller bulanır. Godot 4'te filtre dört farklı yerde ayarlanabilir; hiyerarşi aşağıdan yukarıya ezilir (node ayarı, proje varsayılanını geçersiz kılar):

| Katman | Nerede | Ne zaman kullanılır |
| :--- | :--- | :--- |
| **1. Proje varsayılanı** | Project Settings → `rendering/textures/canvas_textures/default_texture_filter = Nearest` | Tüm 2D projelerde mutlaka. 3D'yi etkilemez. |
| **2. Node (CanvasItem)** | Her Sprite2D/TileMapLayer/Control üzerinde `Texture Filter = Nearest` | Sadece bir node'un farklı filtre istediğinde |
| **3. 3D materyal** | StandardMaterial3D → `Texture Filter = Nearest` | Tüm 3D ve 2.5D'de materyal başına |
| **4. Shader** | Uniform'a `filter_nearest` hint'i (§6) | Custom shader kullanıyorsanız (materyal filtresini devre dışı bırakır) |

> [!NOTE]
> Godot 3'teki "texture import Filter" bayrağı Godot 4'te kaldırılmıştır. Godot 4'te filtre import sırasında değil, yukarıdaki üç katmandan birinde (genelde proje varsayılanı veya materyal) ayarlanır. Unity'den gelen "Filter Mode = Point" alışkanlığının Godot karşılığı budur.

### 1.4 Proje Genel Ayarları (her tür için ortak)
Project Settings'te (Project → Project Settings → Advanced Settings açıkken):

| Ayar | Tam yol | Değer | Amaç |
| :--- | :--- | :--- | :--- |
| **Default Texture Filter** | `rendering/textures/canvas_textures/default_texture_filter` | `Nearest` (0) | Tüm 2D çizimde bulanıklığı bitirir |
| **Stretch Mode** | `display/window/stretch/mode` | `canvas_items` (veya `viewport`) | Farklı pencere boyutlarında piksellerin oranını korur |
| **Stretch Aspect** | `display/window/stretch/aspect` | `keep` | Genişleme bozulmasını engeller |
| **Stretch Scale Mode** | `display/window/stretch/scale_mode` | `integer` (4.2+) | Tam katı ölçek → pikseller eşit büyür (4.0–4.1'de pencereyi sabit çözünürlükte açın) |
| **Snap 2D Transforms** | `rendering/2d/snap/snap_2d_transforms_to_pixel` | `On` (`true`) | Kamera alt-piksel hareketinde titremeyi keser |
| **MSAA 3D** | `rendering/anti_aliasing/quality/msaa_3d` | `Disabled` (0) | 3D'de kenar yumuşatma piksel görünümünü bozar |
| **Screen Space AA** | `rendering/anti_aliasing/quality/screen_space_aa` | `Disabled` (0) | Aynı amaç (FXAA kapalı) |

**Stretch Mode seçimi (referans):**
* `canvas_items`: 2D canvas pencere çözünürlüğünde çizilir, sprite'lar Nearest ile büyütülür; UI metinleri keskin kalır (Pixel-art oyunların çoğu için önerilen başlangıç).
* `viewport`: Tüm root viewport (2D ve 3D dahil) taban çözünürlükte çizilip büyütülür (Tam retro görünüm: PS1 era render, düşük çözünürlüklü 3D + UI).

### 1.5 Texture Import Ayarları
Godot 4'te PNG'ler import edilirken `CompressedTexture2D` olarak işlenir:

| Import seçeneği | 2D sprite için | 3D albedo için | Neden |
| :--- | :--- | :--- | :--- |
| **Compress > Mode** | `Lossless` (0) | `Lossless` (0) | VRAM Compressed palet renklerini bozar, bloklu lekeler yapar |
| **Mipmaps > Generate** | `Off` (`false`) | `Off` (bkz. not) | Mipmap uzak mesafede pikselleri eritir |
| **Detect 3D** | Fark etmez | `Off` (`false`) | Açıkken texture bir 3D materyalde kullanıldığında Godot ayarları VRAM + mipmaps'e çevirir |
| **Process > Fix Alpha Border** | `On` (`true`) | `On` (`true`) | Saydam kenarlardaki renk taşmasını (siyah çerçeve) temizler |

> [!TIP]
> **Mipmap notu:** Uzak nesnelerde titreme (shimmer) ciddi olursa istisna olarak `Mipmaps > Generate = On` + materyalde `Texture Filter = Nearest With Mipmaps` (enum 2) kullanın.

### 1.6 Klasör Yapısı
```text
res://
├─ assets/
│  ├─ raw/              # Aseprite/Blender orijinalleri — içine .gdignore dosyası koyun!
│  ├─ sprites/          # işlenmiş PNG'ler (2D + Sprite3D ortak)
│  ├─ tilesets/
│  ├─ models/           # .glb dosyaları
│  ├─ materials/        # dışarı çıkarılmış .tres materyaller (§3.5)
│  └─ shaders/          # .gdshader dosyaları (§6)
├─ scenes/
├─ scripts/
└─ import_defaults.md   # seçtiğiniz import ayarları
```
*Kritik:* `raw/` klasörüne boş bir `.gdignore` dosyası koyun. Godot bu klasörü tamamen yok sayar.

---

## 2. 2D Oyunlar

### 2.1 Proje Ayarları
* Viewport Boyutu: `display/window/size/viewport_width` / `viewport_height` = Taban çözünürlük (ör. 640×360, 480×270).
* Stretch Scale Mode: `integer`.
* Default Texture Repeat: `Disabled`.

### 2.2 Kamera (`Camera2D`)
```gdscript
# pixel_camera_2d.gd — basit pixel-perfect kamera
class_name PixelCamera2D
extends Camera2D

@export var pixel_scale: int = 4  # PPU büyütme katı

func _ready() -> void:
    zoom = Vector2(pixel_scale, pixel_scale)

func _physics_process(_delta: float) -> void:
    # Kamera konumunu piksel ızgarasına kilitle (titremeyi keser)
    global_position = global_position.floor()
```

### 2.3 TileMapLayer (Godot 4.3+) / TileMap
* **TileSet kaynağı:** Tek atlas PNG kullanın.
* **Use Texture Padding:** `On` (varsayılan) — 1 px saydam kenar ekleyerek texture bleeding'i önler.
* **Margins / Separation:** Tile'lar arası 1–2 px boşluk bırakın.
* **Texture Filter:** `Nearest`.
* **Y Sort Origin:** Yüksek tile'lar için piksel ofseti (ayak noktası).

### 2.4 Animasyon (`AnimatedSprite2D` + `SpriteFrames`)
FPS değerini retro için 6–12 FPS tutun. `Texture Filter = Nearest` olduğundan emin olun.

---

## 3. 3D Oyunlar (Low-Poly + Pixel Texture)

### 3.1 StandardMaterial3D Ayarları
| Özellik | Inspector yolu | Değer | Amaç |
| :--- | :--- | :--- | :--- |
| **Texture Filter** | Material Properties → Texture Filter | `Nearest` (0) | Bulanıklığı bitirir |
| **Albedo Texture** | Albedo → Texture | Pixel PNG | Renk haritası (Lossless import) |
| **Shading Mode** | Shading → Mode | `Per-vertex` | Gölgelemeyi köşelere vurur → retro gradyan |
| **Metallic** | Metallic | `0.0` | Yansıma pikselleri öldürmez |
| **Roughness** | Roughness | `1.0` | Speküler parlamayı kapatır |
| **Specular** | Specular | `0.0` | Yüzey parlaklığını söndürür |
| **Vertex Color** | Vertex Color → Use as Albedo | Gerekirse `On` | Blender vertex color albedo ile çarpılır |
| **Transparency** | Transparency → Mode | `Disabled` / `Alpha Scissor` (Threshold 0.5) | Keskin piksel kenarlar |

### 3.2 Texel Density Formülü
$$\text{metre/texel} = \frac{\text{mesh yüzey boyu (m)}}{\text{o yüzeye düşen texture pikseli}}$$
* Örnek: 3 m duvar, 96 px texture → 1 texel = 3.125 cm.

### 3.3 Işıklandırma ve Ortam
* **DirectionalLight3D:** Shadow opsiyonel (retro için genelde kapalı).
* **WorldEnvironment Ambient:** Color + sabit renk.
* **Tonemap:** `Linear`.
* **Glow / SSS / AO:** `Off`.

### 3.4 glTF Import Akışı (Blender → Godot)
1. Modeli `.glb` olarak export edin.
2. FileSystem'de `.glb` dosyasını seçin → Import dock → Advanced → Actions… → **Extract Materials** (`res://assets/materials/`).
3. **Extract Textures** ile texture'ları `res://assets/sprites/` altına çıkarın (Lossless, Mipmaps Off, Detect 3D Off).
4. Toplu materyal filtreleme EditorScript'i:
```gdscript
# tools/set_nearest_materials.gd
@tool
extends EditorScript

const ROOT := "res://assets"

func _run() -> void:
    _scan(ROOT)
    print("Materyal filtreleri güncellendi.")

func _scan(path: String) -> void:
    var dir := DirAccess.open(path)
    if dir == null:
        push_warning("Klasör bulunamadı: " + path)
        return
    dir.list_dir_begin()
    var fname := dir.get_next()
    while fname != "":
        var full := path.path_join(fname)
        if dir.current_is_dir() and not fname.begins_with("."):
            _scan(full)
        elif fname.ends_with(".tres") or fname.ends_with(".material"):
            var res := load(full)
            if res is BaseMaterial3D:
                res.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
                ResourceSaver.save(res, full)
                print("[ok] ", full)
        fname = dir.get_next()
```

---

## 4. 2.5D FPS (Doom/Wolfenstein Tarzı)

### 4.1 Sahne Yapısı
```text
Main (Node)
├─ Render (SubViewportContainer)     # Düşük çözünürlük için (Stretch, Stretch Shrink=3..6, Nearest)
│  └─ Dünya (Node3D)
│     ├─ Ortam (WorldEnvironment)
│     ├─ Işık (DirectionalLight3D)
│     ├─ Harita (Node3D veya GridMap)
│     ├─ Düşmanlar (Node3D)          # CharacterBody3D + Sprite3D
│     └─ Oyuncu (CharacterBody3D)
│        └─ Kamera (Camera3D)
└─ HUD (CanvasLayer)                 # Tam çözünürlüklü UI katmanı
   └─ Silah (Sprite2D)
```

### 4.2 Sprite3D Billboard Ayarları
* **Billboard:** `Enabled` (her karede kameraya döner).
* **Alpha Cut:** `Discard` (Eşik 0.5; derinlik tamponuna yazar, sıralama hatalarını çözer).
* **Texture Filter:** `Nearest`.
* **Pixel Size:** `1 / PPU` (PPU=32 için `0.03125`).
* **Pivot:** `Centered = Off`, `Offset = Vector2(-w/2, -h)` (alt-orta pivot).

### 4.3 Silah Sprite'ı (`CanvasLayer` üzerinde `Sprite2D`)
```gdscript
# weapon_sprite.gd — silah sprite'ını tam sayı katında alt-ortaya yerleştirir
extends Sprite2D

@export var scale_factor: int = 4

func _ready() -> void:
    scale = Vector2(scale_factor, scale_factor)

func _process(_delta: float) -> void:
    var vp := get_viewport_rect().size
    var half := texture.get_size() * scale_factor / 2.0
    position = Vector2(vp.x / 2.0 - half.x, vp.y - texture.get_size().y * scale_factor)
```

### 4.4 Düşük Çözünürlüklü SubViewport Render
* `SubViewportContainer`: Stretch = `On`, Stretch Shrink = `6` (1080p → 180p render), Texture Filter = `Nearest`.
* `SubViewport`: MSAA 3D = `Disabled`, Screen Space AA = `Disabled`.

---

## 5. 2.5D Top-Down

### 5.1 Yaklaşım A: Tam 2D + Y-Sort
* Dünya (`Node2D`): `y_sort_enabled = On`.
* Duvar/Objeler (`TileMapLayer`): `y_sort_enabled = On`, `Y Sort Origin` ayarlı.
* Karakter Sprite'ı: `Centered = Off`, `Offset = Vector2(-w/2, -h)` (ayak pivotu).

### 5.2 Yaklaşım B: HD-2D (3D Dünya + Sprite3D Karakterler)
* `Sprite3D` Billboard: `Fixed Y` (yatık kamerada yere yatmaz).
* `Alpha Cut`: `Discard`.
* `Shaded`: `On` (gün döngüsü ve 3D ışıklar için).
* Kamera Tilt: 50–60°, FOV 40–55°.

---

## 6. Shader Referansı

### 6.1 PSX Tarzı Spatial Shader (`psx_retro.gdshader`)
```glsl
// psx_retro.gdshader
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, shadows_disabled;

uniform sampler2D base_tex : source_color, filter_nearest, repeat_enable;
uniform float vertex_snap_res : hint_range(120.0, 1080.0) = 240.0; // sanal dikey çözünürlük
uniform bool affine_mapping = true;
uniform float color_levels : hint_range(2.0, 256.0) = 32.0;

varying vec2 uv_affine;
varying float clip_w;

void vertex() {
    vec4 clip = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
    if (clip.w > 0.0001) {
        // Vertex snapping: NDC uzayında köşeleri sanal ızgaraya kilitle
        vec3 ndc = clip.xyz / clip.w;
        float half_res = vertex_snap_res * 0.5;
        ndc.xy = floor(ndc.xy * half_res + 0.5) / half_res;
        clip.xyz = ndc * clip.w;
    }
    POSITION = clip;
    uv_affine = UV * clip.w;
    clip_w = max(clip.w, 0.0001);
}

void fragment() {
    vec2 uv = affine_mapping ? uv_affine / clip_w : UV;
    vec3 col = texture(base_tex, uv).rgb * COLOR.rgb;
    col = floor(col * color_levels + 0.5) / color_levels; // posterize
    ALBEDO = col;
}
```

### 6.2 2D Posterize + Ordered Dither Shader (`posterize_dither.gdshader`)
```glsl
// posterize_dither.gdshader
shader_type canvas_item;

uniform float levels : hint_range(2.0, 64.0) = 8.0;          // kanal başına kademe
uniform float dither_strength : hint_range(0.0, 1.0) = 1.0;  // 0 = düz posterize

// 4x4 Bayer matrisi (0..1 aralığında)
const mat4 BAYER = mat4(
    vec4(0.000, 0.500, 0.125, 0.625),
    vec4(0.750, 0.250, 0.875, 0.375),
    vec4(0.188, 0.688, 0.062, 0.562),
    vec4(0.812, 0.312, 0.938, 0.438)
);

void fragment() {
    vec4 c = COLOR;
    ivec2 px = ivec2(FRAGCOORD.xy) % 4;
    float d = (BAYER[px.x][px.y] - 0.5) * dither_strength;
    c.rgb = floor((c.rgb + d / levels) * levels + 0.5) / levels;
    COLOR = c;
}
```

---

## 7. Otomasyon ve Batch İşleme

### 7.1 Python + Pillow Batch Pipeline
Kullanım:
```bash
python tools/godot_pixel_tool.py batch-process --scale 4 --alpha 128 --src raw_assets --dst res://assets/sprites
```

### 7.2 Aseprite CLI Otomasyonu
```bash
# Yatay şerit export
aseprite -b karakter.aseprite --sheet-type horizontal --sheet karakter.png --data karakter.json
```

---

## 8. Dış Araç Export Ayarları

### 8.1 Aseprite
* Color Mode: `Indexed` (paleti kilitleyin).
* Resize: `Nearest Neighbor`.
* Extrude: `Kapalı` (Godot Use Texture Padding motor tarafında halleder).

### 8.2 Blender → glTF (.glb)
* Format: `glTF Binary (.glb)`.
* +Y Up: Açık.
* Mesh: `UVs` ve `Normals` açık. Tangents kapalı.
* Materials: Export `StandardMaterial3D`.
* Vertex Colors: Varsa açık.
* Texel Density'yi UV gridinde eşit tutun.

---

## 9. Sorun Giderme

| # | Sorun | Çözüm |
| :--- | :--- | :--- |
| 1 | Sprite'lar bulanık | `rendering/textures/canvas_textures/default_texture_filter = Nearest` (0) |
| 2 | 3D model bulanık | Materyalde `Texture Filter = Nearest` |
| 3 | Renkler kaymış, bloklu lekeler | Import: `Compress > Mode = Lossless` |
| 4 | Texture 3D'de birden bozuldu | Import: `Detect 3D = Off` |
| 5 | TileMap aralarında ince çizgiler | TileSet: `Use Texture Padding = On`, Separation $\ge 1$ |
| 6 | Sprite3D'ler iç içe geçiyor / sıralama bozuk | `Alpha Cut = Discard` (Threshold 0.5) |
| 7 | Karakter arkasında aniden kayboluyor | Pivot ayakta değil: `Centered=Off`, `Offset=(-w/2, -h)` |
| 8 | Kamera hareketinde piksel titremesi | `snap_2d_transforms_to_pixel = On`, zoom/shrink tam sayı |
| 9 | Pencere büyüyünce pikseller eşitsiz | `display/window/stretch/scale_mode = integer` |
| 10 | Silah sprite'ı pikselleri eşitsiz | Scale tam sayı vektör olmalı (`Vector2(4, 4)`) |

---

## 10. Hızlı Kontrol Listesi
- [ ] Tek palette dosyası var; tüm asset'ler ondan çizildi (§1.1, §8.3)
- [ ] PPU değerine karar verildi ve her yerde aynı (§1.2)
- [ ] `default_texture_filter = Nearest` (§1.4)
- [ ] Stretch: `canvas_items` + `keep` + `integer` (§1.4)
- [ ] `snap_2d_transforms_to_pixel = On` (§1.4)
- [ ] MSAA / Screen Space AA kapalı (§1.4)
- [ ] Tüm texture importları: Lossless, Mipmaps Off, Detect 3D Off, Fix Alpha Border On (§1.5)
- [ ] `raw/` klasöründe `.gdignore` var (§1.6)
- [ ] 2D: kamera zoom tam sayı; sprite'lar scale ile büyütülmüyor (§2.2)
- [ ] TileSet: Use Texture Padding açık; y-sort tile'larda origin ayarlı (§2.3, §5.1)
- [ ] 3D: materyal filtresi Nearest, metallic/roughness/specular söndürülmüş (§3.1)
- [ ] glTF: Extract Materials yapıldı, Nearest EditorScript çalıştırıldı (§3.4)
- [ ] FPS: Sprite3D Billboard=Enabled, Alpha Cut=Discard; silah sprite'ı tam sayı scale (§4.3–4.4)
- [ ] Düşük çözünürlük isteniyorsa SubViewportContainer: Stretch, Stretch Shrink, Nearest (§4.6)
- [ ] Top-Down: y-sort zinciri doğrulandı (§5)
