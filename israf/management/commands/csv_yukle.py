"""Komut satırından CSV yükleme (toplu yükleme ve otomasyon için).

  python manage.py csv_yukle uretim uretim_2026-11-20.csv
  python manage.py csv_yukle tepsiler gun1.csv gun2.csv
  python manage.py csv_yukle tepsiler duzeltilmis.csv --yerine-gecsin

Bir dosya reddedilirse çıkış kodu 1 olur; sonraki dosyalar yine denenir.
Verisi zaten yüklü bir öğünü içeren dosya --yerine-gecsin verilmedikçe reddedilir.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from israf.aktarim import import_csv
from israf.models import ImportBatch


class Command(BaseCommand):
    help = "CSV dosyalarını doğrulayıp panele yükler."

    def add_arguments(self, parser):
        parser.add_argument("tur", choices=ImportBatch.Kind.values, help="Dosya türü")
        parser.add_argument("dosyalar", nargs="+", help="CSV dosyaları")
        parser.add_argument(
            "--yerine-gecsin",
            action="store_true",
            help="Daha önce yüklenmiş öğünlerin verisinin yerine geç (düzeltilmiş dosyalar için)",
        )

    def handle(self, *args, **opts):
        failed = 0
        for name in opts["dosyalar"]:
            path = Path(name)
            if not path.is_file():
                self.stderr.write(self.style.ERROR(f"{path}: dosya bulunamadı."))
                failed += 1
                continue
            batch = import_csv(opts["tur"], path.read_bytes(), path.name, replace=opts["yerine_gecsin"])
            ok = batch.status == ImportBatch.Status.OK
            style = self.style.SUCCESS if ok else self.style.ERROR
            self.stdout.write(style(f"{path.name}: {batch.get_status_display()} — {batch.summary}"))
            for message in batch.messages[:20]:
                where = f"satır {message['row']}: " if message.get("row") else ""
                self.stdout.write(f"  [{message['level']}] {where}{message['text']}")
            if len(batch.messages) > 20:
                self.stdout.write(f"  … toplam {batch.error_count} hata, {batch.warning_count} uyarı")
            failed += not ok
        if failed:
            raise CommandError(f"{failed} dosya yüklenemedi.")
