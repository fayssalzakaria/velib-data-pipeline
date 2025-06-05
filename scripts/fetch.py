import requests

API_URL = "https://opendata.paris.fr/api/records/1.0/search/"
PARAMS = {"dataset": "velib-disponibilite-en-temps-reel", "rows": 1000}

def fetch_data():
    print("📡 Récupération des données...")
    response = requests.get(API_URL, params=PARAMS)
    response.raise_for_status()
    return response.json()
