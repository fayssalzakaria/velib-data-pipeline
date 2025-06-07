from airflow.decorators import dag, task
from datetime import timedelta
import pendulum
import os
import sys
sys.path.append("/opt/airflow/scripts")
sys.path.append("/opt/airflow/config")

from fetch import fetch_data
from transform import transform_data
from insert import insert_into_cloud_db
from save import save_csv
from generate_report import generate_visual_report

import pandas as pd

local_tz = pendulum.timezone("Europe/Paris")

@dag(
    dag_id='velib_multi_task_dag',
    schedule_interval='@hourly',
    start_date=pendulum.now().subtract(hours=1),
    catchup=False,
    default_args={
        'owner': 'airflow',
        'retries': 1,
        'retry_delay': timedelta(minutes=2),
    },
    description="Pipeline Vélib sans JSON via TaskFlow API"
)
def velib_pipeline():

    @task()
    def task_fetch():
        print(" FETCHING...")
        return fetch_data()

    @task()
    def task_transform(raw_data):
        print(" TRANSFORMING...")
        df = transform_data(raw_data)
        return df  # pickled par Airflow automatiquement

    @task()
    def task_insert(df):
        print(" INSERTING...")
        insert_into_cloud_db(df)

    @task()
    def task_save(df):
        print(" SAVING CSV...")
        save_csv(df)

    @task()
    def task_generate_report():
        print(" GENERATING REPORT...")
        generate_visual_report()

    # Définition du pipeline
    raw = task_fetch()
    df = task_transform(raw)
    task_insert(df)
    task_save(df) >> task_generate_report()

velib_pipeline()
