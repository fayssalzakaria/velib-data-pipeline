#!/bin/bash

set -e

# Set default port if not set
export PORT=${PORT:-8080}
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST=0.0.0.0
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT="$PORT"
export AIRFLOW__WEBSERVER__BASE_URL="https://velib-data-pipeline-production.up.railway.app"

# Log pour debug
echo "➡️  PORT=$PORT"
echo "➡️  AIRFLOW__WEBSERVER__WEB_SERVER_HOST=$AIRFLOW__WEBSERVER__WEB_SERVER_HOST"
echo "➡️  AIRFLOW__WEBSERVER__WEB_SERVER_PORT=$AIRFLOW__WEBSERVER__WEB_SERVER_PORT"
echo "➡️  AIRFLOW__WEBSERVER__BASE_URL=$AIRFLOW__WEBSERVER__BASE_URL"

# Init DB
airflow db upgrade

# Create user if not exists
airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@example.com || true

# Start scheduler in background
airflow scheduler &

# Start webserver in foreground
exec airflow webserver --port "$PORT" --host 0.0.0.0
