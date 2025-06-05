#!/bin/bash
airflow db upgrade

# Créer un utilisateur admin si ce n’est pas encore fait (ignore l’erreur si déjà présent)
airflow users create \
    --username admin \
    --password admin \
    --firstname Air \
    --lastname Flow \
    --role Admin \
    --email admin@example.com || true

# Lancer le webserver (entrypoint final)
exec airflow webserver
