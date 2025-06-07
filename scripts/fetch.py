import requests

API_URL = "https://opendata.paris.fr/api/records/1.0/search/"
DATASET = "velib-disponibilite-en-temps-reel"

def fetch_data(limit=5000, rows_per_call=1000):
    print(" Récupération de toutes les données Vélib’...")
    all_records = []

    for start in range(0, limit, rows_per_call):
        print(f"➡️ Requête {start} → {start + rows_per_call}")
        params = {
            "dataset": DATASET,
            "rows": rows_per_call,
            "start": start,
        }
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        page = response.json()
        records = page.get("records", [])
        all_records.extend(records)

        if len(records) < rows_per_call:
            print(" Fin des données atteinte.")
            break

    print(f" Total de stations récupérées : {len(all_records)}")
    return {"records": all_records}
