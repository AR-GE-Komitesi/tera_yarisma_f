"""CSV veri sözleşmesi — tek kaynak.

Doğrulama (aktarim.py), indirilebilir şablonlar, paneldeki Tanımlar sayfası ve
docs/VERI_FORMATI.md belgesi bu tanımlardan üretilir. Bir sütun değişecekse
yalnızca burası değiştirilir.
"""
from dataclasses import dataclass

from .models import Category, ImportBatch, MealType, PlateState


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # code | text | date | meal | category | time | decimal | state
    required: bool
    description: str
    example: str


@dataclass(frozen=True)
class CsvFormat:
    kind: str
    filename: str
    title: str
    source: str
    frequency: str
    grain: str
    key: tuple[str, ...]
    replace_rule: str
    columns: tuple[Column, ...]
    examples: tuple[tuple[str, ...], ...]
    rules: tuple[str, ...] = ()

    @property
    def column_names(self):
        return [c.name for c in self.columns]

    @property
    def required_names(self):
        return [c.name for c in self.columns if c.required]


def _choices(choices):
    return ", ".join(f"`{value}` ({label})" for value, label in choices)


DATE = Column("tarih", "date", True, "Servis günü. `YYYY-AA-GG` (önerilen) ya da `GG.AA.YYYY`.", "2026-11-20")
MEAL = Column("ogun", "meal", True, f"Öğün: {_choices(MealType.choices)}.", "ogle")
DISH_CODE = Column(
    "yemek_kodu",
    "code",
    True,
    "Yemek kataloğundaki kod. Küçük harf, rakam, `_` ve `-`; Türkçe karakter yok.",
    "tavuk_sote",
)

YEMEKLER = CsvFormat(
    kind=ImportBatch.Kind.DISHES,
    filename="yemekler.csv",
    title="Yemek kataloğu",
    source="Yemekhane yönetimi (panel sahibi)",
    frequency="Menüye yeni bir yemek girdiğinde",
    grain="Bir satır = bir yemek",
    key=("yemek_kodu",),
    replace_rule="Aynı kod varsa adı, kategorisi, türü ve (doluysa) saklanabilir bilgisi güncellenir. Kod silinmez.",
    columns=(
        DISH_CODE,
        Column("yemek_adi", "text", True, "Panelde görünen ad.", "Tavuk Sote"),
        Column("kategori", "category", True, f"Tepsideki yeri: {_choices(Category.choices)}.", "ana_yemek"),
        Column(
            "tur",
            "text",
            False,
            "Gruplama için yemek türü (ör. tavuk, kırmızı et, bakliyat, sebze, pilav, makarna). "
            "Sıralama sayfasındaki tür listeleri bu sütundan çıkar.",
            "tavuk",
        ),
        Column(
            "saklanabilir",
            "bool",
            False,
            "Kapalı ambalajlı, artanı stoka geri dönen ürün (ör. kapalı ayran, paketli meyve) için `evet`. "
            "Bu ürünlerde artan miktar israf sayılmaz; yalnızca tabakta kalan sayılır. Boş bırakılırsa "
            "yeni yemekte `hayir` kabul edilir, var olan yemekte önceki değer korunur.",
            "hayir",
        ),
    ),
    examples=(
        ("tavuk_sote", "Tavuk Sote", "ana_yemek", "tavuk", "hayir"),
        ("izgara_kofte", "Izgara Köfte", "ana_yemek", "kırmızı et", "hayir"),
        ("pirinc_pilavi", "Pirinç Pilavı", "yan_yemek", "pilav", "hayir"),
        ("mercimek_corbasi", "Mercimek Çorbası", "corba", "bakliyat çorbası", "hayir"),
        ("ayran", "Ayran", "icecek", "içecek", "evet"),
    ),
)

OGUNLER = CsvFormat(
    kind=ImportBatch.Kind.SESSIONS,
    filename="ogunler.csv",
    title="Öğün bilgileri (isteğe bağlı)",
    source="Yemekhane yönetimi",
    frequency="Yalnızca servis saati varsayılandan farklı olan günler için",
    grain="Bir satır = bir günün bir öğünü",
    key=("tarih", "ogun"),
    replace_rule="Dosyadaki her (tarih, öğün) için önceki kayıt değiştirilir.",
    columns=(
        DATE,
        MEAL,
        Column("servis_baslangic", "time", True, "Servisin açıldığı saat, `SS:DD`.", "11:30"),
        Column("servis_bitis", "time", True, "Servisin kapandığı saat, `SS:DD`.", "14:00"),
        Column("not", "text", False, "Serbest not (ör. sınav haftası, yağmurlu gün).", "Sınav haftası"),
    ),
    examples=(("2026-11-20", "ogle", "11:00", "14:30", "Sınav haftası, uzatılmış servis"),),
    rules=(
        "Bu dosya yüklenmeyen günlerde Ayarlar sayfasındaki varsayılan servis saatleri kullanılır.",
        "Servis saatleri yalnızca bitiş zamanını servisin yüzdesi olarak göstermek için kullanılır.",
    ),
)

URETIM = CsvFormat(
    kind=ImportBatch.Kind.PRODUCTION,
    filename="uretim.csv",
    title="Yemekhane günlük kaydı",
    source="Yemekhane (servis kapanınca)",
    frequency="Her öğünden sonra",
    grain="Bir satır = o öğünde çıkan bir yemek",
    key=("tarih", "ogun", "yemek_kodu"),
    replace_rule="Dosyadaki her (tarih, öğün) için o öğünün bütün kayıtları silinip dosyadakiler yazılır. "
    "O öğünün kaydı daha önce yüklendiyse dosya reddedilir; düzeltilmiş dosya «Önceki verinin yerine "
    "geçsin» onayıyla yüklenir.",
    columns=(
        DATE,
        MEAL,
        DISH_CODE,
        Column(
            "uretilen_porsiyon",
            "decimal",
            True,
            "Üretilen miktarın tabak karşılığı. Kazandaki miktar ÷ tabak başına konan miktar "
            "(ör. 1000 birim ÷ 10 birim = 100). Ondalık olabilir.",
            "320",
        ),
        Column(
            "artan_porsiyon",
            "decimal",
            True,
            "Servis kapandığında kazanda kalan miktarın tabak karşılığı. Bittiyse `0`.",
            "0",
        ),
        Column(
            "bitis_saati",
            "time",
            False,
            "Yemek servis sırasında tükendiyse tükendiği saat, `SS:DD`. Tükenmediyse boş bırakılır.",
            "12:48",
        ),
    ),
    examples=(
        ("2026-11-20", "ogle", "mercimek_corbasi", "1150", "62", ""),
        ("2026-11-20", "ogle", "tavuk_sote", "620", "0", "12:48"),
        ("2026-11-20", "ogle", "izgara_kofte", "560", "38", ""),
        ("2026-11-20", "ogle", "pirinc_pilavi", "600", "71.5", ""),
        ("2026-11-20", "ogle", "ayran", "500", "35", ""),
    ),
    rules=(
        "Bu dosya o günün menüsüdür: tepsi analizindeki yemek kodları bu dosyadaki kodlarla eşleşmelidir.",
        "Bir öğünün bütün yemekleri tek dosyada gelir.",
        "`artan_porsiyon`, `uretilen_porsiyon` değerini aşamaz.",
        "`bitis_saati` dolu ama `artan_porsiyon` 0 değilse uyarı verilir.",
        "Bir öğünde ana yemek ya da yan yemek sayısı 2 değilse uyarı verilir; tercih analizi o öğünü atlar.",
    ),
)

TEPSILER = CsvFormat(
    kind=ImportBatch.Kind.TRAYS,
    filename="tepsiler.csv",
    title="Tepsi analizi (görüntü işleme çıktısı)",
    source="Görüntü işleme ekibi",
    frequency="Her öğünün tepsileri işlendikten sonra",
    grain="Bir satır = bir tepsideki bir tabak (uzun format)",
    key=("tarih", "ogun", "tepsi_id", "yemek_kodu"),
    replace_rule="Dosyadaki her (tarih, öğün) için o öğünün tepsi özeti silinip dosyadan yeniden hesaplanır. "
    "O öğünün tepsileri daha önce yüklendiyse dosya reddedilir; düzeltilmiş dosya «Önceki verinin yerine "
    "geçsin» onayıyla yüklenir.",
    columns=(
        DATE,
        MEAL,
        Column(
            "tepsi_id",
            "text",
            True,
            "Tepsinin o öğün içindeki benzersiz kimliği. Aynı tepsideki tabaklar aynı kimliği taşır.",
            "T00001",
        ),
        DISH_CODE,
        Column("durum", "state", True, f"Tabağın durumu: {_choices(PlateState.choices)}.", "yarim"),
    ),
    examples=(
        ("2026-11-20", "ogle", "T00001", "mercimek_corbasi", "bitti"),
        ("2026-11-20", "ogle", "T00001", "tavuk_sote", "bitti"),
        ("2026-11-20", "ogle", "T00001", "pirinc_pilavi", "yarim"),
        ("2026-11-20", "ogle", "T00001", "ayran", "dokunulmadi"),
        ("2026-11-20", "ogle", "T00002", "mercimek_corbasi", "belirsiz"),
    ),
    rules=(
        "Bir öğünün bütün tepsileri tek dosyada gelir. Tepsiler birden çok kamerada ya da partide işlendiyse "
        "dosyalar birleştirilip gönderilir; aynı öğünün ikinci parçası ayrı yüklenirse reddedilir.",
        "Tepside olmayan yemek için satır yazılmaz. Alınıp hiç yenmeyen tabak `dokunulmadi` olarak yazılır.",
        "`belirsiz`: model tabağı göremedi ya da karar veremedi. Oranlara katılmaz, ayrıca sayılır.",
        "O öğün için yemekhane kaydı yüklüyse, kaydında olmayan bir yemek kodu hata sayılır.",
        "Tepsi kimliği her tepside bir kez sayılır; analiz edilen tepsi sayısı farklı kimliklerden çıkar.",
    ),
)

FORMATS = {f.kind: f for f in (YEMEKLER, OGUNLER, URETIM, TEPSILER)}

GENERAL_RULES = (
    "Kodlama UTF-8 (BOM'lu ya da BOM'suz). Excel'in Türkçe kaydettiği Windows-1254 dosyalar da okunur, uyarı verilir.",
    "Ayraç virgül `,` (önerilen). Türkçe Excel'in ürettiği noktalı virgül `;` ve sekme de otomatik tanınır.",
    "İlk satır başlıktır. Sütun sırası önemli değildir; başlıkta büyük/küçük harf ve Türkçe karakter farkı tolere edilir.",
    "Ondalık ayırıcı nokta ya da virgül olabilir (`12.5` ve `12,5` aynıdır). Binlik ayırıcı kullanılmaz.",
    "Bir dosya birden fazla günü içerebilir. Hatalı tek bir satır varsa dosyanın tamamı reddedilir, hiçbir şey yazılmaz.",
    "Yükleme sırası: yemekler → (ogunler) → uretim → tepsiler.",
    "Yemekhane kaydı ve tepsi analizi öğün öğün yazılır. Daha önce yüklenmiş bir öğünü içeren dosya, yerine "
    "geçme onayı verilmedikçe reddedilir; böylece aynı öğünün iki parçası birbirini sessizce silmez.",
)
