import os

from .general import *
from decouple import config
import pymysql
pymysql.install_as_MySQLdb()


DEBUG = False

SECRET_KEY = config('SECRET_KEY')



ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'kafurfxz_inventory',
        'USER': 'kafurfxz_kafunda_user',
        'PASSWORD': 'kafunda@123',
        'HOST': 'localhost', 
        'PORT': '3306',
    }
}

