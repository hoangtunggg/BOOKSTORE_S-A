"""
Django settings for search_service project.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'search-service-dev-key-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'app',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
]

ROOT_URLCONF = 'search_service.urls'

WSGI_APPLICATION = 'search_service.wsgi.application'

# Database (minimal - mainly for Django to work)
DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.environ.get('DB_NAME', 'search_db'),
        'USER': os.environ.get('DB_USER', 'bookstore_user'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'bookstore_pass'),
        'HOST': os.environ.get('DB_HOST', 'postgres-db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Elasticsearch
ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST', 'elasticsearch')
ELASTICSEARCH_PORT = os.environ.get('ELASTICSEARCH_PORT', '9200')
ELASTICSEARCH_URL = f"http://{ELASTICSEARCH_HOST}:{ELASTICSEARCH_PORT}"

# Other services
PRODUCT_CORE_SERVICE_URL = os.environ.get('PRODUCT_CORE_SERVICE_URL', 'http://product-core-service:8000')
CATALOG_SERVICE_URL = os.environ.get('CATALOG_SERVICE_URL', 'http://catalog-service:8000')

# RabbitMQ
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'rabbitmq')

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}
