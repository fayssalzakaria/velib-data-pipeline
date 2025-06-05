#!/bin/bash

echo "🏁 ENTRYPOINT lancé"
echo "Env : $(env)" > /opt/airflow/debug_env.txt

airflow db upgrade || { echo "❌ Échec DB upgrade"; exit 1; }

airflow users create \
  --username admin \
  --password admin \
  --firstname Air \
  --lastname Flow \
  --role Admin \
  --email admin@example.com || echo "👤 Utilisateur déjà présent"

airflow scheduler &

# Lancement du webserver (Railway veut 0.0.0.0:8080)
exec airflow webserver --port 8080 --host 0.0.0.0
