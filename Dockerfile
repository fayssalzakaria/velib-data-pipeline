# Utilise l’image officielle d’Airflow
FROM apache/airflow:2.7.2

# Passer en root pour copier et modifier les fichiers
USER root

# Définir le dossier de travail
WORKDIR /opt/airflow

# Copier les fichiers nécessaires
COPY airflow/dags /opt/airflow/dags
COPY airflow/webserver_config.py /opt/airflow/webserver_config.py

COPY scripts /opt/airflow/scripts
COPY requirements.txt /opt/airflow/requirements.txt
COPY entrypoint.sh /entrypoint.sh

# Rendre le script exécutable
RUN chmod +x /entrypoint.sh

# Passer à l’utilisateur airflow pour l'exécution
USER airflow

# Installer les dépendances
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

# Exposer le port pour Railway
EXPOSE 8793


# Spécifier la commande à lancer
CMD ["bash", "/entrypoint.sh"]
