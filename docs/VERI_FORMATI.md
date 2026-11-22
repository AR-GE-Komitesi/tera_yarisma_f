# Veri formatı — yemekhane israf analizi

> Bu belge `israf/formatlar.py` dosyasından `python manage.py format_belgesi` komutuyla üretilir. Elle düzenlemeyin.

Panel dört CSV dosyası alır. Görüntü işleme ekibi yalnızca `tepsiler.csv` dosyasını üretir; diğer üçü yemekhane tarafındandır.

| Dosya | Kim | Ne sıklıkla | Bir satır |
|---|---|---|---|
| `yemekler.csv` | Yemekhane yönetimi (panel sahibi) | Menüye yeni bir yemek girdiğinde | Bir satır = bir yemek |
| `ogunler.csv` | Yemekhane yönetimi | Yalnızca servis saati varsayılandan farklı olan günler için | Bir satır = bir günün bir öğünü |
| `uretim.csv` | Yemekhane (servis kapanınca) | Her öğünden sonra | Bir satır = o öğünde çıkan bir yemek |
| `tepsiler.csv` | Görüntü işleme ekibi | Her öğünün tepsileri işlendikten sonra | Bir satır = bir tepsideki bir tabak (uzun format) |

## Bütün dosyalar için

- Kodlama UTF-8 (BOM'lu ya da BOM'suz). Excel'in Türkçe kaydettiği Windows-1254 dosyalar da okunur, uyarı verilir.
- Ayraç virgül `,` (önerilen). Türkçe Excel'in ürettiği noktalı virgül `;` ve sekme de otomatik tanınır.
- İlk satır başlıktır. Sütun sırası önemli değildir; başlıkta büyük/küçük harf ve Türkçe karakter farkı tolere edilir.
- Ondalık ayırıcı nokta ya da virgül olabilir (`12.5` ve `12,5` aynıdır). Binlik ayırıcı kullanılmaz.
- Bir dosya birden fazla günü içerebilir. Hatalı tek bir satır varsa dosyanın tamamı reddedilir, hiçbir şey yazılmaz.
- Yükleme sırası: yemekler → (ogunler) → uretim → tepsiler.
- Yemekhane kaydı ve tepsi analizi öğün öğün yazılır. Daha önce yüklenmiş bir öğünü içeren dosya, yerine geçme onayı verilmedikçe reddedilir; böylece aynı öğünün iki parçası birbirini sessizce silmez.

## Yemek kodları nasıl eşleşir

1. Yemekhane yönetimi her yemeği bir kez `yemekler.csv` ile kataloğa ekler. Kod değişmez.
2. Yemekhane her öğünden sonra `uretim.csv` yükler. Bu dosya o öğünün menüsüdür.
3. Görüntü işleme ekibi panelden menüyü (`/veri/menu.csv`) ya da kataloğu (`/veri/yemekler.csv`) indirir ve modelin sınıflarını bu kodlarla adlandırır.
4. `tepsiler.csv` yüklenirken her kod o öğünün menüsüyle karşılaştırılır. Menüde olmayan kod dosyayı reddettirir; hata satır numarasıyla gösterilir.

## yemekler.csv — Yemek kataloğu

- **Kim doldurur:** Yemekhane yönetimi (panel sahibi)
- **Ne sıklıkla:** Menüye yeni bir yemek girdiğinde
- **Satır:** Bir satır = bir yemek
- **Benzersiz anahtar:** `yemek_kodu`
- **Yeniden yükleme:** Aynı kod varsa adı, kategorisi, türü ve (doluysa) saklanabilir bilgisi güncellenir. Kod silinmez.

| Sütun | Zorunlu | Açıklama | Örnek |
|---|---|---|---|
| `yemek_kodu` | evet | Yemek kataloğundaki kod. Küçük harf, rakam, `_` ve `-`; Türkçe karakter yok. | `tavuk_sote` |
| `yemek_adi` | evet | Panelde görünen ad. | `Tavuk Sote` |
| `kategori` | evet | Tepsideki yeri: `ana_yemek` (Ana yemek), `yan_yemek` (Yan yemek), `corba` (Çorba), `salata` (Salata), `icecek` (İçecek), `tatli` (Tatlı / meyve). | `ana_yemek` |
| `tur` | hayır | Gruplama için yemek türü (ör. tavuk, kırmızı et, bakliyat, sebze, pilav, makarna). Sıralama sayfasındaki tür listeleri bu sütundan çıkar. | `tavuk` |
| `saklanabilir` | hayır | Kapalı ambalajlı, artanı stoka geri dönen ürün (ör. kapalı ayran, paketli meyve) için `evet`. Bu ürünlerde artan miktar israf sayılmaz; yalnızca tabakta kalan sayılır. Boş bırakılırsa yeni yemekte `hayir` kabul edilir, var olan yemekte önceki değer korunur. | `hayir` |

Örnek:

```csv
yemek_kodu,yemek_adi,kategori,tur,saklanabilir
tavuk_sote,Tavuk Sote,ana_yemek,tavuk,hayir
izgara_kofte,Izgara Köfte,ana_yemek,kırmızı et,hayir
pirinc_pilavi,Pirinç Pilavı,yan_yemek,pilav,hayir
mercimek_corbasi,Mercimek Çorbası,corba,bakliyat çorbası,hayir
ayran,Ayran,icecek,içecek,evet
```

## ogunler.csv — Öğün bilgileri (isteğe bağlı)

- **Kim doldurur:** Yemekhane yönetimi
- **Ne sıklıkla:** Yalnızca servis saati varsayılandan farklı olan günler için
- **Satır:** Bir satır = bir günün bir öğünü
- **Benzersiz anahtar:** `tarih + ogun`
- **Yeniden yükleme:** Dosyadaki her (tarih, öğün) için önceki kayıt değiştirilir.

| Sütun | Zorunlu | Açıklama | Örnek |
|---|---|---|---|
| `tarih` | evet | Servis günü. `YYYY-AA-GG` (önerilen) ya da `GG.AA.YYYY`. | `2026-11-20` |
| `ogun` | evet | Öğün: `kahvalti` (Kahvaltı), `ogle` (Öğle), `aksam` (Akşam). | `ogle` |
| `servis_baslangic` | evet | Servisin açıldığı saat, `SS:DD`. | `11:30` |
| `servis_bitis` | evet | Servisin kapandığı saat, `SS:DD`. | `14:00` |
| `not` | hayır | Serbest not (ör. sınav haftası, yağmurlu gün). | `Sınav haftası` |

Kurallar:

- Bu dosya yüklenmeyen günlerde Ayarlar sayfasındaki varsayılan servis saatleri kullanılır.
- Servis saatleri yalnızca bitiş zamanını servisin yüzdesi olarak göstermek için kullanılır.

Örnek:

```csv
tarih,ogun,servis_baslangic,servis_bitis,not
2026-11-20,ogle,11:00,14:30,"Sınav haftası, uzatılmış servis"
```

## uretim.csv — Yemekhane günlük kaydı

- **Kim doldurur:** Yemekhane (servis kapanınca)
- **Ne sıklıkla:** Her öğünden sonra
- **Satır:** Bir satır = o öğünde çıkan bir yemek
- **Benzersiz anahtar:** `tarih + ogun + yemek_kodu`
- **Yeniden yükleme:** Dosyadaki her (tarih, öğün) için o öğünün bütün kayıtları silinip dosyadakiler yazılır. O öğünün kaydı daha önce yüklendiyse dosya reddedilir; düzeltilmiş dosya «Önceki verinin yerine geçsin» onayıyla yüklenir.

| Sütun | Zorunlu | Açıklama | Örnek |
|---|---|---|---|
| `tarih` | evet | Servis günü. `YYYY-AA-GG` (önerilen) ya da `GG.AA.YYYY`. | `2026-11-20` |
| `ogun` | evet | Öğün: `kahvalti` (Kahvaltı), `ogle` (Öğle), `aksam` (Akşam). | `ogle` |
| `yemek_kodu` | evet | Yemek kataloğundaki kod. Küçük harf, rakam, `_` ve `-`; Türkçe karakter yok. | `tavuk_sote` |
| `uretilen_porsiyon` | evet | Üretilen miktarın tabak karşılığı. Kazandaki miktar ÷ tabak başına konan miktar (ör. 1000 birim ÷ 10 birim = 100). Ondalık olabilir. | `320` |
| `artan_porsiyon` | evet | Servis kapandığında kazanda kalan miktarın tabak karşılığı. Bittiyse `0`. | `0` |
| `bitis_saati` | hayır | Yemek servis sırasında tükendiyse tükendiği saat, `SS:DD`. Tükenmediyse boş bırakılır. | `12:48` |

Kurallar:

- Bu dosya o günün menüsüdür: tepsi analizindeki yemek kodları bu dosyadaki kodlarla eşleşmelidir.
- Bir öğünün bütün yemekleri tek dosyada gelir.
- `artan_porsiyon`, `uretilen_porsiyon` değerini aşamaz.
- `bitis_saati` dolu ama `artan_porsiyon` 0 değilse uyarı verilir.
- Bir öğünde ana yemek ya da yan yemek sayısı 2 değilse uyarı verilir; tercih analizi o öğünü atlar.

Örnek:

```csv
tarih,ogun,yemek_kodu,uretilen_porsiyon,artan_porsiyon,bitis_saati
2026-11-20,ogle,mercimek_corbasi,1150,62,
2026-11-20,ogle,tavuk_sote,620,0,12:48
2026-11-20,ogle,izgara_kofte,560,38,
2026-11-20,ogle,pirinc_pilavi,600,71.5,
2026-11-20,ogle,ayran,500,35,
```

## tepsiler.csv — Tepsi analizi (görüntü işleme çıktısı)

- **Kim doldurur:** Görüntü işleme ekibi
- **Ne sıklıkla:** Her öğünün tepsileri işlendikten sonra
- **Satır:** Bir satır = bir tepsideki bir tabak (uzun format)
- **Benzersiz anahtar:** `tarih + ogun + tepsi_id + yemek_kodu`
- **Yeniden yükleme:** Dosyadaki her (tarih, öğün) için o öğünün tepsi özeti silinip dosyadan yeniden hesaplanır. O öğünün tepsileri daha önce yüklendiyse dosya reddedilir; düzeltilmiş dosya «Önceki verinin yerine geçsin» onayıyla yüklenir.

| Sütun | Zorunlu | Açıklama | Örnek |
|---|---|---|---|
| `tarih` | evet | Servis günü. `YYYY-AA-GG` (önerilen) ya da `GG.AA.YYYY`. | `2026-11-20` |
| `ogun` | evet | Öğün: `kahvalti` (Kahvaltı), `ogle` (Öğle), `aksam` (Akşam). | `ogle` |
| `tepsi_id` | evet | Tepsinin o öğün içindeki benzersiz kimliği. Aynı tepsideki tabaklar aynı kimliği taşır. | `T00001` |
| `yemek_kodu` | evet | Yemek kataloğundaki kod. Küçük harf, rakam, `_` ve `-`; Türkçe karakter yok. | `tavuk_sote` |
| `durum` | evet | Tabağın durumu: `bitti` (Tamamı yendi), `yarim` (Yarısı yendi), `dokunulmadi` (Dokunulmadı), `belirsiz` (Belirlenemedi). | `yarim` |

Kurallar:

- Bir öğünün bütün tepsileri tek dosyada gelir. Tepsiler birden çok kamerada ya da partide işlendiyse dosyalar birleştirilip gönderilir; aynı öğünün ikinci parçası ayrı yüklenirse reddedilir.
- Tepside olmayan yemek için satır yazılmaz. Alınıp hiç yenmeyen tabak `dokunulmadi` olarak yazılır.
- `belirsiz`: model tabağı göremedi ya da karar veremedi. Oranlara katılmaz, ayrıca sayılır.
- O öğün için yemekhane kaydı yüklüyse, kaydında olmayan bir yemek kodu hata sayılır.
- Tepsi kimliği her tepside bir kez sayılır; analiz edilen tepsi sayısı farklı kimliklerden çıkar.

Örnek:

```csv
tarih,ogun,tepsi_id,yemek_kodu,durum
2026-11-20,ogle,T00001,mercimek_corbasi,bitti
2026-11-20,ogle,T00001,tavuk_sote,bitti
2026-11-20,ogle,T00001,pirinc_pilavi,yarim
2026-11-20,ogle,T00001,ayran,dokunulmadi
2026-11-20,ogle,T00002,mercimek_corbasi,belirsiz
```
