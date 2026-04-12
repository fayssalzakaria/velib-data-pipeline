import io
import os

import pandas as pd
import requests
import streamlit as st

from config import S3_BUCKET


# CHARGEMENT DES DONNEES
@st.cache_data(ttl=300)
def load_from_api():
    """Charge depuis l'API Vélib' opendata.paris.fr"""
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

    rows = []
    for rec in all_records:
        f = rec.get("fields", {})
        rows.append({
            "station_id":        f.get("stationcode"),
            "name":              f.get("name", "").upper(),
            "numbikesavailable": int(f.get("numbikesavailable", 0)),
            "mechanical":        int(f.get("mechanical", 0)),
            "ebike":             int(f.get("ebike", 0)),
            "numdocksavailable": int(f.get("numdocksavailable", 0)),
            "is_full":           f.get("numdocksavailable", 1) == 0,
            "is_empty":          f.get("numbikesavailable", 1) == 0,
            "bike_ratio":        round(
                int(f.get("numbikesavailable", 0)) /
                max(int(f.get("numbikesavailable", 0)) + int(f.get("numdocksavailable", 0)), 1),
                2
            ),
            "lat": f.get("coordonnees_geo", [None, None])[0] if f.get("coordonnees_geo") else None,
            "lon": f.get("coordonnees_geo", [None, None])[1] if f.get("coordonnees_geo") else None,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_from_s3():
    """Charge depuis AWS S3"""
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
        paginator = s3.get_paginator("list_objects_v2")
        latest_key = None
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="velib/data/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".csv"):
                    if latest_key is None or key > latest_key:
                        latest_key = key
        if not latest_key:
            return None, "Aucun fichier CSV dans S3."
        obj = s3.get_object(Bucket=S3_BUCKET, Key=latest_key)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()), sep=";")
        return df, latest_key
    except Exception as e:
        return None, str(e)
