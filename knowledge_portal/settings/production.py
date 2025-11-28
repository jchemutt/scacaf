from .base import *

DEBUG = bool(data.get("debug", False))
SECRET_KEY = data.get("secret_key", "django-insecure-xyzmc*)97o3=r81+s$9*1y2!he73!*_clk$1w-0vg6wl2c-re7")  # fall back to base if missing
ALLOWED_HOSTS = data.get("allowed_hosts", [])

# ManifestStaticFilesStorage is recommended in production, to prevent
# outdated JavaScript / CSS assets being served from cache
# (e.g. after a Wagtail upgrade).
# See https://docs.djangoproject.com/en/5.2/ref/contrib/staticfiles/#manifeststaticfilesstorage
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

try:
    from .local import *
except ImportError:
    pass
