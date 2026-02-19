import os
from pathlib import Path
from decouple import config
from datetime import timedelta
import cloudinary

# Загружаем переменные Cloudinary с помощью config (с дефолтами для локальной разработки/CI)
CLOUDINARY_CLOUD_NAME = config('CLOUDINARY_CLOUD_NAME', default='demo')
CLOUDINARY_API_KEY = config('CLOUDINARY_API_KEY', default='demo')
CLOUDINARY_API_SECRET = config('CLOUDINARY_API_SECRET', default='demo')

# Настраиваем Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True  # Использовать HTTPS
)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
MEDIA_URL = '/media/'

BASE_DIR = Path(__file__).resolve().parent.parent

# Безопасный секрет в проде берётся из переменной окружения,
# а для локального запуска в Docker/CI есть дефолтное значение.
SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-me')
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'accounts',
    'cloudinary',
    'cloudinary_storage',
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

ROOT_URLCONF = 'config.urls'
AUTH_USER_MODEL = 'accounts.User'

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

WSGI_APPLICATION = 'config.wsgi.application'

# Если переменные БД не заданы, используем SQLite для локального запуска в Docker/CI.
DB_NAME = config('DB_NAME', default=None)
if DB_NAME:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME,
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='postgres'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Оставляем для админки
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),  # Увеличиваем до 60 минут
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'user-management-api', '*']

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8080",  # Для фронтенда, если используете
]

ALLOWED_HOSTS = ["*"]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Добавляем эту строку

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Настройки email
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'kata1oo5oo87@gmail.com'  # Ваш Gmail адрес
EMAIL_HOST_PASSWORD = 'eckr tvdp yulh ymtj'  # Пароль приложения Gmail (не обычный пароль)
DEFAULT_FROM_EMAIL = 'kata1oo87@gmail.com'