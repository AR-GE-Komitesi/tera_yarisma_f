from datetime import time
from decimal import Decimal

from django.test import TestCase

from israf.models import Dish, ImportBatch, PlateSummary, Production, TrayCount

from .yardimci import DISHES_CSV, PRODUCTION_CSV, TRAYS_CSV, load

K = ImportBatch.Kind


def texts(batch, level=None):
    return " | ".join(m["text"] for m in batch.messages if level is None or m["level"] == level)


class ReadingTests(TestCase):
    def setUp(self):
        load(K.DISHES, DISHES_CSV)

    def test_turkish_excel_semicolon_decimal_comma_bom_and_dotted_date(self):
        text = "﻿tarih;ogun;yemek_kodu;uretilen_porsiyon;artan_porsiyon;bitis_saati\r\n20.11.2026;Öğle;tavuk;120,5;12,25;\r\n"
        batch = load(K.PRODUCTION, text)
        self.assertEqual(batch.status, ImportBatch.Status.OK, texts(batch))
        prod = Production.objects.get()
        self.assertEqual(prod.produced, Decimal("120.50"))
        self.assertEqual(prod.leftover, Decimal("12.25"))
        self.assertEqual(prod.meal, "ogle")

    def test_windows_1254_is_read_with_warning(self):
        text = "yemek_kodu,yemek_adi,kategori,tur\nsehriye,Şehriyeli Pilav,Yan Yemek,pilav\n"
        batch = load(K.DISHES, text, encoding="cp1254")
        self.assertEqual(batch.status, ImportBatch.Status.OK, texts(batch))
        self.assertIn("Windows-1254", texts(batch, "uyari"))

    def test_headers_tolerate_case_and_turkish_letters(self):
        text = "Yemek_Kodu,Yemek_Adı,Kategori,Tür\nsu_boregi,Su Böreği,yan_yemek,hamur işi\n"
        batch = load(K.DISHES, text)
        self.assertEqual(batch.status, ImportBatch.Status.OK, texts(batch))

    def test_wrong_file_type_is_named(self):
        batch = load(K.PRODUCTION, TRAYS_CSV)
        self.assertEqual(batch.status, ImportBatch.Status.REJECTED)
        self.assertIn("Tepsi analizi", texts(batch))

    def test_unquoted_decimal_comma_with_comma_delimiter(self):
        text = "tarih,ogun,yemek_kodu,uretilen_porsiyon,artan_porsiyon,bitis_saati\n2026-11-20,ogle,tavuk,10,2,5,\n"
        batch = load(K.PRODUCTION, text)
        self.assertEqual(batch.status, ImportBatch.Status.REJECTED)
        self.assertIn("başlıktan fazla değer", texts(batch))

    def test_storable_flag_is_parsed_and_kept_when_column_is_absent(self):
        load(K.DISHES, "yemek_kodu,yemek_adi,kategori,saklanabilir\nayran,Ayran,icecek,Evet\n")
        self.assertTrue(Dish.objects.get(code="ayran").storable)
        load(K.DISHES, "yemek_kodu,yemek_adi,kategori\nayran,Ayran,içecek\n")
        self.assertTrue(Dish.objects.get(code="ayran").storable)
        batch = load(K.DISHES, "yemek_kodu,yemek_adi,kategori,saklanabilir\nayran,Ayran,icecek,belki\n")
        self.assertEqual(batch.status, ImportBatch.Status.REJECTED)
        self.assertIn("evet", texts(batch, "hata"))

    def test_rejected_batch_keeps_archive_file(self):
        batch = load(K.PRODUCTION, "tarih,ogun\n", name="bozuk.csv")
        self.assertEqual(batch.status, ImportBatch.Status.REJECTED)
        self.assertTrue(batch.stored_file.name.endswith("bozuk.csv"))


class ProductionTests(TestCase):
    def setUp(self):
        load(K.DISHES, DISHES_CSV)

    def test_one_bad_row_rejects_whole_file(self):
        text = PRODUCTION_CSV + "2026-11-20,ogle,bilinmeyen,10,0,\n"
        batch = load(K.PRODUCTION, text)
        self.assertEqual(batch.status, ImportBatch.Status.REJECTED)
        self.assertEqual(Production.objects.count(), 0)
        bad = [m for m in batch.messages if m["level"] == "hata"]
        self.assertEqual(bad[0]["row"], 7)
        self.assertIn("Katalogda olmayan", bad[0]["text"])

    def test_value_rules(self):
        text = (
            "tarih,ogun,yemek_kodu,uretilen_porsiyon,artan_porsiyon,bitis_saati\n"
            "2026-11-20,ogle,tavuk,10,12,\n"  # artan > üretilen
            "2026-11-20,ogle,kofte,0,0,\n"  # üretim 0
            "2026-11-20,ogle,pilav,10,0,25:00\n"  # saat
            "2026-11-31,ogle,makarna,10,0,\n"  # tarih
            "2026-11-20,ogle,tavuk,10,1,\n"  # tekrar
        )
        batch = load(K.PRODUCTION, text)
        rows = {m["row"] for m in batch.messages if m["level"] == "hata"}
        self.assertEqual(rows, {2, 3, 4, 5, 6})

    def test_warnings_do_not_block(self):
        text = (
            "tarih,ogun,yemek_kodu,uretilen_porsiyon,artan_porsiyon,bitis_saati\n"
            "2026-11-20,ogle,tavuk,10,3,15:30\n"
        )
        batch = load(K.PRODUCTION, text)
        self.assertEqual(batch.status, ImportBatch.Status.OK)
        warnings = texts(batch, "uyari")
        self.assertIn("artmış görünüyor", warnings)
        self.assertIn("servis saatlerinin", warnings)
        self.assertIn("1 adet ana yemek", warnings)
        self.assertIn("0 adet yan yemek", warnings)

    def test_reupload_replaces_meal(self):
        load(K.PRODUCTION, PRODUCTION_CSV)
        self.assertEqual(Production.objects.count(), 5)
        smaller = "\n".join(PRODUCTION_CSV.strip().splitlines()[:3]) + "\n"
        batch = load(K.PRODUCTION, smaller)
        self.assertEqual(batch.status, ImportBatch.Status.OK)
        self.assertEqual(Production.objects.count(), 2)
        self.assertEqual(Production.objects.get(dish__code="tavuk").ran_out_at, time(12, 30))
        self.assertEqual(batch.affected, ["2026-11-20/ogle"])


class TrayTests(TestCase):
    def setUp(self):
        load(K.DISHES, DISHES_CSV)
        load(K.PRODUCTION, PRODUCTION_CSV)

    def test_aggregation(self):
        batch = load(K.TRAYS, TRAYS_CSV)
        self.assertEqual(batch.status, ImportBatch.Status.OK, texts(batch))
        soup = PlateSummary.objects.get(dish__code="mercimek")
        self.assertEqual((soup.finished, soup.half, soup.untouched, soup.unknown), (6, 1, 1, 1))
        kofte = PlateSummary.objects.get(dish__code="kofte")
        self.assertEqual((kofte.finished, kofte.half, kofte.untouched), (1, 1, 1))
        self.assertEqual(TrayCount.objects.get().trays, 9)

    def test_dish_missing_from_menu_is_an_error(self):
        text = TRAYS_CSV + "2026-11-20,ogle,T10,salata,bitti\n"
        batch = load(K.TRAYS, text)
        self.assertEqual(batch.status, ImportBatch.Status.REJECTED)
        self.assertIn("yemekhane kaydında yok", texts(batch, "hata"))
        self.assertEqual(PlateSummary.objects.count(), 0)

    def test_without_production_only_warns(self):
        text = "tarih,ogun,tepsi_id,yemek_kodu,durum\n2026-11-21,ogle,T1,tavuk,bitti\n"
        batch = load(K.TRAYS, text)
        self.assertEqual(batch.status, ImportBatch.Status.OK)
        self.assertIn("henüz yüklenmemiş", texts(batch, "uyari"))

    def test_duplicate_plate_and_bad_state(self):
        text = (
            "tarih,ogun,tepsi_id,yemek_kodu,durum\n"
            "2026-11-20,ogle,T1,tavuk,bitti\n"
            "2026-11-20,ogle,T1,tavuk,yarim\n"
            "2026-11-20,ogle,T2,tavuk,yarı\n"
        )
        batch = load(K.TRAYS, text)
        errors = {m["row"]: m["text"] for m in batch.messages if m["level"] == "hata"}
        self.assertIn("2. satırda da var", errors[3])
        self.assertIn("Geçersiz durum", errors[4])

    def test_more_plates_than_served_warns(self):
        extra = "".join(f"2026-11-20,ogle,X{i},kofte,bitti\n" for i in range(5))
        batch = load(K.TRAYS, TRAYS_CSV + extra)
        self.assertEqual(batch.status, ImportBatch.Status.OK)
        self.assertIn("servis edilen porsiyonu", texts(batch, "uyari"))
