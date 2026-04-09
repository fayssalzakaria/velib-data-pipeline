import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
_cache: dict = {}


def _get_secret(secret_name: str) -> dict:
    if secret_name in _cache:
        return _cache[secret_name]
    client = boto3.client("secretsmanager",
                          region_name=os.environ.get("AWS_REGION", "eu-north-1"))
    try:
        response = client.get_secret_value(SecretId=secret_name)
        secret   = json.loads(response["SecretString"])
        _cache[secret_name] = secret
        return secret
    except ClientError as e:
        logger.error(f"Impossible de récupérer le secret {secret_name} : {e}")
        raise


def get_db_url() -> str:
    if url := os.environ.get("POSTGRES_URL"):
        return url
    secret_name = os.environ.get("DB_SECRET_NAME", "velib-pipeline-prod/db-credentials")
    creds = _get_secret(secret_name)
    return (
        f"postgresql://{creds['username']}:{creds['password']}"
        f"@{creds['host']}:{creds.get('port', 5432)}/{creds['dbname']}"
    )