from .general import *
from decouple import config


DEBUG = True

SECRET_KEY = config('SECRET_KEY')

INTERNAL_IPS = [
    "127.0.0.1",
]

def show_toolbar(request):
    return True

DEBUG_TOOLBAR_CONFIG = {
  "SHOW_TOOLBAR_CALLBACK" : show_toolbar,
}

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}