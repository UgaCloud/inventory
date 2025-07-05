import os
from .general import *
from decouple import config


DEBUG = False

SECRET_KEY = config('SECRET_KEY')


ALLOWED_HOSTS = ['kafunda-ug.com', 'www.kafunda-ug.com', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'inventory_db',
        'USER': 'root',
        'PASSWORD': '',
        'HOST': 'localhost',  
        'PORT': '3306',
    }
}