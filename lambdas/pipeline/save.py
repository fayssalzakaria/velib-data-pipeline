import io
import logging
import os
from datetime import datetime, timezone

import boto3
import pandas as pd
import pytz

logger = logging.getLogger(__name__)

def _get_s3():
    return boto3.client(
        "s3",
        region_name=os.environ.get("AWS_REGION", "eu-north-1"),
    )

def save_to_s3(df: pd.DataFrame, snapshot_id: str) -> str:
    s3     = _get_s3()
    bucket = os.environ["S3_BUCKET"]

    paris_tz  = pytz.timezone("Europe/Paris")
    now       = datetime.now(paris_tz)

    s3_key = (
        f"velib/data/"
        f"year={now.strftime('%Y')}/"
        f"month={now.strftime('%m')}/"
        f"day={now.strftime('%d')}/"
        f"velib_{snapshot_id}.csv"
    )

    df_export = df.copy()
    for col in ["Derniere_Actualisation_UTC", "Derniere_Actualisation_Heure_locale"]:
        if pd.api.types.is_datetime64_any_dtype(df_export[col]):
            df_export[col] = df_export[col].dt.strftime("%Y-%m-%d %H:%M:%S")

    buf = io.StringIO()
    df_export.to_csv(buf, index=False, sep=";")

    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=buf.getvalue().encode("utf-8"),
        ContentType="text/csv; charset=utf-8",
        Metadata={"snapshot_id": snapshot_id},
    )
    logger.info(f"CSV uploadé : s3://{bucket}/{s3_key}")
    return s3_key


def save_report_to_s3(pdf_bytes: bytes, snapshot_id: str) -> str:
    s3     = _get_s3()
    bucket = os.environ["S3_BUCKET"]

    paris_tz = pytz.timezone("Europe/Paris")
    now      = datetime.now(paris_tz)

    versioned_key = (
        f"velib/reports/"
        f"year={now.strftime('%Y')}/"
        f"month={now.strftime('%m')}/"
        f"day={now.strftime('%d')}/"
        f"report_{snapshot_id}.pdf"
    )

    s3.put_object(
        Bucket=bucket, Key=versioned_key,
        Body=pdf_bytes, ContentType="application/pdf",
        Metadata={"snapshot_id": snapshot_id},
    )
    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": versioned_key},
        Key="velib/reports/latest.pdf",
    )
    logger.info(f"PDF uploadé : s3://{bucket}/{versioned_key}")
    return versioned_key
