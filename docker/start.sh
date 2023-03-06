#!/bin/bash  

cd /app 

python manage.py collectstatic --noinput  
python manage.py makemigrations users books movies games music sync mastodon management collection
python manage.py makemigrations  
python manage.py migrate users
python manage.py migrate
python manage.py rqworker --with-scheduler doufen export mastodon &
# enqueue scheduled jobs per minute
python manage.py rqscheduler --queue mastodon &

gunicorn \
    -b 0.0.0.0:8000 \
    -w 2 \
    -k uvicorn.workers.UvicornWorker \
    --log-level DEBUG \
    --access-logfile '-' \
    --error-logfile '-' \
    boofilsic.asgi:application

