from .general import *
from decouple import config
from django.conf import settings


DEBUG = True

SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production-!@#$%^&*()')

INTERNAL_IPS = [
    "127.0.0.1",
]

# def show_toolbar(request):
#     # Respect DEBUG so the toolbar stays out of the way when the test runner
#     # forces DEBUG=False (its middleware would otherwise inject a toolbar
#     # whose panel URLs are not configured).
#     return settings.DEBUG

# DEBUG_TOOLBAR_CONFIG = {
#   "SHOW_TOOLBAR_CALLBACK" : show_toolbar,
#   # "test" is always in sys.argv under the test runner, which trips the
#   # toolbar's E001 system check; the DEBUG-aware callback above already
#   # makes that situation safe, so bypass the check as the toolbar documents.
#   "IS_RUNNING_TESTS": False,
# }

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}