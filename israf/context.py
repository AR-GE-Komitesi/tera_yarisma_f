from urllib.parse import urlencode

FILTER_KEYS = ("baslangic", "bitis", "ogun")


def filter_querystring(request) -> str:
    params = {k: request.GET[k] for k in FILTER_KEYS if request.GET.get(k)}
    return urlencode(params)


def panel(request):
    """Gezinme bağlantılarının seçili tarih aralığını taşıması için."""
    return {"filtre_qs": filter_querystring(request)}
