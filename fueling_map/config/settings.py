"""Django settings for the fueling map service.

Secrets and per-environment values come from environment variables (constitution: Security).
No templates or auth apps: the service exposes JSON only, and the stations database holds
only station data.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = ["stations"]
MIDDLEWARE: list[str] = []
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# `default` holds Station (stations_locations); `cities` holds City. See stations/db_router.py.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("STATIONS_DB_PATH", BASE_DIR / "stations_locations.sqlite3"),
    },
    "cities": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("CITIES_DB_PATH", BASE_DIR / "cities.sqlite3"),
    },
}
DATABASE_ROUTERS = ["stations.db_router.CitiesRouter"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_TZ = True

# Default inputs for `manage.py build_data`; override with the command's flags.
FUEL_CSV_PATH = Path(
    os.environ.get("FUEL_CSV_PATH", BASE_DIR.parent / "fuel-prices-for-be-assessment.csv")
)
CITIES_CSV_PATH = Path(os.environ.get("CITIES_CSV_PATH", BASE_DIR.parent / "us_cities.csv"))
