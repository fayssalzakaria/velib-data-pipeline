FROM apache/airflow:2.9.1-python3.9

USER airflow

COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

ENV AIRFLOW_HOME=/opt/airflow

COPY airflow/dags/ ${AIRFLOW_HOME}/dags/
COPY scripts/ ${AIRFLOW_HOME}/scripts/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh  # 👈 ligne importante

ENTRYPOINT ["/entrypoint.sh"]
