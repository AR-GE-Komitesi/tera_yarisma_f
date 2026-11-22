"""İsraf metrikleri.

Tanımlar (bir yemeğin bir öğündeki kaydı için):
  U  üretilen porsiyon                  (yemekhane)
  A  artan porsiyon (kazan artığı)      (yemekhane)
  S  servis edilen = U − A
  b, y, d  tamamı yenen / yarısı yenen / dokunulmayan tabak sayısı (görüntü işleme)
  N  = b + y + d  (belirsiz tabaklar oranlara katılmaz)

  Kazan artığı oranı       = A / U
  Bitirilmeyen tabak oranı = (y + d) / N
  Dokunulmayan tabak oranı = d / N
  Tabak artığı oranı       = (0,5·y + d) / N        servis edilenin tabakta kalan payı
  Tabakta kalan porsiyon   = S × tabak artığı oranı
  Toplam israf             = A + tabakta kalan porsiyon
  Toplam israf oranı       = toplam israf / U

Birden çok kayıt birleştirilirken oranlar günlük oranların ortalaması değil,
toplamların oranıdır (porsiyon ağırlıklı). Toplam israf yalnızca hem yemekhane
hem tepsi verisi olan kayıtlardan hesaplanır.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, fields
from datetime import date, time, timedelta
from functools import cached_property

from .models import (
    CATEGORY_ORDER,
    PAIRED_CATEGORIES,
    Category,
    Dish,
    MealSession,
    MealType,
    PlateState,
    PlateSummary,
    Production,
    ServiceWindowDefault,
    ThresholdProfile,
    TrayCount,
)

WASTE_WEIGHT = {
    PlateState.FINISHED: 0.0,
    PlateState.HALF: 0.5,
    PlateState.UNTOUCHED: 1.0,
}


def ratio(numerator, denominator):
    if numerator is None or not denominator:
        return None
    return numerator / denominator


@dataclass
class Measures:
    """Toplanabilir ham sayılar. Oranlar bu sayılardan türetilir."""

    appearances: int = 0
    produced: float = 0.0
    leftover: float = 0.0
    finished: int = 0
    half: int = 0
    untouched: int = 0
    unknown: int = 0
    plate_rows: int = 0
    complete_rows: int = 0
    complete_produced: float = 0.0
    complete_leftover: float = 0.0
    complete_plate_waste: float = 0.0

    def add(self, other: "Measures") -> "Measures":
        for f in fields(self):
            setattr(self, f.name, getattr(self, f.name) + getattr(other, f.name))
        return self

    @property
    def served(self):
        return self.produced - self.leftover

    @property
    def plates(self):
        return self.finished + self.half + self.untouched

    @property
    def plates_all(self):
        return self.plates + self.unknown

    @property
    def pot_rate(self):
        return ratio(self.leftover, self.produced)

    @property
    def unfinished_rate(self):
        return ratio(self.half + self.untouched, self.plates)

    @property
    def untouched_rate(self):
        return ratio(self.untouched, self.plates)

    @property
    def finished_rate(self):
        return ratio(self.finished, self.plates)

    @property
    def half_rate(self):
        return ratio(self.half, self.plates)

    @property
    def unknown_rate(self):
        return ratio(self.unknown, self.plates_all)

    @property
    def plate_waste_rate(self):
        weighted = WASTE_WEIGHT[PlateState.HALF] * self.half + WASTE_WEIGHT[PlateState.UNTOUCHED] * self.untouched
        return ratio(weighted, self.plates)

    @property
    def total_waste(self):
        if not self.complete_rows:
            return None
        return self.complete_leftover + self.complete_plate_waste

    @property
    def total_waste_rate(self):
        return ratio(self.total_waste, self.complete_produced)

    @property
    def pot_share(self):
        """Toplam israf oranının kazan artığından gelen kısmı (tam kayıtlar)."""
        return ratio(self.complete_leftover, self.complete_produced) if self.complete_rows else None

    @property
    def plate_share(self):
        """Toplam israf oranının tabak artığından gelen kısmı (tam kayıtlar)."""
        return ratio(self.complete_plate_waste, self.complete_produced) if self.complete_rows else None

    def metric(self, key: str):
        return METRICS[key].getter(self)


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    short: str
    getter: callable
    is_rate: bool = True


METRICS = {
    m.key: m
    for m in (
        Metric("toplam", "Toplam israf oranı", "Toplam israf", lambda m: m.total_waste_rate),
        Metric("kazan", "Kazan artığı oranı", "Kazan artığı", lambda m: m.pot_rate),
        Metric("bitirilmeyen", "Bitirilmeyen tabak oranı", "Bitirilmeyen tabak", lambda m: m.unfinished_rate),
        Metric("dokunulmayan", "Dokunulmayan tabak oranı", "Dokunulmayan tabak", lambda m: m.untouched_rate),
        Metric("tabak", "Tabak artığı oranı", "Tabak artığı", lambda m: m.plate_waste_rate),
        Metric("porsiyon", "İsraf edilen porsiyon", "İsraf (porsiyon)", lambda m: m.total_waste, is_rate=False),
    )
}


@dataclass
class DishDay:
    """Bir yemeğin bir öğündeki kaydı: yemekhane + (varsa) tepsi özeti."""

    date: date
    meal: str
    dish: Dish
    produced: float
    leftover: float
    ran_out_at: time | None
    plates: PlateSummary | None
    window: tuple[time, time] | None

    @property
    def served(self):
        return self.produced - self.leftover

    @property
    def meal_label(self):
        return MealType(self.meal).label

    @cached_property
    def measures(self) -> Measures:
        if self.dish.storable:
            # Artan stoka döner: üretim tabanı servis edilen kadardır, kazan artığı yoktur.
            m = Measures(appearances=1, produced=self.served, leftover=0.0)
        else:
            m = Measures(appearances=1, produced=self.produced, leftover=self.leftover)
        if self.plates is not None:
            m.finished = self.plates.finished
            m.half = self.plates.half
            m.untouched = self.plates.untouched
            m.unknown = self.plates.unknown
            m.plate_rows = 1
        plate_rate = m.plate_waste_rate
        if self.served <= 0:
            plate_rate = 0.0  # kimse almadıysa tabak artığı yoktur; israfın tamamı kazanda
        if plate_rate is not None:
            m.complete_rows = 1
            m.complete_produced = m.produced
            m.complete_leftover = m.leftover
            m.complete_plate_waste = self.served * plate_rate
        return m

    @property
    def coverage(self):
        """Analiz edilen tabak / servis edilen porsiyon."""
        if self.plates is None:
            return None
        return ratio(self.plates.total, self.served)

    @property
    def run_out_position(self):
        """Tükenme anının servis süresi içindeki yeri (0 = açılış, 1 = kapanış)."""
        if self.ran_out_at is None or self.window is None:
            return None
        start, end = (_minutes(t) for t in self.window)
        if end <= start:
            return None
        position = (_minutes(self.ran_out_at) - start) / (end - start)
        return min(max(position, 0.0), 1.0)


def _minutes(t: time) -> float:
    return t.hour * 60 + t.minute + t.second / 60


def window_lookup(start: date, end: date):
    defaults = {d.meal: (d.service_start, d.service_end) for d in ServiceWindowDefault.objects.all()}
    sessions = {
        (s.date, s.meal): (s.service_start, s.service_end)
        for s in MealSession.objects.filter(date__range=(start, end))
    }
    return lambda day, meal: sessions.get((day, meal)) or defaults.get(meal)


def load_dish_days(start: date, end: date, meal: str | None = None, dish: Dish | None = None):
    """(kayıtlar, yetim tepsi özetleri) döndürür.

    Yetim özet: tepsi verisi olup yemekhane kaydı olmayan yemek. Analize
    katılmaz, Veri durumu sayfasında gösterilir.
    """
    productions = Production.objects.select_related("dish").filter(date__range=(start, end))
    summaries = PlateSummary.objects.select_related("dish").filter(date__range=(start, end))
    if meal:
        productions = productions.filter(meal=meal)
        summaries = summaries.filter(meal=meal)
    if dish is not None:
        productions = productions.filter(dish=dish)
        summaries = summaries.filter(dish=dish)

    plates = {(p.date, p.meal, p.dish_id): p for p in summaries}
    window = window_lookup(start, end)
    rows = []
    for prod in productions.order_by("date", "meal"):
        rows.append(
            DishDay(
                date=prod.date,
                meal=prod.meal,
                dish=prod.dish,
                produced=float(prod.produced),
                leftover=float(prod.leftover),
                ran_out_at=prod.ran_out_at,
                plates=plates.pop((prod.date, prod.meal, prod.dish_id), None),
                window=window(prod.date, prod.meal),
            )
        )
    rows.sort(key=lambda r: (r.date, r.meal, CATEGORY_ORDER.get(r.dish.category, 99), r.dish.name))
    return rows, list(plates.values())


def total(rows) -> Measures:
    result = Measures()
    for row in rows:
        result.add(row.measures)
    return result


@dataclass
class Group:
    key: str
    label: str
    measures: Measures
    dish: Dish | None = None
    category: str | None = None
    food_type: str | None = None

    @property
    def category_label(self):
        return Category(self.category).label if self.category else ""


GROUPINGS = {
    "yemek": "Yemek",
    "tur": "Tür",
    "kategori": "Kategori",
}


def group_rows(rows, by: str) -> list[Group]:
    groups: dict[str, Group] = {}
    for row in rows:
        dish = row.dish
        if by == "yemek":
            key, label = dish.code, dish.name
            make = lambda: Group(key, label, Measures(), dish=dish, category=dish.category, food_type=dish.food_type)
        elif by == "tur":
            key = dish.food_type or "-"
            label = dish.food_type.capitalize() if dish.food_type else "Türü girilmemiş"
            make = lambda: Group(key, label, Measures(), food_type=dish.food_type)
        elif by == "kategori":
            key, label = dish.category, dish.get_category_display()
            make = lambda: Group(key, label, Measures(), category=dish.category)
        else:
            raise ValueError(f"Bilinmeyen gruplama: {by}")
        if key not in groups:
            groups[key] = make()
        groups[key].measures.add(row.measures)
    result = list(groups.values())
    if by == "kategori":
        result.sort(key=lambda g: CATEGORY_ORDER.get(g.key, 99))
    return result


def sort_groups(groups: list[Group], metric: str, descending: bool = True) -> list[Group]:
    """Değeri olmayanlar her zaman en sonda."""
    getter = METRICS[metric].getter
    with_value = [g for g in groups if getter(g.measures) is not None]
    without = [g for g in groups if getter(g.measures) is None]
    with_value.sort(key=lambda g: (getter(g.measures), g.measures.produced), reverse=descending)
    return with_value + sorted(without, key=lambda g: g.label)


# ---------------------------------------------------------------------- eğilim

TREND_DAILY_LIMIT = 92


def trend(rows, start: date, end: date):
    """Gün (ya da uzun dönemde hafta) başına israf bileşenleri.

    Yalnızca tam kayıtlar kullanılır; böylece kazan + tabak payları toplam
    israf oranına eşit olur.
    """
    weekly = (end - start).days + 1 > TREND_DAILY_LIMIT
    buckets: dict[date, Measures] = defaultdict(Measures)
    for row in rows:
        bucket = row.date - timedelta(days=row.date.weekday()) if weekly else row.date
        buckets[bucket].add(row.measures)
    points = []
    for bucket in sorted(buckets):
        m = buckets[bucket]
        if m.complete_rows:
            label = f"{bucket:%d.%m.%Y} haftası" if weekly else f"{bucket:%d.%m.%Y}"
            points.append((label, m))
    return weekly, points


# --------------------------------------------------------------------- tercih


@dataclass
class Pair:
    """Aynı öğünde aynı kategoride çıkan iki seçenek (ör. tavuk ve köfte)."""

    date: date
    meal: str
    category: str
    a: DishDay
    b: DishDay

    @property
    def meal_label(self):
        return MealType(self.meal).label

    @property
    def category_label(self):
        return Category(self.category).label

    @property
    def served_total(self):
        return self.a.served + self.b.served

    @property
    def produced_total(self):
        return self.a.produced + self.b.produced

    def share(self, side: DishDay):
        return ratio(side.served, self.served_total)

    def production_share(self, side: DishDay):
        return ratio(side.produced, self.produced_total)

    def rival(self, side: DishDay) -> DishDay:
        return self.b if side is self.a else self.a

    @property
    def first_out(self) -> DishDay | None:
        a_out, b_out = self.a.ran_out_at, self.b.ran_out_at
        if a_out and b_out:
            if a_out == b_out:
                return None
            return self.a if a_out < b_out else self.b
        if a_out:
            return self.a
        if b_out:
            return self.b
        return None

    @property
    def outcome(self) -> str:
        a_out, b_out = self.a.ran_out_at, self.b.ran_out_at
        if a_out and b_out:
            if a_out == b_out:
                return "Aynı anda tükendi"
            return f"{self.first_out.dish.name} önce tükendi"
        if a_out or b_out:
            return f"Yalnız {self.first_out.dish.name} tükendi"
        return "İkisi de tükenmedi"

    @property
    def sides(self):
        return (self.a, self.b)


def build_pairs(rows) -> list[Pair]:
    buckets = defaultdict(list)
    for row in rows:
        if row.dish.category in PAIRED_CATEGORIES:
            buckets[(row.date, row.meal, row.dish.category)].append(row)
    pairs = []
    for (day, meal, category), items in buckets.items():
        if len(items) == 2:
            a, b = sorted(items, key=lambda r: r.dish.name)
            pairs.append(Pair(day, meal, category, a, b))
    # Yeni öğün önce; aynı öğünde ana yemek yan yemekten önce.
    pairs.sort(key=lambda p: (-p.date.toordinal(), p.meal, CATEGORY_ORDER[p.category]))
    return pairs


@dataclass
class DishPreference:
    dish: Dish
    pairs: int = 0
    ran_out: int = 0
    first_out: int = 0
    rival_first: int = 0
    share_sum: float = 0.0
    production_share_sum: float = 0.0
    position_sum: float = 0.0
    position_count: int = 0

    @property
    def avg_share(self):
        return ratio(self.share_sum, self.pairs)

    @property
    def avg_production_share(self):
        return ratio(self.production_share_sum, self.pairs)

    @property
    def avg_position(self):
        return ratio(self.position_sum, self.position_count)

    @property
    def first_out_rate(self):
        return ratio(self.first_out, self.pairs)


def preference_summary(pairs: list[Pair]) -> list[DishPreference]:
    stats: dict[int, DishPreference] = {}
    for pair in pairs:
        winner = pair.first_out
        for side in pair.sides:
            item = stats.setdefault(side.dish.pk, DishPreference(side.dish))
            item.pairs += 1
            item.share_sum += pair.share(side) or 0.0
            item.production_share_sum += pair.production_share(side) or 0.0
            if side.ran_out_at:
                item.ran_out += 1
                position = side.run_out_position
                if position is not None:
                    item.position_sum += position
                    item.position_count += 1
            if winner is side:
                item.first_out += 1
            elif winner is pair.rival(side):
                item.rival_first += 1
    result = list(stats.values())
    result.sort(
        key=lambda p: (CATEGORY_ORDER[p.dish.category], -(p.first_out_rate or 0), -(p.avg_share or 0), p.dish.name)
    )
    return result


# ------------------------------------------------------------------ tepsi alımı


def tray_total(start: date, end: date, meal: str | None = None) -> int:
    qs = TrayCount.objects.filter(date__range=(start, end))
    if meal:
        qs = qs.filter(meal=meal)
    return sum(qs.values_list("trays", flat=True))


def take_rates(rows, trays: int):
    """Kategori başına tepsi başına alınan tabak (yalnızca tepsi verisi olan kayıtlar)."""
    if not trays:
        return {}
    counts = defaultdict(int)
    for row in rows:
        if row.plates is not None:
            counts[row.dish.category] += row.plates.total
    return {category: count / trays for category, count in counts.items()}


# ------------------------------------------------------------------ veri durumu


@dataclass
class MealStatus:
    date: date
    meal: str
    production_rows: int = 0
    plate_rows: int = 0
    trays: int | None = None
    main_served: float = 0.0
    main_plates: int = 0
    unknown: int = 0
    plates_all: int = 0
    missing_plates: list = None
    orphans: list = None
    main_count: int = 0
    side_count: int = 0
    session_note: str = ""

    @property
    def meal_label(self):
        return MealType(self.meal).label

    @property
    def coverage(self):
        return ratio(self.main_plates, self.main_served)

    @property
    def unknown_rate(self):
        return ratio(self.unknown, self.plates_all)

    @property
    def is_complete(self):
        return self.production_rows > 0 and self.plate_rows > 0 and not self.missing_plates and not self.orphans


def data_status(start: date, end: date, meal: str | None = None) -> list[MealStatus]:
    rows, orphans = load_dish_days(start, end, meal)
    status: dict[tuple, MealStatus] = {}

    def get(day, meal_value):
        key = (day, meal_value)
        if key not in status:
            status[key] = MealStatus(day, meal_value, missing_plates=[], orphans=[])
        return status[key]

    for row in rows:
        item = get(row.date, row.meal)
        item.production_rows += 1
        if row.dish.category == Category.MAIN:
            item.main_count += 1
        elif row.dish.category == Category.SIDE:
            item.side_count += 1
        if row.plates is None:
            item.missing_plates.append(row.dish.name)
            continue
        item.plate_rows += 1
        item.unknown += row.plates.unknown
        item.plates_all += row.plates.total
        if row.dish.category == Category.MAIN:
            item.main_served += row.served
            item.main_plates += row.plates.total
    for summary in orphans:
        item = get(summary.date, summary.meal)
        item.orphans.append(summary.dish.name)
    trays = TrayCount.objects.filter(date__range=(start, end))
    sessions = MealSession.objects.filter(date__range=(start, end))
    if meal:
        trays = trays.filter(meal=meal)
        sessions = sessions.filter(meal=meal)
    for tray in trays:
        get(tray.date, tray.meal).trays = tray.trays
    for session in sessions:
        if (session.date, session.meal) in status:
            status[(session.date, session.meal)].session_note = session.note
    return sorted(status.values(), key=lambda s: (s.date, s.meal), reverse=True)


# ---------------------------------------------------------------------- eşikler

FALLBACK_PROFILE = ThresholdProfile(
    key="dengeli", name="Dengeli", unfinished_plate_rate=50, pot_leftover_rate=10, total_waste_rate=20
)


def active_profile() -> ThresholdProfile:
    return (
        ThresholdProfile.objects.filter(is_active=True).first()
        or ThresholdProfile.objects.order_by("order").first()
        or FALLBACK_PROFILE
    )


def exceeds(profile: ThresholdProfile, metric: str, value) -> bool:
    limit = profile.limit_for(metric)
    return limit is not None and value is not None and value >= limit
