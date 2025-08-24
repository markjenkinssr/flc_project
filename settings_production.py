cat > settings_production.py <<'PY'
import os
from settings import *  # import your base dev settings

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS","").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS","").split(",") if o]

import dj_database_url
DATABASES = {
    "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600, ssl_require=True)
}

STATIC_ROOT = BASE_DIR / "staticfiles"
MIDDLEWARE = ["whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
PY
