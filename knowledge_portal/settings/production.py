from .base import *

DEBUG = bool(data.get("debug", False))
SECRET_KEY = data.get("secret_key", "django-insecure-xyzmc*)97o3=r81+s$9*1y2!he73!*_clk$1w-0vg6wl2c-re7")  # fall back to base if missing
ALLOWED_HOSTS = data.get("allowed_hosts", [])

# Allow up to 1GB request body
DATA_UPLOAD_MAX_MEMORY_SIZE = None  # or None for “no limit”

# How much of a single file can be kept in memory before using a temp file.
# This does NOT limit total upload size, it just affects memory vs disk.
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB is usually fine

WAGTAILIMAGES_MAX_UPLOAD_SIZE = 1024 * 1024 * 1024  # 1 GB
# keep the default pixel limit unless you know you need more:
WAGTAILIMAGES_MAX_IMAGE_PIXELS = 128000000  # 128 megapixels (default)

# ManifestStaticFilesStorage is recommended in production, to prevent
# outdated JavaScript / CSS assets being served from cache
# (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/#manifeststaticfilesstorage
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

try:
    from .local import *
except ImportError:
    pass

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "django_errors.log",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": True,
        },
        "wagtail": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}

