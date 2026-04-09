import logging
import requests

logger = logging.getLogger(__name__)

API_URL = "https://opendata.paris.fr/api/records/1.0/search/"
DATASET = "velib-disponibilite-en-temps-reel"


def fetch_data(limit: int = 5000, rows_per_call: int = 1000) -> dict:
    logger.info("Récupération des données Vélib'...")
    all_records = []

    for start in range(0, limit, rows_per_call):
        params = {
            "dataset": DATASET,
            "rows": rows_per_call,
            "start": start,
        }
        try:
            response = requests.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Erreur API Vélib' à start={start} : {e}")
            raise

        page = response.json()
        records = page.get("records", [])
        all_records.extend(records)

        if len(records) < rows_per_call:
            logger.info(f"Fin des données à start={start + len(records)}")
            break

    logger.info(f"Total stations récupérées : {len(all_records)}")
    return {"records": all_records}