# Yemekhane İsraf Analizi

Üniversite yemekhanesinde **hangi yemeğin ne kadar israf edildiğini** gösteren bir yönetim paneli.

Yemekhane her gün yemek üretir. Bir kısmı hiç servis edilmeden kazanda kalır, bir kısmı öğrencinin
tabağında yenmeden geri döner. Bu panel ikisini de ölçer, yemek yemek ve gün gün gösterir. Amaç, yönetimin
"porsiyonlar fazla mı?", "bu yemek menüden çıkmalı mı?", "hangisinden daha çok pişirmeli?" sorularına
veriyle cevap verebilmesi ve toplam israfın azalmasıdır.

## İçindekiler

1. [Proje ne yapıyor?](#1-proje-ne-yapıyor)
2. [Hangi sorulara cevap verir?](#2-hangi-sorulara-cevap-verir)
3. [Temel kavramlar](#3-temel-kavramlar)
4. [Örnek: bir öğün nasıl hesaplanır?](#4-örnek-bir-öğün-nasıl-hesaplanır)
5. [Kurulum ve ilk açılış](#5-kurulum-ve-ilk-açılış)
6. [Kullanım kılavuzu](#6-kullanım-kılavuzu)
   - [6.1 Kim ne yapar?](#61-kim-ne-yapar)
   - [6.2 Tipik bir gün](#62-tipik-bir-gün)
   - [6.3 Dosya yükleme, adım adım](#63-dosya-yükleme-adım-adım)
   - [6.4 Yemekhane: günlük kaydı Excel'de hazırlamak](#64-yemekhane-günlük-kaydı-excelde-hazırlamak)
   - [6.5 Görüntü işleme ekibiyle çalışmak](#65-görüntü-işleme-ekibiyle-çalışmak)
   - [6.6 Katalog, düzeltme ve silme](#66-katalog-düzeltme-ve-silme)
   - [6.7 Panelde gezinmek](#67-panelde-gezinmek)
   - [6.8 Sonuçları okumak](#68-sonuçları-okumak)
   - [6.9 Excel'e rapor almak](#69-excele-rapor-almak)
   - [6.10 Eşikleri ve servis saatlerini değiştirmek](#610-eşikleri-ve-servis-saatlerini-değiştirmek)
   - [6.11 Düzenli değerlendirme önerisi](#611-düzenli-değerlendirme-önerisi)
7. [Veri formatları](#7-veri-formatları)
8. [Panel sayfaları](#8-panel-sayfaları)
9. [Eşik profilleri](#9-eşik-profilleri)
10. [Kullanıcılar ve yetkiler](#10-kullanıcılar-ve-yetkiler)
11. [Sık karşılaşılan durumlar](#11-sık-karşılaşılan-durumlar)
12. [Komutlar](#12-komutlar)
13. [Üretim ortamında çalıştırma](#13-üretim-ortamında-çalıştırma)
14. [Proje yapısı](#14-proje-yapısı)
15. [Tasarım kararları ve sınırlar](#15-tasarım-kararları-ve-sınırlar)

---

## 1. Proje ne yapıyor?

Proje iki parçadan oluşur. **Bu depo yalnızca ikinci parçadır.**

| Parça | Kim yapar | Ne yapar |
|---|---|---|
| Görüntü işleme | Ayrı bir ekip | Yemekhaneden dönen tepsilerin fotoğraflarını inceler. Her tabak için "tamamı yendi", "yarısı yendi" ya da "hiç dokunulmadı" kararı verir. Sonucu CSV dosyası olarak verir. |
| **Analiz paneli (bu depo)** | Bu ekip | Görüntü işlemenin CSV'sini ve yemekhanenin günlük kaydını alır. İkisini birleştirir, israf oranlarını hesaplar ve web panelinde gösterir. |

```
  Yemekhane                              Görüntü işleme ekibi
  (ne kadar üretildi, ne kadar arttı,    (her tepsideki her tabak:
   hangi yemek saat kaçta tükendi)        tamamı / yarısı yendi / dokunulmadı)
          │  uretim.csv                         │  tepsiler.csv
          └──────────────────┬──────────────────┘
                             ▼
              Bu panel: doğrular → birleştirir → hesaplar
                             ▼
     İsraf oranları · israf sıralamaları · tercih analizi · eşik işaretleri
                             ▼
                 Yemekhane yönetimi karar verir
```

**Panel ne yapmaz?**

- Görüntü işleme yapmaz. Fotoğraf görmez, yalnızca CSV okur.
- Karar vermez. "Bu yemeği kaldırın" demez; veriyi ve ayarlanabilir eşikleri gösterir. Menü günden güne
  değiştiği için kararı, oranları zaman içinde izleyen yönetim verir.
- Şimdilik veri CSV dosyasıyla gelir ve panel yerel bilgisayarda çalışır. Bunun dışındaki her şey (giriş,
  yetki, doğrulama, arşiv, yedekleme) gerçek kullanıma göre kuruludur.

## 2. Hangi sorulara cevap verir?

| Yönetimin sorusu | Panelde nereye bakılır |
|---|---|
| Bu dönem üretilen yemeğin yüzde kaçı israf oldu? | **Genel bakış** → Toplam israf oranı |
| En çok israf edilen yemekler hangileri? | **İsraf sıralaması** → Liste: Yemek |
| Tavuk yemekleri mi, bakliyat mı daha çok israf ediliyor? | **İsraf sıralaması** → Liste: Tür |
| Porsiyonlar gereğinden büyük mü? | **Bitirilmeyen tabak** oranı: tabakların çoğu bitirilmiyorsa porsiyon büyük olabilir |
| Hangi yemek alınıp hiç yenmiyor? | **İsraf sıralaması** → Ölçüt: Dokunulmayan tabak |
| Hangi yemekten gereğinden fazla pişiriliyor? | **İsraf sıralaması** → Ölçüt: Kazan artığı |
| Aynı gün çıkan iki ana yemekten hangisi tercih ediliyor? | **Tercih analizi** |
| Dün öğlen tam olarak ne oldu? | **Gün detayı** |
| Bir yemeğin geçmişi nasıl? | Herhangi bir tablodan yemeğin adına tıklayın |
| Salata ve ayran ne kadar alınıyor? | **Genel bakış** → Tepsi başına alım |
| Bütün veriler eksiksiz geldi mi? | **Veri durumu** |

## 3. Temel kavramlar

### Birim: porsiyon (tabak)

Bütün miktarlar **tabak karşılığı** olarak yazılır. Kazanda 1.000 birim yemek varsa ve tabağa 10 birim
konuyorsa, bu 100 porsiyon demektir. Artan miktar da aynı şekilde çevrilir.

### Bir tabağın dört durumu

| Durum | Anlamı | İsrafa katkısı |
|---|---|---|
| `bitti` | Tabağın tamamı yendi | 0 porsiyon |
| `yarim` | Yaklaşık yarısı yendi | 0,5 porsiyon |
| `dokunulmadi` | Alındı ama hiç yenmedi | 1 porsiyon |
| `belirsiz` | Görüntü işleme karar veremedi | Oranlara katılmaz, ayrıca sayılır |

### İsraf ölçüleri

Bir yemeğin bir öğündeki kaydı için: **U** üretilen porsiyon, **A** artan porsiyon, **S = U − A** servis
edilen porsiyon. Tepsilerden **b** tamamı yenen, **y** yarısı yenen, **d** dokunulmayan tabak sayısı;
**N = b + y + d**.

| Ölçü | Formül | Ne söyler |
|---|---|---|
| **Kazan artığı oranı** | A ÷ U | Pişirilip hiç servis edilmeyen pay. Yüksekse gereğinden fazla pişiriliyor. |
| **Bitirilmeyen tabak oranı** | (y + d) ÷ N | Tabağını bitirmeyenlerin payı. Çoğunluk bitiremiyorsa porsiyon büyük olabilir. |
| **Dokunulmayan tabak oranı** | d ÷ N | Alıp hiç yemeyenlerin payı. Yüksekse yemeğin kendisi istenmiyor olabilir. |
| **Tabak artığı oranı** | (0,5·y + d) ÷ N | Servis edilen yemeğin tabakta kalan payı. |
| **Toplam israf** | A + S × tabak artığı oranı | Üretilip yenmeyen her şey, porsiyon olarak. |
| **Toplam israf oranı** | toplam israf ÷ U | **Ana ölçü.** Düşürülmek istenen sayı budur. |

### Tercih ölçüleri

Her öğünde iki ana yemek ve iki yan yemek çıkar; öğrenci her birinden birini seçer. Bir seçenek tükenince
sonra gelenler diğerini almak zorunda kalır. Bu yüzden tercih tek bir sayıyla ölçülmez:

| Ölçü | Anlamı |
|---|---|
| **Alım payı** | Servis edilenlerin bu seçeneğe düşen payı. **Tercihin ana ölçüsü.** Tükenme sonrası mecburi geçişleri de içerir; tükenen yemeğin gerçek talebi bu yüzden alım payından yüksektir. |
| **Üretim payı** | Yemekhanenin bu seçeneğe ayırdığı pay. Alım payıyla farkı, talebin ne kadar doğru tahmin edildiğini gösterir. |
| **Rakibinden önce tükendi** | İki seçenekten bu önce bitti: talep, ayrılan üretimi aştı. **Tek başına tercih göstermez**, çünkü az üretilen yemek de önce tükenir. Üretim payıyla birlikte okunur. |
| **Tükenme anı** | Servisin yüzde kaçında tükendi (%0 açılış, %100 kapanış). Küçükse erken bitti. |

### Diğer terimler

| Terim | Anlamı |
|---|---|
| **Çıkış** | Yemeğin menüye girdiği öğün sayısı. Az çıkan yemeğin oranı tek bir günün koşullarından etkilenebilir. |
| **Tam kayıt** | Hem yemekhane kaydı hem tepsi verisi olan kayıt. Toplam israf yalnızca bunlardan hesaplanır. |
| **Tepsi başına alım** | Bir kategoriden alınan tabak ÷ analiz edilen tepsi. Salata için 0,50 = tepsilerin yarısında salata var. |
| **Saklanabilir ürün** | Kapalı ambalajlı ürün (ör. kapalı ayran). Artanı depoya döner, israf sayılmaz. |
| **Eşik profili** | Hangi değerin dikkat çekici sayılacağını belirleyen üç ayardan biri ([bölüm 9](#9-eşik-profilleri)). |

## 4. Örnek: bir öğün nasıl hesaplanır?

20 Kasım öğle yemeğinde **Tavuk Sote** ve **Izgara Köfte** çıktı. Servis 11:30–14:00 arası.

Yemekhanenin kaydı (`uretim.csv`):

```csv
tarih,ogun,yemek_kodu,uretilen_porsiyon,artan_porsiyon,bitis_saati
2026-11-20,ogle,tavuk_sote,600,40,
2026-11-20,ogle,izgara_kofte,400,0,12:40
```

Tavukta 600 porsiyon üretildi, 40'ı arttı, 560'ı servis edildi. Görüntü işleme bu 560 tabağı gördü:
420'si tamamen yendi, 100'ü yarısı yenerek döndü, 40'ına hiç dokunulmadı.

| Ölçü | Hesap | Sonuç |
|---|---|---|
| Kazan artığı oranı | 40 ÷ 600 | %6,7 |
| Bitirilmeyen tabak oranı | (100 + 40) ÷ 560 | %25,0 |
| Dokunulmayan tabak oranı | 40 ÷ 560 | %7,1 |
| Tabak artığı oranı | (0,5 × 100 + 40) ÷ 560 | %16,1 |
| Tabakta kalan | 560 × %16,1 | 90 porsiyon |
| Toplam israf | 40 + 90 | 130 porsiyon |
| **Toplam israf oranı** | 130 ÷ 600 | **%21,7** |

Varsayılan "Dengeli" profilde toplam israf eşiği %20'dir. Tavuğun %21,7'lik değeri panelde **▲** ile
işaretlenir. Diğer iki değer eşiklerin altında kaldığı için işaretlenmez.

**Tercih tarafı.** Köfte 12:40'ta tükendi, tavuk tükenmedi. Panel bu öğünü "Yalnız Izgara Köfte
tükendi" olarak gösterir:

| | Üretim payı | Alım payı | Tükenme anı |
|---|---|---|---|
| Izgara Köfte | 400 ÷ 1000 = %40 | 400 ÷ 960 = %41,7 | 12:40 → servisin %47'si |
| Tavuk Sote | %60 | 560 ÷ 960 = %58,3 | tükenmedi |

Yönetim bunu şöyle okuyabilir: Köfteye üretimin %40'ı ayrıldı ve servisin yarısı dolmadan bitti. 12:40'tan
sonra gelenler mecburen tavuk aldı. Bu yüzden köftenin gerçek talebi %41,7'den yüksek, tavuğunki
%58,3'ten düşüktür. Mecburen tavuk alanlar tabağı daha sık bitirmemiş de olabilir. Bu yorum yönetime
aittir; panel yalnızca sayıları gösterir.

**Birden çok öğün birleşince** oranlar günlük oranların ortalaması değil, toplamların oranıdır. Bir gün
600 porsiyondan 130'u, ertesi gün 200 porsiyondan 10'u israf olduysa dönem oranı (130 + 10) ÷ 800 = %17,5'tir.
Basit ortalama (%13,3) olmaz; kalabalık gün daha çok etkiler.

## 5. Kurulum ve ilk açılış

### Kurulum (bir kez)

Gereken: Windows ve Python 3.10 ya da üstü. Proje klasöründe (`yemekhane-israf`) PowerShell açıp sırayla:

```powershell
python -m venv .venv                                           # projeye özel Python ortamı
.\.venv\Scripts\python.exe -m pip install -r requirements.txt  # gerekli paketler
.\.venv\Scripts\python.exe manage.py migrate                   # veritabanını oluşturur
.\.venv\Scripts\python.exe manage.py createsuperuser           # ilk yönetici hesabı (ad ve parola sorar)
```

### Paneli açmak (her kullanımda)

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Tarayıcıda <http://127.0.0.1:8000> adresini açın ve yönetici hesabıyla giriş yapın. PowerShell penceresi
açık kaldığı sürece panel çalışır; kapatmak için pencerede `Ctrl+C`'ye basın.

### Örnek veriyle denemek (isteğe bağlı)

Gerçek veri gelmeden paneli görmek için:

```powershell
.\.venv\Scripts\python.exe manage.py ornek_veri --yukle
```

Bu komut **yapay** veri üretip yükler: 40 iş günü öğle yemeği, 28 yemek, yaklaşık 44 bin tepsi. Veri bir
simülasyondur, gerçek ölçüm değildir. Öğrenciler servis süresine yayılarak gelir, iki seçenekten birini
popülerliğe göre seçer, seçtiği tükenmişse diğerine geçer. Dosyalar `ornek_veri/` klasörüne de yazılır;
format örneği olarak açıp bakılabilir.

İlk bakılacak yerler:

1. **Genel bakış:** dönemin toplam israf oranı ve günlük grafik.
2. **İsraf sıralaması:** en çok israf edilen yemekler. "Liste" seçimini "Tür" yapıp yemek türlerini karşılaştırın.
3. **Gün detayı:** tek bir öğünün bütün ayrıntısı.
4. **Tanımlar ve formatlar:** paneldeki her sayının tanımı.

**Gerçek veriye geçerken** örnek veriyi temizlemek için: paneli kapatın, `instance/` klasörünü silin,
sonra `migrate` ve `createsuperuser` komutlarını yeniden çalıştırın.

## 6. Kullanım kılavuzu

### 6.1 Kim ne yapar?

| Rol | Görevi | Panel hesabı |
|---|---|---|
| **Yemekhane** | Her öğünden sonra ne kadar üretildiğini, ne kadar arttığını ve tükenen yemeklerin saatini kaydeder (`uretim.csv`). | Gerekmez; dosyayı panel sorumlusuna verir. Personel hesabı varsa kendisi de yükleyebilir. |
| **Görüntü işleme ekibi** | Tepsileri işler, `tepsiler.csv` üretir. | Gerekmez; dosyayı panel sorumlusuna verir. |
| **Panel sorumlusu** | Dosyaları yükler, hataları düzeltir, yemek kataloğunu ve kullanıcıları yönetir. | Personel yetkili hesap |
| **Yemekhane yönetimi** | Sonuçları izler, karar verir. | Yalnızca izleme hesabı yeterli |

### 6.2 Tipik bir gün

| Ne zaman | Kim | Ne yapar |
|---|---|---|
| Servis sırasında | Yemekhane | Tükenen yemeğin saatini not eder. |
| Servis kapanınca | Yemekhane | Her yemek için üretilen ve artan miktarı porsiyona çevirir, `uretim.csv`'yi doldurur ([6.4](#64-yemekhane-günlük-kaydı-excelde-hazırlamak)). |
| Aynı gün | Panel sorumlusu | `uretim.csv`'yi yükler ([6.3](#63-dosya-yükleme-adım-adım)). O öğünün menüsünü görüntü işleme ekibine gönderir ([6.5](#65-görüntü-işleme-ekibiyle-çalışmak)). |
| Akşam | Görüntü işleme ekibi | Tepsileri işler, `tepsiler.csv`'yi gönderir. |
| Akşam ya da ertesi sabah | Panel sorumlusu | `tepsiler.csv`'yi yükler. |
| Ertesi gün | Yönetim | **Gün detayı**'nda dünkü öğüne bakar. |

Sıra zorunlu değildir; tepsi dosyası önce gelirse de yüklenir ve yemekhane kaydı gelince analiz tamamlanır.
Yine de en sağlıklısı yemekhane kaydını önce yüklemektir: o zaman tepsi dosyasındaki her yemek kodu o
öğünün menüsüyle karşılaştırılır ve yanlış etiketler hemen yakalanır.

### 6.3 Dosya yükleme, adım adım

Personel yetkisi gerekir.

1. Sol menüden **Veri yükleme**'ye girin.
2. **Dosya türü** listesinden dosyanın türünü seçin:

   | Seçenek | Dosya |
   |---|---|
   | Yemek kataloğu | `yemekler.csv` |
   | Öğün bilgileri | `ogunler.csv` |
   | Yemekhane günlük kaydı | `uretim.csv` |
   | Tepsi analizi (görüntü işleme) | `tepsiler.csv` |

3. **CSV dosyası** alanından dosyayı seçin.
4. Daha önce yüklenmiş bir öğünün **düzeltilmiş** dosyasını yüklüyorsanız **Önceki verinin yerine geçsin**
   kutusunu işaretleyin. İlk yüklemede işaretlemeyin.
5. **Yükle ve doğrula** düğmesine basın.
6. **Yükleme raporu** sayfası açılır:
   - **✓ Yüklendi:** Veri panele girdi. **Güncellenen öğünler** bölümündeki bağlantılar sonuca götürür.
     **Uyarılar** bölümü varsa okuyun: uyarılar yüklemeyi durdurmaz ama verideki bir tutarsızlığa işaret
     eder (ör. "tabak sayısı servis edilen porsiyonu aşıyor").
   - **✕ Reddedildi:** Hiçbir şey yazılmadı. **Hatalar** bölümü her hatanın satır numarasını ve sütununu
     gösterir. Satır numarası, dosya Excel'de açıldığında soldaki satır numarasıyla aynıdır (başlık 1.
     satırdır). Dosyayı düzeltip **Yeni dosya yükle** ile baştan yükleyin.

Bilmeniz gerekenler:

- Bir dosya birden çok günü içerebilir. En fazla 20 MB olabilir: öğün başına ~1.100 tepsiyle yaklaşık 100
  öğünlük tepsi verisi. Daha uzun dönemleri tarih aralıklarına bölerek yükleyin.
- **Bir öğün tek dosyada gelir.** Yemekhane kaydı ya da tepsi analizi daha önce yüklenmiş bir öğünü içeren
  dosya reddedilir. Bu, aynı öğünün iki parçasının (ör. iki kameranın tepsileri) birbirini sessizce
  silmesini önler. Parçaları tek dosyada birleştirip yükleyin.
- **Düzeltilmiş bir dosya** yüklerken **Önceki verinin yerine geçsin** kutusunu işaretleyin. Dosyadaki
  öğünlerin eski verisi silinip yenisi yazılır; önce silmek gerekmez. Yeni dosyada eski kayıttaki bir yemek
  yoksa ya da tepsi sayısı azaldıysa rapor bunu uyarı olarak gösterir.
- Reddedilenler dahil her yükleme, dosyasıyla birlikte arşivlenir. **Veri yükleme** sayfasındaki **Son
  yüklemeler** tablosundan rapora, raporda **Arşivdeki dosyayı indir** ile dosyanın kendisine ulaşılır.

### 6.4 Yemekhane: günlük kaydı Excel'de hazırlamak

1. **Veri yükleme** → **Şablonlar** tablosunda `uretim.csv` satırındaki **Excel (TR)** bağlantısıyla
   şablonu indirin. Türkçe Excel'de sütunlara ayrılmış olarak açılır.
2. Örnek satırları silin. O öğünde çıkan **her yemek** için bir satır yazın:

   | Sütun | Ne yazılır | Örnek |
   |---|---|---|
   | `tarih` | Servis günü | `2026-11-20` ya da `20.11.2026` |
   | `ogun` | `ogle`, `aksam` ya da `kahvalti` (`Öğle` yazmak da olur) | `ogle` |
   | `yemek_kodu` | Katalogdaki kod. Bütün kodlar **Veri yükleme** → **Yemek kataloğu** bağlantısıyla indirilir. | `tavuk_sote` |
   | `uretilen_porsiyon` | Kazandaki miktar ÷ tabak başına konan miktar | 1000 ÷ 10 → `100` |
   | `artan_porsiyon` | Servis kapanınca kalan miktar, aynı şekilde porsiyona çevrilmiş. Bittiyse `0`. | `12,5` |
   | `bitis_saati` | Yemek tükendiyse saati. Tükenmediyse boş bırakın. | `12:40` |

3. Çorba, salata ve ayran dahil **tepside olabilecek her şeyi** yazın. Görüntü işleme bir tepside ayran
   görür ama o öğünün kaydında ayran yoksa tepsi dosyası reddedilir.
4. **Dosya → Farklı Kaydet** ile dosya türü olarak **CSV UTF-8** seçeneğini seçin (yoksa düz **CSV** de olur).
5. [6.3](#63-dosya-yükleme-adım-adım)'teki adımlarla "Yemekhane günlük kaydı" türüyle yükleyin.

### 6.5 Görüntü işleme ekibiyle çalışmak

Panel ve görüntü işleme aynı yemeğe aynı **kodu** vermelidir. Bunun için:

**Başlangıçta (bir kez)**

- **Veri yükleme** → **Görüntü işleme ekibi için** → **Yemek kataloğu** bağlantısıyla bütün kodları indirip
  ekibe verin. Ekip, modelinin yemek sınıflarını bu kodlarla adlandırır.
- Ekibe [docs/VERI_FORMATI.md](docs/VERI_FORMATI.md) belgesini verin. `tepsiler.csv` için gereken her şey
  oradadır.

**Her öğün**

1. Yemekhane kaydını yükledikten sonra **Gün detayı**'nda o öğünü açın.
2. **Bu öğünün menüsünü indir (görüntü ekibi için)** bağlantısıyla o öğünde çıkan yemeklerin kodlarını
   indirip ekibe gönderin.
3. Ekipten gelen `tepsiler.csv`'yi "Tepsi analizi (görüntü işleme)" türüyle yükleyin. Menüde olmayan bir kod
   varsa dosya reddedilir ve satır numarası gösterilir; ekipten düzeltilmiş dosyayı isteyin.
4. Bir öğünün bütün tepsileri tek dosyada gelmelidir. Tepsiler birden çok kamerada ya da partide
   işleniyorsa ekip dosyaları birleştirip göndermelidir; aynı öğünün ikinci dosyası panelde reddedilir.

**Kalite kontrolü:** **Veri durumu** sayfasındaki **Ana yemek kapsaması**, görüntü işlemenin tepsilerin ne
kadarını gördüğünü gösterir ve %100'e yakın olmalıdır. **Belirsiz tabak** oranı yükseliyorsa ekibe
bildirin. Katalogda yeni bir yemek açıldığında güncel kataloğu ekibe yeniden gönderin.

İleride dosyalar bir klasöre düzenli olarak düşerse, yükleme `csv_yukle` komutuyla ([bölüm 12](#12-komutlar))
zamanlanmış bir göreve bağlanabilir.

### 6.6 Katalog, düzeltme ve silme

- **Yeni yemek eklemek:** `yemekler.csv`'ye satır ekleyip "Yemek kataloğu" türüyle yükleyin. Dosyada
  yalnızca yeni yemeklerin olması yeterlidir; dosyada olmayan yemekler silinmez.
- **Kod kuralı:** küçük harf, rakam, `_` ve `-`. Türkçe karakter kullanılmaz: `tavuk_sis` doğru,
  `tavuk_şiş` yanlış. Kod bir kez verilince değiştirilmez; yemeğin adını değiştirmek için aynı kodla yeni
  adı yükleyin.
- **Kategori** şunlardan biridir: `ana_yemek`, `yan_yemek`, `corba`, `salata`, `icecek`, `tatli`.
  **Tür** serbest metindir (ör. `tavuk`, `bakliyat`); türe göre listelerin doğru çıkması için aynı tür
  her seferinde aynı yazılmalıdır.
- **Kapalı ambalajlı ürünler** (ör. kapalı ayran) için `saklanabilir` sütununa `evet` yazın; artan miktar
  israf sayılmaz.
- **Yönetim sayfasından ekleme:** `/admin/` → **Yemek kataloğu** → Ekle da çalışır; kod kuralı orada da
  denetlenir.
- **Hatalı bir öğünü düzeltmek:** o öğünün dosyasını düzeltin, **Önceki verinin yerine geçsin** kutusunu
  işaretleyip yeniden yükleyin; eskisinin yerine geçer.
- **Bir öğünü tamamen silmek:** `/admin/` → **Üretim kayıtları**, **Tabak özetleri** ve **Tepsi
  sayıları**'ndan o güne ait kayıtları silin.

### 6.7 Panelde gezinmek

- **Sol menü** üç bölümdür: *Analiz* (Genel bakış, Gün detayı, İsraf sıralaması, Tercih analizi), *Veri*
  (Veri yükleme, Veri durumu), *Sistem* (Ayarlar, Tanımlar ve formatlar, Yönetim). Ayarlar ve Yönetim
  yalnızca personel yetkisiyle görünür.
- **Filtre satırı:** analiz sayfalarının üstündedir. **Başlangıç**, **Bitiş** ve **Öğün** seçilip
  **Uygula**'ya basılır. Sağdaki hazır seçenekler (Tüm dönem, Son 7 / 30 / 90 gün) **son verinin
  tarihine** göre hesaplanır, bugüne göre değil. Seçilen aralık sayfalar arasında gezinirken korunur.
- **Bağlantılar:** bir yemeğin adına tıklamak o yemeğin geçmiş sayfasını, bir tarihe tıklamak o öğünün
  **Gün detayı**'nı açar.
- **Gün detayı**'nda **← Önceki öğün** ve **Sonraki öğün →** düğmeleriyle öğün öğün gezilir; üstteki tarih
  kutusuyla istenen güne gidilir.

### 6.8 Sonuçları okumak

**Genel bakış**

- Üstteki kutular dönemin özetidir. En soldaki **Toplam israf oranı** ana ölçüdür.
- **Grafik:** her çubuk bir gündür (92 günden uzun dönemlerde bir hafta). Mavi kısım kazan artığı, turuncu
  kısım tabak artığıdır; çubuğun toplam yüksekliği o günün toplam israf oranıdır. Kırmızı kesikli çizgi
  etkin eşik profilinin toplam israf eşiğidir. Çubuğun üzerine gelince değerler görünür; **Tablo
  görünümü** aynı sayıları tablo olarak açar.
- **Kategorilere göre:** ana yemek, yan yemek, çorba, salata ve içecek ayrı ayrı. **Tepsi başına alım**
  sütunu isteğe bağlı kalemlerin (salata, ayran) ne kadar alındığını gösterir.
- **En yüksek / en düşük toplam israf:** dönemin ilk ve son beş yemeği.

**Tablolardaki işaretler**

| İşaret | Anlamı |
|---|---|
| **▲** | Değer, etkin eşik profilinin eşiğini aştı. Üzerine gelince hangi eşik olduğu yazar. |
| Tabak durumu çubuğu | Soldan sağa üç parça: tamamı yendi, yarısı yendi, dokunulmadı. Sağdaki iki parça büyüdükçe israf artar. Üzerine gelince sayılar görünür. |
| **—** | Bu değer için veri yok (ör. o öğünün tepsi verisi gelmemiş). |
| stoka döner | Saklanabilir ürün; artan miktar israf sayılmaz. |

**Gün detayı**

- Menüdeki her yemek kategorisine göre listelenir: üretilen, artan, servis edilen porsiyon.
- **Bitiş** sütunu tükenme saatini ve servisin yüzde kaçında tükendiğini gösterir; tükenmediyse
  "tükenmedi" yazar.
- **Tamamı / yarısı / dokunulmadı** sütunu tabak sayılarıdır; `+N?` belirlenemeyen tabakları gösterir.
- Alttaki **Seçenekler arası tercih** iki ana yemeği ve iki yan yemeği karşılaştırır.

**İsraf sıralaması**

- **Liste:** Yemek, Tür ya da Kategori bazında. **Kategori:** yalnızca bir kategoriyi listeler.
  **Sıralama ölçütü:** listenin neye göre sıralanacağı. **En az çıkış:** daha az çıkmış yemekleri gizler.
- Sütun başlıklarına tıklayarak da sıralanır.
- **En az çıkışı 3–4 yapmak**, bir iki kez çıkmış yemeklerin listeyi yanıltmasını önler.

**Tercih analizi**

- Ana yemek ve yan yemek ayrı tablolarda; tablolar **Ort. alım payı**na göre sıralıdır. Tercihin doğrudan
  ölçüsü budur: iki seçenekten servis edilen tabakların yüzde kaçının bu yemekten alındığı.
- **Rakibinden önce tükendi** sütunu tek başına tercih göstermez: az üretilen yemek de önce tükenir. Bu
  sütunu **Ort. üretim payı**yla birlikte okuyun. Üretim payı rakibininkine eşit ya da yüksekken önce
  tükenen yemek gerçekten daha çok istenmiştir. Alım payı üretim payına yakın ve yemek sık tükeniyorsa
  talep, ayrılan paydan fazladır.
- Örnek veriyle yapılan ölçümde yemeklerin gerçek popülerliğini alım payı iyi izledi, önce tükenme izlemedi.
  Çünkü yemekhane az sevilen yemeği az üretiyordu ve küçük üretimdeki tahmin hatası onu daha sık
  tükendiriyordu.
- Alttaki **Öğün öğün eşleşmeler** her günün sonucunu tek tek gösterir.

**Okuma rehberi.** Panel karar vermez; yönetim bir yemeği değerlendirirken şu tabloyu kullanabilir:

| Görülen | Olası anlamı |
|---|---|
| Çıkış sayısı az (1–2) | Karar için erken; birkaç kez daha çıkmasını bekleyin. |
| Kazan artığı yüksek | Gereğinden fazla pişiriliyor. |
| Bitirilmeyen tabak yüksek, dokunulmayan düşük | Yemek yeniyor ama porsiyon büyük. |
| Dokunulmayan tabak yüksek | Yemek alınıyor ama istenmiyor (standart tepsiye konduğu için alınıyor olabilir). |
| Alım payı rakiplerine karşı sürekli yüksek | Öğrenciler bu seçeneği tercih ediyor. |
| Rakibinden sık önce tükeniyor | Talep, ayrılan üretimi aşıyor; üretimdeki payı artırılabilir. Üretim payı zaten düşükse bu bir tercih işareti değil, az üretim işaretidir. |

### 6.9 Excel'e rapor almak

1. **İsraf sıralaması**'nda filtre satırından dönemi ve öğünü, alttaki satırdan listeyi ve ölçütü seçip
   **Listele**'ye basın.
2. Sağ üstteki **CSV indir** düğmesine basın.

Dosya Türkçe Excel'de doğrudan sütunlara ayrılmış olarak açılır. Ekrandaki seçimlerin hepsi rapora
uygulanır. Sütunlar: ad, çıkış sayısı, üretilen ve servis edilen porsiyon; kazan artığı, tamamı yenen
tabak, bitirilmeyen tabak, dokunulmayan tabak, tabak artığı ve toplam israf yüzdeleri; israf edilen
porsiyon; analiz edilen tabak ve bunun tamamı yenen, yarısı yenen, dokunulmayan tabak sayıları. Liste
"Yemek" iken yemek kodu, kategori ve tür sütunları da eklenir. `=`, `+`, `-` ya da `@` ile başlayan bir
ad, Excel'in onu formül olarak çalıştırmaması için başına `'` eklenerek yazılır.

### 6.10 Eşikleri ve servis saatlerini değiştirmek

Personel yetkisi gerekir.

1. Sol menüden **Ayarlar**'a girin.
2. **Eşik profili** bölümünde kullanılacak profili seçin: Sıkı, Dengeli ya da Esnek ([bölüm 9](#9-eşik-profilleri)).
   İsterseniz herhangi bir profilin üç değerini de değiştirin.
3. **Varsayılan servis saatleri** bölümünde öğünlerin açılış ve kapanış saatlerini kontrol edin. Tükenme
   anının yüzdesi bu saatlere göre hesaplanır.
4. **Kaydet**'e basın. Değişiklik bütün sayfalara hemen yansır. Veri değişmez; yalnızca hangi değerin
   ▲ ile işaretleneceği değişir.

Tek bir günün servis saati farklıysa (sınav haftası, erken kapanış) ayarları değiştirmeyin; `ogunler.csv`
ile yalnızca o günü yükleyin.

### 6.11 Düzenli değerlendirme önerisi

| Sıklık | Nereye bakılır |
|---|---|
| Her gün | **Gün detayı**'nda dünkü öğün; **Veri durumu**'nda eksik veri var mı. |
| Her hafta | **Genel bakış**'ta "Son 7 gün"; ▲ ile işaretli yemekler. |
| Her ay ve dönem sonu | **İsraf sıralaması**'nda "Tüm dönem", En az çıkış 3–4; Liste "Tür" ile tür karşılaştırması; **Tercih analizi**. Excel'e alıp toplantıda kullanın. |

## 7. Veri formatları

| Dosya | Bir satır | Sütunlar (* zorunlu) |
|---|---|---|
| `yemekler.csv` | Bir yemek | `yemek_kodu`*, `yemek_adi`*, `kategori`*, `tur`, `saklanabilir` |
| `ogunler.csv` | Bir günün bir öğünü | `tarih`*, `ogun`*, `servis_baslangic`*, `servis_bitis`*, `not` |
| `uretim.csv` | O öğünde çıkan bir yemek | `tarih`*, `ogun`*, `yemek_kodu`*, `uretilen_porsiyon`*, `artan_porsiyon`*, `bitis_saati` |
| `tepsiler.csv` | Bir tepsideki bir tabak | `tarih`*, `ogun`*, `tepsi_id`*, `yemek_kodu`*, `durum`* |

`tepsiler.csv` **her tabak için bir satır** içerir. Tepside dört tabak varsa dört satır yazılır; tepside
olmayan yemek için satır yazılmaz:

```csv
tarih,ogun,tepsi_id,yemek_kodu,durum
2026-11-20,ogle,T00001,mercimek_corbasi,bitti
2026-11-20,ogle,T00001,tavuk_sote,yarim
2026-11-20,ogle,T00001,pirinc_pilavi,bitti
2026-11-20,ogle,T00001,ayran,dokunulmadi
2026-11-20,ogle,T00002,mercimek_corbasi,bitti
```

Bu format, günlük özetten daha çok bilgi taşır: özet bu satırlardan çıkarılabilir ama tersi olmaz. Salata
ve ayran alma oranları da tepsi bazında hesaplanır.

Kolaylıklar:

- Türkçe Excel'in kaydettiği dosyalar da okunur: noktalı virgül ayracı, `12,5` gibi ondalık virgül,
  `20.11.2026` gibi tarih, Windows-1254 kodlaması.
- Başlıklarda ve seçenek değerlerinde büyük/küçük harf ve Türkçe karakter farkı sorun değildir
  (`Yemek_Adı` = `yemek_adi`, `Öğle` = `ogle`). Yemek kodlarında Türkçe karakter kullanılmaz.
- Panelin **Veri yükleme** sayfasında her dosyanın şablonu iki biçimde indirilebilir: standart CSV ve
  Türkçe Excel'de doğrudan açılan biçim.

Bütün sütunların açıklaması, kuralları ve örnekleri: **[docs/VERI_FORMATI.md](docs/VERI_FORMATI.md)**. Bu
belge görüntü işleme ekibine ve yemekhaneye verilecek belgedir. `israf/formatlar.py` dosyasından üretilir;
elle düzenlenmez.

## 8. Panel sayfaları

| Sayfa | Adres | Ne gösterir |
|---|---|---|
| Genel bakış | `/` | Dönemin toplam israf oranı, kazan ve tabak artığı, günlük (92 günden uzun dönemde haftalık) grafik, kategori tablosu, en çok ve en az israf edilen 5 yemek |
| Gün detayı | `/gun/` | Bir öğünün menüsü: üretilen, artan, tükenme saati, tabak durumları; iki seçeneğin karşılaştırması; önceki/sonraki öğüne geçiş |
| İsraf sıralaması | `/siralama/` | Dönem başından sonuna israf listesi. Yemek, tür ya da kategori bazında; istenen ölçüte göre sıralanır; Excel'e uygun CSV olarak indirilir |
| Tercih analizi | `/tercih/` | Yemeklerin ortalama alım payı (tercih) ve üretim payı, rakibinden önce tükenme ve tükenme anı; öğün öğün eşleşmeler |
| Yemek sayfası | `/yemek/<kod>/` | Bir yemeğin bütün geçmişi, grafiği ve rakipleriyle eşleşmeleri |
| Veri yükleme | `/veri/` | CSV yükleme, şablonlar, görüntü ekibi için menü ve katalog, son yüklemeler |
| Veri durumu | `/veri/durum/` | Her öğün için hangi verinin geldiği, görüntü işlemenin tepsilerin ne kadarını gördüğü, eksik ya da tutarsız kayıtlar |
| Ayarlar | `/ayarlar/` | Eşik profili seçimi ve değerleri, varsayılan servis saatleri |
| Tanımlar ve formatlar | `/tanimlar/` | Her formülün tanımı ve CSV kuralları |
| Yönetim | `/admin/` | Kullanıcılar, yemek kataloğu ve kayıtların doğrudan düzenlenmesi |

## 9. Eşik profilleri

Eşikler, tablolarda dikkat çekmesi gereken değerleri **▲** ile işaretler. Karar üretmez, menüyü
değiştirmez. Üç hazır profil vardır; biri seçilir ve her profilin değerleri **Ayarlar** sayfasından
değiştirilebilir ([6.10](#610-eşikleri-ve-servis-saatlerini-değiştirmek)):

| Profil | Bitirilmeyen tabak | Kazan artığı | Toplam israf |
|---|---|---|---|
| Sıkı | %30 | %5 | %10 |
| **Dengeli** (varsayılan) | %50 | %10 | %20 |
| Esnek | %70 | %20 | %30 |

Değer eşiğe eşit ya da eşikten büyükse işaretlenir. İşaretin üzerine gelince hangi profilin hangi eşiğinin
aşıldığı görünür.

## 10. Kullanıcılar ve yetkiler

- Bütün sayfalar giriş ister (`/giris/`).
- **Personel** yetkisi olan kullanıcılar (yönetim sayfasında "Personel durumu") veri yükler ve ayarları
  değiştirir. Diğer kullanıcılar yalnızca analizleri görür; örneğin yemekhane müdürüne yalnızca izleme
  hesabı verilebilir.
- **Yeni kullanıcı:** `/admin/` → **Kullanıcılar** → **Kullanıcı ekle** → kullanıcı adı ve parola →
  Kaydet. Açılan sayfada ad-soyadı yazın; veri yükleyecekse **Personel durumu**'nu işaretleyin → Kaydet.
- Yönetim sayfasında katalog ve kayıtları düzenlemek için süper kullanıcı olmak ya da ilgili izinlerin
  ayrıca verilmesi gerekir.
- **Parola değiştirmek:** `.\.venv\Scripts\python.exe manage.py changepassword <kullanıcı>`

## 11. Sık karşılaşılan durumlar

| Görülen | Nedeni | Çözüm |
|---|---|---|
| Tarayıcı panele bağlanamıyor | Panel çalışmıyor (PowerShell penceresi kapanmış). | [Bölüm 5](#5-kurulum-ve-ilk-açılış)'teki `runserver` komutuyla açın. |
| "Katalogda olmayan yemek kodu" | Kod `yemekler.csv` ile eklenmemiş. | Önce yemeği kataloğa ekleyin, sonra dosyayı yeniden yükleyin. |
| "… yemekhane kaydında yok" | Görüntü ekibi o öğünün menüsünde olmayan bir kod yazmış ya da `uretim.csv`'de o yemek eksik. | Etiketi ya da yemekhane kaydını düzeltip yeniden yükleyin. |
| "Satırda başlıktan fazla değer var" | Virgül ayraçlı dosyada `12,5` gibi tırnaksız ondalık virgül kullanılmış. | `12.5` yazın ya da dosyayı Excel (TR) şablonuyla hazırlayın. |
| "Eksik sütun … Bu dosya «…» formatına uyuyor" | Yüklerken yanlış dosya türü seçilmiş. | Doğru türü seçip tekrar yükleyin. |
| "… daha önce yüklenmiş … tepsi var" ya da "… yemek kaydı var" | Dosyadaki öğün zaten yüklü. | Dosya aynı öğünün bir parçasıysa parçaları tek dosyada birleştirip yükleyin. Düzeltilmiş dosyaysa **Önceki verinin yerine geçsin** kutusunu işaretleyip yeniden yükleyin. |
| "önceki … tepsinin yerine bu dosyadaki … tepsi geçti" (uyarı) | Onaylı düzeltme dosyasında öncekinden az tepsi var. | Beklenen bir düzeltmeyse sorun yok. Değilse eksik parçayı birleştirip yeniden yükleyin; eski dosya arşivdedir. |
| "Dosya 20 MB sınırını aşıyor" | Dosya çok uzun bir dönemi içeriyor. | Tarih aralıklarına bölün (ör. ay ay). Bir öğünü iki dosyaya bölmeyin. |
| "Dosya Windows-1254 kodlamasıyla okundu" (uyarı) | Excel'de düz CSV seçilerek kaydedilmiş. | Sorun değil. Mümkünse **CSV UTF-8** ile kaydedin. |
| "… için yemekhane kaydı henüz yüklenmemiş" (uyarı) | Tepsi dosyası, yemekhane kaydından önce geldi. | Sorun değil. `uretim.csv` yüklenince analiz tamamlanır. |
| "… Bu öğün tercih analizine katılmaz" (uyarı) | O öğünde 2'den farklı sayıda ana ya da yan yemek var. | Bilgi amaçlıdır; israf hesapları etkilenmez. |
| Excel'de açınca her şey tek sütunda | Standart CSV şablonu Türkçe Excel'de açılmış. | **Excel (TR)** şablonunu kullanın. |
| Toplam israf "—" görünüyor | O kayıt için tepsi verisi yok. | **Veri durumu** sayfasından eksik öğünleri kontrol edin. |
| Menüde "Ayarlar" yok | Kullanıcının personel yetkisi yok. | Yönetim sayfasından yetki verin ([bölüm 10](#10-kullanıcılar-ve-yetkiler)). |

## 12. Komutlar

Hepsi proje klasöründe `.\.venv\Scripts\python.exe manage.py <komut>` biçiminde çalışır.

| Komut | Ne yapar |
|---|---|
| `runserver` | Paneli <http://127.0.0.1:8000> adresinde açar (deneme ve yerel kullanım). |
| `csv_yukle <tür> <dosya>... [--yerine-gecsin]` | CSV yükler. Tür: `yemekler`, `ogunler`, `uretim`, `tepsiler`. Dosya reddedilirse çıkış kodu 1 olur; otomasyon için uygundur. Verisi zaten yüklü bir öğünü içeren dosya `--yerine-gecsin` verilmedikçe reddedilir. 20 MB sınırı yalnızca paneldeki yüklemeye uygulanır. |
| `ornek_veri [--yukle] [--yerine-gecsin] [--gun 40] [--bitis 2026-11-20] [--tohum 42]` | Yapay örnek veri üretir. Aynı tohum her zaman aynı veriyi verir. Aynı günler zaten yüklüyse `--yukle` ile birlikte `--yerine-gecsin` gerekir. |
| `format_belgesi` | `docs/VERI_FORMATI.md` belgesini yeniden üretir. Format değişince çalıştırılır. |
| `test israf` | Testleri çalıştırır. |
| `createsuperuser` / `changepassword` | Yönetici oluşturur / parola değiştirir (Django'nun kendi komutları). |

Testler şunları kapsar: Türkçe Excel dosyalarının okunması, bütün doğrulama kuralları, ya-hep-ya-hiç
yükleme, onaylı yeniden yükleme ve bölünmüş dosyanın reddi, tepsi özetleme, elle hesaplanmış örneklerle
bütün formüller, tercih kuralları ve sıralaması, yönetim sayfasında kod kuralı, Excel raporunun formül koruması,
sayfalar, yetkiler ve format belgesinin koddan sapmaması.

## 13. Üretim ortamında çalıştırma

Geliştirme sunucusu (`runserver`) yalnızca deneme ve yerel kullanım içindir. Panel bir sunucuda birden çok
kişiye açılacaksa:

```powershell
$env:DJANGO_DEBUG = "0"
$env:DJANGO_ALLOWED_HOSTS = "panel.ornek.edu.tr"
$env:DJANGO_HTTPS = "1"     # panel HTTPS arkasındaysa
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\.venv\Scripts\waitress-serve.exe --listen=0.0.0.0:8000 config.wsgi:application
```

| Ortam değişkeni | Varsayılan | Anlamı |
|---|---|---|
| `DJANGO_SECRET_KEY` | `instance/secret_key.txt` üretilir | Oturumları imzalayan gizli anahtar |
| `DJANGO_DEBUG` | `1` | `0` = üretim modu (hata ayrıntıları gizlenir) |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Panelin yayınlandığı alan adları, virgülle |
| `DJANGO_HTTPS` | `0` | `1` = çerezler yalnızca HTTPS'le gider, HTTP yönlendirilir |
| `DJANGO_HSTS_SECONDS` | `0` | HTTPS kalıcı olarak kurulunca HSTS süresi (saniye) |
| `ISRAF_INSTANCE_DIR` | `instance/` | Veritabanı, arşiv ve anahtarın tutulduğu klasör |

**Yedekleme:** `instance/` klasörü veritabanını, arşivlenen bütün CSV dosyalarını ve gizli anahtarı
içerir. Yedeklenmesi gereken tek klasör budur. Git'e eklenmez.

## 14. Proje yapısı

```
yemekhane-israf/
├── config/                   Django ayarları, adresler, test çalıştırıcısı
├── israf/                    Uygulama
│   ├── models.py             Veri modeli: yemek, üretim kaydı, tabak özeti, eşik profili, yükleme kaydı
│   ├── formatlar.py          CSV sözleşmesi — tek kaynak (doğrulama, şablonlar ve belge buradan beslenir)
│   ├── aktarim.py            CSV okuma, doğrulama, ya-hep-ya-hiç yazma
│   ├── analiz.py             İsraf ve tercih ölçülerinin hesabı
│   ├── views.py, urls.py     Panel sayfaları
│   ├── templates/israf/      Sayfa şablonları
│   ├── static/israf/         Stil, grafik betiği, Chart.js 4.4.1 (yerel kopya, internet gerekmez)
│   ├── management/commands/  csv_yukle, ornek_veri, format_belgesi
│   ├── migrations/           Veritabanı şeması ve başlangıç ayarları (3 eşik profili, servis saatleri)
│   └── tests/                Testler
├── templates/registration/   Giriş sayfası
├── docs/VERI_FORMATI.md      Format belgesi (üretilmiş)
├── instance/                 Veritabanı, arşiv, gizli anahtar (git dışı, yedeklenir)
├── ornek_veri/               Üretilen örnek CSV'ler (git dışı)
└── requirements.txt          Django 5.2, whitenoise, waitress
```

## 15. Tasarım kararları ve sınırlar

**Kararlar**

- **Ham tepsi satırları veritabanında tutulmaz.** Her gün, öğün ve yemek için durum sayıları özetlenir;
  dosyanın kendisi arşivlenir. Yılda milyonlarca satır yerine birkaç bin satır tutulur; gerekirse arşivden
  yeniden yüklenir.
- **Oranlar porsiyon ağırlıklıdır.** Dönem oranı toplamların oranıdır ([bölüm 4](#4-örnek-bir-öğün-nasıl-hesaplanır)).
- **Toplam israf yalnızca tam kayıtlardan hesaplanır.** Kazan artığı bütün yemekhane kayıtlarından, tabak
  oranları bütün tepsi verilerinden hesaplanır. Eksikler **Veri durumu** sayfasında görünür.
- **Saklanabilir ürünlerde artan israf sayılmaz.** Bu ürünlerde üretim tabanı servis edilen miktardır;
  israf yalnızca tabakta kalandır. Varsayılan "hayır"dır; yemekhane işaretlemedikçe hesap değişmez.
- **Format tek yerde tanımlıdır.** Doğrulama, şablonlar, Tanımlar sayfası ve format belgesi aynı tanımdan
  beslenir; biri değişip diğeri eski kalamaz.
- **Bir öğünün üzerine yazmak açık onay ister.** Öğün daha önce yüklendiyse yeni dosya reddedilir;
  düzeltme **Önceki verinin yerine geçsin** ile yüklenir. Onay olmasaydı aynı öğünün ikinci parçası
  birinciyi uyarısız silerdi (örnek veride 1.008 tepsilik öğün 504'e iniyordu).
- **Yükleme sınırı 20 MB'dir.** İçe aktarma dosya boyutunun yaklaşık 25 katı bellek kullanır (7,7 MB'lık
  dosya 195 MB). 20 MB yaklaşık 500 MB belleğe karşılık gelir.

**Bilinen sınırlar**

- **Yarım tabak 0,5 porsiyon sayılır.** Görüntü işleme üç durum verdiği için ara değerler (%25, %75)
  ayırt edilmez.
- **Porsiyonlar eşit sayılır.** Toplam israf bir kase çorbayı ve bir tabak tavuğu birer porsiyon sayar;
  kilogram ya da maliyet ağırlığı yoktur.
- **Tabak oranı örneklemden gelebilir.** Görüntü işleme bazı tepsileri kaçırırsa oran görülen tabaklardan
  hesaplanıp servis edilen porsiyonun tamamına uygulanır. Ne kadarının görüldüğü **Veri durumu**
  sayfasında "ana yemek kapsaması" olarak izlenir.
- **Alım payı gerçek talebi tam göstermez.** Tükenme sonrası mecburi geçişleri içerir; bu yüzden tükenme
  bilgisiyle birlikte okunmalıdır.
- **Veri yalnızca CSV ile gelir** ve panel şimdilik yerel çalışır. İleride görüntü işleme doğrudan bağlanmak
  isterse `aktarim.py` içindeki doğrulama aynen kullanılabilir.
