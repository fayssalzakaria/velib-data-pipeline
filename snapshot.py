"""
snapshot.py
Capture un snapshot temps réel et l'ajoute à l'historique.
- Avec AWS : invoque la Lambda pipeline
- Sans AWS  : fetch l'API Vélib et sauvegarde dans le CSV local
"""
import os
import io
import pandas as pd
import requests
import numpy as np
from datetime import datetime, timezone
import pytz

SAMPLE_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "data", "sample_history.csv"
)

PARIS_TZ = pytz.timezone("Europe/Paris")


def _fetch_velib_snapshot() -> pd.DataFrame:
    """Fetch les données temps réel depuis l'API Vélib."""
    all_records = []
    for start in range(0, 2000, 1000):
        params = {
            "dataset": "velib-disponibilite-en-temps-reel",
            "rows": 1000,
            "start": start,
        }
        r = requests.get(
            "https://opendata.paris.fr/api/records/1.0/search/",
            params=params,
            timeout=30,
        )
        records = r.json().get("records", [])
        all_records.extend(records)
        if len(records) < 1000:
            break

    now = datetime.now(PARIS_TZ)
    snapshot_id = now.strftime("%Y%m%d_%H%M")
    rows = []

    for rec in all_records:
        f = rec.get("fields", {})
        nb = int(f.get("numbikesavailable", 0))
        nd = int(f.get("numdocksavailable", 0))
        total = nb + nd
        ebike = int(f.get("ebike", 0))
        mechanical = int(f.get("mechanical", 0))

        rows.append({
            "snapshot_id":        snapshot_id,
            "run_at":             now.isoformat(),
            "station_id":         f.get("stationcode"),
            "name":               f.get("name", "").upper(),
            "numbikesavailable":  nb,
            "mechanical":         mechanical,
            "ebike":              ebike,
            "numdocksavailable":  nd,
            "bike_ratio":         round(nb / max(total, 1), 2),
            "is_empty":           nb == 0,
            "is_full":            nd == 0,
            "hour":               now.hour,
            "weekday":            now.strftime("%A"),
            "is_weekend":         now.weekday() >= 5,
        })

    return pd.DataFrame(rows)


def capture_snapshot_local() -> tuple[bool, str]:
    """
    Capture un snapshot et le sauvegarde dans le CSV local.
    Utilisé quand Aurora est down.
    """
    try:
        df = _fetch_velib_snapshot()
        os.makedirs(os.path.dirname(SAMPLE_DATA_PATH), exist_ok=True)

        if os.path.exists(SAMPLE_DATA_PATH):
            existing = pd.read_csv(SAMPLE_DATA_PATH, sep=";")
            df_combined = pd.concat([existing, df], ignore_index=True)
        else:
            df_combined = df

        df_combined.to_csv(SAMPLE_DATA_PATH, index=False, sep=";")
        now_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d %H:%M")
        return True, f"Snapshot capturé à {now_str} — {len(df)} stations"

    except Exception as e:
        return False, f"Erreur : {e}"


def capture_snapshot_aws() -> tuple[bool, str]:
    """
    Déclenche le pipeline Lambda AWS pour capturer un snapshot.
    Utilisé quand Aurora est active.
    """
    try:
        import boto3
        client = boto3.client(
            "lambda",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
        function_name = os.environ.get(
            "PIPELINE_LAMBDA", "velib-pipeline-fz-prod-pipeline"
        )
        response = client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=b"{}",
        )
        payload = response["Payload"].read().decode()
        if response.get("FunctionError"):
            return False, f"Erreur Lambda : {payload}"

        now_str = datetime.now(PARIS_TZ).strftime("%Y-%m-%d %H:%M")
        return True, f"Pipeline lancé à {now_str} — snapshot sauvegardé dans Aurora + S3"

    except Exception as e:
        return False, f"Erreur : {e}"