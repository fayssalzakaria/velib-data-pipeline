#!/bin/bash

# Upgrade la DB
airflow db upgrade

# Crée l'utilisateur admin (ignore l'erreur si déjà créé)
airflow users create \
    --username admin \
    --password admin \
    --firstname Air \
    --lastname Flow \
    --role Admin \
    --email admin@example.com || true

# Lance le scheduler en arrière-plan
airflow scheduler &

# Lance le webserver (process principal)
exec airflow webserver
