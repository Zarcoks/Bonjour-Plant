#!/bin/sh
set -e

# Wait for database to be ready
echo "Waiting for PostgreSQL..."

while ! python -c "
import os
import psycopg2
try:
    psycopg2.connect(
        dbname=os.environ.get('DATABASE_NAME', 'bonjour_plant'),
        user=os.environ.get('DATABASE_USERNAME', 'bonjour_plant'),
        password=os.environ.get('DATABASE_PASSWORD', 'bonjour_plant'),
        host=os.environ.get('DATABASE_HOST', 'db'),
        port=os.environ.get('DATABASE_PORT', '5432')
    )
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; do
    echo "PostgreSQL is unavailable - sleeping..."
    sleep 2
done
echo "PostgreSQL is ready!"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files into the mounted volume
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Run the server
echo "Starting gunicorn..."
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 1 \
    --access-logfile - \
    --error-logfile -
