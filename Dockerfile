FROM apache/airflow:2.9.1-python3.9

USER root  # On passe temporairement root pour l'installation

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

USER airflow  # Revenir à l'utilisateur non-root officiel

ENV AIRFLOW_HOME=/opt/airflow

COPY airflow/dags/ ${AIRFLOW_HOME}/dags/
COPY scripts/ ${AIRFLOW_HOME}/scripts/
COPY entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
