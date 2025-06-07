import pandas as pd
import numpy as np
import re
import pytz

# Fonction pour nettoyer les noms de station (suppression des espaces, majuscules)
def clean_text(text):
    if not isinstance(text, str):
        return None
    text = text.strip()                      # Supprime les espaces en début/fin
    text = re.sub(r"\s+", " ", text)         # Remplace les espaces multiples par un seul
    return text.upper()                      # Convertit en MAJUSCULES pour homogénéiser

# Fonction principale de transformation des données JSON en DataFrame structuré
def transform_data(json_data):
    print(" Étapes : nettoyage → normalisation → enrichissement")

    records = json_data.get("records", [])   # Récupère la liste d'enregistrements
    rows = []                                # Liste qui contiendra les lignes nettoyées

    for rec in records:
        fields = rec.get("fields", {})       # Extraction des champs utiles
        timestamp = fields.get("duedate")    # Date/heure de mesure

        # Tentative de récupération des valeurs numériques, avec gestion des erreurs
        try:
            numbikes = int(fields.get("numbikesavailable", 0))
        except:
            numbikes = 0

        try:
            numdocks = int(fields.get("numdocksavailable", 0))
        except:
            numdocks = 0

        total = numbikes + numdocks          # Capacité totale (vélos + bornes libres)
        station_id = fields.get("stationcode")
        name = clean_text(fields.get("name"))  # Nettoyage du nom de station

        # Ignore les lignes sans identifiant ou nom de station
        if not station_id or not name:
            continue

        # Construction d’un dictionnaire représentant une ligne de données
        row = {
            "station_id": station_id,
            "name": name,
            "numbikesavailable": numbikes,
            "mechanical": int(fields.get("mechanical", 0)),
            "ebike": int(fields.get("ebike", 0)),
            "numdocksavailable": numdocks,
            "timestamp": timestamp,
            "is_full": numdocks == 0,                               # Station pleine ?
            "is_empty": numbikes == 0,                              # Station vide ?
            "bike_ratio": round(numbikes / total, 2) if total > 0 else np.nan  # Ratio vélos / total
        }

        rows.append(row)  # Ajoute la ligne au tableau brut

    # Conversion en DataFrame
    df = pd.DataFrame(rows)

    # Nettoyage : conversion explicite de timestamp (en UTC) + suppression des dates invalides
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp"])

    # Création de colonnes dérivées pour l'analyse
    df["date"] = df["timestamp"].dt.date
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.day_name()
    df["is_weekend"] = df["weekday"].isin(["Saturday", "Sunday"])

    # Réorganisation des colonnes dans un ordre logique
    df = df[[
        "station_id", "name", "numbikesavailable", "mechanical", "ebike", "numdocksavailable",
        "timestamp", "date", "hour", "weekday", "is_weekend",
        "is_full", "is_empty", "bike_ratio"
    ]]

    print(f" Données transformées : {len(df)} lignes prêtes")
    return df
