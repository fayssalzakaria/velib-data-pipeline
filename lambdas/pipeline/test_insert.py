"""
Test local de insert.py
Lance avec : python3 test_insert.py
Nécessite POSTGRES_URL dans l'environnement.
"""
import os
import pandas as pd
from datetime import datetime, timezone
from insert import insert_into_db, get_latest_snapshot

# Données fictives pour tester
def make_fake_df():
    return pd.DataFrame([{
        "station_id":   "TEST-001",
        "name":         "STATION TEST",
        "numbikesavailable": 5,
        "mechanical":   3,
        "ebike":        2,
        "numdocksavailable": 10,
        "Derniere_Actualisation_UTC": datetime.now(timezone.utc),
        "Derniere_Actualisation_Heure_locale": datetime.now(timezone.utc),
        "date":         datetime.now().date(),
        "hour":         datetime.now().hour,
        "weekday":      "Thursday",
        "is_full":      False,
        "is_empty":     False,
        "bike_ratio":   0.33,
        "is_weekend":   False,
    }])

if __name__ == "__main__":
    if not os.environ.get("POSTGRES_URL"):
        print("POSTGRES_URL non défini — test ignoré")
        exit(0)

    snapshot_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    df = make_fake_df()

    print(f"→ Insertion snapshot {snapshot_id}...")
    n = insert_into_db(df, snapshot_id)
    print(f" {n} ligne(s) insérée(s)")

    print("→ Lecture dernier snapshot...")
    df_back = get_latest_snapshot()
    print(f" {len(df_back)} ligne(s) récupérée(s)")
    print(df_back[["snapshot_id", "station_id", "name", "run_at"]])