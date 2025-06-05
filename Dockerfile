# Base image Airflow officielle
FROM apache/airflow:2.7.2

# Définir le dossier de travail
WORKDIR /opt/airflow

# Copier les fichiers de l'hôte vers l'image Docker
COPY airflow/dags ./dags
COPY scripts ./scripts

COPY requirements.txt .

# Installer les dépendances Python nécessaires
USER root
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Redonner les droits à l'utilisateur airflow
USER airflow
