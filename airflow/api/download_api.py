import os
import boto3
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.environ.get("AWS_REGION", "eu-north-1")
S3_BUCKET = os.environ["S3_BUCKET"]

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION
)

DOWNLOAD_DIR = "/tmp"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

@router.get("/report")
def download_report():
    key = "velib/reports/report.pdf"
    local_path = os.path.join(DOWNLOAD_DIR, "report.pdf")
    try:
        s3.download_file(S3_BUCKET, key, local_path)
        return FileResponse(local_path, filename="report.pdf", media_type="application/pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur téléchargement rapport : {e}")

@router.get("/csv")
def download_csv():
    try:
        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix="velib/")
        csv_files = sorted([
            obj["Key"] for obj in response.get("Contents", [])
            if obj["Key"].endswith(".csv")
        ], reverse=True)

        if not csv_files:
            raise Exception("Aucun fichier CSV trouvé.")

        latest_key = csv_files[0]
        local_path = os.path.join(DOWNLOAD_DIR, "latest.csv")
        s3.download_file(S3_BUCKET, latest_key, local_path)
        return FileResponse(local_path, filename="velib_latest.csv", media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur téléchargement CSV : {e}")
