from django.urls import path

from . import views

app_name = "israf"

urlpatterns = [
    path("", views.genel, name="genel"),
    path("gun/", views.gun, name="gun"),
    path("siralama/", views.siralama, name="siralama"),
    path("siralama.csv", views.siralama_csv, name="siralama_csv"),
    path("tercih/", views.tercih, name="tercih"),
    path("yemek/<str:code>/", views.yemek, name="yemek"),
    path("veri/", views.veri, name="veri"),
    path("veri/durum/", views.durum, name="durum"),
    path("veri/aktarim/<int:pk>/", views.aktarim, name="aktarim"),
    path("veri/aktarim/<int:pk>/dosya/", views.aktarim_dosya, name="aktarim_dosya"),
    path("veri/sablon/<str:kind>.csv", views.sablon, name="sablon"),
    path("veri/menu.csv", views.menu_csv, name="menu_csv"),
    path("veri/yemekler.csv", views.katalog_csv, name="katalog_csv"),
    path("ayarlar/", views.ayarlar, name="ayarlar"),
    path("tanimlar/", views.tanimlar, name="tanimlar"),
]
