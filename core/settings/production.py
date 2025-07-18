import os

from .general import *
from decouple import config
import pymysql
pymysql.install_as_MySQLdb()


DEBUG = False

# SECRET_KEY = os.environ['SECRET_KEY']
SECRET_KEY = 'django-insecure-gqgpv+7+nke4*fefzsr63+a=r0!!t@bgn!_1a*5(_^ow@^3t)('


<<<<<<< HEAD
ALLOWED_HOSTS = ['kafunda-ug.com', 'www.kafunda-ug.com']
=======
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
>>>>>>> main

