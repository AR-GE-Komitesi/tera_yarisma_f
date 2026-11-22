"""docs/VERI_FORMATI.md belgesini formatlar.py'den üretir.

Belge elle düzenlenmez; format değişirse bu komut yeniden çalıştırılır:
  python manage.py format_belgesi
"""
import csv
import io

from django.conf import settings
from django.core.management.base import BaseCommand

from israf.formatlar import FORMATS, GENERAL_RULES


def _cell(text):
    return str(text).replace("|", "\\|")


def render() -> str:
    lines = [
        "# Veri formatı — yemekhane israf analizi",
        "",
        "> Bu belge `israf/formatlar.py` dosyasından `python manage.py format_belgesi` komutuyla üretilir. "
        "Elle düzenlemeyin.",
        "",
        "Panel dört CSV dosyası alır. Görüntü işleme ekibi yalnızca `tepsiler.csv` dosyasını üretir; "
        "diğer üçü yemekhane tarafındandır.",
        "",
        "| Dosya | Kim | Ne sıklıkla | Bir satır |",
        "|---|---|---|---|",
    ]
    for f in FORMATS.values():
        lines.append(f"| `{f.filename}` | {_cell(f.source)} | {_cell(f.frequency)} | {_cell(f.grain)} |")
    lines += ["", "## Bütün dosyalar için", ""]
    lines += [f"- {rule}" for rule in GENERAL_RULES]
    lines += [
        "",
        "## Yemek kodları nasıl eşleşir",
        "",
        "1. Yemekhane yönetimi her yemeği bir kez `yemekler.csv` ile kataloğa ekler. Kod değişmez.",
        "2. Yemekhane her öğünden sonra `uretim.csv` yükler. Bu dosya o öğünün menüsüdür.",
        "3. Görüntü işleme ekibi panelden menüyü (`/veri/menu.csv`) ya da kataloğu (`/veri/yemekler.csv`) "
        "indirir ve modelin sınıflarını bu kodlarla adlandırır.",
        "4. `tepsiler.csv` yüklenirken her kod o öğünün menüsüyle karşılaştırılır. Menüde olmayan kod "
        "dosyayı reddettirir; hata satır numarasıyla gösterilir.",
        "",
    ]
    for f in FORMATS.values():
        lines += [
            f"## {f.filename} — {f.title}",
            "",
            f"- **Kim doldurur:** {f.source}",
            f"- **Ne sıklıkla:** {f.frequency}",
            f"- **Satır:** {f.grain}",
            f"- **Benzersiz anahtar:** `{' + '.join(f.key)}`",
            f"- **Yeniden yükleme:** {f.replace_rule}",
            "",
            "| Sütun | Zorunlu | Açıklama | Örnek |",
            "|---|---|---|---|",
        ]
        for c in f.columns:
            lines.append(
                f"| `{c.name}` | {'evet' if c.required else 'hayır'} | {_cell(c.description)} | `{_cell(c.example)}` |"
            )
        if f.rules:
            lines += ["", "Kurallar:", ""]
            lines += [f"- {rule}" for rule in f.rules]
        lines += ["", "Örnek:", "", "```csv", _csv_lines(f.column_names, f.examples), "```", ""]
    return "\n".join(lines)


def _csv_lines(header, rows) -> str:
    """Örnekleri gerçek CSV kurallarıyla yazar (virgül içeren alan tırnaklanır)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().rstrip("\n")


class Command(BaseCommand):
    help = "docs/VERI_FORMATI.md belgesini CSV sözleşmesinden üretir."

    def handle(self, *args, **opts):
        path = settings.BASE_DIR / "docs" / "VERI_FORMATI.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text(render(), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"{path} yazıldı."))
