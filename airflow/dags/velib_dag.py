import sys
import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Ajouter les chemins aux scripts et config
sys.path.append("/opt/airflow/scripts")
sys.path.append("/opt/airflow/config")

from fetch import fetch_data
from transform import transform_data
from insert import insert_into_cloud_db
from save import save_csv
import pandas as pd

default_args = {
    'owner': 'airflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

with DAG(
    dag_id='velib_multi_task_dag',
    default_args=default_args,
    description='Pipeline Vélib avec plusieurs tâches',
    start_date=datetime(2025, 6, 5),
    schedule_interval='@hourly',
    catchup=False
) as dag:

    def task_fetch(**context):
        print("📥 FETCHING...")
        data = fetch_data()
        context['ti'].xcom_push(key='json_data', value=data)

    def task_transform(**context):
        print("🔧 TRANSFORMING...")
        json_data = context['ti'].xcom_pull(task_ids='fetch_data', key='json_data')
        df = transform_data(json_data)
        context['ti'].xcom_push(key='df_json', value=df.to_json())

    def task_insert(**context):
        print("💾 INSERTING...")
        df_json = context['ti'].xcom_pull(task_ids='transform_data', key='df_json')
        df = pd.read_json(df_json)
        insert_into_cloud_db(df)

    def task_save(**context):
        print("📁 SAVING CSV...")
        df_json = context['ti'].xcom_pull(task_ids='transform_data', key='df_json')
        df = pd.read_json(df_json)
        save_csv(df)

    # Déclaration des tâches
    t1 = PythonOperator(task_id='fetch_data', python_callable=task_fetch, provide_context=True)
    t2 = PythonOperator(task_id='transform_data', python_callable=task_transform, provide_context=True)
    t3 = PythonOperator(task_id='insert_to_db', python_callable=task_insert, provide_context=True)
    t4 = PythonOperator(task_id='save_csv', python_callable=task_save, provide_context=True)

    # Dépendances
    t1 >> t2 >> [t3, t4]
