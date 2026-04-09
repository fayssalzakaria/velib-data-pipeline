import base64
import json
import logging
import os

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ["S3_BUCKET"]
s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "eu-north-1"))


def _response(status, body, content_type, is_binary=False):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": content_type,
            "Access-Control-Allow-Origin": "*",
        },
        "body": base64.b64encode(body).decode() if is_binary else body,
        "isBase64Encoded": is_binary,
    }


def _error(status, message):
    return _response(status, json.dumps({"error": message}), "application/json")


def _get_latest_csv_key():
    paginator = s3.get_paginator("list_objects_v2")
    latest_key = None
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="velib/data/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".csv"):
                if latest_key is None or key > latest_key:
                    latest_key = key
    return latest_key


def _handle_report():
    try:
        obj = s3.get_object(Bucket=S3_BUCKET, Key="velib/reports/latest.pdf")
        return {
            **_response(200, obj["Body"].read(), "application/pdf", is_binary=True),
            "headers": {
                "Content-Type": "application/pdf",
                "Content-Disposition": "attachment; filename=\"velib_report.pdf\"",
                "Access-Control-Allow-Origin": "*",
            }
        }
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return _error(404, "Aucun rapport disponible.")
        return _error(500, str(e))


def _handle_csv():
    key = _get_latest_csv_key()
    if not key:
        return _error(404, "Aucun CSV disponible.")
    try:
        obj      = s3.get_object(Bucket=S3_BUCKET, Key=key)
        filename = key.split("/")[-1]
        return {
            **_response(200, obj["Body"].read(), "text/csv", is_binary=True),
            "headers": {
                "Content-Type": "text/csv; charset=utf-8",
                "Content-Disposition": f"attachment; filename=\"{filename}\"",
                "Access-Control-Allow-Origin": "*",
            }
        }
    except ClientError as e:
        return _error(500, str(e))


def _handle_health():
    try:
        s3.head_bucket(Bucket=S3_BUCKET)
        return _response(200, json.dumps({"status": "ok"}), "application/json")
    except ClientError as e:
        return _error(503, str(e))


ROUTES = {
    "GET /download/report": _handle_report,
    "GET /download/csv":    _handle_csv,
    "GET /health":          _handle_health,
}


def lambda_handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    path   = event.get("rawPath", "/")
    route  = f"{method} {path}"
    logger.info(f"Request : {route}")
    handler_fn = ROUTES.get(route)
    if handler_fn is None:
        return _error(404, f"Route inconnue : {route}")
    return handler_fn()