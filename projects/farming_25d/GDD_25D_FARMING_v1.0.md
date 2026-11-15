# O Y U N  T A S A R I M  B E L G E S İ · G D D  V 1 . 0
## 2.5D FARMING — Birinci Şahıs Retro FPS + Izgara Tabanlı Çiftçilik Simülasyonu Hibriti

- **Belge Kodu:** `GDD-2026-001` · Sürüm `1.0` (Ekim 2026)
- **Motor:** Godot 4.x (`SubViewport 480×270` + `Sprite3D Y-Billboard` + `MultiMeshInstance3D`)
- **Görsel Hedef:** `480×270` işleme tamponu @ `60 FPS`, **32-Renk Referans Palet**, **8×8 Bayer Dither**, **Fosfor Yeşili CRT** arayüz estetiği
- **Perspektif:** Birinci şahıs (`70°–80° FOV`), `PPU = 32` piksel kilidi (`pixel snapping`)
- **Proje Klasörü:** `D:\GameMaker\projects\farming_25d`

---

## Bölüm 1 · Proje Genel Bakış ve Tasarım Sütunları

**2.5D FARMING**, klasik 1990’lar birinci şahıs nişancı (FPS) hissini, ızgara tabanlı çiftçilik ve yaşam simülasyonu döngüsüyle aynı dünya içinde birleştiren bir hibrit oyundur:
> *“Gündüz ek, gece kaz, her iki dünyanın da ritmi seni bir sonraki güne taşısın.”*

| Sütun | Çiftçilik Karşılığı | FPS & Madencilik Karşılığı |
| :--- | :--- | :--- |
| **1. RİTİM** | Gün atlama tetikli büyüme; sabah ekim penceresi | Anlık ışın izleme (`hitscan`), refleks temelli vuruş geri bildirimi |
| **2. DERİNLİK** | Ekin kârı alet yükseltmelerini finanse eder | Cevher mağaza gelirine dönüşür; zırh canı ve ölüm cezasını korur |
| **3. OTANTİKLİK** | `16×16` tarla dokuları, paletli toprak geçişleri | `480×270` düşük çözünürlük + `8×8 Bayer dither`, 8 yönlü düşman kareleri |

---

## Bölüm 2 · Çekirdek Oyun Döngüleri (Mikro, Mezo, Makro)

### 2.1 Mikro Döngü (10–60 sn): Alet Kullanımı
- Alet kullan (**Çapa / Kazma / Sulama Kabı / Tırpan**) → Karo veya cevher durumu anında değişir → **3 Kanallı Geri Bildirim** (Görsel durum değişimi + Piksel parçacık + 8-bit ses).

### 2.2 Mezo Döngü (18–22 dk): Oyun Günü ve 5 Aşama (Tablo 3)

| Aşama | Oyun Saati | Gerçek Süre | Kural Etkileri |
| :--- | :---: | :---: | :--- |
| **1. Sabah** | `06:00–09:00` | 3 dk | Sulama bayrakları sıfırlanır; toprak kuru dokuya döner; **Gün Hedefi Tahtası** gösterilir |
| **2. Gündüz** | `09:00–17:00` | 8 dk | Ekim-sulama penceresi; mağaza ve maden erişimi tam; düşmanlar normal saldırganlıkta |
| **3. Akşam** | `17:00–20:00` | 3 dk | Mağaza son satış penceresi (**%105 akşam fiyat bonusu**); düşman saldırganlığı +%25 artar |
| **4. Gece** | `20:00–06:00` | 5 dk | Mağaza kapalı; oyuncu ışık yarıçapı `5,5 m`’ye düşer; cevher parlaklığı artar |
| **5. Gün Atlama** | `Kayıt + Tarama` | 1 dk | Sulanmış karolar taranır; büyüme sayaçları `+1` ilerler; günlük özet ve otomatik kayıt |

---

## Bölüm 3 · Çiftçilik Sistemi

### 3.1 Karo Durum Makinesi (Tablo 4)
1. **İşlenmemiş** (Çim dokusu + otlar) — *Çapa vuruşu* → **Sürülmüş**
2. **Sürülmüş** (Koyu toprak sıraları) — *Tohum çantası + ekin seçimi* → **Ekili**
3. **Ekili** (Tohum / büyüme evresi karesi) — *Sulama kabı vuruşu* → **Sulanmış-Ekili**
4. **Sulanmış-Ekili** (Koyu ıslak toprak + mavi yansıma + mini harita mavi nokta) — *Gün atlama taraması* → **Büyüme sayacı +1**
5. **Hasada Hazır** (Olgun evre karesi + parıltı) — *Boş el veya Tırpan vuruşu* → **İşlenmemiş (Ürün + Deneyim)**

### 3.2 Başlangıç Ekin Kataloğu ve Denge Değerleri (Tablo 5 & Şekil 3)

| Ekin | Tohum Maliyeti | Satış Fiyatı | Sulanmış Gün | Görsel Evre Sayısı | Çok Hasat | Kâr / Gün (Kuruş) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **1. Yonca** | 10 | 30 | 2 | 3 | Hayır | **2,7** |
| **2. Turp** | 18 | 55 | 3 | 3 | Hayır | **3,8** |
| **3. Buğday** | 25 | 80 | 3 | 4 | Evet (`×2`) | **4,6** |
| **4. Patates** | 40 | 130 | 4 | 4 | Hayır | **5,9** |
| **5. Havuç** | 55 | 190 | 5 | 4 | Evet (`×2`) | **6,8** |
| **6. Lahana** | 70 | 240 | 5 | 5 | Hayır | **7,4** |
| **7. Domates** | 95 | 150 | 6 | 5 | Evet (`×4`) | **9,6** |
| **8. Kabak** | 130 | 310 | 6 | 5 | Hayır | **11,2** |

---

## Bölüm 4 · Madencilik ve Zindan Sistemi

### 4.1 Altı Temel Cevher Kataloğu (Tablo 6)

| Cevher | Dayanıklılık | Gerekli Kazma | Bırakma | Birim Değer | Bulunma Katmanı |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Taş** | 3 | Temel | 2 taş | 2 | Tüm katmanlar, çok yaygın |
| **2. Bakır** | 5 | Temel | 2 bakır | 8 | Katman 1–2, yaygın |
| **3. Demir** | 8 | Bakır | 2 demir | 20 | Katman 2–3, orta |
| **4. Gümüş** | 12 | Demir | 2 gümüş | 45 | Katman 3–4, seyrek |
| **5. Altın** | 16 | Gümüş | 2 altın | 95 | Katman 4, cepler hâlinde |
| **6. Fosforit** | 22 | Altın | 1 kristal | 220 | Katman 4 nişleri, tekil (Fosfor yeşili parıltı) |

### 4.2 Dört Zindan Katmanı (Tablo 7)
- **K1 — Üst Galeri:** Ayakta durulabilir galeriler, turuncu fenerler (`Taş, Bakır`).
- **K2 — Boşluk Ağı:** Dikey şaftlar, kırılabilir ahşap iskeleler, düşüş hasarı (`Bakır, Demir`).
- **K3 — Su Damarları:** Sızan tavanlar, koyu yeşil taş, su dibinde dar görüş (`Demir, Gümüş`).
- **K4 — Fosfor Çekirdek:** Kalıcı karanlık, fosfor yeşili damarlar, oyuncu feneri zorunlu (`Gümüş, Altın, Fosforit`).

---

## Bölüm 5 · Savaş ve 8-Yönlü Düşman Yapay Zekâsı

### 5.1 Dört Durumlu Düşman FSM (Şekil 4)
- **DEVRİYE** (`8 m` menzil, `120°` görüş konisi) ↔ **TAKİP** (`mesafe < 2,5 m`) → **SALDIRI** (`can < %20`) → **GERİ ÇEKİLME** (Savunmacı türlerde kapalı).

### 5.2 Altı Düşman Türü Kataloğu (Tablo 8)

| Tür | Can | Hasar | Rol | Davranış Özeti (8-Yönlü Sprite Seti) |
| :--- | :-: | :-: | :--- | :--- |
| **1. Mayın Sıçanı** | 24 | 8 | Sürü | Yakın dövüş; 3–6 bireylik kümeler hâlinde devriye atar |
| **2. Fener Gölgesi** | 36 | 12 | Avcı | Görüş dışında hızlanır; ışık kaynağına yaklaşınca yavaşlar |
| **3. Kaya Fırlatıcı** | 44 | 16 | Menzilli | 6–10 m arası taş küresi (`12 m/sn`) fırlatır; yaklaşınca geri adımlar |
| **4. Damar Zırhlısı** | 90 | 14 | Savunmacı | Cevher damarlarını korur; vuruş anında hasar %50 azalır |
| **5. Fosfor Hayaleti** | 60 | 20 | Dolandırıcı | K4’e özel; yarı saydam, periyodik ışık kesintisinde hızlanır |
| **6. Galeri Muhafızı** | 150 | 24 | Katman Patronu | Her katman sonunda tekil; üç saldırı deseni sırayla döner |

---

## Bölüm 6 · Ekonomi ve Alet Yükseltme Yolu (Tablo 9 & Şekil 5)

| Alet / Ekipman | Bakır | Demir | Gümüş | Altın | Altın Kademe Ödülü |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Kazma** | 900 | 1.700 | 3.800 | 7.600 | Tek vuruşta K3 taş blokları kırılır (Kümülatif: `14.000`) |
| **2. Çapa** | 700 | 1.300 | 2.800 | 5.700 | `5×5` sürme alanı (Kümülatif: `10.500`) |
| **3. Sulama Kabı** | 500 | 1.000 | 2.100 | 4.400 | `24 karo` kapasite + otomatik dolum (Kümülatif: `8.000`) |
| **4. Tırpan** | 600 | 1.200 | 2.600 | 5.200 | `3×3` hasat + otomatik toplama |
| **5. Zırh Seti** | 800 | 1.500 | 3.400 | 6.800 | Ölümde madende kalan cevher cezası `%10`’dan `%5`’e düşer |

---

## Bölüm 7 · Dünya ve Bölüm Tasarımı (`240×240` Üstyapı — Tablo 10)

1. **Çiftlik Alanı (`80×80`):** Sürülebilir koyu toprak (`400 → 1.600 karo`), çeşme, küçük ahır, sera, kompost çukuru, fener direkleri.
2. **Köy Meydanı (`40×40`):** Taş döşeme, mağaza (4 sekme: Tohumlar, Sarf, Yükseltmeler, Geri Satış), müze panosu, NPC buluşması.
3. **Çayır Kuşağı (`60×50`):** Açık yeşil çim, seyrek ağaçlar (3B gövde + billboard taç), odun kaynağı.
4. **Bataklık Kenarı (`45×45`):** Suyu yüksek koyu yeşil zemin, bataklık yosunu, özel bitki kaynakları.
5. **Maden Girişi (`25×25`):** Kırık kayalar, maden tahtaları, katman seçim asansörü.
6. **Terkedilmiş Ahır (`30×30`):** Kırık çit, saman, yosunlu taş, kilitli sandık odaları, terk ahır balı.

---

## Bölüm 8 & 9 · Görsel Sanat Hattı (`480×270` + `32 Renk` + `8×8 Bayer Dither`) ve Fosfor CRT UI/UX

- **6 Aşamalı Görsel İşleme Hattı (Şekil 6):**
  `1. 3B Sahne (Düşük poligon + Y-Billboard + Gölge Vekili)` → `2. 480×270 SubViewport (PPU=32 Piksel Kilidi)` → `3. En Yakın Komşu (Nearest) Büyütme` → `4. 8×8 Bayer Dither` → `5. 32-Renk Referans Palet Öteleme` → `6. Üst Tamponda Filtresiz 2× Fosfor CRT UI`.
- **HUD Yerleşimi (Tablo 14):**
  - **Sol Üst:** Can + Zırh İkili Çubuğu
  - **Üst Orta:** Saat, Gün Göstergesi ve Faz İkonu (Gece yaklaşırken turuncu uyarı)
  - **Sağ Üst:** Mini Harita (Bölge adları + sulanmış karolar mavi nokta / madende katman taslağı)
  - **Sol Orta (Geçici — `H` Tuşu):** Gün Hedefi Tahtası
  - **Alt Orta:** 8 Yuvalık Hotbar (`1–4` Sabit Aletler: Kazma, Çapa, Sulama Kabı, Tırpan; `5–8` Tohum/Sarf/Silah; seçili yuva fosfor yeşili çerçeve)
  - **Dünya İçi:** Bakış noktasındaki `1×1 m` karo köşelerinde fosfor yeşili / geçersiz eylemde turuncu köşe imleci.
