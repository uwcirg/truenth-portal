# Heroku Procfile
# See https://devcenter.heroku.com/articles/procfile

web: gunicorn --bind "0.0.0.0:${PORT:-8008}" wsgi:application
worker: celery worker --app portal.celery_worker.celery --loglevel=info
