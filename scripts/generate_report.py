import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from sqlalchemy import create_engine
import boto3
import pytz

def generate_visual_report():
    print(" Génération du rapport graphique en PDF...")

    # Connexion à la DB PostgreSQL
    engine = create_engine(os.environ["POSTGRES_URL"])

    # Récupération des données les plus récentes
    query = "SELECT * FROM velib_data ORDER BY timestamp DESC LIMIT 1000"
    df = pd.read_sql(query, engine)

    if df.empty:
        print(" Pas de données disponibles")
        return

    # Conversion UTC → heure locale Paris
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    paris_tz = pytz.timezone("Europe/Paris")
    df["timestamp_local"] = df["timestamp"].dt.tz_convert(paris_tz)

    # Horodatage du snapshot
    snapshot_time = df["timestamp_local"].max()
    snapshot_str = snapshot_time.strftime('%Y-%m-%d %H:%M')

    # Top 10 des stations à ce moment précis
    top_stations = (
        df.sort_values(by="numbikesavailable", ascending=False)
          .head(10)
          .set_index("name")["numbikesavailable"]
    )

    # Création du graphique
    plt.figure(figsize=(10, 6))
    top_stations.plot(kind='barh', color='skyblue')
    plt.xlabel("Nombre de vélos disponibles")
    plt.title(f" Top 10 stations Vélib’ – {snapshot_str} (heure locale)")
    plt.gca().invert_yaxis()
    plt.tight_layout()

    # Sauvegarde locale
    report_dir = "/opt/airflow/reports"
    os.makedirs(report_dir, exist_ok=True)
    filename = f"velib_snapshot_{snapshot_time.strftime('%Y%m%d_%H%M')}.pdf"
    filepath = os.path.join(report_dir, filename)
    plt.savefig(filepath, format='pdf')
    plt.close()
    print(f" Rapport PDF sauvegardé : {filepath}")

    # Upload vers S3
    upload_report_pdf_to_s3(filepath, filename)

def upload_report_pdf_to_s3(filepath, filename):
    print(" Upload du PDF vers S3...")

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        region_name=os.environ.get('AWS_REGION', 'eu-north-1')
    )

    bucket_name = os.environ['S3_BUCKET']
    s3_prefix = "velib/reports/"

    # Suppression des anciens fichiers PDF
    print(" Suppression des anciens fichiers PDF dans S3...")
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_prefix)
    if "Contents" in response:
        for obj in response["Contents"]:
            if obj["Key"].endswith(".pdf"):
                print(f"🗑️ Suppression : {obj['Key']}")
                s3.delete_object(Bucket=bucket_name, Key=obj["Key"])
    else:
        print(" Aucun rapport PDF à supprimer")

    s3_key = f"{s3_prefix}{filename}"
    s3.upload_file(filepath, bucket_name, s3_key)
    print(f" Rapport PDF uploadé : s3://{bucket_name}/{s3_key}")
