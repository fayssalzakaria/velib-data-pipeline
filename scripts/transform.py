import pandas as pd
import numpy as np
import re
import pytz

def clean_text(text):
    if not isinstance(text, str):
        return None
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.upper()

def transform_data(json_data):
    print(" Étapes : nettoyage → normalisation → enrichissement")

    records = json_data.get("records", [])
    rows = []

    for rec in records:
        fields = rec.get("fields", {})
        timestamp = fields.get("duedate")

        try:
            numbikes = int(fields.get("numbikesavailable", 0))
        except:
            numbikes = 0

        try:
            numdocks = int(fields.get("numdocksavailable", 0))
        except:
            numdocks = 0

        total = numbikes + numdocks
        station_id = fields.get("stationcode")
        name = clean_text(fields.get("name"))

        if not station_id or not name:
            continue

        row = {
            "station_id": station_id,
            "name": name,
            "numbikesavailable": numbikes,
            "mechanical": int(fields.get("mechanical", 0)),
            "ebike": int(fields.get("ebike", 0)),
            "numdocksavailable": numdocks,
            "Derniere Actualisation UTC": timestamp,
            "is_full": numdocks == 0,
            "is_empty": numbikes == 0,
            "bike_ratio": round(numbikes / total, 2) if total > 0 else np.nan
        }

        rows.append(row)

    df = pd.DataFrame(rows)
    df["Derniere Actualisation UTC"] = pd.to_datetime(df["Derniere Actualisation UTC"], errors="coerce", utc=True)
    df = df.dropna(subset=["Derniere Actualisation UTC"])

    paris_tz = pytz.timezone("Europe/Paris")
    df["Derniere Actualisation Heure locale"] = df["Derniere Actualisation UTC"].dt.tz_convert(paris_tz)

    df["date"] = df["Derniere Actualisation UTC"].dt.date
    df["hour"] = df["Derniere Actualisation UTC"].dt.hour
    df["weekday"] = df["Derniere Actualisation UTC"].dt.day_name()
    df["is_weekend"] = df["weekday"].isin(["Saturday", "Sunday"])

    df = df[[
        "station_id", "name", "numbikesavailable", "mechanical", "ebike", "numdocksavailable",
        "Derniere Actualisation UTC", "Derniere Actualisation Heure locale",
        "date", "hour", "weekday", "is_weekend",
        "is_full", "is_empty", "bike_ratio"
    ]]

    print(f" Données transformées : {len(df)} lignes prêtes")
    # Renommer les colonnes pour usage cohérent (pas d’espaces)
    df.columns = [col.replace(" ", "_") for col in df.columns]

    return df
