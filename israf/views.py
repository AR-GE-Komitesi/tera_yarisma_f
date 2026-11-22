import csv
import io
from dataclasses import dataclass
from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Min
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import analiz
from .aktarim import import_csv
from .formatlar import FORMATS, GENERAL_RULES
from .forms import FilterForm, RankingForm, ServiceWindowForm, ThresholdProfileForm, UploadForm
from .models import (
    PAIRED_CATEGORIES,
    Category,
    Dish,
    ImportBatch,
    MealSession,
    MealType,
    Production,
    ServiceWindowDefault,
    ThresholdProfile,
    TrayCount,
)


def staff_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Bu işlem için yönetici yetkisi gerekir.")
        return view(request, *args, **kwargs)

    return wrapper


# ------------------------------------------------------------------- filtre


@dataclass
class PanelFilter:
    form: FilterForm
    first: date | None
    last: date | None
    start: date | None
    end: date | None
    meal: str

    @property
    def empty(self):
        return self.first is None

    @property
    def meal_or_none(self):
        return self.meal or None

    @property
    def meal_label(self):
        return MealType(self.meal).label if self.meal else "Tüm öğünler"

    @property
    def days(self):
        return (self.end - self.start).days + 1 if self.start and self.end else 0

    @property
    def presets(self):
        if self.empty:
            return []
        options = [("Tüm dönem", self.first)]
        for label, length in (("Son 7 gün", 7), ("Son 30 gün", 30), ("Son 90 gün", 90)):
            begin = self.last - timedelta(days=length - 1)
            if begin > self.first:
                options.append((label, begin))
        result = []
        for label, begin in options:
            params = {"ogun": self.meal} if self.meal else {}
            if begin != self.first:
                params.update(baslangic=begin.isoformat(), bitis=self.last.isoformat())
            result.append(
                {
                    "label": label,
                    "qs": urlencode(params),
                    "active": self.start == begin and self.end == self.last,
                }
            )
        return result


def resolve_filter(request) -> PanelFilter:
    bounds = Production.objects.aggregate(first=Min("date"), last=Max("date"))
    first, last = bounds["first"], bounds["last"]
    bound = any(request.GET.get(k) for k in ("baslangic", "bitis", "ogun"))
    form = FilterForm(request.GET if bound else None)
    data = form.cleaned_data if bound and form.is_valid() else {}
    start = data.get("baslangic") or first
    end = data.get("bitis") or last
    if start and end and start > end:
        start, end = end, start
    if not bound:
        form = FilterForm(initial={"baslangic": start, "bitis": end})
    return PanelFilter(form, first, last, start, end, data.get("ogun") or "")


def panel_context(request, flt=None, **extra):
    context = {"filtre": flt, "esik_profili": analiz.active_profile()}
    context.update(extra)
    return context


def _empty(request, flt=None):
    return render(request, "israf/bos.html", panel_context(request, flt))


def _pct(value):
    return None if value is None else round(value * 100, 1)


def _stack_chart(labels, measures_list, profile):
    limit = profile.limit_for("toplam")
    return {
        "labels": labels,
        "series": [
            {"key": "pot", "label": "Kazan artığı", "values": [_pct(m.pot_share) for m in measures_list]},
            {"key": "plate", "label": "Tabak artığı", "values": [_pct(m.plate_share) for m in measures_list]},
        ],
        "totals": [_pct(m.total_waste_rate) for m in measures_list],
        "threshold": None if limit is None else round(limit * 100, 1),
        "thresholdLabel": f"{profile.name} eşiği",
    }


# ------------------------------------------------------------------ sayfalar


@login_required
def genel(request):
    flt = resolve_filter(request)
    if flt.empty:
        return _empty(request, flt)
    profile = analiz.active_profile()
    rows, orphans = analiz.load_dish_days(flt.start, flt.end, flt.meal_or_none)
    measures = analiz.total(rows)
    categories = analiz.group_rows(rows, "kategori")
    trays = analiz.tray_total(flt.start, flt.end, flt.meal_or_none)
    take = analiz.take_rates(rows, trays)
    for group in categories:
        group.take_rate = take.get(group.key)
    dishes = [g for g in analiz.group_rows(rows, "yemek") if g.measures.total_waste_rate is not None]
    ranked = analiz.sort_groups(dishes, "toplam")

    weekly, points = analiz.trend(rows, flt.start, flt.end)
    trend_chart = _stack_chart([label for label, _ in points], [m for _, m in points], profile)

    charted = [g for g in categories if g.measures.complete_rows]
    category_chart = _stack_chart([g.label for g in charted], [g.measures for g in charted], profile)

    meals = {(r.date, r.meal) for r in rows}
    meals_with_plates = {(r.date, r.meal) for r in rows if r.plates is not None}
    return render(
        request,
        "israf/genel.html",
        panel_context(
            request,
            flt,
            toplam=measures,
            kategoriler=categories,
            en_cok=ranked[:5],
            en_az=list(reversed(ranked[-5:])) if len(ranked) > 5 else [],
            haftalik=weekly,
            egilim=points,
            egilim_grafik=trend_chart,
            kategori_grafik=category_chart,
            tepsi=trays,
            ogun_sayisi=len(meals),
            tepsili_ogun=len(meals_with_plates),
            yetim=len(orphans),
        ),
    )


def _parse_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


@login_required
def gun(request):
    keys = list(Production.objects.values_list("date", "meal").distinct().order_by("date", "meal"))
    if not keys:
        return _empty(request)
    wanted_date = _parse_date(request.GET.get("tarih"))
    wanted_meal = request.GET.get("ogun") or ""
    selected = keys[-1]
    if wanted_date:
        same_day = [k for k in keys if k[0] == wanted_date]
        exact = [k for k in same_day if k[1] == wanted_meal]
        if exact or same_day:
            selected = (exact or same_day)[0]
        else:
            earlier = [k for k in keys if k[0] <= wanted_date]
            selected = earlier[-1] if earlier else keys[0]
            messages.info(request, f"{wanted_date:%d.%m.%Y} için kayıt yok; en yakın önceki öğün gösteriliyor.")
    index = keys.index(selected)
    day, meal = selected
    rows, orphans = analiz.load_dish_days(day, day, meal)
    groups = []
    for category in Category.values:
        items = [r for r in rows if r.dish.category == category]
        if items:
            groups.append((Category(category).label, items))
    tray = TrayCount.objects.filter(date=day, meal=meal).first()
    trays = tray.trays if tray else 0
    session = MealSession.objects.filter(date=day, meal=meal).first()
    window = analiz.window_lookup(day, day)(day, meal)
    take = analiz.take_rates(rows, trays)
    return render(
        request,
        "israf/gun.html",
        panel_context(
            request,
            None,
            tarih=day,
            ogun=meal,
            ogun_adi=MealType(meal).label,
            ogunler=[k[1] for k in keys if k[0] == day],
            onceki=keys[index - 1] if index > 0 else None,
            sonraki=keys[index + 1] if index + 1 < len(keys) else None,
            gruplar=groups,
            ciftler=analiz.build_pairs(rows),
            toplam=analiz.total(rows),
            tepsi=trays,
            alim=[(Category(c).label, take[c]) for c in Category.values if c in take],
            oturum=session,
            servis=window,
            yetim=orphans,
            meal_choices=MealType.choices,
        ),
    )


def _ranking_params(request):
    form = RankingForm(request.GET)
    data = form.cleaned_data if form.is_valid() else {}
    return {
        "form": form,
        "grup": data.get("grup") or "yemek",
        "kategori": data.get("kategori") or "",
        "metrik": data.get("metrik") or "toplam",
        "min_cikis": data.get("min_cikis") or 1,
    }


def _ranking(request):
    flt = resolve_filter(request)
    params = _ranking_params(request)
    if flt.empty:
        return flt, params, []
    rows, _ = analiz.load_dish_days(flt.start, flt.end, flt.meal_or_none)
    if params["kategori"]:
        rows = [r for r in rows if r.dish.category == params["kategori"]]
    groups = analiz.group_rows(rows, params["grup"])
    groups = [g for g in groups if g.measures.appearances >= params["min_cikis"]]
    return flt, params, analiz.sort_groups(groups, params["metrik"])


@login_required
def siralama(request):
    flt, params, groups = _ranking(request)
    if flt.empty:
        return _empty(request, flt)
    return render(
        request,
        "israf/siralama.html",
        panel_context(
            request,
            flt,
            gruplar=groups,
            secim=params,
            form=params["form"],
            metrik=analiz.METRICS[params["metrik"]],
            grup_adi=analiz.GROUPINGS[params["grup"]],
            csv_qs=request.GET.urlencode(),
        ),
    )


def _tr_decimal(value, digits=1):
    if value is None:
        return ""
    return f"{value:.{digits}f}".replace(".", ",")


@login_required
def siralama_csv(request):
    flt, params, groups = _ranking(request)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    first = analiz.GROUPINGS[params["grup"]].lower()
    header = [first]
    if params["grup"] == "yemek":
        header += ["yemek_kodu", "kategori", "tur"]
    header += [
        "cikis_sayisi",
        "uretilen_porsiyon",
        "servis_edilen_porsiyon",
        "kazan_artigi_yuzde",
        "bitirilmeyen_tabak_yuzde",
        "dokunulmayan_tabak_yuzde",
        "tabak_artigi_yuzde",
        "toplam_israf_yuzde",
        "israf_porsiyon",
        "analiz_edilen_tabak",
    ]
    writer.writerow(header)
    for g in groups:
        m = g.measures
        line = [g.label]
        if params["grup"] == "yemek":
            line += [g.dish.code, g.category_label, g.food_type]
        line += [
            m.appearances,
            _tr_decimal(m.produced),
            _tr_decimal(m.served),
            _tr_decimal(_pct(m.pot_rate)),
            _tr_decimal(_pct(m.unfinished_rate)),
            _tr_decimal(_pct(m.untouched_rate)),
            _tr_decimal(_pct(m.plate_waste_rate)),
            _tr_decimal(_pct(m.total_waste_rate)),
            _tr_decimal(m.total_waste),
            m.plates,
        ]
        writer.writerow(line)
    span = f"{flt.start:%Y%m%d}-{flt.end:%Y%m%d}" if flt.start else "bos"
    response = HttpResponse("﻿" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="israf_siralamasi_{params["grup"]}_{span}.csv"'
    return response


@login_required
def tercih(request):
    flt = resolve_filter(request)
    if flt.empty:
        return _empty(request, flt)
    category = request.GET.get("kategori") or ""
    if category not in PAIRED_CATEGORIES:
        category = ""
    rows, _ = analiz.load_dish_days(flt.start, flt.end, flt.meal_or_none)
    pairs = analiz.build_pairs(rows)
    if category:
        pairs = [p for p in pairs if p.category == category]
    summary = analiz.preference_summary(pairs)
    sections = []
    for value in PAIRED_CATEGORIES:
        items = [s for s in summary if s.dish.category == value]
        if items:
            sections.append((Category(value).label, items))
    limit = 60
    return render(
        request,
        "israf/tercih.html",
        panel_context(
            request,
            flt,
            bolumler=sections,
            ciftler=pairs[:limit],
            cift_sayisi=len(pairs),
            cift_sinir=limit,
            kategori=category,
            kategori_secenekleri=[(c, Category(c).label) for c in PAIRED_CATEGORIES],
        ),
    )


@login_required
def yemek(request, code):
    dish = get_object_or_404(Dish, code=code)
    flt = resolve_filter(request)
    if flt.empty:
        return _empty(request, flt)
    profile = analiz.active_profile()
    all_rows, _ = analiz.load_dish_days(flt.start, flt.end, flt.meal_or_none)
    rows = [r for r in all_rows if r.dish.pk == dish.pk]
    pairs = [p for p in analiz.build_pairs(all_rows) if dish.pk in (p.a.dish.pk, p.b.dish.pk)]
    preference = next((p for p in analiz.preference_summary(pairs) if p.dish.pk == dish.pk), None)
    charted = [r for r in rows if r.measures.complete_rows]
    chart = _stack_chart(
        [f"{r.date:%d.%m.%Y}" + ("" if flt.meal else f" {r.meal_label}") for r in charted],
        [r.measures for r in charted],
        profile,
    )
    return render(
        request,
        "israf/yemek.html",
        panel_context(
            request,
            flt,
            yemek=dish,
            kayitlar=list(reversed(rows)),
            toplam=analiz.total(rows),
            grafik=chart,
            ciftler=pairs,
            tercih=preference,
        ),
    )


# ---------------------------------------------------------------------- veri


@login_required
def veri(request):
    if request.method == "POST":
        if not request.user.is_staff:
            raise PermissionDenied("Veri yüklemek için yönetici yetkisi gerekir.")
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.cleaned_data["dosya"]
            batch = import_csv(form.cleaned_data["tur"], upload.read(), upload.name, request.user)
            if batch.status == ImportBatch.Status.OK:
                messages.success(request, f"{batch.original_name} yüklendi. {batch.summary}")
            else:
                messages.error(request, f"{batch.original_name} reddedildi. {batch.summary}")
            return redirect("israf:aktarim", pk=batch.pk)
    else:
        form = UploadForm(initial={"tur": request.GET.get("tur") or ImportBatch.Kind.TRAYS})
    latest = Production.objects.aggregate(last=Max("date"))["last"]
    return render(
        request,
        "israf/veri.html",
        panel_context(
            request,
            None,
            form=form,
            formatlar=list(FORMATS.values()),
            yuklemeler=ImportBatch.objects.select_related("uploaded_by")[:30],
            yemek_sayisi=Dish.objects.count(),
            son_tarih=latest,
        ),
    )


@login_required
def aktarim(request, pk):
    batch = get_object_or_404(ImportBatch.objects.select_related("uploaded_by"), pk=pk)
    affected = []
    for item in batch.affected:
        day_text, _, meal = item.partition("/")
        day = _parse_date(day_text)
        if day and meal in MealType.values:
            affected.append({"tarih": day, "ogun": meal, "ad": MealType(meal).label})
    return render(
        request,
        "israf/aktarim.html",
        panel_context(
            request,
            None,
            yukleme=batch,
            hatalar=[m for m in batch.messages if m.get("level") == "hata"],
            uyarilar=[m for m in batch.messages if m.get("level") != "hata"],
            etkilenen=affected,
            format=FORMATS[batch.kind],
        ),
    )


@login_required
def aktarim_dosya(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    if not batch.stored_file:
        raise Http404("Arşiv dosyası yok.")
    return FileResponse(batch.stored_file.open("rb"), as_attachment=True, filename=batch.original_name)


@login_required
def sablon(request, kind):
    fmt = FORMATS.get(kind)
    if fmt is None:
        raise Http404("Bilinmeyen dosya türü.")
    excel = request.GET.get("excel") == "1"
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";" if excel else ",", lineterminator="\r\n")
    writer.writerow(fmt.column_names)
    decimal_columns = {i for i, c in enumerate(fmt.columns) if c.kind == "decimal"}
    for example in fmt.examples:
        writer.writerow(
            [v.replace(".", ",") if excel and i in decimal_columns else v for i, v in enumerate(example)]
        )
    body = ("﻿" if excel else "") + buffer.getvalue()
    response = HttpResponse(body, content_type="text/csv; charset=utf-8")
    suffix = "_excel" if excel else ""
    response["Content-Disposition"] = f'attachment; filename="{fmt.filename.removesuffix(".csv")}{suffix}.csv"'
    return response


@login_required
def menu_csv(request):
    """Görüntü işleme ekibi için: seçilen günlerin menüsü ve yemek kodları."""
    start = _parse_date(request.GET.get("baslangic"))
    end = _parse_date(request.GET.get("bitis"))
    latest = Production.objects.aggregate(last=Max("date"))["last"]
    if latest is None:
        raise Http404("Henüz yemekhane kaydı yok.")
    start = start or end or latest
    end = end or start
    if start > end:
        start, end = end, start
    productions = (
        Production.objects.select_related("dish").filter(date__range=(start, end)).order_by("date", "meal", "dish__category")
    )
    meal = request.GET.get("ogun")
    if meal in MealType.values:
        productions = productions.filter(meal=meal)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["tarih", "ogun", "yemek_kodu", "yemek_adi", "kategori"])
    for prod in productions:
        writer.writerow([prod.date.isoformat(), prod.meal, prod.dish.code, prod.dish.name, prod.dish.category])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="menu_{start:%Y%m%d}_{end:%Y%m%d}.csv"'
    return response


@login_required
def katalog_csv(request):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["yemek_kodu", "yemek_adi", "kategori", "tur", "saklanabilir"])
    for dish in Dish.objects.order_by("category", "name"):
        writer.writerow([dish.code, dish.name, dish.category, dish.food_type, "evet" if dish.storable else "hayir"])
    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="yemekler.csv"'
    return response


@login_required
def durum(request):
    flt = resolve_filter(request)
    if flt.empty:
        return _empty(request, flt)
    return render(
        request,
        "israf/durum.html",
        panel_context(request, flt, satirlar=analiz.data_status(flt.start, flt.end, flt.meal_or_none)),
    )


# --------------------------------------------------------------------- ayarlar


@staff_required
def ayarlar(request):
    profiles = list(ThresholdProfile.objects.order_by("order"))
    windows = list(ServiceWindowDefault.objects.all())
    data = request.POST if request.method == "POST" else None
    profile_forms = [(p, ThresholdProfileForm(data, instance=p, prefix=p.key)) for p in profiles]
    window_forms = [(w, ServiceWindowForm(data, instance=w, prefix=f"saat-{w.meal}")) for w in windows]
    active = next((p.key for p in profiles if p.is_active), profiles[0].key if profiles else "")
    if request.method == "POST":
        chosen = request.POST.get("etkin_profil", active)
        valid_choice = chosen in {p.key for p in profiles}
        forms_ok = all(f.is_valid() for _, f in profile_forms + window_forms)
        if valid_choice and forms_ok:
            with transaction.atomic():
                ThresholdProfile.objects.update(is_active=False)
                for _, form in profile_forms:
                    profile = form.save(commit=False)
                    profile.is_active = profile.key == chosen
                    profile.save()
                for _, form in window_forms:
                    form.save()
            messages.success(request, "Ayarlar kaydedildi.")
            return redirect("israf:ayarlar")
        if not valid_choice:
            messages.error(request, "Geçerli bir eşik profili seçin.")
        active = chosen
    return render(
        request,
        "israf/ayarlar.html",
        panel_context(request, None, profiller=profile_forms, saatler=window_forms, etkin=active),
    )


@login_required
def tanimlar(request):
    return render(
        request,
        "israf/tanimlar.html",
        panel_context(
            request,
            None,
            formatlar=list(FORMATS.values()),
            genel_kurallar=GENERAL_RULES,
            yarim_agirligi=analiz.WASTE_WEIGHT["yarim"],
        ),
    )
