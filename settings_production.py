from settings import * 
import os
DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
SECRET_KEY = os.getenv("SECRET_KEY", SECRET_KEY)  # fallback to base if not set

if "DATABASE_URL" in os.environ:
    from urllib.parse import urlparse
    u = urlparse(os.environ["DATABASE_URL"])
    DATABASES = {
        "default": {

            "ENGINE": "django.db.backends.postgresql",
            "NAME": u.path.lstrip("/"),
            "USER": u.username,
            "PASSWORD": u.password,
            "HOST": u.hostname,
            "PORT": u.port or 5432,
        }
    }

STATIC_ROOT = os.getenv("STATIC_ROOT", str(BASE_DIR / "staticfiles"))

STATICFILES_DIRS = []

STATIC_URL = "/static/"


