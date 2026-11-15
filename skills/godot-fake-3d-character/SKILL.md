---
name: godot-fake-3d-character
description: >-
  Godot 4'te sadece 2D düğümler (Node2D, Sprite2D, RemoteTransform2D, Line2D) kullanarak sahte 3D
  (Fake 3D / 2.5D) top-down kukla karakterler oluşturma tekniği. Üstten görünümlü (top-down) oyunlarda
  3D model veya yüzlerce karelik sprite animasyonuna gerek kalmadan akıcı dönen, derinlik hissi veren
  karakterler, prosedürel uzuvlar (Line2D) ve dinamik Z-sorting katmanları oluştururken kullanılır.
---

# Godot Fake 3D Top-Down Karakter Sistemi (2D Puppet Tekniği)

Bu teknik, Godot'nun 2D dönüşüm hiyerarşisini (transform parenting) ve `RemoteTransform2D` düğümünü akıllıca kullanarak, tamamen 2D düğümlerden **3D gibi dönen ve derinliği olan bir kukla (puppet) karakter** yaratır.

3D modelleme veya her açı için ayrı sprite çizmeye gerek kalmadan; yuvarlak, stilize karakterler (*ördek, balçık/slime, minik robotlar, chibi karakterler*) için kusursuz bir 2.5D illüzyonu sağlar.

---

## 1. Temel İlke ve Matematiksel Mantık

İllüzyon üç basit gerçeğe dayanır:

1. **Kamera Açısı (Y-Ekseninde Sıkıştırma):** Bir üst ebeveyn düğümün (`Rig`) Y ölçeği küçültüldüğünde (`scale.y = 0.5` gibi), altındaki düzlemde dönen her nokta 2D ekranda bir **elips** çizer. Bu elips, izometrik veya top-down açıyla bakan bir kameranın yarattığı 3D perspektifle birebir örtüşür.
2. **Yükseklik / İrtifa (Elevation):** Bir noktanın Y pozisyonu (`position.y`) değiştirildiğinde, o nokta sanal 3D dünyada yukarı/aşağı taşınır.
3. **Ebeveynlikten Kaçış (`RemoteTransform2D`):** Eğer sprite'lar doğrudan bu sıkıştırılmış `Rig` altına konulursa, sprite'ların kendisi de basık (`squashed`) görünür. `RemoteTransform2D` düğümünün `update_scale = false` ve `update_rotation = false` ayarları kullanılarak, **sadece hesaplanan (x, y) pozisyonu** dışarıdaki `Visual` sprite'ına aktarılır; sprite'ın kendi orijinal ölçeği ve en-boy oranı bozulmaz.

```
       [Sanal 3D Boşluk: Rig]                    [Ekrana Çizim: Visual]
  Rig (scale.y = 0.5) [Kamera Açısı]
     └── Anchor (rotation = açı) 
           └── HeightOffset (position.y = -yükseklik)
                 └── RemoteTransform2D (SADECE pozisyon gönderir!) ──> Sprite2D (Basılmamış, düzgün sprite)
```

---

## 2. Sahne Ağacı Mimarisi (Visual & Rig Ayrımı)

Karakter düğümünü daima iki ana gruba ayırın:
- **`Visual`**: Çizim sırası (Z-Index / Y-Sort) ve sprite'ları barındırır.
- **`Rig`**: Sanal 3D uzaydaki açıları, yükseklikleri ve pozisyonları hesaplar.

```text
Duck (CharacterBody2D veya Node2D) - duck.gd
├── Visual (Node2D)
│   ├── ShadowSprite (Sprite2D - sabit zemin gölgesi)
│   ├── FootSpriteL (Sprite2D)
│   ├── FootSpriteR (Sprite2D)
│   ├── LegLineL (Line2D - bacak bağı)
│   ├── LegLineR (Line2D - bacak bağı)
│   ├── BodySprite (Sprite2D)
│   ├── NeckLine (Line2D - esnek boyun bağı)
│   └── HeadGroup (Node2D)
│       ├── HeadSprite (Sprite2D)
│       ├── EyesSprite (Sprite2D)
│       └── BeakSprite (Sprite2D)
└── Rig (Node2D) -> [scale = Vector2(1.0, 0.5)]
    ├── FootAnchorL (Node2D)
    │   └── PlaneResult (RemoteTransform2D -> %FootSpriteL)
    ├── FootAnchorR (Node2D)
    │   └── PlaneResult (RemoteTransform2D -> %FootSpriteR)
    ├── BodyAnchor (Node2D, position.y = -10)
    │   └── PlaneResult (RemoteTransform2D -> %BodySprite)
    └── NeckPositionCopy (Node2D - Body'nin pozisyonunu alır)
        └── HeadHeightOffset (Node2D, position.y = -25)
            └── HeadAnchor (Node2D)
                ├── HeadPlane (RemoteTransform2D -> %HeadGroup)
                ├── EyesAnchor (Node2D)
                │   └── PlaneResult (RemoteTransform2D -> %EyesSprite)
                └── BeakAnchor (Node2D)
                    └── PlaneResult (RemoteTransform2D -> %BeakSprite)
```

> [!IMPORTANT]
> `PlaneResult` olarak kullanılan tüm `RemoteTransform2D` düğümlerinde Inspector'dan:
> - `Update Position` = **ON**
> - `Update Rotation` = **OFF** (Sprite'ın kendi rotasyonunu script kontrol edecekse)
> - `Update Scale` = **OFF** (Rig'in 0.5 Y-scale'inin sprite'ı ezmesini engellemek için ŞART!)

---

## 3. GDScript Mantığı (`duck.gd`)

Dönüş, Z-Index derinlik sıralaması ve bacak açılarını yöneten ana kontrolcü:

```gdscript
extends CharacterBody2D

# 0 ile 360 derece arası Inspector ayarı (arkada radyan olarak tutulur)
@export_range(0.0, 360.0, 0.1, "radians") var direction: float = 0.0: set = _set_direction

# Görsel Düğümler
@onready var foot_sprite_l: Sprite2D = %FootSpriteL
@onready var foot_sprite_r: Sprite2D = %FootSpriteR
@onready var body_sprite: Sprite2D = %BodySprite
@onready var head_group: Node2D = %HeadGroup
@onready var beak_sprite: Sprite2D = %BeakSprite
@onready var eyes_sprite: Sprite2D = %EyesSprite

# Rig İçerisindeki Döndürülecek Çapa (Anchor) Düğümleri
@onready var foot_anchor_l: Node2D = %FootAnchorL
@onready var foot_anchor_r: Node2D = %FootAnchorR
@onready var body_anchor: Node2D = %BodyAnchor
@onready var head_anchor: Node2D = %HeadAnchor
@onready var beak_anchor: Node2D = %BeakAnchor

@onready var all_anchors: Array[Node2D] = [
    foot_anchor_l, foot_anchor_r, body_anchor, head_anchor, beak_anchor
]

func _set_direction(value: float) -> void:
    if not is_inside_tree():
        direction = value
        return
        
    direction = value
    
    # Açıyı 0.0 ile TAU (2*PI) arasına sar
    var angle: float = wrapf(direction, 0.0, TAU)
    
    # 1. Tüm çapa düğümlerini aynı açıya çevir
    for anchor in all_anchors:
        anchor.rotation = angle
        
    # 2. Ayak sprite rotasyonlarına tatlı bir ofset ver (vurgulu paytak yürüyüş için)
    foot_sprite_l.rotation = angle + 0.3
    foot_sprite_r.rotation = angle - 0.3
    
    # 3. Yüz ve Gövde Z-Index Sıralaması (Karakter Arkaya Baktığında)
    # Kuzeye/yukarıya (arka tarafa) bakarken yüz elemanları gövdenin arkasında kalmalıdır:
    # PI / 2 (90°) ile 3 * PI / 2 (270°) arası yukarı bakar
    var is_facing_north: bool = angle > (PI * 0.5) and angle < (PI * 1.5)
    
    if is_facing_north:
        beak_sprite.z_index = -1
        eyes_sprite.z_index = -1
        head_group.z_index = 0
        body_sprite.z_index = 1
    else:
        beak_sprite.z_index = 2
        eyes_sprite.z_index = 2
        head_group.z_index = 1
        body_sprite.z_index = 0
```

---

## 4. Dinamik Uzuvlar & Esneme: `Line2D` (`limb_line_2d.gd`)

Boyun, bacaklar veya kollar için sprite çizmek yerine, iki rig noktası arasında dinamik gerilen bir `Line2D` kullanmak karakterin esnemesini (squash & stretch) ve doğallığını muazzam artırır.

```gdscript
# limb_line_2d.gd
extends Line2D

@export var start_node: Node2D
@export var end_node: Node2D

func _ready() -> void:
    top_level = true # Kendi yerel dönüşümünden bağımsız, global koordinatla çiz
    width = 6.0
    default_color = Color("e0a526") # Bacak / boyun rengi
    round_precision = 8
    begin_cap_mode = Line2D.LINE_CAP_ROUND
    end_cap_mode = Line2D.LINE_CAP_ROUND

func _process(_delta: float) -> void:
    if is_instance_valid(start_node) and is_instance_valid(end_node):
        clear_points()
        add_point(start_node.global_position)
        add_point(end_node.global_position)
```

---

## 5. Karakter Tasarımı (Art & Rigging Kuralları)

Bu tekniği başarıyla uygulamak için grafik tasarımda şu kurallara dikkat edin:

1. **Yuvarlak ve Organik Formlar:** Küre, elips, silindir ve yumuşak kıvrımlı tasarımlar açısı değiştikçe formunu korur. Keskin köşeli kutular bu teknikte sahte durur çünkü gerçek 3D poligon kenarları yoktur.
2. **Karakter Mockup & Parçalara Ayırma (Figma / Inkscape / Photoshop):**
   - Karakteri hafif yukarıdan (30°-45° oblique) bakış açısıyla çizin.
   - Parçaları ayrı PNG olarak dışa aktarın:
     - `body.png`
     - `head.png`
     - `beak.png` (veya burun/ağız)
     - `eye.png`
     - `foot_left.png`, `foot_right.png`
     - `shadow.png` (yarı saydam siyah elips)
3. **Animasyon (Tween & Wobble):**
   - Karakter yürürken `BodyAnchor.position.y` değerini bir tween ile hafifçe zıplatın (`bobbing`).
   - Ayak çapalarını (`FootAnchorL`, `FootAnchorR`) sırayla öne ve arkaya hareket ettirerek doğal bir top-down yürüme hissi yakalayın.

---

## 7. İnsan (Humanoid) Karakter Uyarlaması: Saç, Kollar, Bacaklar ve Yüz

İnsan karakterlerde (2 kol, 2 bacak, gövde, kafa, yüz ve saç) bu tekniği uygularken dikkat edilmesi gereken kritik tasarım ve katman mimarisi şöyledir:

### 1. Stil Kuralı (Orantı)
- Gerçekçi (anatomik) insan formları bu matematikte garip görünebilir.
- Bu teknik en çok **Chibi / Stylized / Cartoon** insan formlarında harikalar yaratır (*Animal Crossing, Zelda: Minish Cap / Link's Awakening, Fall Guys, Cult of the Lamb* tarzı).
- Yuvarlak bir kafa formu, silindirik/yuvarlak bir gövde ve hafif abartılı saç kütleleri mükemmel sonuç verir.

### 2. İnsan Karakter Parçaları (PNG Çıktıları)
Tek bir çizimden (hafif yukarıdan/önden bakış) şu parçalar ayrıştırılır:
- `shadow.png` (Zemin elips gölgesi)
- `foot_l.png`, `foot_r.png` (Ayakkabılar)
- `torso.png` (Gövde / Kıyafet)
- `arm_l.png`, `arm_r.png` veya `hand_l.png`, `hand_r.png` (Eller / Kollar)
- `head_base.png` (Yüzün ten rengi yuvarlak kafatası)
- `face.png` (Gözler, kaşlar, ağız tek bir grupta)
- `hair_front.png` (Ön saç / Kahkül)
- `hair_back.png` (Arka saç / Ense / Saç arkası kütlesi - **Kritik Parça!**)

### 3. İnsan Rig Hiyerarşisi
```text
HumanRig (Node2D, scale = Vector2(1.0, 0.5))
├── FeetLayer (position.y = 0)
│   ├── FootAnchorL ──> RemoteTransform2D ──> FootL
│   └── FootAnchorR ──> RemoteTransform2D ──> FootR
├── TorsoLayer (position.y = -18)
│   ├── TorsoAnchor ──> RemoteTransform2D ──> Torso
│   ├── ShoulderL (position.x = -12) ──> ArmAnchorL ──> HandL
│   └── ShoulderR (position.x = +12) ──> ArmAnchorR ──> HandR
└── HeadLayer (position.y = -40)
    └── HeadAnchor (rotation = angle)
        ├── HairBackAnchor (position.y = +4) ──> RemoteTransform2D ──> HairBack
        ├── HeadBaseAnchor ──> RemoteTransform2D ──> HeadBase
        ├── FaceAnchor (position.y = -4) ──> RemoteTransform2D ──> FaceGroup
        └── HairFrontAnchor (position.y = -6) ──> RemoteTransform2D ──> HairFront
```

### 4. İnsan Karakterde Saç & Kol Z-Index Mantığı (Ön vs Arka)

İnsan karakterin arkaya döndüğünü gösteren en büyük görsel numara **Saç Arkası (`hair_back`)** ve **Yüz (`face`)** katman sıralamasıdır:

```gdscript
func update_human_sorting(angle: float) -> void:
    # Karakter arkaya/kuzeye bakıyor (PI/2 ile 3*PI/2 arası)
    var is_facing_back: bool = angle > (PI * 0.5) and angle < (PI * 1.5)
    
    if is_facing_back:
        face_group.visible = false            # Yüz arkadan görünmez
        hair_front.z_index = 0
        head_base.z_index = 1
        hair_back.z_index = 2                 # Arka saç kafanın ÜSTÜNE çıkar, kafanın arkasını örter!
        torso.z_index = 1
    else:
        face_group.visible = true             # Yüz görünür
        hair_back.z_index = -1                # Arka saç kafanın arkasında kalır
        head_base.z_index = 0
        face_group.z_index = 1                # Yüz kafanın üstünde
        hair_front.z_index = 2                # Ön saç/kahkül yüzün üstünde
        torso.z_index = 0

    # Yanlara bakarken (Doğu / Batı) kolların derinliği:
    # Örneğin 0 ile PI arası sağ kol önde, sol kol gövdenin arkasında kalabilir:
    if angle > 0 and angle < PI:
        hand_r.z_index = torso.z_index + 1
        hand_l.z_index = torso.z_index - 1
    else:
        hand_r.z_index = torso.z_index - 1
        hand_l.z_index = torso.z_index + 1
```

### 5. Kollar ve Bacaklar İçin 2 Seçenek:
1. **Rayman / Animal Crossing Tarzı (Floating Limbs):** Kollar ve bacaklar çizilmez, sadece eller ve ayaklar gövdenin etrafında süzülür. Hem çizimi çok kolaydır hem de son derece şirin bir cartoon havası verir.
2. **Line2D Eklem Bağı:** Gövde omuz noktasından ele uzanan bir `Line2D` (`top_level = true`) ten veya tişört renginde dinamik kol çizer; el nereye giderse kol oraya esner.

---

## 8. Sık Karşılaşılan Hatalar ve Çözümleri

| Hata / Belirti | Nedeni | Çözüm |
|---|---|---|
| **Sprite basık/ezik görünüyor** | `RemoteTransform2D` ölçeği kopyalıyor | `update_scale = false` yapın. |
| **Kafa gövdeden bağımsız kopuyor** | Ebeveynlik zinciri kırılmış | `RemoteTransform2D` ile boyun/omuz pozisyonunu kafa köküne kopyalayın (`NeckPositionCopy`). |
| **Arkaya döndüğünde gaga gövdenin önünde kalıyor** | Z-index güncellenmiyor | `_set_direction` içinde açı aralığına göre `z_index = -1` uygulayın. |
| **Karakter titriyor (jitter)** | `_process` ile fizik çakışması | Karakter hareketi `CharacterBody2D` ile yapılıyorsa yön güncellemelerini fizik hızına göre yapın: `direction = velocity.angle()`. |
