from datetime import date, time

from django.test import TestCase

from israf import analiz
from israf.models import Dish, PlateSummary, ThresholdProfile

from .yardimci import load_fixture

DAY = date(2026, 11, 20)


class MeasureTests(TestCase):
    """Değerler tests/yardimci.py'deki veri setinden elle hesaplandı."""

    @classmethod
    def setUpTestData(cls):
        load_fixture()

    def rows(self):
        rows, orphans = analiz.load_dish_days(DAY, DAY)
        self.assertEqual(orphans, [])
        return {r.dish.code: r for r in rows}

    def test_single_dish_day(self):
        # Köfte: U=6, A=2, S=4; tabaklar 1 tamamı / 1 yarısı / 1 dokunulmadı (N=3)
        m = self.rows()["kofte"].measures
        self.assertAlmostEqual(m.pot_rate, 2 / 6)
        self.assertAlmostEqual(m.unfinished_rate, 2 / 3)
        self.assertAlmostEqual(m.untouched_rate, 1 / 3)
        self.assertAlmostEqual(m.plate_waste_rate, (0.5 + 1) / 3)
        # tabakta kalan = S × tabak artığı oranı = 4 × 0,5 = 2 → toplam = 2 + 2 = 4
        self.assertAlmostEqual(m.total_waste, 4)
        self.assertAlmostEqual(m.total_waste_rate, 4 / 6)

    def test_unknown_plates_are_excluded_from_rates(self):
        # Mercimek: 6 tamamı, 1 yarısı, 1 dokunulmadı, 1 belirsiz → N = 8
        m = self.rows()["mercimek"].measures
        self.assertEqual(m.unknown, 1)
        self.assertEqual(m.plates, 8)
        self.assertAlmostEqual(m.plate_waste_rate, 1.5 / 8)
        self.assertAlmostEqual(m.total_waste_rate, (1 + 9 * 1.5 / 8) / 10)

    def test_totals_are_portion_weighted(self):
        rows = list(self.rows().values())
        total = analiz.total(rows)
        expected_waste = (1 + 9 * 1.5 / 8) + (0 + 1.5) + (2 + 2) + (1 + 0.5) + (0 + 1.5)
        self.assertAlmostEqual(total.total_waste, expected_waste)
        self.assertAlmostEqual(total.total_waste_rate, expected_waste / 32)
        # Ortalama-oran değil toplam-oran: günlük oranların basit ortalaması farklı çıkar.
        simple_mean = sum(r.measures.total_waste_rate for r in rows) / len(rows)
        self.assertNotAlmostEqual(total.total_waste_rate, simple_mean)
        # Kazan + tabak payı toplam orana eşit
        self.assertAlmostEqual(total.pot_share + total.plate_share, total.total_waste_rate)

    def test_nobody_took_it_means_all_waste_is_in_the_pot(self):
        dish = Dish.objects.get(code="kofte")
        row = analiz.DishDay(DAY, "ogle", dish, 40.0, 40.0, None, None, None)
        self.assertEqual(row.measures.total_waste_rate, 1.0)

    def test_storable_leftover_is_not_waste(self):
        # 20 kap çıktı, 10'u stoka döndü; alınan 10 kabın 2'si açılmadı.
        storable = Dish.objects.create(code="kapali_ayran", name="Ayran", category="icecek", storable=True)
        plates = PlateSummary(date=DAY, meal="ogle", dish=storable, finished=8, half=0, untouched=2, unknown=0)
        m = analiz.DishDay(DAY, "ogle", storable, 20.0, 10.0, None, plates, None).measures
        self.assertEqual(m.pot_rate, 0)
        self.assertAlmostEqual(m.total_waste_rate, 2 / 10)
        storable.storable = False  # aynı veri, açık ürün olsaydı: (10 + 2) / 20
        m = analiz.DishDay(DAY, "ogle", storable, 20.0, 10.0, None, plates, None).measures
        self.assertAlmostEqual(m.total_waste_rate, 12 / 20)

    def test_missing_plates_excluded_from_total_but_not_from_pot(self):
        PlateSummary.objects.filter(dish__code="kofte").delete()
        rows = list(self.rows().values())
        total = analiz.total(rows)
        self.assertAlmostEqual(total.pot_rate, 4 / 32)  # bütün yemekhane kayıtları
        self.assertAlmostEqual(total.complete_produced, 32 - 6)  # köfte toplam israfa katılmaz

    def test_group_by_category(self):
        groups = {g.key: g for g in analiz.group_rows(self.rows().values(), "kategori")}
        main = groups["ana_yemek"].measures
        self.assertEqual(main.appearances, 2)
        self.assertAlmostEqual(main.total_waste_rate, (1.5 + 4) / 12)

    def test_sort_puts_missing_values_last(self):
        dish = Dish.objects.get(code="kofte")
        empty = analiz.Group("x", "Veri yok", analiz.Measures(appearances=1, produced=5, leftover=1))
        full = analiz.Group("kofte", "Köfte", self.rows()["kofte"].measures, dish=dish)
        ordered = analiz.sort_groups([empty, full], "toplam")
        self.assertEqual([g.key for g in ordered], ["kofte", "x"])


class PreferenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        load_fixture()

    def test_pairs_and_outcomes(self):
        rows, _ = analiz.load_dish_days(DAY, DAY)
        ordered = analiz.build_pairs(rows)
        self.assertEqual([p.category for p in ordered], ["ana_yemek", "yan_yemek"])
        pairs = {p.category: p for p in ordered}
        main = pairs["ana_yemek"]
        self.assertEqual(main.first_out.dish.code, "tavuk")
        self.assertEqual(main.outcome, "Yalnız Tavuk Sote tükendi")
        tavuk = main.b if main.b.dish.code == "tavuk" else main.a
        self.assertAlmostEqual(main.share(tavuk), 6 / 10)
        self.assertAlmostEqual(main.production_share(tavuk), 0.5)
        # Varsayılan öğle servisi 11:30–14:00; 12:30 → 60 / 150
        self.assertAlmostEqual(tavuk.run_out_position, 0.4)

    def test_earlier_run_out_wins_and_ties(self):
        dish_a, dish_b = Dish.objects.get(code="tavuk"), Dish.objects.get(code="kofte")
        a = analiz.DishDay(DAY, "ogle", dish_a, 10, 0, time(13, 0), None, None)
        b = analiz.DishDay(DAY, "ogle", dish_b, 10, 0, time(12, 0), None, None)
        pair = analiz.Pair(DAY, "ogle", "ana_yemek", a, b)
        self.assertIs(pair.first_out, b)
        b.ran_out_at = time(13, 0)
        self.assertIsNone(pair.first_out)
        self.assertEqual(pair.outcome, "Aynı anda tükendi")
        a.ran_out_at = b.ran_out_at = None
        self.assertEqual(pair.outcome, "İkisi de tükenmedi")

    def test_preference_summary(self):
        rows, _ = analiz.load_dish_days(DAY, DAY)
        summary = {p.dish.code: p for p in analiz.preference_summary(analiz.build_pairs(rows))}
        self.assertEqual((summary["tavuk"].first_out, summary["tavuk"].rival_first), (1, 0))
        self.assertEqual((summary["kofte"].first_out, summary["kofte"].rival_first), (0, 1))
        self.assertAlmostEqual(summary["makarna"].avg_position, 105 / 150)

    def test_preference_summary_is_ordered_by_take_share_not_by_running_out(self):
        # Az üretilen tavuk önce tükendi ama tabakların çoğu köfteden alındı: tercih edilen köftedir.
        tavuk, kofte = Dish.objects.get(code="tavuk"), Dish.objects.get(code="kofte")
        a = analiz.DishDay(DAY, "ogle", tavuk, 3, 0, time(12, 0), None, None)
        b = analiz.DishDay(DAY, "ogle", kofte, 10, 2, None, None, None)
        summary = analiz.preference_summary([analiz.Pair(DAY, "ogle", "ana_yemek", a, b)])
        self.assertEqual([p.dish.code for p in summary], ["kofte", "tavuk"])
        self.assertEqual(summary[1].first_out, 1)


class ThresholdTests(TestCase):
    def test_seeded_profiles(self):
        profiles = list(ThresholdProfile.objects.order_by("order").values_list("key", flat=True))
        self.assertEqual(profiles, ["siki", "dengeli", "esnek"])
        self.assertEqual(analiz.active_profile().key, "dengeli")

    def test_exceeds_is_inclusive(self):
        profile = analiz.active_profile()  # dengeli: toplam %20
        self.assertTrue(analiz.exceeds(profile, "toplam", 0.20))
        self.assertFalse(analiz.exceeds(profile, "toplam", 0.199))
        self.assertFalse(analiz.exceeds(profile, "toplam", None))
        self.assertFalse(analiz.exceeds(profile, "dokunulmayan", 0.9))  # eşiği olmayan metrik
