from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "Yemekhane İsraf Analizi — Yönetim"
admin.site.site_title = "Yemekhane İsraf Analizi"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("giris/", auth_views.LoginView.as_view(), name="login"),
    path("cikis/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("israf.urls")),
]
