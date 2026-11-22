from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from israf.formatlar import FORMATS
from israf.models import Dish, ImportBatch, Production, ThresholdProfile

from .yardimci import PRODUCTION_CSV, load_fixture

PAGES = [
    ("israf:genel", {}),
    ("israf:genel", {"baslangic": "2026-11-01", "bitis": "2026-11-30", "ogun": "ogle"}),
    ("israf:gun", {}),
    ("israf:gun", {"tarih": "2026-11-20", "ogun": "ogle"}),
    ("israf:gun", {"tarih": "2026-12-31"}),
    ("israf:siralama", {}),
    ("israf:siralama", {"grup": "tur", "metrik": "kazan"}),
    ("israf:siralama", {"grup": "kategori", "kategori": "ana_yemek", "min_cikis": "2"}),
    ("israf:tercih", {}),
    ("israf:tercih", {"kategori": "yan_yemek"}),
    ("israf:veri", {}),
    ("israf:durum", {}),
    ("israf:ayarlar", {}),
    ("israf:tanimlar", {}),
]


class AccessTests(TestCase):
    def test_login_required(self):
        response = self.client.get(reverse("israf:genel"))
        self.assertRedirects(response, f"{reverse('login')}?next=/")

    def test_non_staff_cannot_upload_or_change_settings(self):
        user = User.objects.create_user("izleyici", password="x-Parola-123")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("israf:genel")).status_code, 200)
        self.assertEqual(self.client.get(reverse("israf:ayarlar")).status_code, 403)
        upload = SimpleUploadedFile("uretim.csv", PRODUCTION_CSV.encode())
        response = self.client.post(reverse("israf:veri"), {"tur": "uretim", "dosya": upload})
        self.assertEqual(response.status_code, 403)

    def test_empty_database_shows_guidance(self):
        self.client.force_login(User.objects.create_user("bos", password="x-Parola-123", is_staff=True))
        response = self.client.get(reverse("israf:genel"))
        self.assertContains(response, "Henüz analiz edilecek veri yok")


class AdminTests(TestCase):
    def test_admin_enforces_dish_code_rule(self):
        # Önceden yönetim sayfası CSV'nin reddettiği kodları kabul ediyordu; böyle bir yemek
        # CSV'lerde hiç kullanılamaz, '/' içeren kod ise bağlantı üretirken sayfaları çökertir.
        self.client.force_login(User.objects.create_superuser("kok", password="x-Parola-123"))
        url = reverse("admin:israf_dish_add")
        data = {"name": "Tavuk Şiş", "category": "ana_yemek", "food_type": "tavuk"}
        for bad in ("Tavuk Şiş", "tavuk/sis", "_tavuk"):
            response = self.client.post(url, {**data, "code": bad})
            self.assertContains(response, "Yalnızca küçük harf", msg_prefix=bad)
        self.assertFalse(Dish.objects.exists())
        self.assertEqual(self.client.post(url, {**data, "code": "tavuk_sis"}).status_code, 302)
        self.assertTrue(Dish.objects.filter(code="tavuk_sis").exists())


class PageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_fixture()
        cls.staff = User.objects.create_user("yonetici", password="x-Parola-123", is_staff=True)

    def setUp(self):
        self.client.force_login(self.staff)

    def test_all_pages_render(self):
        for name, params in PAGES:
            with self.subTest(page=name, params=params):
                response = self.client.get(reverse(name), params)
                self.assertEqual(response.status_code, 200)

    def test_filter_dates_use_iso_format_for_date_inputs(self):
        response = self.client.get(reverse("israf:genel"))
        self.assertContains(response, 'name="baslangic" value="2026-11-20"')
        response = self.client.get(reverse("israf:genel"), {"baslangic": "2026-11-20", "bitis": "2026-11-20"})
        self.assertContains(response, 'name="bitis" value="2026-11-20"')

    def test_dish_page(self):
        response = self.client.get(reverse("israf:yemek", args=["kofte"]))
        self.assertContains(response, "Izgara Köfte")
        self.assertContains(response, "%66,7")  # toplam israf oranı 4/6
        self.assertEqual(self.client.get(reverse("israf:yemek", args=["yok"])).status_code, 404)

    def test_day_page_numbers(self):
        response = self.client.get(reverse("israf:gun"), {"tarih": "2026-11-20", "ogun": "ogle"})
        self.assertContains(response, "Yalnız Tavuk Sote tükendi")
        self.assertContains(response, "12:30")
        self.assertContains(response, "%35,0")  # gün toplamı 11,1875 / 32

    def test_threshold_marker(self):
        response = self.client.get(reverse("israf:siralama"))
        self.assertContains(response, "Dengeli eşiği (%20,0) aşıldı")

    def test_ranking_csv(self):
        response = self.client.get(reverse("israf:siralama_csv"), {"grup": "yemek"})
        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("﻿yemek;yemek_kodu;"))
        header = body.splitlines()[0].lstrip("﻿").split(";")
        kofte = next(line for line in body.splitlines() if line.startswith("Izgara Köfte"))
        values = dict(zip(header, kofte.split(";")))
        self.assertEqual(values["toplam_israf_yuzde"], "66,7")
        # Köfte tabakları: 1 tamamı, 1 yarısı, 1 dokunulmadı
        self.assertEqual(values["tamami_yenen_tabak_yuzde"], "33,3")
        self.assertEqual(
            [values[k] for k in ("tamami_yenen_tabak", "yarisi_yenen_tabak", "dokunulmayan_tabak")], ["1", "1", "1"]
        )

    def test_ranking_csv_neutralises_spreadsheet_formulas(self):
        Dish.objects.filter(code="kofte").update(name="=HYPERLINK(\"x\")", food_type="+et")
        body = self.client.get(reverse("israf:siralama_csv"), {"grup": "yemek"}).content.decode("utf-8")
        line = next(line for line in body.splitlines() if ";kofte;" in line)
        self.assertTrue(line.startswith("\"'=HYPERLINK(\"\"x\"\")\";kofte;"), line)
        self.assertIn(";'+et;", line)

    def test_templates_and_menu_downloads(self):
        for kind, fmt in FORMATS.items():
            body = self.client.get(reverse("israf:sablon", args=[kind])).content.decode("utf-8")
            self.assertEqual(body.splitlines()[0], ",".join(fmt.column_names))
            excel = self.client.get(reverse("israf:sablon", args=[kind]), {"excel": "1"}).content.decode("utf-8")
            self.assertTrue(excel.startswith("﻿" + ";".join(fmt.column_names)))
        menu = self.client.get(reverse("israf:menu_csv")).content.decode("utf-8").splitlines()
        self.assertEqual(menu[0], "tarih,ogun,yemek_kodu,yemek_adi,kategori")
        self.assertEqual(len(menu), 6)

    def test_upload_through_view(self):
        upload = SimpleUploadedFile("uretim.csv", PRODUCTION_CSV.replace("2026-11-20", "2026-11-21").encode())
        response = self.client.post(reverse("israf:veri"), {"tur": "uretim", "dosya": upload})
        batch = ImportBatch.objects.latest("uploaded_at")
        self.assertRedirects(response, reverse("israf:aktarim", args=[batch.pk]))
        self.assertEqual(batch.uploaded_by, self.staff)
        self.assertEqual(Production.objects.filter(date="2026-11-21").count(), 5)
        archive = self.client.get(reverse("israf:aktarim_dosya", args=[batch.pk]))
        self.assertEqual(b"".join(archive.streaming_content).decode(), PRODUCTION_CSV.replace("2026-11-20", "2026-11-21"))

    def test_reupload_through_view_needs_the_checkbox(self):
        self.assertContains(self.client.get(reverse("israf:veri")), 'name="yerine_gecsin"')
        for extra, expected in (({}, ImportBatch.Status.REJECTED), ({"yerine_gecsin": "on"}, ImportBatch.Status.OK)):
            upload = SimpleUploadedFile("uretim.csv", PRODUCTION_CSV.encode())  # 20.11 öğle zaten yüklü
            self.client.post(reverse("israf:veri"), {"tur": "uretim", "dosya": upload, **extra})
            self.assertEqual(ImportBatch.objects.order_by("-pk").first().status, expected)
        self.assertEqual(Production.objects.count(), 5)

    @override_settings(ISRAF_MAX_UPLOAD_MB=0.0001)  # ~100 bayt
    def test_upload_size_limit(self):
        upload = SimpleUploadedFile("uretim.csv", PRODUCTION_CSV.encode())
        response = self.client.post(reverse("israf:veri"), {"tur": "uretim", "dosya": upload})
        self.assertContains(response, "MB sınırını aşıyor")
        self.assertEqual(ImportBatch.objects.filter(original_name="uretim.csv").count(), 0)

    def test_settings_switch_profile_and_edit_values(self):
        data = {"etkin_profil": "siki"}
        for profile in ThresholdProfile.objects.all():
            data[f"{profile.key}-unfinished_plate_rate"] = profile.unfinished_plate_rate
            data[f"{profile.key}-pot_leftover_rate"] = profile.pot_leftover_rate
            data[f"{profile.key}-total_waste_rate"] = profile.total_waste_rate
        data["siki-total_waste_rate"] = "12.5"
        for meal, start, end in (("kahvalti", "07:00", "09:30"), ("ogle", "11:30", "14:00"), ("aksam", "16:30", "19:00")):
            data[f"saat-{meal}-service_start"] = start
            data[f"saat-{meal}-service_end"] = end
        response = self.client.post(reverse("israf:ayarlar"), data)
        self.assertRedirects(response, reverse("israf:ayarlar"))
        active = ThresholdProfile.objects.get(is_active=True)
        self.assertEqual((active.key, str(active.total_waste_rate)), ("siki", "12.5"))
        self.assertEqual(ThresholdProfile.objects.filter(is_active=True).count(), 1)

    def test_settings_reject_inverted_service_window(self):
        data = {"etkin_profil": "dengeli"}
        for profile in ThresholdProfile.objects.all():
            for field in ("unfinished_plate_rate", "pot_leftover_rate", "total_waste_rate"):
                data[f"{profile.key}-{field}"] = getattr(profile, field)
        for meal in ("kahvalti", "ogle", "aksam"):
            data[f"saat-{meal}-service_start"] = "14:00"
            data[f"saat-{meal}-service_end"] = "11:00"
        response = self.client.post(reverse("israf:ayarlar"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kapanış saati açılıştan sonra olmalı")
