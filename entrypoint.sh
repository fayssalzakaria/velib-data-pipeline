#!/bin/bash
set -e

# Configuration réseau pour Railway
export PORT=8080
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST=0.0.0.0
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=$PORT
export AIRFLOW__WEBSERVER__BASE_URL="https://velib-data-pipeline-production.up.railway.app"

# ⚡ Optimisations Airflow
export AIRFLOW__CORE__STORE_SERIALIZED_DAGS=True
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=30
export AIRFLOW__CORE__DAGBAG_IMPORT_TIMEOUT=30

echo "➡️  Démarrage de la base de données Airflow..."
airflow db upgrade

echo "➡️  Création de l'utilisateur Airflow (admin)..."
airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@example.com || true

echo "➡️  Lancement du scheduler Airflow en arrière-plan..."
airflow scheduler &

echo "➡️  Lancement de l'API FastAPI (serve.py) avec Uvicorn optimisé..."
exec uvicorn serve:app --host 0.0.0.0 --port "$PORT" --workers 4 --timeout-keep-alive 30
