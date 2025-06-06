from fetch import fetch_data
from transform import transform_data
from insert import insert_into_cloud_db
from save import save_csv 

def run_pipeline():
    print(" Début pipeline Vélib'")
    json_data = fetch_data()
    df = transform_data(json_data)
    insert_into_cloud_db(df)
    save_csv(df)
    print(" Pipeline terminé")
