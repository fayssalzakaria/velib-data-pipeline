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

# Forcer l'utilisation de Flask (Werkzeug) en développement
export AIRFLOW__WEBSERVER__WORKERS=1
export AIRFLOW__WEBSERVER__WEB_SERVER_HOST=0.0.0.0
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080

echo "🌐 Lancement du webserver Flask (werkzeug) sur le port 8080..."
exec airflow webserver --port 8080 --host 0.0.0.0 --web-server-worker-class werkzeug
