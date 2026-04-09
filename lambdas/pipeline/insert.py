import logging
import os
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer,
    MetaData, String, Table, Text, create_engine, text,
)
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _get_engine():
    db_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("POSTGRES_URL non défini.")
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        connect_args={"connect_timeout": 10},
    )


def _ensure_table(engine):
    metadata = MetaData()
    Table(
        "velib_data", metadata,
        Column("id",          Integer,  primary_key=True, autoincrement=True),
        Column("snapshot_id", String(20), nullable=False, index=True),
        Column("run_at",      DateTime(timezone=True), nullable=False),
        Column("station_id",  String(20)),
        Column("name",        Text),
        Column("numbikesavailable",  Integer),
        Column("mechanical",         Integer),
        Column("ebike",              Integer),
        Column("numdocksavailable",  Integer),
        Column("Derniere_Actualisation_UTC",          DateTime(timezone=True)),
        Column("Derniere_Actualisation_Heure_locale", DateTime(timezone=True)),
        Column("date",        Date),
        Column("hour",        Integer),
        Column("weekday",     String(20)),
        Column("is_full",     Boolean),
        Column("is_empty",    Boolean),
        Column("bike_ratio",  Float),
        Column("is_weekend",  Boolean),
    )
    metadata.create_all(engine)
    logger.info("Table velib_data vérifiée / créée.")


def insert_into_db(df: pd.DataFrame, snapshot_id: str) -> int:
    logger.info(f"Insertion snapshot {snapshot_id} ({len(df)} lignes)...")

    engine = _get_engine()
    _ensure_table(engine)

    df_insert = df.copy()
    df_insert.fillna({"bike_ratio": 0.0, "weekday": "UNKNOWN"}, inplace=True)
    df_insert["bike_ratio"]  = df_insert["bike_ratio"].astype(float)
    df_insert["is_full"]     = df_insert["is_full"].astype(bool)
    df_insert["is_empty"]    = df_insert["is_empty"].astype(bool)
    df_insert["is_weekend"]  = df_insert["is_weekend"].astype(bool)
    df_insert["weekday"]     = df_insert["weekday"].astype(str)
    df_insert.columns        = [col.replace(" ", "_") for col in df_insert.columns]
    df_insert["snapshot_id"] = snapshot_id
    df_insert["run_at"]      = datetime.now(timezone.utc)

    try:
        df_insert.to_sql(
            "velib_data", engine,
            if_exists="append",
            index=False,
            method="multi",
            chunksize=500,
        )
        logger.info(f"Snapshot {snapshot_id} inséré : {len(df_insert)} lignes.")
        return len(df_insert)
    except SQLAlchemyError as e:
        logger.error(f"Erreur insertion : {e}")
        raise


def get_latest_snapshot(engine=None) -> pd.DataFrame:
    if engine is None:
        engine = _get_engine()
    query = text("""
        SELECT * FROM velib_data
        WHERE snapshot_id = (
            SELECT snapshot_id FROM velib_data
            ORDER BY run_at DESC LIMIT 1
        )
    """)
    with engine.connect() as conn:
        return pd.read_sql(query, conn)