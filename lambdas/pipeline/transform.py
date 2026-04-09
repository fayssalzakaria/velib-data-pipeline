import logging
import re

import numpy as np
import pandas as pd
import pytz

logger = logging.getLogger(__name__)


def clean_text(text: str):
    if not isinstance(text, str):
        return None
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def parse_timestamp(ts):
    if isinstance(ts, str):
        try:
            return pd.to_datetime(ts, utc=True)
        except Exception:
            return pd.NaT
    elif isinstance(ts, (int, float)):
        try:
            if int(ts) < 1_000_000_000_000:
                return pd.NaT
            return pd.to_datetime(int(ts), unit="ms", utc=True)
        except Exception:
            return pd.NaT
    return pd.NaT


def transform_data(json_data: dict) -> pd.DataFrame:
    logger.info("Transformation des données...")
    records = json_data.get("records", [])
    rows = []

    for rec in records:
        fields = rec.get("fields", {})
        timestamp = parse_timestamp(fields.get("duedate"))

        try:
            numbikes = int(fields.get("numbikesavailable", 0))
        except (ValueError, TypeError):
            numbikes = 0

        try:
            numdocks = int(fields.get("numdocksavailable", 0))
        except (ValueError, TypeError):
            numdocks = 0

        total = numbikes + numdocks
        station_id = fields.get("stationcode")
        name = clean_text(fields.get("name"))

        if not station_id or not name:
            continue

        rows.append({
            "station_id":             station_id,
            "name":                   name,
            "numbikesavailable":      numbikes,
            "mechanical":             int(fields.get("mechanical", 0)),
            "ebike":                  int(fields.get("ebike", 0)),
            "numdocksavailable":      numdocks,
            "Derniere_Actualisation_UTC": timestamp,
            "is_full":                numdocks == 0,
            "is_empty":               numbikes == 0,
            "bike_ratio":             round(numbikes / total, 2) if total > 0 else np.nan,
        })

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["Derniere_Actualisation_UTC"])

    if not pd.api.types.is_datetime64_any_dtype(df["Derniere_Actualisation_UTC"]):
        df["Derniere_Actualisation_UTC"] = pd.to_datetime(
            df["Derniere_Actualisation_UTC"], utc=True, errors="coerce"
        )

    paris_tz = pytz.timezone("Europe/Paris")
    df["Derniere_Actualisation_Heure_locale"] = (
        df["Derniere_Actualisation_UTC"].dt.tz_convert(paris_tz)
    )
    df["date"]       = df["Derniere_Actualisation_Heure_locale"].dt.date
    df["hour"]       = df["Derniere_Actualisation_Heure_locale"].dt.hour
    df["weekday"]    = df["Derniere_Actualisation_Heure_locale"].dt.day_name()
    df["is_weekend"] = df["weekday"].isin(["Saturday", "Sunday"])

    df = df[[
        "station_id", "name", "numbikesavailable", "mechanical", "ebike",
        "numdocksavailable", "Derniere_Actualisation_UTC",
        "Derniere_Actualisation_Heure_locale", "date", "hour",
        "weekday", "is_weekend", "is_full", "is_empty", "bike_ratio",
    ]]

    logger.info(f"Transformation terminée : {len(df)} lignes")
    return df