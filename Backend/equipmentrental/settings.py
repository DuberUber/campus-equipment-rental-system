"""
Django settings for the Campus Equipment Rental System API.

Environment-specific values (secret key, hosts, database credentials, rate limits)
are read from the environment or a Backend/.env file via python-decouple; nothing
secret is hard-coded here. See .env.example.

https://docs.djangoproject.com/en/5.2/ref/settings/
"""

from pathlib import Path

import dj_database_url
from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Security
# https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Enable once the site is served over HTTPS (behind a proxy that sets X-Forwarded-Proto).
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'corsheaders',
    'accounts',
    'rentals',
    'drf_spectacular',
    'drf_spectacular_sidecar',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'equipmentrental.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Origins allowed to call the API from a browser (the React dev server by default).
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://127.0.0.1:3000', cast=Csv()
)

WSGI_APPLICATION = 'equipmentrental.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# SQLite (Backend/db.sqlite3) is the default and the documented setup. DATABASE_URL can point the project at
# another database supported by dj-database-url, provided its driver is installed.

DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=config('DATABASE_CONN_MAX_AGE', default=0, cast=int),
    ),
}
# Concurrent bookings queue for SQLite's write lock (see rentals.services.lock_equipment) instead of failing.
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    DATABASES['default'].setdefault('OPTIONS', {})['timeout'] = 20


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Reservation times are stored in UTC; bare dates in query strings (?from=2026-10-01) are read in this zone.
TIME_ZONE = config('TIME_ZONE', default='UTC')

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

AUTH_USER_MODEL = 'accounts.User'

# Rental rules: how many reserved or checked-out items a student may hold at once.
MAX_ACTIVE_RESERVATIONS = config('MAX_ACTIVE_RESERVATIONS', default=3, cast=int)

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    # The React client authenticates with a token; the session lets admin users use the browsable API.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'equipmentrental.exceptions.exception_handler',
    # Every list endpoint is paginated (PageNumberPagination) so response size stays bounded as data grows.
    'DEFAULT_PAGINATION_CLASS': 'equipmentrental.pagination.StandardPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    # Throttle state lives in the default cache; use a shared cache (e.g. Redis) when running several workers.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    # Per-client request budgets; the 'login' and 'register' scopes guard the unauthenticated auth endpoints.
    'DEFAULT_THROTTLE_RATES': {
        'anon': config('THROTTLE_RATE_ANON', default='60/minute'),
        'user': config('THROTTLE_RATE_USER', default='300/minute'),
        'login': config('THROTTLE_RATE_LOGIN', default='5/minute'),
        'register': config('THROTTLE_RATE_REGISTER', default='10/hour'),
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Campus Equipment Rental System API',
    'DESCRIPTION': 'Lab and sports equipment, availability checks, reservations and overdue returns.',
    'VERSION': '1.0.0',
    'SWAGGER_UI_DIST': 'SIDECAR',  # serve Swagger UI / ReDoc assets locally instead of from a CDN
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
    # Equipment condition and return condition share one choice set.
    'ENUM_NAME_OVERRIDES': {
        'ConditionEnum': 'rentals.models.Condition',
        'ReservationStatusEnum': 'rentals.models.Reservation.Status',
    },
}
