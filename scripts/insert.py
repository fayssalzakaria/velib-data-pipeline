import os
import pandas as pd
from sqlalchemy import create_engine, Table, Column, String, Integer, DateTime, MetaData, Boolean, Float
from sqlalchemy.dialects.postgresql import DATE
from sqlalchemy.exc import SQLAlchemyError

def insert_into_cloud_db(df):
    print(" Insertion dans PostgreSQL...")

    DB_URL = os.environ.get("POSTGRES_URL")
    if not DB_URL:
        raise ValueError(" POSTGRES_URL non défini dans les variables d’environnement.")
    
    df = df.copy()
    df.fillna({
        "bike_ratio": 0.0,
        "weekday": "UNKNOWN"
    }, inplace=True)

    df["bike_ratio"] = df["bike_ratio"].astype(float)
    df["is_full"] = df["is_full"].astype(bool)
    df["is_empty"] = df["is_empty"].astype(bool)
    df["is_weekend"] = df["is_weekend"].astype(bool)
    df["weekday"] = df["weekday"].astype(str)

    engine = create_engine(DB_URL)
    metadata = MetaData()

    velib_data_table = Table('velib_data', metadata,
        Column('station_id', String),
        Column('name', String),
        Column('numbikesavailable', Integer),
        Column('mechanical', Integer),
        Column('ebike', Integer),
        Column('numdocksavailable', Integer),
        Column('Date actualisation', DateTime),  
        Column('date', DATE),
        Column('hour', Integer),
        Column('weekday', String),
        Column('is_full', Boolean),
        Column('is_empty', Boolean),
        Column('bike_ratio', Float),
        Column('is_weekend', Boolean),
        Column('Heure locale', DateTime(timezone=True)),

    )

    try:
        velib_data_table.drop(engine, checkfirst=True)
        print(" Table existante supprimée.")
        metadata.create_all(engine)
        print(" Table recréée avec succès.")
        df.to_sql("velib_data", engine, if_exists="append", index=False)
        print(" Données insérées avec succès.")
        
    except SQLAlchemyError as e:
        print(" Erreur lors de l'insertion :", str(e))
