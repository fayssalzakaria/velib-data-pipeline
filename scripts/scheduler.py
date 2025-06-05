import schedule
import time
from ingest_velib import fetch_data, parse_data, save_csv

def job():
    print(" Ingestion des données Vélib’ en cours...")
    data = fetch_data()
    df = parse_data(data)
    save_csv(df)

# Planifie une exécution immédiate + toutes les heures
job()
schedule.every(1).hours.do(job)

print(" Le scheduler tourne... (CTRL+C pour arrêter)")

while True:
    schedule.run_pending()
    time.sleep(1)
