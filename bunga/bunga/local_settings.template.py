# Rename this file to 'local_settings.py' and adjust the settings as needed.


SECRET_KEY = "YOUR_SECRET_KEY"


DEBUG = False
USE_DEBUG_TOOLBAR = False

# Gunicorn service port for manage.sh
SERVER_PORT = 8000

# Redis host
REDIS_HOST = {"host": "localhost", "port": 6379}

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/
ALLOWED_HOSTS = []
