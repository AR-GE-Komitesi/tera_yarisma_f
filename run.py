"""Paneli tek komutla çalıştırır.

    python run.py                  # kurar (gerekirse), açar, tarayıcıyı başlatır
    python run.py --ornek-veri     # veritabanı boşsa ornek_veri/ klasöründeki yapay veriyi yükler
    python run.py --port 8080      # başka port
    python run.py --tarayici-yok   # tarayıcıyı açma

Sırasıyla:
  1. .venv yoksa oluşturur; requirements.txt değiştiyse kütüphaneleri kurar.
  2. Veritabanını hazırlar (migrate). Hiç yönetici yoksa oluşturmanızı ister.
  3. Paneli başlatır ve tarayıcıda açar. Durdurmak için Ctrl+C.

Docker içinde `python run.py --docker` olarak çalışır: sanal ortam kurmaz, üretim
sunucusu (waitress) ile 0.0.0.0 üzerinde açar, tarayıcı açmaz.

Bu dosya yalnızca Python'un standart kütüphanesini kullanır; Django kurulmadan önce de çalışır.
"""
import argparse
import hashlib
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
STAMP = VENV / ".kurulu-gereksinimler"
MIN_PYTHON = (3, 10)
SAMPLE_FILES = (("yemekler", "yemekler.csv"), ("ogunler", "ogunler.csv"), ("uretim", "uretim.csv"),
                ("tepsiler", "tepsiler.csv"))


def say(text):
    print(f"[panel] {text}", flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def inside_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


# --------------------------------------------------------------- 1. kurulum


def ensure_venv():
    if sys.version_info < MIN_PYTHON:
        sys.exit(f"Python {'.'.join(map(str, MIN_PYTHON))} ya da üstü gerekir; bu Python {sys.version.split()[0]}.")
    python = venv_python()
    if not python.exists():
        say("Sanal ortam (.venv) oluşturuluyor…")
        venv.EnvBuilder(with_pip=True).create(VENV)
    wanted = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    installed = STAMP.read_text(encoding="utf-8").strip() if STAMP.exists() else ""
    if wanted != installed:
        say("Kütüphaneler kuruluyor (ilk seferde birkaç dakika sürebilir)…")
        result = subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-q",
                                 "-r", str(REQUIREMENTS)], cwd=ROOT)
        if result.returncode != 0:
            sys.exit("Kütüphaneler kurulamadı. İnternet bağlantısını kontrol edip tekrar deneyin.")
        STAMP.write_text(wanted, encoding="utf-8")
    return python


# ------------------------------------------------------- 2. veritabanı hazırlığı


def prepare(args):
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    from django.core.management import call_command

    say("Veritabanı hazırlanıyor…")
    call_command("migrate", interactive=False, verbosity=0)
    ensure_admin()
    if args.ornek_veri:
        load_sample_data()
    if args.docker:
        call_command("collectstatic", interactive=False, verbosity=0)


def ensure_admin():
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    users = get_user_model().objects
    if users.filter(is_superuser=True).exists():
        return
    name = os.environ.get("DJANGO_SUPERUSER_USERNAME")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
    if name and password:
        users.create_superuser(name, email=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""), password=password)
        say(f"Yönetici hesabı oluşturuldu: {name}")
    elif sys.stdin.isatty():
        say("Henüz yönetici hesabı yok. Panele giriş için bir hesap oluşturun:")
        call_command("createsuperuser")
    else:
        say("UYARI: yönetici hesabı yok. Oluşturmak için: python manage.py createsuperuser")


def load_sample_data():
    from israf.aktarim import import_csv
    from israf.models import ImportBatch, Production

    if Production.objects.exists():
        say("Veritabanında zaten veri var; örnek veri yüklenmedi.")
        return
    for kind, name in SAMPLE_FILES:
        path = ROOT / "ornek_veri" / name
        batch = import_csv(kind, path.read_bytes(), name)
        say(f"Örnek veri {name}: {batch.get_status_display()} — {batch.summary}")
        if batch.status != ImportBatch.Status.OK:
            sys.exit("Örnek veri yüklenemedi.")


# ------------------------------------------------------------- 3. başlatma


def free_port(host, first):
    for port in range(first, first + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex((host, port)) != 0:
                return port
    sys.exit(f"{first}–{first + 19} arasında boş port bulunamadı. --port ile başka bir port verin.")


def wait_until_ready(url, process, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except urllib.error.HTTPError:
            return True  # sunucu cevap veriyor
        except OSError:
            time.sleep(0.5)
    return False


def serve_local(args):
    host = "127.0.0.1"
    port = free_port(host, args.port)
    if port != args.port:
        say(f"{args.port} portu dolu; {port} kullanılıyor.")
    url = f"http://{host}:{port}/"
    process = subprocess.Popen([sys.executable, "manage.py", "runserver", f"{host}:{port}"], cwd=ROOT)
    try:
        if wait_until_ready(url + "giris/", process):
            say(f"Panel açık: {url}  (durdurmak için Ctrl+C)")
            if not args.tarayici_yok:
                webbrowser.open(url)
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        say("Panel durduruldu.")
        return 0


def serve_docker(args):
    from waitress import serve

    from config.wsgi import application

    say(f"Panel açık: http://localhost:{args.port}/  (kapsayıcı içinde 0.0.0.0:{args.port})")
    serve(application, host="0.0.0.0", port=args.port, threads=8)


# ------------------------------------------------------------------- giriş


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Yemekhane israf panelini kurar ve çalıştırır.")
    parser.add_argument("--port", type=int, default=8000, help="Port (varsayılan 8000)")
    parser.add_argument("--tarayici-yok", action="store_true", help="Tarayıcıyı otomatik açma")
    parser.add_argument(
        "--ornek-veri",
        action="store_true",
        default=os.environ.get("ISRAF_ORNEK_VERI") == "1",
        help="Veritabanı boşsa yapay örnek veriyi yükle (ya da ortamda ISRAF_ORNEK_VERI=1)",
    )
    parser.add_argument("--docker", action="store_true", help="Docker kapsayıcısı içinde çalış (waitress)")
    return parser.parse_args(argv)


def main(argv=None):
    raw = sys.argv[1:] if argv is None else argv
    args = parse_args(raw)
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    if not args.docker and not inside_venv():
        python = ensure_venv()
        try:
            return subprocess.run([str(python), str(Path(__file__).resolve()), *raw], cwd=ROOT).returncode
        except KeyboardInterrupt:
            return 0
    try:
        prepare(args)
        return serve_docker(args) if args.docker else serve_local(args)
    except KeyboardInterrupt:
        say("Durduruldu.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
