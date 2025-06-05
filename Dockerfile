FROM apache/airflow:2.9.1-python3.9

USER airflow

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

ENV AIRFLOW_HOME=/opt/airflow

COPY airflow/dags/ ${AIRFLOW_HOME}/dags/
COPY scripts/ ${AIRFLOW_HOME}/scripts/
COPY entrypoint.sh /entrypoint.sh

# Changer les permissions avec root
USER root
RUN chmod +x /entrypoint.sh

# Revenir à l'utilisateur airflow
USER airflow

ENTRYPOINT ["/entrypoint.sh"]
