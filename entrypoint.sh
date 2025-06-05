#!/bin/bash

airflow db upgrade

airflow users create \
    --username admin \
    --password admin \
    --firstname admin \
    --lastname admin \
    --role Admin \
    --email admin@example.com

# Utilise le port Railway si défini, sinon 8080
exec airflow webserver --port "${PORT:-8080}"