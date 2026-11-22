from django import forms
from django.conf import settings

from .analiz import GROUPINGS, METRICS
from .models import Category, ImportBatch, MealType, ServiceWindowDefault, ThresholdProfile


def _date_input():
    # <input type="date"> yalnızca ISO biçimini kabul eder; Türkçe yerel biçim boş görünür.
    return forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


class FilterForm(forms.Form):
    baslangic = forms.DateField(label="Başlangıç", required=False, widget=_date_input())
    bitis = forms.DateField(label="Bitiş", required=False, widget=_date_input())
    ogun = forms.ChoiceField(
        label="Öğün", required=False, choices=[("", "Tüm öğünler"), *MealType.choices]
    )


class RankingForm(forms.Form):
    grup = forms.ChoiceField(label="Liste", choices=list(GROUPINGS.items()), required=False)
    kategori = forms.ChoiceField(
        label="Kategori", required=False, choices=[("", "Tüm kategoriler"), *Category.choices]
    )
    metrik = forms.ChoiceField(
        label="Sıralama ölçütü", required=False, choices=[(m.key, m.label) for m in METRICS.values()]
    )
    min_cikis = forms.IntegerField(label="En az çıkış", required=False, min_value=1, max_value=1000)


class UploadForm(forms.Form):
    tur = forms.ChoiceField(label="Dosya türü", choices=ImportBatch.Kind.choices)
    dosya = forms.FileField(label="CSV dosyası")
    yerine_gecsin = forms.BooleanField(label="Önceki verinin yerine geçsin", required=False)

    def clean_dosya(self):
        upload = self.cleaned_data["dosya"]
        limit = settings.ISRAF_MAX_UPLOAD_MB * 1024 * 1024
        if upload.size > limit:
            raise forms.ValidationError(
                f"Dosya {settings.ISRAF_MAX_UPLOAD_MB} MB sınırını aşıyor. Uzun dönemleri tarih aralıklarına "
                "bölerek yükleyin; bir öğünü iki dosyaya bölmeyin."
            )
        if not upload.name.lower().endswith((".csv", ".txt")):
            raise forms.ValidationError("Yalnızca .csv uzantılı dosya yüklenebilir.")
        return upload


class ThresholdProfileForm(forms.ModelForm):
    class Meta:
        model = ThresholdProfile
        fields = ["unfinished_plate_rate", "pot_leftover_rate", "total_waste_rate"]
        labels = {
            "unfinished_plate_rate": "Bitirilmeyen tabak",
            "pot_leftover_rate": "Kazan artığı",
            "total_waste_rate": "Toplam israf",
        }
        widgets = {
            name: forms.NumberInput(attrs={"step": "0.5", "min": "0", "max": "100"})
            for name in ["unfinished_plate_rate", "pot_leftover_rate", "total_waste_rate"]
        }


class ServiceWindowForm(forms.ModelForm):
    class Meta:
        model = ServiceWindowDefault
        fields = ["service_start", "service_end"]
        labels = {"service_start": "Açılış", "service_end": "Kapanış"}
        widgets = {
            "service_start": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "service_end": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("service_start"), data.get("service_end")
        if start and end and end <= start:
            raise forms.ValidationError("Kapanış saati açılıştan sonra olmalı.")
        return data
