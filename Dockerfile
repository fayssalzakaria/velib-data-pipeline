FROM apache/airflow:2.9.1-python3.9

ENV AIRFLOW_HOME=/opt/airflow

USER airflow

# Installer les dépendances Python
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Copier les DAGs et les scripts
COPY airflow/dags/ ${AIRFLOW_HOME}/dags/
COPY scripts/ ${AIRFLOW_HOME}/scripts/

#  Copier entrypoint.sh et serve.py à la racine de l'image
COPY entrypoint.sh /entrypoint.sh
COPY serve.py ${AIRFLOW_HOME}/serve.py  # 

# Donner les permissions d'exécution à entrypoint
USER root
RUN chmod +x /entrypoint.sh

# Positionner le dossier de travail sur /opt/airflow (là où est serve.py)
WORKDIR /opt/airflow

# Revenir à l'utilisateur airflow
USER airflow

EXPOSE 8080

# Lancer l'entrypoint
ENTRYPOINT ["/entrypoint.sh"]
