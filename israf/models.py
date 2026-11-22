"""Veri modeli.

Ham tepsi satırları veritabanında tutulmaz: her (tarih, öğün, yemek) için
durum sayıları özetlenir ve yüklenen CSV dosyası olduğu gibi arşivlenir.
Böylece veritabanı küçük kalır, gerekirse arşivden yeniden yüklenebilir.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q

# Yemek kodu kuralı: CSV yüklemesi (aktarim.py) ve yönetim sayfası aynı kuralı kullanır.
DISH_CODE_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,39}$"
dish_code_validator = RegexValidator(
    DISH_CODE_PATTERN,
    "Yalnızca küçük harf, rakam, '_' ve '-' kullanın; ilk karakter harf ya da rakam olmalı. "
    "Türkçe karakter ve boşluk kullanılmaz (ör. tavuk_sis).",
)


class Category(models.TextChoices):
    MAIN = "ana_yemek", "Ana yemek"
    SIDE = "yan_yemek", "Yan yemek"
    SOUP = "corba", "Çorba"
    SALAD = "salata", "Salata"
    DRINK = "icecek", "İçecek"
    DESSERT = "tatli", "Tatlı / meyve"


# Her gün iki seçenekle çıkan, öğrencinin birini seçtiği kategoriler.
PAIRED_CATEGORIES = (Category.MAIN, Category.SIDE)
CATEGORY_ORDER = {value: index for index, value in enumerate(Category.values)}


class MealType(models.TextChoices):
    BREAKFAST = "kahvalti", "Kahvaltı"
    LUNCH = "ogle", "Öğle"
    DINNER = "aksam", "Akşam"


class PlateState(models.TextChoices):
    FINISHED = "bitti", "Tamamı yendi"
    HALF = "yarim", "Yarısı yendi"
    UNTOUCHED = "dokunulmadi", "Dokunulmadı"
    UNKNOWN = "belirsiz", "Belirlenemedi"


class Dish(models.Model):
    code = models.CharField("yemek kodu", max_length=40, unique=True, validators=[dish_code_validator])
    name = models.CharField("yemek adı", max_length=120)
    category = models.CharField("kategori", max_length=20, choices=Category.choices)
    food_type = models.CharField("tür", max_length=60, blank=True)
    storable = models.BooleanField(
        "saklanabilir",
        default=False,
        help_text="Kapalı ambalajlı; artanı stoka döner, israf sayılmaz (ör. ayran).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "name"]
        verbose_name = "yemek"
        verbose_name_plural = "yemek kataloğu"

    def __str__(self):
        return self.name


class MealSession(models.Model):
    """Bir öğünün o güne özel servis saatleri (ogunler.csv). İsteğe bağlıdır."""

    date = models.DateField("tarih")
    meal = models.CharField("öğün", max_length=10, choices=MealType.choices)
    service_start = models.TimeField("servis başlangıcı")
    service_end = models.TimeField("servis bitişi")
    note = models.CharField("not", max_length=200, blank=True)

    class Meta:
        ordering = ["-date", "meal"]
        verbose_name = "öğün bilgisi"
        verbose_name_plural = "öğün bilgileri"
        constraints = [
            models.UniqueConstraint(fields=["date", "meal"], name="uniq_session_date_meal"),
            models.CheckConstraint(
                condition=Q(service_end__gt=F("service_start")), name="session_end_after_start"
            ),
        ]

    def __str__(self):
        return f"{self.date:%d.%m.%Y} {self.get_meal_display()}"


class ServiceWindowDefault(models.Model):
    """Öğün bilgisi yüklenmeyen günlerde kullanılan varsayılan servis saatleri."""

    meal = models.CharField("öğün", max_length=10, choices=MealType.choices, unique=True)
    service_start = models.TimeField("servis başlangıcı")
    service_end = models.TimeField("servis bitişi")

    class Meta:
        ordering = ["service_start"]
        verbose_name = "varsayılan servis saati"
        verbose_name_plural = "varsayılan servis saatleri"
        constraints = [
            models.CheckConstraint(
                condition=Q(service_end__gt=F("service_start")), name="default_end_after_start"
            ),
        ]

    def __str__(self):
        return self.get_meal_display()


class Production(models.Model):
    """Yemekhanenin günlük kaydı (uretim.csv): menü + üretim + artan + bitiş."""

    date = models.DateField("tarih")
    meal = models.CharField("öğün", max_length=10, choices=MealType.choices)
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, related_name="productions")
    produced = models.DecimalField("üretilen porsiyon", max_digits=10, decimal_places=2)
    leftover = models.DecimalField("artan porsiyon", max_digits=10, decimal_places=2)
    ran_out_at = models.TimeField("bitiş saati", null=True, blank=True)

    class Meta:
        ordering = ["-date", "meal", "dish__category"]
        verbose_name = "üretim kaydı"
        verbose_name_plural = "üretim kayıtları"
        indexes = [models.Index(fields=["date", "meal"])]
        constraints = [
            models.UniqueConstraint(fields=["date", "meal", "dish"], name="uniq_production"),
            models.CheckConstraint(condition=Q(produced__gt=0), name="production_positive"),
            models.CheckConstraint(
                condition=Q(leftover__gte=0) & Q(leftover__lte=F("produced")),
                name="leftover_within_production",
            ),
        ]

    def __str__(self):
        return f"{self.date:%d.%m.%Y} {self.get_meal_display()} — {self.dish}"


class PlateSummary(models.Model):
    """Görüntü işlemeden gelen tepsi satırlarının yemek bazında özeti."""

    date = models.DateField("tarih")
    meal = models.CharField("öğün", max_length=10, choices=MealType.choices)
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, related_name="plate_summaries")
    finished = models.PositiveIntegerField("tamamı yenen tabak", default=0)
    half = models.PositiveIntegerField("yarısı yenen tabak", default=0)
    untouched = models.PositiveIntegerField("dokunulmayan tabak", default=0)
    unknown = models.PositiveIntegerField("belirlenemeyen tabak", default=0)

    class Meta:
        ordering = ["-date", "meal"]
        verbose_name = "tabak özeti"
        verbose_name_plural = "tabak özetleri"
        indexes = [models.Index(fields=["date", "meal"])]
        constraints = [
            models.UniqueConstraint(fields=["date", "meal", "dish"], name="uniq_plate_summary"),
        ]

    @property
    def total(self):
        return self.finished + self.half + self.untouched + self.unknown


class TrayCount(models.Model):
    """Bir öğünde görüntü işlemeden geçen farklı tepsi sayısı."""

    date = models.DateField("tarih")
    meal = models.CharField("öğün", max_length=10, choices=MealType.choices)
    trays = models.PositiveIntegerField("tepsi sayısı")

    class Meta:
        verbose_name = "tepsi sayısı"
        verbose_name_plural = "tepsi sayıları"
        constraints = [
            models.UniqueConstraint(fields=["date", "meal"], name="uniq_tray_count"),
        ]


def _archive_path(instance, filename):
    return f"{instance.kind}/{instance.uploaded_at:%Y/%m}/{filename}"


class ImportBatch(models.Model):
    class Kind(models.TextChoices):
        DISHES = "yemekler", "Yemek kataloğu"
        SESSIONS = "ogunler", "Öğün bilgileri"
        PRODUCTION = "uretim", "Yemekhane günlük kaydı"
        TRAYS = "tepsiler", "Tepsi analizi (görüntü işleme)"

    class Status(models.TextChoices):
        OK = "basarili", "Yüklendi"
        REJECTED = "reddedildi", "Reddedildi"

    kind = models.CharField("dosya türü", max_length=20, choices=Kind.choices)
    status = models.CharField("durum", max_length=20, choices=Status.choices)
    original_name = models.CharField("dosya adı", max_length=255)
    stored_file = models.FileField("arşiv dosyası", upload_to=_archive_path, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    uploaded_at = models.DateTimeField("yükleme zamanı")
    row_count = models.PositiveIntegerField("satır sayısı", default=0)
    error_count = models.PositiveIntegerField("hata sayısı", default=0)
    warning_count = models.PositiveIntegerField("uyarı sayısı", default=0)
    messages = models.JSONField("mesajlar", default=list)
    affected = models.JSONField("etkilenen öğünler", default=list)
    summary = models.CharField("özet", max_length=300, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "veri yüklemesi"
        verbose_name_plural = "veri yüklemeleri"

    def __str__(self):
        return f"{self.get_kind_display()} — {self.original_name}"


class ThresholdProfile(models.Model):
    """Eşik profili. Değerler yüzde olarak (0–100) saklanır.

    Eşikler karar üretmez; yalnızca tablolarda eşiği aşan değerleri işaretler.
    """

    key = models.SlugField("anahtar", unique=True)
    name = models.CharField("ad", max_length=40)
    order = models.PositiveSmallIntegerField("sıra", default=0)
    unfinished_plate_rate = models.DecimalField(
        "bitirilmeyen tabak eşiği (%)",
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    pot_leftover_rate = models.DecimalField(
        "kazan artığı eşiği (%)",
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    total_waste_rate = models.DecimalField(
        "toplam israf eşiği (%)",
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_active = models.BooleanField("etkin", default=False)

    class Meta:
        ordering = ["order"]
        verbose_name = "eşik profili"
        verbose_name_plural = "eşik profilleri"
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"], condition=Q(is_active=True), name="single_active_profile"
            ),
        ]

    def __str__(self):
        return self.name

    def limit_for(self, metric: str):
        """Metrik anahtarına karşılık gelen eşik (oran, 0–1) ya da None."""
        field = {
            "bitirilmeyen": self.unfinished_plate_rate,
            "kazan": self.pot_leftover_rate,
            "toplam": self.total_waste_rate,
        }.get(metric)
        return None if field is None else float(field) / 100
