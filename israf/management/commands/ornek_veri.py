"""Gerçekçi örnek veri üretir: dört CSV dosyası.

Dosyalar hem format örneği hem de panel denemesi içindir. Simülasyon:
öğrenciler servis süresine yayılarak gelir, her biri iki ana yemekten ve iki
yan yemekten birini popülerliğe göre seçer. Seçtiği tükenmişse diğerini almak
zorunda kalır (bu öğrencilerin tabağı daha sık artar). Görüntü işleme
tepsilerin küçük bir kısmını kaçırır.

Kullanım:
  python manage.py ornek_veri                  # ornek_veri/ klasörüne yazar
  python manage.py ornek_veri --yukle          # yazar ve panele yükler
  python manage.py ornek_veri --yukle --yerine-gecsin   # aynı günler zaten yüklüyse
  python manage.py ornek_veri --gun 60 --tohum 7
"""
import csv
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from israf.aktarim import import_csv
from israf.models import ImportBatch

# kod, ad, kategori, tür, popülerlik, (tamamı, yarısı, dokunulmadı) olasılıkları
DISHES = [
    ("tavuk_sote", "Tavuk Sote", "ana_yemek", "tavuk", 1.00, (0.78, 0.15, 0.07)),
    ("firin_tavuk_but", "Fırın Tavuk But", "ana_yemek", "tavuk", 1.10, (0.80, 0.14, 0.06)),
    ("tavuk_sinitzel", "Tavuk Şinitzel", "ana_yemek", "tavuk", 1.30, (0.84, 0.12, 0.04)),
    ("izgara_kofte", "Izgara Köfte", "ana_yemek", "kırmızı et", 1.35, (0.85, 0.11, 0.04)),
    ("et_sote", "Et Sote", "ana_yemek", "kırmızı et", 1.05, (0.74, 0.18, 0.08)),
    ("etli_nohut", "Etli Nohut", "ana_yemek", "bakliyat", 0.80, (0.66, 0.22, 0.12)),
    ("etli_kuru_fasulye", "Etli Kuru Fasulye", "ana_yemek", "bakliyat", 0.95, (0.72, 0.19, 0.09)),
    ("etli_bezelye", "Etli Bezelye", "ana_yemek", "sebze", 0.50, (0.45, 0.30, 0.25)),
    ("karniyarik", "Karnıyarık", "ana_yemek", "sebze", 0.75, (0.60, 0.26, 0.14)),
    ("firin_balik", "Fırın Balık", "ana_yemek", "balık", 0.60, (0.50, 0.33, 0.17)),
    ("patates_oturtma", "Patates Oturtma", "ana_yemek", "sebze", 0.70, (0.62, 0.25, 0.13)),
    ("pirinc_pilavi", "Pirinç Pilavı", "yan_yemek", "pilav", 1.20, (0.72, 0.21, 0.07)),
    ("bulgur_pilavi", "Bulgur Pilavı", "yan_yemek", "pilav", 0.70, (0.58, 0.28, 0.14)),
    ("sehriyeli_pilav", "Şehriyeli Pilav", "yan_yemek", "pilav", 1.00, (0.70, 0.22, 0.08)),
    ("domatesli_makarna", "Domatesli Makarna", "yan_yemek", "makarna", 1.15, (0.74, 0.19, 0.07)),
    ("firin_makarna", "Fırın Makarna", "yan_yemek", "makarna", 1.25, (0.80, 0.15, 0.05)),
    ("patates_puresi", "Patates Püresi", "yan_yemek", "sebze", 0.90, (0.70, 0.20, 0.10)),
    ("zeytinyagli_fasulye", "Zeytinyağlı Taze Fasulye", "yan_yemek", "sebze", 0.55, (0.48, 0.30, 0.22)),
    ("su_boregi", "Su Böreği", "yan_yemek", "hamur işi", 1.30, (0.86, 0.10, 0.04)),
    ("mercimek_corbasi", "Mercimek Çorbası", "corba", "bakliyat çorbası", 1.0, (0.80, 0.12, 0.08)),
    ("ezogelin_corbasi", "Ezogelin Çorbası", "corba", "bakliyat çorbası", 1.0, (0.76, 0.14, 0.10)),
    ("domates_corbasi", "Domates Çorbası", "corba", "sebze çorbası", 1.0, (0.70, 0.16, 0.14)),
    ("yayla_corbasi", "Yayla Çorbası", "corba", "yoğurtlu çorba", 1.0, (0.52, 0.18, 0.30)),
    ("tarhana_corbasi", "Tarhana Çorbası", "corba", "tahıl çorbası", 1.0, (0.60, 0.18, 0.22)),
    ("sebze_corbasi", "Sebze Çorbası", "corba", "sebze çorbası", 1.0, (0.58, 0.20, 0.22)),
    ("mevsim_salata", "Mevsim Salata", "salata", "yeşillik", 1.0, (0.62, 0.24, 0.14)),
    ("coban_salata", "Çoban Salata", "salata", "yeşillik", 1.0, (0.70, 0.20, 0.10)),
    ("ayran", "Ayran", "icecek", "içecek", 1.0, (0.88, 0.04, 0.08)),
]

STORABLE = {"ayran"}  # kapalı kap: artanı stoka döner
DEFAULT_WINDOW = (time(11, 30), time(14, 0))
SPECIAL_DAYS = {
    # gün sırası (sondan): (açılış, kapanış, not)
    3: (time(11, 0), time(14, 30), "Sınav haftası, uzatılmış servis"),
    11: (time(11, 30), time(13, 0), "Resmî tatil arifesi, erken kapanış"),
}
SOUP_TAKE, SALAD_TAKE, DRINK_TAKE = 0.97, 0.50, 0.45
MISSED_TRAY_RATE = 0.015
UNKNOWN_RATE = 0.006


def _minutes(t):
    return t.hour * 60 + t.minute


def _clock(start, offset_min):
    moment = datetime.combine(date(2000, 1, 1), start) + timedelta(minutes=offset_min)
    return moment.strftime("%H:%M")


class Command(BaseCommand):
    help = "Gerçekçi örnek veri üretir (yemekler, ogunler, uretim, tepsiler CSV)."

    def add_arguments(self, parser):
        parser.add_argument("--gun", type=int, default=40, help="Hafta içi gün sayısı (varsayılan 40)")
        parser.add_argument("--bitis", type=date.fromisoformat, default=date(2026, 11, 20), help="Son gün, YYYY-AA-GG")
        parser.add_argument("--tohum", type=int, default=42, help="Rastgelelik tohumu")
        parser.add_argument("--klasor", default=str(settings.BASE_DIR / "ornek_veri"))
        parser.add_argument("--yukle", action="store_true", help="Üretilen dosyaları panele yükle")
        parser.add_argument(
            "--yerine-gecsin",
            action="store_true",
            help="--yukle ile: aynı günlerin daha önce yüklenmiş verisinin yerine geç",
        )

    def handle(self, *args, **opts):
        if opts["gun"] < 1:
            raise CommandError("--gun en az 1 olmalı.")
        rng = random.Random(opts["tohum"])
        folder = Path(opts["klasor"])
        folder.mkdir(parents=True, exist_ok=True)

        days = []
        current = opts["bitis"]
        while len(days) < opts["gun"]:
            if current.weekday() < 5:
                days.append(current)
            current -= timedelta(days=1)
        days.reverse()

        catalogue = {d[0]: d for d in DISHES}
        by_category = {}
        for d in DISHES:
            by_category.setdefault(d[2], []).append(d[0])

        sessions, production, trays = [], [], []
        for index, day in enumerate(days):
            from_end = len(days) - 1 - index
            special = SPECIAL_DAYS.get(from_end)
            window = (special[0], special[1]) if special else DEFAULT_WINDOW
            if special:
                sessions.append([day.isoformat(), "ogle", window[0].strftime("%H:%M"), window[1].strftime("%H:%M"), special[2]])
            p_rows, t_rows = self._simulate_day(rng, day, window, catalogue, by_category, index)
            production.extend(p_rows)
            trays.extend(t_rows)

        files = {
            ImportBatch.Kind.DISHES: ("yemekler.csv", ["yemek_kodu", "yemek_adi", "kategori", "tur", "saklanabilir"],
                                      [[d[0], d[1], d[2], d[3], "evet" if d[0] in STORABLE else "hayir"]
                                       for d in DISHES]),
            ImportBatch.Kind.SESSIONS: ("ogunler.csv", ["tarih", "ogun", "servis_baslangic", "servis_bitis", "not"], sessions),
            ImportBatch.Kind.PRODUCTION: ("uretim.csv", ["tarih", "ogun", "yemek_kodu", "uretilen_porsiyon",
                                                         "artan_porsiyon", "bitis_saati"], production),
            ImportBatch.Kind.TRAYS: ("tepsiler.csv", ["tarih", "ogun", "tepsi_id", "yemek_kodu", "durum"], trays),
        }
        for kind, (name, header, rows) in files.items():
            path = folder / name
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(header)
                writer.writerows(rows)
            self.stdout.write(f"{path}  ({len(rows)} satır)")

        if opts["yukle"]:
            for kind, (name, _, _) in files.items():
                path = folder / name
                batch = import_csv(kind, path.read_bytes(), name, replace=opts["yerine_gecsin"])
                style = self.style.SUCCESS if batch.status == ImportBatch.Status.OK else self.style.ERROR
                self.stdout.write(style(f"{name}: {batch.get_status_display()} — {batch.summary} "
                                        f"({batch.warning_count} uyarı)"))
                if batch.status != ImportBatch.Status.OK:
                    for message in batch.messages[:10]:
                        self.stdout.write(f"  satır {message.get('row')}: {message['text']}")
                    raise CommandError(f"{name} yüklenemedi.")

    def _simulate_day(self, rng, day, window, catalogue, by_category, index):
        start, end = window
        span = _minutes(end) - _minutes(start)
        diners = max(300, round(rng.gauss(950 if day.weekday() == 4 else 1150, 110) * span / 150))
        peak = min(span * 0.4, 60)
        arrivals = sorted(min(max(rng.gauss(peak, span * 0.2), 0), span - 1) for _ in range(diners))

        soup = by_category["corba"][index % len(by_category["corba"])]
        salad = by_category["salata"][index % 2]
        mains = rng.sample(by_category["ana_yemek"], 2)
        while catalogue[mains[0]][3] == catalogue[mains[1]][3]:
            mains = rng.sample(by_category["ana_yemek"], 2)
        sides = rng.sample(by_category["yan_yemek"], 2)
        menu = [soup, *mains, *sides, salad, "ayran"]

        def plan(expected):
            return max(20, round(expected / 5) * 5)  # 5 porsiyonluk kaplar

        def kitchen_share(a, b):
            true_share = catalogue[a][4] / (catalogue[a][4] + catalogue[b][4])
            return min(max(true_share + rng.gauss(0, 0.08), 0.2), 0.8)

        produced = {}
        for pair in (mains, sides):
            share = kitchen_share(*pair)
            produced[pair[0]] = plan(diners * share * rng.uniform(1.0, 1.15))
            produced[pair[1]] = plan(diners * (1 - share) * rng.uniform(1.0, 1.15))
        produced[soup] = plan(diners * rng.uniform(0.98, 1.08))
        produced[salad] = plan(diners * rng.uniform(0.45, 0.6))
        produced["ayran"] = plan(diners * rng.uniform(0.42, 0.55))

        remaining = dict(produced)
        ran_out = {}
        noise = {code: rng.gauss(0, 0.03) for code in menu}
        tray_rows = []
        tray_no = 0

        def take(code, moment):
            remaining[code] -= 1
            if remaining[code] == 0:
                ran_out[code] = moment

        def state(code, forced):
            if rng.random() < UNKNOWN_RATE:
                return "belirsiz"
            finished, half, untouched = catalogue[code][5]
            finished += noise[code] - (0.08 if forced else 0)
            untouched += (0.08 if forced else 0) - noise[code] / 2
            roll = rng.random()
            if roll < finished:
                return "bitti"
            if roll < finished + half:
                return "yarim"
            return "dokunulmadi"

        for moment in arrivals:
            items = []
            for pair in (mains, sides):
                a, b = pair
                p_a = catalogue[a][4] / (catalogue[a][4] + catalogue[b][4])
                wanted = a if rng.random() < p_a else b
                other = b if wanted == a else a
                if remaining[wanted] > 0:
                    take(wanted, moment)
                    items.append((wanted, False))
                elif remaining[other] > 0:
                    take(other, moment)
                    items.append((other, True))
            for code, chance in ((soup, SOUP_TAKE), (salad, SALAD_TAKE), ("ayran", DRINK_TAKE)):
                if remaining[code] > 0 and rng.random() < chance:
                    take(code, moment)
                    items.append((code, False))
            if not items:
                continue
            tray_no += 1
            if rng.random() < MISSED_TRAY_RATE:
                continue
            tray_id = f"T{tray_no:05d}"
            for code, forced in items:
                tray_rows.append([day.isoformat(), "ogle", tray_id, code, state(code, forced)])

        production_rows = []
        for code in menu:
            out = ran_out.get(code)
            production_rows.append([
                day.isoformat(),
                "ogle",
                code,
                produced[code],
                remaining[code],
                _clock(start, out) if out is not None else "",
            ])
        return production_rows, tray_rows
