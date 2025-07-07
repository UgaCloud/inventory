import os
from .general import *


DEBUG = False

SECRET_KEY = os.environ['SECRET_KEY']


ALLOWED_HOSTS = ['kafunda-ug.com', 'www.kafunda-ug.com', '127.0.0.1']