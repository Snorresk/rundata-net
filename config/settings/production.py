import logging

from .base import *  # noqa
from .base import env

# GENERAL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
SECRET_KEY = env("DJANGO_SECRET_KEY")
# Canonical domain for 301 redirects (www and Azure hostname → apex domain)
CANONICAL_DOMAIN = env("CANONICAL_DOMAIN", default="rundata.info")
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
default_allowed_hosts = [f"www.{CANONICAL_DOMAIN}", CANONICAL_DOMAIN]
if "DJANGO_ALLOWED_HOSTS" in env:
    default_allowed_hosts += env.list("DJANGO_ALLOWED_HOSTS")
if "WEBSITE_HOSTNAME" in env:
    # Configure the domain name using the environment variable
    # that Azure automatically creates for us.
    ALLOWED_HOSTS = default_allowed_hosts + [env("WEBSITE_HOSTNAME")]
    CSRF_TRUSTED_ORIGINS = ["https://" + env("WEBSITE_HOSTNAME")]

# DATABASES
# ------------------------------------------------------------------------------
if "AZURE_POSTGRESQL_CONNECTIONSTRING" in env:
    # Configure Postgres database based on connection string of the libpq Keyword/Value form
    # https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-CONNSTRING
    conn_str = env("AZURE_POSTGRESQL_CONNECTIONSTRING")
    conn_str_params = {pair.split("=")[0]: pair.split("=")[1] for pair in conn_str.split(" ")}
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": conn_str_params["dbname"],
        "HOST": conn_str_params["host"],
        "USER": conn_str_params["user"],
        "PASSWORD": conn_str_params["password"],
        # Azure Database for PostgreSQL requires TLS. Honor sslmode from the
        # connection string if provided, otherwise default to "require".
        "OPTIONS": {"sslmode": conn_str_params.get("sslmode", "require")},
    }
else:
    DATABASES["default"] = env.db("DATABASE_URL")  # noqa F405
    DATABASES["default"]["ATOMIC_REQUESTS"] = True  # noqa F405
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)  # noqa F405

# CACHES
# ------------------------------------------------------------------------------
CACHES = {
    # 'default': {
    #     'BACKEND': 'django_redis.cache.RedisCache',
    #     'LOCATION': env('REDIS_URL'),
    #     'OPTIONS': {
    #         'CLIENT_CLASS': 'django_redis.client.DefaultClient',
    #         # Mimicing memcache behavior.
    #         # http://niwinz.github.io/django-redis/latest/#_memcached_exceptions_behavior
    #         'IGNORE_EXCEPTIONS': True,
    #     }
    # }
    # Use local-memory caching in production. Although it is not intendent for it, but the app is small
    # and cache is not really used.
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-rundata-info",
    }
}

# SECURITY
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-proxy-ssl-header
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-ssl-redirect
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-secure
SESSION_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#session-cookie-httponly
SESSION_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-secure
CSRF_COOKIE_SECURE = True
# https://docs.djangoproject.com/en/dev/ref/settings/#csrf-cookie-httponly
CSRF_COOKIE_HTTPONLY = True
# https://docs.djangoproject.com/en/dev/topics/security/#ssl-https
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-seconds
# TODO: set this to 60 seconds first and then to 518400 once you prove the former works
SECURE_HSTS_SECONDS = 60
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-include-subdomains
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-hsts-preload
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
# https://docs.djangoproject.com/en/dev/ref/middleware/#x-content-type-options-nosniff
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True)
# https://docs.djangoproject.com/en/dev/ref/settings/#secure-browser-xss-filter
SECURE_BROWSER_XSS_FILTER = True
# https://docs.djangoproject.com/en/dev/ref/settings/#x-frame-options
X_FRAME_OPTIONS = "DENY"

# STORAGES
# ------------------------------------------------------------------------------
# https://django-storages.readthedocs.io/en/latest/#installation
INSTALLED_APPS += [
    #'storages'
]  # noqa F405
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_ACCESS_KEY_ID = env('DJANGO_AWS_ACCESS_KEY_ID')
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_SECRET_ACCESS_KEY = env('DJANGO_AWS_SECRET_ACCESS_KEY')
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_STORAGE_BUCKET_NAME = env('DJANGO_AWS_STORAGE_BUCKET_NAME')
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_AUTO_CREATE_BUCKET = True
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
AWS_QUERYSTRING_AUTH = False
# DO NOT change these unless you know what you're doing.
_AWS_EXPIRY = 60 * 60 * 24 * 7
# https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html#settings
# AWS_S3_OBJECT_PARAMETERS = {
#    'CacheControl': f'max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate',
# }

# STATIC (see also storages)
# --------------------------

# MEDIA
# ------------------------------------------------------------------------------
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
# MEDIA_URL = f'https://s3.amazonaws.com/{AWS_STORAGE_BUCKET_NAME}/'

# TEMPLATES
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#templates
TEMPLATES[0]["OPTIONS"]["loaders"] = [  # noqa F405
    (
        "django.template.loaders.cached.Loader",
        [
            "django.template.loaders.filesystem.Loader",
            "django.template.loaders.app_directories.Loader",
        ],
    ),
]

# EMAIL
# ------------------------------------------------------------------------------
# https://docs.djangoproject.com/en/dev/ref/settings/#default-from-email
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="Rundata-net <noreply@rundata.info>")
# https://docs.djangoproject.com/en/dev/ref/settings/#server-email
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
# https://docs.djangoproject.com/en/dev/ref/settings/#email-subject-prefix
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="[Rundata-net]")

# ADMIN
# ------------------------------------------------------------------------------
# Django Admin URL regex.
ADMIN_URL = env("DJANGO_ADMIN_URL")

# Anymail (Mailgun)
# ------------------------------------------------------------------------------
# https://anymail.readthedocs.io/en/stable/installation/#installing-anymail
# INSTALLED_APPS += ['anymail']  # noqa F405
# EMAIL_BACKEND = 'anymail.backends.mailgun.EmailBackend'
# # https://anymail.readthedocs.io/en/stable/installation/#anymail-settings-reference
# ANYMAIL = {
#     'MAILGUN_API_KEY': env('MAILGUN_API_KEY'),
#     'MAILGUN_SENDER_DOMAIN': env('MAILGUN_DOMAIN')
# }

# Gunicorn
# ------------------------------------------------------------------------------
# This adds `run_gunicorn` command to `./manage.py`.
INSTALLED_APPS += ["gunicorn"]  # noqa F405

# InternalHealthCheckMiddleware
# ------------------------------------------------------------------------------
# Short-circuit Azure App Service internal probes (link-local 169.254.x.x and
# similar) with a 200 OK before any other middleware runs. Azure rotates these
# IPs periodically, so maintaining them in ALLOWED_HOSTS is not viable.
MIDDLEWARE.insert(0, "rundatanet.runes.middleware.InternalHealthCheckMiddleware")  # noqa F405

# CanonicalDomainMiddleware
# ------------------------------------------------------------------------------
# Redirect all non-canonical hostnames to the canonical domain. Placed here so
# it only runs in production where CANONICAL_DOMAIN is configured; local
# development is unaffected.
try:
    index = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
    MIDDLEWARE.insert(index, "rundatanet.runes.middleware.CanonicalDomainMiddleware")
except ValueError:
    MIDDLEWARE.insert(1, "rundatanet.runes.middleware.CanonicalDomainMiddleware")  # noqa F405

# WhiteNoise
# ------------------------------------------------------------------------------
# http://whitenoise.evans.io/en/latest/django.html#enable-whitenoise
try:
    # Place whitenoise after "rundatanet.runes.middleware.CanonicalDomainMiddleware" so redirects happen before static files are served.
    index = MIDDLEWARE.index("rundatanet.runes.middleware.CanonicalDomainMiddleware")
    MIDDLEWARE.insert(index + 1, "whitenoise.middleware.WhiteNoiseMiddleware")
except ValueError:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# LOGGING
# ------------------------------------------------------------------------------
# See: https://docs.djangoproject.com/en/dev/ref/settings/#logging
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins bon every HTTP 500 error when DEBUG=False.
# See https://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"require_debug_false": {"()": "django.utils.log.RequireDebugFalse"}},
    "formatters": {
        "verbose": {"format": "%(levelname)s %(asctime)s %(module)s " "%(process)d %(thread)d %(message)s"},
    },
    "handlers": {
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.request": {"handlers": ["console", "mail_admins"], "level": "ERROR", "propagate": True},
        "django.security.DisallowedHost": {
            "level": "ERROR",
            "handlers": ["console", "mail_admins"],
            "propagate": True,
        },
        "rundatanet": {
            "level": "ERROR",
            "handlers": ["console"],
            "propagate": True,
        },
    },
}
# Your stuff...
# ------------------------------------------------------------------------------
USE_GA = env.bool("USE_GA", default=True)
