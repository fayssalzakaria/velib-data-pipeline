#!/bin/bash

set -e

# Configuration minimale nécessaire pour Railway
export PORT=${PORT:-8080}
export AIRFLOW__CORE__EXECUTOR=LocalExecutor
export AIRFLOW__CORE__FERNET_KEY=${AIRFLOW__CORE__FERNET_KEY:-your_generated_key}
export AIRFLOW__CORE__SQL_ALCHEMY_CONN=${AIRFLOW__CORE__SQL_ALCHEMY_CONN:-your_postgres_url}
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST=0.0.0.0
export AIRFLOW__WEBSERVER__AUTH_BACKENDS=airflow.auth.backend.allow_all
export AIRFLOW__WEBSERVER__BASE_URL="https://velib-data-pipeline-production.up.railway.app"
export AIRFLOW__WEBSERVER__SESSION_COOKIE_SECURE=False
export AIRFLOW_HOME=/opt/airflow

# Appliquer les migrations de base de données (idempotent)
airflow db upgrade

# Créer un utilisateur admin si non existant
airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@example.com || true

# Lancer le scheduler en arrière-plan
airflow scheduler &

# Lancer le webserver en avant-plan
exec airflow webserver --port "$PORT" --host 0.0.0.0
