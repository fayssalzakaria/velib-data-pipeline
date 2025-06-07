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

def parse_timestamp(ts):
    if isinstance(ts, str):
        try:
            dt = pd.to_datetime(ts, utc=True)
            return dt
        except Exception as e:
            print(f" Erreur de conversion string → datetime : {ts} ({e})")
            return pd.NaT
    elif isinstance(ts, (int, float)):
        try:
            if int(ts) < 1000000000000:  # timestamp trop petit
                print(f" Timestamp trop petit, ignoré : {ts}")
                return pd.NaT
            return pd.to_datetime(int(ts), unit='ms', utc=True)
        except Exception as e:
            print(f" Erreur de conversion timestamp int → datetime : {ts} ({e})")
            return pd.NaT
    print(f" Type de timestamp inattendu : {type(ts)} – valeur : {ts}")
    return pd.NaT

def transform_data(json_data):
    print(" Étapes : nettoyage → normalisation → enrichissement")

    records = json_data.get("records", [])
    rows = []

    for rec in records:
        fields = rec.get("fields", {})
        timestamp = parse_timestamp(fields.get("duedate"))

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
            "Derniere_Actualisation_UTC": timestamp,
            "is_full": numdocks == 0,
            "is_empty": numbikes == 0,
            "bike_ratio": round(numbikes / total, 2) if total > 0 else np.nan
        }

        rows.append(row)

    df = pd.DataFrame(rows)

    # Supprimer les lignes sans timestamp valide
    df = df.dropna(subset=["Derniere_Actualisation_UTC"])

    # Vérifier/convertir en datetime explicite si besoin
    if not pd.api.types.is_datetime64_any_dtype(df["Derniere_Actualisation_UTC"]):
        df["Derniere_Actualisation_UTC"] = pd.to_datetime(df["Derniere_Actualisation_UTC"], utc=True, errors="coerce")

    # Conversion en heure locale
    paris_tz = pytz.timezone("Europe/Paris")
    df["Derniere_Actualisation_Heure_locale"] = df["Derniere_Actualisation_UTC"].dt.tz_convert(paris_tz)

    # Colonnes dérivées
    df["date"] = df["Derniere_Actualisation_Heure_locale"].dt.date
    df["hour"] = df["Derniere_Actualisation_Heure_locale"].dt.hour
    df["weekday"] = df["Derniere_Actualisation_Heure_locale"].dt.day_name()
    df["is_weekend"] = df["weekday"].isin(["Saturday", "Sunday"])

    df = df[[
        "station_id", "name", "numbikesavailable", "mechanical", "ebike", "numdocksavailable",
        "Derniere_Actualisation_UTC", "Derniere_Actualisation_Heure_locale",
        "date", "hour", "weekday", "is_weekend",
        "is_full", "is_empty", "bike_ratio"
    ]]

    print(f" Données transformées : {len(df)} lignes prêtes")
    return df
