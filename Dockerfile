# Base image Airflow officielle
FROM apache/airflow:2.7.2

# Passer en root pour effectuer certaines actions si besoin
USER root

# Définir le dossier de travail
WORKDIR /opt/airflow

# Copier les dossiers et fichiers
COPY airflow/dags /opt/airflow/dags
COPY scripts /opt/airflow/scripts
COPY requirements.txt /opt/airflow/requirements.txt

# Installer les dépendances avec l'utilisateur airflow (meilleure pratique)
USER airflow
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

# Exposer le port 8080 pour le webserver Airflow
EXPOSE 8080

# Lancer Airflow Webserver au démarrage du conteneur
CMD ["airflow", "webserver"]
