#!/bin/bash

set -e

# Port Railway
export PORT=8080
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST=0.0.0.0
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080
export AIRFLOW__WEBSERVER__BASE_URL="https://velib-data-pipeline-production.up.railway.app"

echo "➡️  Démarrage de la base Airflow..."
airflow db upgrade

echo "➡️  Création de l'utilisateur Airflow (admin)..."
airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@example.com || true

echo "➡️  Lancement du scheduler Airflow..."
airflow scheduler &

echo "➡️  Lancement de l'application combinée FastAPI + Airflow..."
exec uvicorn serve:app --host 0.0.0.0 --port "$PORT"
