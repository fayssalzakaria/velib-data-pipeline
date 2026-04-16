import os
import pandas as pd
from sqlalchemy import create_engine, text


def get_engine():
    url = os.environ.get("POSTGRES_URL")
    if not url:
        return None
    return create_engine(url, pool_pre_ping=True)


def get_station_history(station_name: str, hours: int = 24) -> pd.DataFrame:
    engine = get_engine()
    if engine is None:
        return pd.DataFrame()

    query = text("""
        SELECT
            run_at,
            name,
            numbikesavailable,
            ebike,
            mechanical,
            numdocksavailable,
            bike_ratio
        FROM velib_data
        WHERE name ILIKE :name
          AND run_at >= NOW() - INTERVAL ':hours hours'
        ORDER BY run_at ASC
    """).bindparams(name=f"%{station_name.upper()}%", hours=hours)

    try:
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


def get_available_stations(hours: int = 1) -> list:
    engine = get_engine()
    if engine is None:
        return []

    query = text("""
        SELECT DISTINCT name
        FROM velib_data
        WHERE run_at >= NOW() - INTERVAL ':hours hours'
        ORDER BY name
    """).bindparams(hours=hours)

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
            return df["name"].tolist()
    except Exception:
        return []