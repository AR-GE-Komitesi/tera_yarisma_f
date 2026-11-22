"""Üç eşik profili ve varsayılan servis saatleri.

Profil değerleri başlangıç önerisidir; yönetim Ayarlar sayfasından değiştirir.
"""
from datetime import time

from django.db import migrations

PROFILES = [
    # anahtar, ad, sıra, bitirilmeyen tabak %, kazan artığı %, toplam israf %, etkin
    ("siki", "Sıkı", 1, 30, 5, 10, False),
    ("dengeli", "Dengeli", 2, 50, 10, 20, True),
    ("esnek", "Esnek", 3, 70, 20, 30, False),
]

WINDOWS = [
    ("kahvalti", time(7, 0), time(9, 30)),
    ("ogle", time(11, 30), time(14, 0)),
    ("aksam", time(16, 30), time(19, 0)),
]


def seed(apps, schema_editor):
    ThresholdProfile = apps.get_model("israf", "ThresholdProfile")
    ServiceWindowDefault = apps.get_model("israf", "ServiceWindowDefault")
    for key, name, order, unfinished, pot, total, active in PROFILES:
        ThresholdProfile.objects.update_or_create(
            key=key,
            defaults={
                "name": name,
                "order": order,
                "unfinished_plate_rate": unfinished,
                "pot_leftover_rate": pot,
                "total_waste_rate": total,
                "is_active": active,
            },
        )
    for meal, start, end in WINDOWS:
        ServiceWindowDefault.objects.update_or_create(
            meal=meal, defaults={"service_start": start, "service_end": end}
        )


class Migration(migrations.Migration):
    dependencies = [("israf", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
