from django.contrib import admin

from .models import (
    Dish,
    ImportBatch,
    MealSession,
    PlateSummary,
    Production,
    ServiceWindowDefault,
    ThresholdProfile,
    TrayCount,
)


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "food_type", "storable")
    list_filter = ("category", "storable", "food_type")
    search_fields = ("name", "code", "food_type")


@admin.register(Production)
class ProductionAdmin(admin.ModelAdmin):
    list_display = ("date", "meal", "dish", "produced", "leftover", "ran_out_at")
    list_filter = ("meal", "dish__category")
    date_hierarchy = "date"
    search_fields = ("dish__name", "dish__code")
    autocomplete_fields = ("dish",)


@admin.register(PlateSummary)
class PlateSummaryAdmin(admin.ModelAdmin):
    list_display = ("date", "meal", "dish", "finished", "half", "untouched", "unknown")
    list_filter = ("meal", "dish__category")
    date_hierarchy = "date"
    search_fields = ("dish__name", "dish__code")

    def has_add_permission(self, request):
        return False  # yalnızca tepsi CSV'sinden türetilir


@admin.register(TrayCount)
class TrayCountAdmin(admin.ModelAdmin):
    list_display = ("date", "meal", "trays")
    date_hierarchy = "date"

    def has_add_permission(self, request):
        return False


@admin.register(MealSession)
class MealSessionAdmin(admin.ModelAdmin):
    list_display = ("date", "meal", "service_start", "service_end", "note")
    date_hierarchy = "date"


@admin.register(ServiceWindowDefault)
class ServiceWindowDefaultAdmin(admin.ModelAdmin):
    list_display = ("meal", "service_start", "service_end")


@admin.register(ThresholdProfile)
class ThresholdProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "unfinished_plate_rate", "pot_leftover_rate", "total_waste_rate", "is_active")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("uploaded_at", "kind", "original_name", "status", "row_count", "error_count", "warning_count")
    list_filter = ("kind", "status")
    readonly_fields = [f.name for f in ImportBatch._meta.fields]

    def has_add_permission(self, request):
        return False
