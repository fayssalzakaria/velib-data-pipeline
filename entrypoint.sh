#!/bin/bash
export AIRFLOW__WEBSERVER__WORKERS=1
export AIRFLOW__CORE__LOAD_EXAMPLES=False

airflow db upgrade

airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@example.com

# Utilise le port Railway si défini, sinon 8080
exec airflow webserver --port "${PORT:-8080}" --host 0.0.0.0 --workers 1
