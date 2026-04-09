import json
import os
import logging
import traceback
from datetime import datetime

import boto3

from fetch import fetch_data
from transform import transform_data
from insert import insert_into_db
from save import save_to_s3
from generate_report import generate_visual_report

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns", region_name=os.environ.get("AWS_REGION", "eu-north-1"))


def _notify_failure(step: str, error: str, snapshot_id: str):
    topic_arn = os.environ.get("SNS_ALERT_TOPIC_ARN")
    if not topic_arn:
        logger.warning("SNS_ALERT_TOPIC_ARN non défini, pas d'alerte envoyée.")
        return
    try:
        sns.publish(
            TopicArn=topic_arn,
            Subject=f"[Vélib Pipeline] ÉCHEC — étape: {step}",
            Message=(
                f"snapshot_id : {snapshot_id}\n"
                f"étape       : {step}\n"
                f"erreur      : {error}\n"
                f"timestamp   : {datetime.utcnow().isoformat()}Z"
            ),
        )
    except Exception as e:
        logger.error(f"Impossible d'envoyer l'alerte SNS : {e}")


def lambda_handler(event, context):
    snapshot_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    logger.info(f"=== Démarrage pipeline Vélib — snapshot {snapshot_id} ===")

    csv_s3_key = None
    pdf_s3_key = None

    try:
        logger.info("→ [1/5] fetch_data")
        raw_data = fetch_data()
        logger.info(f"   {len(raw_data.get('records', []))} stations récupérées")

        logger.info("→ [2/5] transform_data")
        df = transform_data(raw_data)
        logger.info(f"   {len(df)} lignes transformées")

        logger.info("→ [3/5] insert_into_db")
        insert_into_db(df, snapshot_id)

        logger.info("→ [4/5] save_to_s3")
        csv_s3_key = save_to_s3(df, snapshot_id)
        logger.info(f"   CSV uploadé : {csv_s3_key}")

        logger.info("→ [5/5] generate_visual_report")
        pdf_s3_key = generate_visual_report(snapshot_id)
        logger.info(f"   Rapport uploadé : {pdf_s3_key}")

    except Exception as exc:
        tb = traceback.format_exc()
        logger.error(f"PIPELINE FAILED :\n{tb}")
        _notify_failure(step="pipeline", error=str(exc), snapshot_id=snapshot_id)
        raise

    result = {
        "statusCode": 200,
        "snapshot_id": snapshot_id,
        "csv_s3_key": csv_s3_key,
        "pdf_s3_key": pdf_s3_key,
        "stations_count": len(df),
    }
    logger.info(f"=== Pipeline terminé : {json.dumps(result)} ===")
    return result