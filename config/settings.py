"""Yemekhane israf analizi paneli ayarları.

Ortam değişkenleri:
  DJANGO_SECRET_KEY     Gizli anahtar. Verilmezse instance/secret_key.txt üretilir.
  DJANGO_DEBUG          "1" geliştirme (varsayılan), "0" üretim.
  DJANGO_ALLOWED_HOSTS  Virgülle ayrılmış alan adları.
  DJANGO_HTTPS          "1" ise çerezler yalnızca HTTPS üzerinden gönderilir, HTTP yönlendirilir.
  DJANGO_HSTS_SECONDS   HTTPS kalıcıysa HSTS süresi (saniye). Varsayılan 0 (kapalı).
  ISRAF_INSTANCE_DIR    Veritabanı, arşivlenen CSV'ler ve gizli anahtarın klasörü.
"""
import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = Path(os.environ.get("ISRAF_INSTANCE_DIR", BASE_DIR / "instance"))
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)


def _secret_key() -> str:
    key = os.environ.get("DJANGO_SECRET_KEY")
    if key:
        return key
    path = INSTANCE_DIR / "secret_key.txt"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(50), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


SECRET_KEY = _secret_key()
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "israf",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "israf.context.panel",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": INSTANCE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = INSTANCE_DIR / "static"
# Üretimde (DEBUG=0) statik dosyaları whitenoise sunar; önce `collectstatic` çalıştırılır.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Yüklenen CSV'lerin arşivi. Herkese açık sunulmaz; yalnızca giriş yapmış
# kullanıcıya görünüm üzerinden indirilir.
MEDIA_ROOT = INSTANCE_DIR / "aktarimlar"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TEST_RUNNER = "config.test_runner.TempMediaRunner"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "israf:genel"
LOGOUT_REDIRECT_URL = "login"

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
ISRAF_MAX_UPLOAD_MB = 100

_HTTPS = os.environ.get("DJANGO_HTTPS", "0") == "1"
SESSION_COOKIE_SECURE = _HTTPS
CSRF_COOKIE_SECURE = _HTTPS
SECURE_SSL_REDIRECT = _HTTPS
# HSTS geri alınması zor bir taahhüttür; HTTPS kalıcı olarak kurulunca açılır.
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"israf": {"handlers": ["console"], "level": "INFO"}},
}
