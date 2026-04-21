import io
import os

import boto3
import pandas as pd


S3_BUCKET = os.environ.get("S3_BUCKET", "velib-pipeline-fz-prod-data")
S3_HISTORY_PREFIX = "velib/history/"


def _get_engine():
    url = os.environ.get("POSTGRES_URL", "")
    if not url:
        return None
    try:
        from sqlalchemy import create_engine
        return create_engine(url, pool_pre_ping=True)
    except Exception:
        return None


def _get_s3():
    try:
        return boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
    except Exception:
        return None


def _load_from_aurora(station_name: str, hours: int) -> pd.DataFrame:
    engine = _get_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        from sqlalchemy import text
        query = text("""
            SELECT run_at, name, numbikesavailable, ebike, mechanical,
                   numdocksavailable, bike_ratio
            FROM velib_data
            WHERE name ILIKE :name
              AND run_at >= NOW() - INTERVAL ':hours hours'
            ORDER BY run_at ASC
        """).bindparams(name=f"%{station_name.upper()}%", hours=hours)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


def _load_from_s3(station_name: str, hours: int) -> pd.DataFrame:
    s3 = _get_s3()
    if s3 is None:
        return pd.DataFrame()
    try:
        paginator = s3.get_paginator("list_objects_v2")
        dfs = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_HISTORY_PREFIX):
            for obj in page.get("Contents", []):
                response = s3.get_object(Bucket=S3_BUCKET, Key=obj["Key"])
                df = pd.read_csv(io.BytesIO(response["Body"].read()), sep=";")
                dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        df_all = pd.concat(dfs, ignore_index=True)
        df_all["run_at"] = pd.to_datetime(df_all["run_at"], utc=True, errors="coerce")
        df_all = df_all.dropna(subset=["run_at"])

        df_station = df_all[
            df_all["name"].str.contains(station_name.upper(), na=False)
        ].copy()

        if df_station.empty:
            return pd.DataFrame()

        # Filtre par date seulement si hours est raisonnable
        # Sinon retourne tout
        if hours <= 720:
            cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=hours)
            df_station = df_station[df_station["run_at"] >= cutoff]

        return df_station.sort_values("run_at").drop_duplicates(
            subset=["snapshot_id"]  
        )

    except Exception:
        return pd.DataFrame()

def get_station_history(station_name: str, hours: int = 24) -> pd.DataFrame:
    # Essaie Aurora d'abord
    df = _load_from_aurora(station_name, hours)
    if not df.empty:
        return df

    # Fallback sur S3
    return _load_from_s3(station_name, hours)


def get_available_stations(hours: int = 24) -> list:
    engine = _get_engine()
    if engine is not None:
        try:
            from sqlalchemy import text
            query = text("""
                SELECT DISTINCT name FROM velib_data
                WHERE run_at >= NOW() - INTERVAL ':hours hours'
                ORDER BY name
            """).bindparams(hours=hours)
            with engine.connect() as conn:
                df = pd.read_sql(query, conn)
                return df["name"].tolist()
        except Exception:
            pass

    # Fallback S3
    s3 = _get_s3()
    if s3 is None:
        return []
    try:
        paginator = s3.get_paginator("list_objects_v2")
        dfs = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_HISTORY_PREFIX):
            for obj in page.get("Contents", []):
                response = s3.get_object(Bucket=S3_BUCKET, Key=obj["Key"])
                df = pd.read_csv(io.BytesIO(response["Body"].read()), sep=";")
                dfs.append(df)
        if not dfs:
            return []
        df_all = pd.concat(dfs, ignore_index=True)
        return sorted(df_all["name"].unique().tolist())
    except Exception:
        return []