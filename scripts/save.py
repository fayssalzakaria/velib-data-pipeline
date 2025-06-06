import os
from datetime import datetime

def save_csv(df):
    output_dir = "/opt/airflow/data"
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"velib_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    df.to_csv(filepath, index=False, sep=';')
    print(f" Données sauvegardées dans : {filepath}")
