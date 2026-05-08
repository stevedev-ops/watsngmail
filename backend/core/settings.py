import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'drf_spectacular',
    'messaging',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

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

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Django Channels — InMemoryChannelLayer (no Redis needed locally)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS — allow dynamic origins from .env
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',')
CORS_ALLOW_CREDENTIALS = True

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['messaging.permissions.HasAPIKey'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Unified Messaging Hub API',
    'DESCRIPTION': (
        'A microservice for sending and receiving messages via WhatsApp (Twilio) and Gmail.\n\n'
        '## Authentication\n'
        'All endpoints (except webhooks and Gmail OAuth) require an `X-API-KEY` header.\n\n'
        '```\nX-API-KEY: your_secret_api_key_here\n```'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_PATCH': True,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'ApiKeyAuth': []}],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'ApiKeyAuth': {
                'type': 'apiKey',
                'in': 'header',
                'name': 'X-API-KEY',
                'description': 'Enter your secret API key.'
            }
        }
    }
}

# ─── Twilio ───────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

# ─── WhatsApp Cloud API (Meta direct) ─────────────────────
WA_PHONE_NUMBER_ID = os.getenv('WA_PHONE_NUMBER_ID', '')
WA_ACCESS_TOKEN    = os.getenv('WA_ACCESS_TOKEN', '')
WA_VERIFY_TOKEN    = os.getenv('WA_VERIFY_TOKEN', 'my_wa_verify_token')

# ─── Gmail OAuth ──────────────────────────────────────────
GMAIL_CLIENT_ID = os.getenv('GMAIL_CLIENT_ID', '')
GMAIL_CLIENT_SECRET = os.getenv('GMAIL_CLIENT_SECRET', '')
GMAIL_REDIRECT_URI = os.getenv('GMAIL_REDIRECT_URI', 'http://localhost:8000/api/gmail/callback/')
GMAIL_ACCOUNT = os.getenv('GMAIL_ACCOUNT', 'hasbuinvestments@gmail.com')
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', '')
PUBSUB_TOPIC = os.getenv('PUBSUB_TOPIC', '')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8000')

# API Key for Microservice authentication
API_KEY = os.getenv('API_KEY', 'default-key-change-this')

# Store OAuth token in project root
GMAIL_TOKEN_FILE = BASE_DIR / 'gmail_token.json'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
