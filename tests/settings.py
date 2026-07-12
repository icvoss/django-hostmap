"""Django settings for django-hostmap standalone tests.

No database behaviour is exercised beyond Django bootstrapping; tests run
against SQLite (05-verification.md section 3).
"""

SECRET_KEY = "hostmap-test-secret-key"  # noqa: S105

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    # thirdparty_app is listed BEFORE hostmap so its module-level
    # ``from django.urls import reverse`` binds before hostmap.ready()
    # (AC-HOSTMAP-002).
    "thirdparty_app",
    "hostmap",
]

MIDDLEWARE = [
    "hostmap.middleware.HostmapMiddleware",
    "django.middleware.common.CommonMiddleware",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"

ALLOWED_HOSTS = [".example.com"]

ROOT_URLCONF = "urls_www"

# --- Hostmap configuration -------------------------------------------------

HOSTMAP = {
    "www": {"subdomain": "www", "urlconf": "urls_www"},
    "api": {"subdomain": "api", "urlconf": "urls_api"},
    "tenant": {"subdomain": "*", "urlconf": "urls_tenant"},
    "apex": {"host": "example.com", "redirect_to": "www"},
}
HOSTMAP_PARENT_DOMAIN = "example.com"
HOSTMAP_DEFAULT = "www"
HOSTMAP_SCHEME = "https"
