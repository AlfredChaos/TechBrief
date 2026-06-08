from __future__ import annotations

from pathlib import Path

import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    APP_ENV=(str, "local"),
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, ["http://127.0.0.1:8010", "http://localhost:8010"]),
    DATABASE_CONN_MAX_AGE=(int, 60),
    CELERY_TIMEZONE=(str, "UTC"),
    COS_ENABLED=(bool, False),
    EMAIL_DELIVERY_ADAPTER=(str, "mock"),
    WECHAT_DRAFT_ADAPTER=(str, "mock"),
    LLM_ADAPTER=(str, "mock"),
    ASR_ADAPTER=(str, "mock"),
    REVIEW_AUTO_APPROVE=(bool, True),
    LOG_JSON=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="unsafe-dev-secret-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
APP_ENV = env("APP_ENV")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS")
INITIAL_ADMIN_USERNAME = env("INITIAL_ADMIN_USERNAME", default="")
INITIAL_ADMIN_EMAIL = env("INITIAL_ADMIN_EMAIL", default="")
INITIAL_ADMIN_PASSWORD = env("INITIAL_ADMIN_PASSWORD", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "taggit",
    "modelcluster",
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "django_celery_beat",
    "techbrief.apps.core.apps.CoreConfig",
    "techbrief.apps.web.apps.WebConfig",
    "techbrief.apps.admin_console.apps.AdminConsoleConfig",
    "techbrief.apps.content_pipeline.apps.ContentPipelineConfig",
    "techbrief.apps.publishers.apps.PublishersConfig",
    "techbrief.apps.integrations.apps.IntegrationsConfig",
    "techbrief.apps.observability.apps.ObservabilityConfig",
]

AUTH_USER_MODEL = "core.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "techbrief.middleware.RequestIdMiddleware",
    "techbrief.middleware.ApiExceptionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

ROOT_URLCONF = "techbrief.urls"
WSGI_APPLICATION = "techbrief.wsgi.application"
ASGI_APPLICATION = "techbrief.asgi.application"

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
            ],
        },
    }
]

DATABASES = {
    "default": dj_database_url.parse(
        env("DATABASE_URL", default="postgresql://techbrief:techbrief@127.0.0.1:5432/techbrief"),
        conn_max_age=env.int("DATABASE_CONN_MAX_AGE"),
    )
}

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6380/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": 300,
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = env("CELERY_TIMEZONE")
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

COS_ENABLED = env.bool("COS_ENABLED", default=False)
COS_CONFIG = {
    "enabled": COS_ENABLED,
    "secret_id": env("COS_SECRET_ID", default=""),
    "secret_key": env("COS_SECRET_KEY", default=""),
    "bucket": env("COS_BUCKET", default=""),
    "region": env("COS_REGION", default=""),
    "domain": env("COS_DOMAIN", default=""),
    "key_prefix": env("COS_KEY_PREFIX", default="techbrief/local"),
}

EMAIL_DELIVERY_ADAPTER = env("EMAIL_DELIVERY_ADAPTER", default="mock")
WECHAT_DRAFT_ADAPTER = env("WECHAT_DRAFT_ADAPTER", default="mock")
EMAIL_FROM_ADDRESS = env("EMAIL_FROM_ADDRESS", default="digest@example.com")
RESEND_API_KEY = env("RESEND_API_KEY", default="")
WECHAT_API_BASE_URL = env("WECHAT_API_BASE_URL", default="https://api.weixin.qq.com")
WECHAT_ACCESS_TOKEN = env("WECHAT_ACCESS_TOKEN", default="")

# LLM integration
LLM_ADAPTER = env("LLM_ADAPTER", default="mock")
LLM_API_KEY = env("LLM_API_KEY", default="")
LLM_API_BASE_URL = env("LLM_API_BASE_URL", default="https://api.openai.com/v1")
LLM_MODEL = env("LLM_MODEL", default="gpt-4o")

# ASR integration
ASR_ADAPTER = env("ASR_ADAPTER", default="mock")
ASR_API_KEY = env("ASR_API_KEY", default="")
ASR_API_BASE_URL = env("ASR_API_BASE_URL", default="https://api.openai.com/v1")

# Pipeline configuration
REVIEW_AUTO_APPROVE = env.bool("REVIEW_AUTO_APPROVE", default=True)

PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://127.0.0.1:8010")
ADMIN_BASE_URL = env("ADMIN_BASE_URL", default="http://127.0.0.1:8010")
GA4_MEASUREMENT_ID = env("GA4_MEASUREMENT_ID", default="")
WAGTAIL_SITE_NAME = "TechBrief"
WAGTAILADMIN_BASE_URL = ADMIN_BASE_URL

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOG_JSON = env.bool("LOG_JSON", default=False)
FORMATTER_CLASS = "techbrief.logging_utils.JsonFormatter" if LOG_JSON else "techbrief.logging_utils.TextFormatter"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_context": {
            "()": "techbrief.logging_utils.RequestContextFilter",
        }
    },
    "formatters": {
        "structured": {
            "()": FORMATTER_CLASS,
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_context"],
            "formatter": "structured",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "techbrief": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
