import os
from sqlalchemy import create_engine, Table, Column, String, Integer, DateTime, MetaData, Boolean
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.exc import SQLAlchemyError

def insert_into_cloud_db(df):
    print("🌍 Insertion dans PostgreSQL...")

    DB_URL = os.environ.get("POSTGRES_URL")
    if not DB_URL:
        raise ValueError("🚨 POSTGRES_URL non défini dans les variables d’environnement.")
    
    engine = create_engine(DB_URL)
    metadata = MetaData()

    velib_data_table = Table('velib_data', metadata,
        Column('station_id', String),
        Column('name', String),
        Column('numbikesavailable', Integer),
        Column('mechanical', Integer),
        Column('ebike', Integer),
        Column('numdocksavailable', Integer),
        Column('timestamp', DateTime),
        Column('date', DATE),
        Column('hour', Integer),
        Column('weekday', String),
    )

    try:
        # Crée la table si elle n'existe pas déjà
        metadata.create_all(engine, checkfirst=True)

        # Insère les données
        df.to_sql("velib_data", engine, if_exists="append", index=False)
        print("✅ Données insérées avec succès")
    except SQLAlchemyError as e:
        print("❌ Erreur lors de l'insertion :", str(e))
