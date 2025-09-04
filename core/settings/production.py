import os

from .general import *
from decouple import config
import pymysql
pymysql.install_as_MySQLdb()


DEBUG = True

SECRET_KEY = config('SECRET_KEY')

# SECRET_KEY = 'django-insecure-gqgpv+7+nke4*fefzsr63+a=r0!!t@bgn!_1a*5(_^ow@^3t)('


ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

