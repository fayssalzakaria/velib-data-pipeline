# Base image Airflow officielle
FROM apache/airflow:2.7.2

USER root

WORKDIR /opt/airflow

COPY airflow/dags /opt/airflow/dags
COPY scripts /opt/airflow/scripts
COPY requirements.txt /opt/airflow/requirements.txt

USER airflow
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

EXPOSE 8080

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]

