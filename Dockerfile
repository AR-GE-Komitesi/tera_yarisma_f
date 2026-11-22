# Yemekhane israf paneli — üretim kapsayıcısı (waitress, DEBUG kapalı).
#   docker compose up --build
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_DEBUG=0 \
    ISRAF_INSTANCE_DIR=/data

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Veritabanı, arşiv ve gizli anahtar /data biriminde kalır; kapsayıcı silinse de kaybolmaz.
RUN useradd --create-home --uid 1000 panel \
    && mkdir -p /data \
    && chown panel:panel /data
USER panel
VOLUME ["/data"]

EXPOSE 8000
CMD ["python", "run.py", "--docker"]
