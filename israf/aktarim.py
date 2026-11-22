"""CSV içe aktarma: okuma, doğrulama, yazma.

Kural: Dosyada tek bir hata varsa hiçbir şey yazılmaz (ya hep ya hiç).
Uyarılar yüklemeyi durdurmaz. Her yükleme, reddedilse bile, dosyasıyla
birlikte ImportBatch olarak kaydedilir.

Yemekhane kaydı ve tepsi analizi öğün öğün yazılır: dosyadaki bir öğün
öncekinin yerine geçer. Verisi zaten yüklü bir öğünü içeren dosya, açık onay
(`replace=True`) verilmedikçe reddedilir; böylece aynı öğünün iki parçası
birbirini sessizce silmez.
"""
import csv
import io
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename

from .formatlar import FORMATS, CsvFormat
from .models import (
    DISH_CODE_PATTERN,
    PAIRED_CATEGORIES,
    Category,
    Dish,
    ImportBatch,
    MealSession,
    MealType,
    PlateState,
    PlateSummary,
    Production,
    ServiceWindowDefault,
    TrayCount,
)

MAX_STORED_MESSAGES = 300
CODE_RE = re.compile(DISH_CODE_PATTERN)
REPLACE_HINT = (
    "Bu dosyadaki öğünlerin verisi daha önce yüklenmiş; kabul edilirse öncekinin yerine geçer. "
    "Dosya aynı öğünün bir parçasıysa (ör. ikinci kameranın tepsileri) parçaları tek dosyada birleştirip "
    "yükleyin, yoksa ikinci parça birinciyi siler. Düzeltilmiş bir dosyaysa yerine geçme onayıyla yeniden "
    "yükleyin: panelde «Önceki verinin yerine geçsin» kutusu, komut satırında --yerine-gecsin."
)
_TR_FOLD = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")
TWO_PLACES = Decimal("0.01")


def fold(value: str) -> str:
    """Türkçe karakterleri ASCII'ye indirir, küçük harfe çevirir, boşlukları `_` yapar."""
    text = value.strip().translate(_TR_FOLD).lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", "_", text)


@dataclass
class Message:
    level: str  # "hata" | "uyari"
    text: str
    row: int | None = None
    column: str | None = None


class Report:
    def __init__(self):
        self.errors: list[Message] = []
        self.warnings: list[Message] = []

    def error(self, text, row=None, column=None):
        self.errors.append(Message("hata", text, row, column))

    def warn(self, text, row=None, column=None):
        self.warnings.append(Message("uyari", text, row, column))

    def stored_messages(self):
        items = self.errors + self.warnings
        stored = [asdict(m) for m in items[:MAX_STORED_MESSAGES]]
        if len(items) > MAX_STORED_MESSAGES:
            stored.append(
                asdict(Message("uyari", f"{len(items) - MAX_STORED_MESSAGES} mesaj daha var; ilk "
                               f"{MAX_STORED_MESSAGES} mesaj gösteriliyor."))
            )
        return stored


# --------------------------------------------------------------------------- okuma


class FileError(Exception):
    pass


@dataclass
class ParsedFile:
    headers: list[str]
    rows: list[tuple[int, dict[str, str], int]]  # (satır no, değerler, hücre sayısı)
    encoding: str
    delimiter: str


def read_csv(raw: bytes) -> ParsedFile:
    if not raw.strip():
        raise FileError("Dosya boş.")
    try:
        text, encoding = raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        try:
            text, encoding = raw.decode("cp1254"), "windows-1254"
        except UnicodeDecodeError as exc:
            raise FileError("Dosyanın karakter kodlaması okunamadı. UTF-8 olarak kaydedin.") from exc

    first_line = text.lstrip("﻿").splitlines()[0] if text.strip() else ""
    delimiter = max((",", ";", "\t"), key=first_line.count)
    if first_line.count(delimiter) == 0:
        delimiter = ","

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    header = next(reader, None)
    if not header or not any(h.strip() for h in header):
        raise FileError("Başlık satırı bulunamadı.")
    headers = [fold(h) for h in header]
    duplicates = [h for h, n in Counter(headers).items() if n > 1 and h]
    if duplicates:
        raise FileError(f"Başlıkta tekrarlanan sütun var: {', '.join(duplicates)}.")

    rows = []
    for record in reader:
        if not any(cell.strip() for cell in record):
            continue
        values = {h: (record[i].strip() if i < len(record) else "") for i, h in enumerate(headers)}
        rows.append((reader.line_num, values, len(record)))
    return ParsedFile(headers, rows, encoding, delimiter)


# ------------------------------------------------------------------- alan okuyucular


def parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Tarih okunamadı: '{value}'. YYYY-AA-GG biçiminde yazın (ör. 2026-11-20).")


def parse_time(value: str) -> time:
    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})(?::(\d{2}))?", value)
    if match:
        hour, minute, second = int(match[1]), int(match[2]), int(match[3] or 0)
        if hour < 24 and minute < 60 and second < 60:
            return time(hour, minute, second)
    raise ValueError(f"Saat okunamadı: '{value}'. SS:DD biçiminde yazın (ör. 12:45).")


def parse_decimal(value: str) -> Decimal:
    text = value.replace(" ", "")
    if "," in text and "." in text:
        raise ValueError(f"Sayı okunamadı: '{value}'. Binlik ayırıcı kullanmayın (ör. 1250 ya da 12,5).")
    try:
        number = Decimal(text.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Sayı okunamadı: '{value}'.") from exc
    if not number.is_finite():
        raise ValueError(f"Sayı okunamadı: '{value}'.")
    return number.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _choice_parser(choices, label):
    valid = {value for value, _ in choices}
    listed = ", ".join(valid_value for valid_value, _ in choices)

    def parse(value: str) -> str:
        folded = fold(value)
        if folded in valid:
            return folded
        raise ValueError(f"Geçersiz {label}: '{value}'. Geçerli değerler: {listed}.")

    return parse


def parse_code(value: str) -> str:
    code = value.strip().lower()
    if CODE_RE.match(code):
        return code
    suggestion = re.sub(r"[^a-z0-9_-]", "", fold(value))
    hint = f" Öneri: '{suggestion}'." if suggestion and CODE_RE.match(suggestion) else ""
    raise ValueError(
        f"Geçersiz yemek kodu: '{value}'. Yalnızca küçük harf, rakam, '_' ve '-' kullanın.{hint}"
    )


TRUE_VALUES = {"evet", "e", "1", "true", "yes", "var"}
FALSE_VALUES = {"hayir", "h", "0", "false", "no", "yok"}


def parse_bool(value: str) -> bool:
    folded = fold(value)
    if folded in TRUE_VALUES:
        return True
    if folded in FALSE_VALUES:
        return False
    raise ValueError(f"Evet/hayır değeri okunamadı: '{value}'. `evet` ya da `hayir` yazın.")


def parse_text(max_length):
    def parse(value: str) -> str:
        if len(value) > max_length:
            raise ValueError(f"En fazla {max_length} karakter olabilir ({len(value)} karakter).")
        return value

    return parse


PARSERS = {
    "date": parse_date,
    "time": parse_time,
    "decimal": parse_decimal,
    "meal": _choice_parser(MealType.choices, "öğün"),
    "category": _choice_parser(Category.choices, "kategori"),
    "state": _choice_parser(PlateState.choices, "durum"),
    "code": parse_code,
    "bool": parse_bool,
}
TEXT_LIMITS = {"yemek_adi": 120, "tur": 60, "not": 200, "tepsi_id": 64}


# -------------------------------------------------------------------- doğrulama


def check_headers(fmt: CsvFormat, parsed: ParsedFile, report: Report):
    present = set(parsed.headers)
    missing = [name for name in fmt.required_names if name not in present]
    if missing:
        report.error(f"Eksik sütun: {', '.join(missing)}. Beklenen başlık: {', '.join(fmt.column_names)}.")
        for other in FORMATS.values():
            if other.kind != fmt.kind and set(other.required_names) <= present:
                report.error(f"Bu dosya «{other.title}» formatına uyuyor. Dosya türünü kontrol edin.")
    unknown = [h for h in parsed.headers if h and h not in fmt.column_names]
    if unknown:
        report.warn(f"Tanınmayan sütunlar yok sayıldı: {', '.join(unknown)}.")


def parse_rows(fmt: CsvFormat, parsed: ParsedFile, report: Report) -> list[tuple[int, dict]]:
    records = []
    header_count = len(parsed.headers)
    for line, values, cell_count in parsed.rows:
        if cell_count > header_count:
            report.error(
                f"Satırda başlıktan fazla değer var ({cell_count}/{header_count}). Ondalık virgül "
                "kullandıysanız değeri tırnak içine alın ya da nokta kullanın.",
                row=line,
            )
            continue
        record, ok = {}, True
        for column in fmt.columns:
            raw = values.get(column.name, "")
            if raw == "":
                if column.required:
                    report.error("Zorunlu alan boş.", row=line, column=column.name)
                    ok = False
                record[column.name] = None
                continue
            parser = PARSERS.get(column.kind) or parse_text(TEXT_LIMITS.get(column.name, 200))
            try:
                record[column.name] = parser(raw)
            except ValueError as exc:
                report.error(str(exc), row=line, column=column.name)
                ok = False
        if ok:
            records.append((line, record))
    return records


def check_duplicates(fmt: CsvFormat, records, report: Report):
    seen = {}
    for line, record in records:
        key = tuple(record[name] for name in fmt.key)
        if key in seen:
            shown = " / ".join(str(k) for k in key)
            report.error(f"Aynı kayıt ({shown}) {seen[key]}. satırda da var.", row=line)
        else:
            seen[key] = line


def _dish_lookup(records, report: Report):
    codes = {r["yemek_kodu"] for _, r in records}
    dishes = {d.code: d for d in Dish.objects.filter(code__in=codes)}
    for line, record in records:
        if record["yemek_kodu"] not in dishes:
            report.error(
                f"Katalogda olmayan yemek kodu: '{record['yemek_kodu']}'. Önce yemek kataloğuna ekleyin.",
                row=line,
                column="yemek_kodu",
            )
    return dishes


def _window_lookup(dates):
    defaults = {d.meal: (d.service_start, d.service_end) for d in ServiceWindowDefault.objects.all()}
    sessions = {
        (s.date, s.meal): (s.service_start, s.service_end)
        for s in MealSession.objects.filter(date__in=dates)
    }
    return lambda day, meal: sessions.get((day, meal)) or defaults.get(meal)


def _meal_label(meal):
    return MealType(meal).label


def _key_label(day, meal):
    return f"{day:%d.%m.%Y} {_meal_label(meal)}"


def _key_id(day, meal):
    return f"{day.isoformat()}/{meal}"


def _check_existing(existing: dict, incoming: dict, unit: str, replace: bool, report: Report):
    """Verisi zaten yüklü öğünlerin üzerine yazmayı açık onaya bağlar.

    `existing` ve `incoming`: (tarih, öğün) → adet (yemek ya da tepsi).
    """
    clashes = sorted(key for key in incoming if existing.get(key))
    if replace or not clashes:
        return
    for key in clashes:
        report.error(
            f"{_key_label(*key)}: daha önce yüklenmiş {existing[key]} {unit} var; bu dosyada {incoming[key]} {unit}."
        )
    report.error(REPLACE_HINT)


# ------------------------------------------------------------ türe özel işlemler


def validate_dishes(records, report: Report):
    existing = {d.code: d for d in Dish.objects.filter(code__in=[r["yemek_kodu"] for _, r in records])}
    for line, record in records:
        dish = existing.get(record["yemek_kodu"])
        if dish and dish.category != record["kategori"]:
            report.warn(
                f"'{dish.code}' kategorisi {dish.get_category_display()} → "
                f"{Category(record['kategori']).label} olarak değişecek. Geçmiş analizler yeni "
                "kategoriyle görünür.",
                row=line,
            )


def write_dishes(records, report: Report):
    created = updated = 0
    for _, record in records:
        defaults = {
            "name": record["yemek_adi"],
            "category": record["kategori"],
            "food_type": (record["tur"] or "").strip().lower(),
        }
        if record["saklanabilir"] is not None:  # boş ya da sütun yoksa mevcut değer korunur
            defaults["storable"] = record["saklanabilir"]
        _, was_created = Dish.objects.update_or_create(code=record["yemek_kodu"], defaults=defaults)
        created += was_created
        updated += not was_created
    return [], f"{created} yeni, {updated} güncellenen yemek."


def validate_sessions(records, report: Report):
    for line, record in records:
        if record["servis_bitis"] <= record["servis_baslangic"]:
            report.error("Servis bitişi başlangıçtan sonra olmalı.", row=line, column="servis_bitis")


def write_sessions(records, report: Report):
    affected = []
    for _, record in records:
        MealSession.objects.update_or_create(
            date=record["tarih"],
            meal=record["ogun"],
            defaults={
                "service_start": record["servis_baslangic"],
                "service_end": record["servis_bitis"],
                "note": record["not"] or "",
            },
        )
        affected.append(_key_id(record["tarih"], record["ogun"]))
    return sorted(set(affected)), f"{len(records)} öğün bilgisi yazıldı."


def validate_production(records, report: Report, replace: bool = False):
    dishes = _dish_lookup(records, report)
    dates = {r["tarih"] for _, r in records}
    _check_existing(
        Counter(Production.objects.filter(date__in=dates).values_list("date", "meal")),
        Counter((r["tarih"], r["ogun"]) for _, r in records),
        "yemek kaydı",
        replace,
        report,
    )
    window = _window_lookup(dates)
    per_key = defaultdict(list)
    for line, record in records:
        produced, leftover = record["uretilen_porsiyon"], record["artan_porsiyon"]
        if produced <= 0:
            report.error("Üretilen porsiyon 0'dan büyük olmalı.", row=line, column="uretilen_porsiyon")
        if leftover < 0:
            report.error("Artan porsiyon negatif olamaz.", row=line, column="artan_porsiyon")
        elif leftover > produced:
            report.error(
                f"Artan porsiyon ({leftover}) üretileni ({produced}) aşıyor.", row=line, column="artan_porsiyon"
            )
        ran_out = record["bitis_saati"]
        if ran_out is not None:
            if leftover > 0:
                report.warn(
                    f"Bitiş saati yazılmış ama {leftover} porsiyon artmış görünüyor.", row=line, column="bitis_saati"
                )
            span = window(record["tarih"], record["ogun"])
            if span and not (span[0] <= ran_out <= span[1]):
                report.warn(
                    f"Bitiş saati {ran_out:%H:%M}, servis saatlerinin ({span[0]:%H:%M}–{span[1]:%H:%M}) dışında.",
                    row=line,
                    column="bitis_saati",
                )
        dish = dishes.get(record["yemek_kodu"])
        if dish:
            per_key[(record["tarih"], record["ogun"])].append(dish)

    existing_plates = defaultdict(set)
    for day, meal, code in PlateSummary.objects.filter(date__in=dates).values_list("date", "meal", "dish__code"):
        existing_plates[(day, meal)].add(code)

    for (day, meal), dish_list in sorted(per_key.items()):
        counts = Counter(d.category for d in dish_list)
        for category in PAIRED_CATEGORIES:
            if counts[category] != 2:
                report.warn(
                    f"{_key_label(day, meal)}: {counts[category]} adet {Category(category).label.lower()} var "
                    "(standart 2). Bu öğün tercih analizine katılmaz."
                )
        missing = existing_plates[(day, meal)] - {d.code for d in dish_list}
        if missing:
            report.warn(
                f"{_key_label(day, meal)}: yüklü tepsi verisinde olan {', '.join(sorted(missing))} "
                "bu kayıtta yok. Bu yemeklerin tepsi verisi analizde görünmez."
            )
    return dishes


def write_production(records, report: Report, dishes):
    by_key = defaultdict(list)
    for _, record in records:
        by_key[(record["tarih"], record["ogun"])].append(record)
    replaced = 0
    for (day, meal), items in sorted(by_key.items()):
        previous = Production.objects.filter(date=day, meal=meal)
        before = set(previous.values_list("dish__code", flat=True))
        removed = before - {r["yemek_kodu"] for r in items}
        if removed:
            report.warn(
                f"{_key_label(day, meal)}: önceki kayıttaki {', '.join(sorted(removed))} bu dosyada yoktu; "
                "kayıtları silindi."
            )
        replaced += bool(before)
        previous.delete()
        Production.objects.bulk_create(
            Production(
                date=day,
                meal=meal,
                dish=dishes[r["yemek_kodu"]],
                produced=r["uretilen_porsiyon"],
                leftover=r["artan_porsiyon"],
                ran_out_at=r["bitis_saati"],
            )
            for r in items
        )
    affected = sorted(_key_id(day, meal) for day, meal in by_key)
    note = f"; {replaced} öğünün önceki kaydının yerine geçti" if replaced else ""
    return affected, f"{len(by_key)} öğün için {len(records)} yemek kaydı yazıldı{note}."


def validate_trays(records, report: Report, replace: bool = False):
    dishes = _dish_lookup(records, report)
    dates = {r["tarih"] for _, r in records}
    trays = defaultdict(set)
    for _, record in records:
        trays[(record["tarih"], record["ogun"])].add(record["tepsi_id"])
    _check_existing(
        {(d, m): n for d, m, n in TrayCount.objects.filter(date__in=dates).values_list("date", "meal", "trays")},
        {key: len(ids) for key, ids in trays.items()},
        "tepsi",
        replace,
        report,
    )
    menus = defaultdict(dict)
    for prod in Production.objects.filter(date__in=dates).select_related("dish"):
        menus[(prod.date, prod.meal)][prod.dish.code] = prod

    missing_menu = set()
    for line, record in records:
        key = (record["tarih"], record["ogun"])
        code = record["yemek_kodu"]
        if code not in dishes:
            continue
        if key not in menus:
            missing_menu.add(key)
        elif code not in menus[key]:
            report.error(
                f"'{code}' {_key_label(*key)} yemekhane kaydında yok. Görüntü işlemenin etiketini ya da "
                "yemekhane kaydını kontrol edin.",
                row=line,
                column="yemek_kodu",
            )
    for key in sorted(missing_menu):
        report.warn(
            f"{_key_label(*key)} için yemekhane kaydı henüz yüklenmemiş. Yemek kodları menüyle "
            "karşılaştırılamadı; kayıt yüklenince analiz tamamlanır."
        )

    if report.errors:
        return dishes, None

    plates = defaultdict(Counter)
    tray_categories = defaultdict(Counter)
    for _, record in records:
        key = (record["tarih"], record["ogun"])
        dish = dishes[record["yemek_kodu"]]
        plates[(*key, dish.code)][record["durum"]] += 1
        tray_categories[(*key, record["tepsi_id"])][dish.category] += 1

    for (day, meal, code), counter in sorted(plates.items()):
        prod = menus.get((day, meal), {}).get(code)
        if prod is None:
            continue
        served = prod.produced - prod.leftover
        plate_total = sum(counter.values())
        if plate_total > served * Decimal("1.05") + 2:
            report.warn(
                f"{_key_label(day, meal)} {prod.dish.name}: tabak sayısı ({plate_total}) servis edilen "
                f"porsiyonu ({served.normalize():f}) aşıyor."
            )

    extra = Counter()
    for (day, meal, _tray), counter in tray_categories.items():
        for category in (Category.MAIN, Category.SIDE, Category.SOUP):
            if counter[category] > 1:
                extra[(day, meal, category)] += 1
    for (day, meal, category), count in sorted(extra.items()):
        report.warn(f"{_key_label(day, meal)}: {count} tepside birden fazla {Category(category).label.lower()} var.")

    return dishes, (plates, trays)


def write_trays(records, report: Report, dishes, aggregates):
    plates, trays = aggregates
    previous = {
        (d, m): n
        for d, m, n in TrayCount.objects.filter(date__in={day for day, _ in trays}).values_list("date", "meal", "trays")
    }
    replaced = 0
    for day, meal in sorted(trays):
        before = previous.get((day, meal))
        if before:
            replaced += 1
            now = len(trays[(day, meal)])
            if now < before:
                report.warn(
                    f"{_key_label(day, meal)}: önceki {before} tepsinin yerine bu dosyadaki {now} tepsi geçti "
                    f"({before - now} tepsi eksildi)."
                )
        PlateSummary.objects.filter(date=day, meal=meal).delete()
        TrayCount.objects.filter(date=day, meal=meal).delete()
    PlateSummary.objects.bulk_create(
        PlateSummary(
            date=day,
            meal=meal,
            dish=dishes[code],
            finished=counter[PlateState.FINISHED],
            half=counter[PlateState.HALF],
            untouched=counter[PlateState.UNTOUCHED],
            unknown=counter[PlateState.UNKNOWN],
        )
        for (day, meal, code), counter in plates.items()
    )
    TrayCount.objects.bulk_create(
        TrayCount(date=day, meal=meal, trays=len(ids)) for (day, meal), ids in trays.items()
    )
    affected = sorted(_key_id(day, meal) for day, meal in trays)
    tray_total = sum(len(ids) for ids in trays.values())
    note = f"; {replaced} öğünün önceki verisinin yerine geçti" if replaced else ""
    return affected, f"{len(trays)} öğün, {tray_total} tepsi, {len(records)} tabak işlendi{note}."


# ----------------------------------------------------------------- ana giriş noktası


def import_csv(kind: str, raw: bytes, filename: str, user=None, replace: bool = False) -> ImportBatch:
    """`replace`: verisi zaten yüklü öğünlerin yerine geçmeye onay (düzeltilmiş dosya)."""
    fmt = FORMATS[kind]
    report = Report()
    parsed = None
    records = []
    try:
        parsed = read_csv(raw)
    except FileError as exc:
        report.error(str(exc))

    if parsed is not None:
        if parsed.encoding != "utf-8":
            report.warn("Dosya Windows-1254 kodlamasıyla okundu. Mümkünse UTF-8 olarak kaydedin.")
        check_headers(fmt, parsed, report)
        if not report.errors:
            if not parsed.rows:
                report.error("Dosyada başlık dışında satır yok.")
            records = parse_rows(fmt, parsed, report)
            check_duplicates(fmt, records, report)

    context = None
    if records:
        if kind == ImportBatch.Kind.DISHES:
            validate_dishes(records, report)
        elif kind == ImportBatch.Kind.SESSIONS:
            validate_sessions(records, report)
        elif kind == ImportBatch.Kind.PRODUCTION:
            context = validate_production(records, report, replace)
        elif kind == ImportBatch.Kind.TRAYS:
            context = validate_trays(records, report, replace)

    batch = ImportBatch(
        kind=kind,
        original_name=filename[:255],
        uploaded_by=user if getattr(user, "is_authenticated", False) else None,
        uploaded_at=timezone.now(),
        row_count=len(parsed.rows) if parsed else 0,
    )
    stored_name = get_valid_filename(f"{batch.uploaded_at:%Y%m%d-%H%M%S}-{filename}") or "dosya.csv"

    if report.errors:
        batch.status = ImportBatch.Status.REJECTED
        batch.summary = f"{len(report.errors)} hata nedeniyle reddedildi; hiçbir veri yazılmadı."
        _finish(batch, report, raw, stored_name)
        return batch

    with transaction.atomic():
        if kind == ImportBatch.Kind.DISHES:
            affected, summary = write_dishes(records, report)
        elif kind == ImportBatch.Kind.SESSIONS:
            affected, summary = write_sessions(records, report)
        elif kind == ImportBatch.Kind.PRODUCTION:
            affected, summary = write_production(records, report, context)
        else:
            dishes, aggregates = context
            affected, summary = write_trays(records, report, dishes, aggregates)
        batch.status = ImportBatch.Status.OK
        batch.summary = summary
        batch.affected = affected
        _finish(batch, report, raw, stored_name)
    return batch


def _finish(batch: ImportBatch, report: Report, raw: bytes, stored_name: str):
    batch.error_count = len(report.errors)
    batch.warning_count = len(report.warnings)
    batch.messages = report.stored_messages()
    batch.stored_file.save(stored_name, ContentFile(raw), save=False)
    batch.save()
