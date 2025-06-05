#!/bin/bash

echo "🏁 ENTRYPOINT lancé"

airflow db upgrade || { echo "❌ DB upgrade échoué"; exit 1; }

airflow users create \
  --username admin \
  --password admin \
  --firstname Air \
  --lastname Flow \
  --role Admin \
  --email admin@example.com || echo "👤 Utilisateur déjà présent"

echo "🚀 Lancement du scheduler..."
airflow scheduler &

# 👇 Correction critique ici
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=${PORT:-8793}

echo "🌐 Lancement du webserver Gunicorn sur le port ${AIRFLOW__WEBSERVER__WEB_SERVER_PORT}..."
exec airflow webserver
