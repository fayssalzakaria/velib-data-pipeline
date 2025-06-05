#!/bin/bash

# Appliquer les migrations (une seule fois, idempotent)
airflow db upgrade || true

# Créer un utilisateur admin si besoin (ignore les erreurs si déjà créé)
airflow users create \
  --username admin \
  --password admin \
  --firstname admin \
  --lastname admin \
  --role Admin \
  --email admin@example.com || true

# Lancer le webserver sur le port Railway
airflow scheduler &
exec airflow webserver --port "${PORT:-8793}" --host 0.0.0.0
