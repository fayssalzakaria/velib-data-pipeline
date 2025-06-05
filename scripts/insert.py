import os
from sqlalchemy import create_engine

def insert_into_cloud_db(df):
    print("🌍 Insertion dans Railway PostgreSQL...")
    DB_URL = os.environ.get("POSTGRES_URL")
    if not DB_URL:
        raise ValueError("🚨 POSTGRES_URL non défini dans les variables d’environnement.")
    
    engine = create_engine(DB_URL)
    df.to_sql("velib_data", engine, if_exists="append", index=False)
    print("✅ Données insérées avec succès")
