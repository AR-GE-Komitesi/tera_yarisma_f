from django import template
from django.utils.html import format_html

from ..analiz import METRICS, exceeds
from ..context import FILTER_KEYS

register = template.Library()

DASH = "—"


def _tr_number(value: float, decimals: int) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")


@register.filter
def yuzde(value, decimals=1):
    """0,234 → %23,4 (Türkçe yazımda yüzde işareti başta)."""
    if value is None or value == "":
        return DASH
    return f"%{_tr_number(float(value) * 100, int(decimals))}"


@register.filter
def yuzde_sayi(value, decimals=1):
    """Grafik ve CSV için yalnızca sayı: 0,234 → 23.4"""
    if value is None:
        return ""
    return round(float(value) * 100, int(decimals))


@register.filter
def porsiyon(value):
    if value is None or value == "":
        return DASH
    number = float(value)
    if abs(number - round(number)) < 0.05:
        return _tr_number(round(number), 0)
    return _tr_number(number, 1)


@register.filter
def metrik(measures, key):
    return measures.metric(key)


@register.filter
def metrik_metin(measures, key):
    value = measures.metric(key)
    return yuzde(value) if METRICS[key].is_rate else porsiyon(value)


@register.filter
def cift_alim_payi(pair, side):
    return pair.share(side)


@register.filter
def cift_uretim_payi(pair, side):
    return pair.production_share(side)


@register.filter
def esik_degeri(profile, metric):
    return profile.limit_for(metric) if profile else None


@register.simple_tag(takes_context=True)
def diger_parametreler(context):
    """Filtre dışındaki sorgu parametreleri (ör. sıralama türü): gizli alan ve bağlantılar için."""
    request = context["request"]
    return [(k, v) for k, v in request.GET.items() if k not in FILTER_KEYS and v]


@register.simple_tag(takes_context=True)
def diger_qs(context):
    request = context["request"]
    params = request.GET.copy()
    for key in FILTER_KEYS:
        params.pop(key, None)
    encoded = params.urlencode()
    return f"&{encoded}" if encoded else ""


@register.simple_tag(takes_context=True)
def esik(context, value, metric):
    """Etkin eşik profili aşıldıysa işaret basar. Renk tek başına anlam taşımaz: ikon + açıklama."""
    profile = context.get("esik_profili")
    if profile is None or not exceeds(profile, metric, value):
        return ""
    limit = profile.limit_for(metric)
    label = f"{profile.name} eşiği ({yuzde(limit)}) aşıldı"
    return format_html('<span class="esik" title="{}" aria-label="{}">▲</span>', label, label)


@register.inclusion_tag("israf/_durum_cubugu.html")
def durum_cubugu(measures):
    plates = measures.plates
    if not plates:
        return {"bos": True}
    parts = [
        ("bitti", "Tamamı yendi", measures.finished),
        ("yarim", "Yarısı yendi", measures.half),
        ("dokunulmadi", "Dokunulmadı", measures.untouched),
    ]
    return {
        "bos": False,
        "parcalar": [
            {"sinif": key, "ad": name, "sayi": count, "oran": count / plates} for key, name, count in parts if count
        ],
    }


@register.simple_tag(takes_context=True)
def qs(context, **changes):
    """Geçerli sorgu dizesini, verilen anahtarları değiştirerek yeniden kurar."""
    request = context["request"]
    params = request.GET.copy()
    for key, value in changes.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else "?"
