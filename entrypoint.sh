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

# Forcer le mode développement (serveur Flask)
export AIRFLOW__WEBSERVER__WORKERS=1
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST=0.0.0.0
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080
export AIRFLOW__WEBSERVER__WEB_SERVER_WORKER_CLASS=werkzeug

echo "🌐 Lancement du webserver Flask sur le port 8080..."
exec airflow webserver --debug
