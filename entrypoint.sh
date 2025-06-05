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

echo "🌐 Lancement du webserver sur 0.0.0.0:$PORT..."
exec airflow webserver --port "$PORT" --host 0.0.0.0
