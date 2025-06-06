import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from sqlalchemy import create_engine
import boto3

def generate_visual_report():
    print(" Génération du rapport graphique en PDF...")

    # Connexion à la DB PostgreSQL
    engine = create_engine(os.environ["POSTGRES_URL"])
    today = datetime.now().date()

    # Requête : moyenne par station aujourd’hui
    query = f"SELECT * FROM velib_data WHERE date = '{today}'"
    df = pd.read_sql(query, engine)

    if df.empty:
        print(" Pas de données pour aujourd’hui")
        return

    # Groupement
    top_stations = (
        df.groupby("name")["numbikesavailable"]
        .mean()
        .sort_values(ascending=False)
        .head(10)
    )

    # Création du graphique
    plt.figure(figsize=(10, 6))
    top_stations.plot(kind='barh', color='skyblue')
    plt.xlabel("Nombre moyen de vélos")
    plt.title("🚲 Top 10 stations Vélib’ – " + str(today))
    plt.gca().invert_yaxis()
    plt.tight_layout()

    #  Sauvegarde locale
    report_dir = "/opt/airflow/reports"
    os.makedirs(report_dir, exist_ok=True)
    filename = f"velib_graph_{today}.pdf"
    filepath = os.path.join(report_dir, filename)
    plt.savefig(filepath, format='pdf')
    plt.close()
    print(f"✅ Rapport PDF sauvegardé : {filepath}")

    #  Upload vers S3
    upload_report_pdf_to_s3(filepath, filename)

def upload_report_pdf_to_s3(filepath, filename):
    print("☁️ Upload du PDF vers S3...")

    # Préparation du client S3
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        region_name=os.environ.get('AWS_REGION', 'eu-north-1')
    )

    bucket_name = os.environ['S3_BUCKET']
    s3_prefix = "velib/reports/"

    # Suppression des anciens rapports
    print(" Suppression des anciens fichiers PDF dans S3...")
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_prefix)
    if "Contents" in response:
        for obj in response["Contents"]:
            if obj["Key"].endswith(".pdf"):
                print(f"🗑️ Suppression : {obj['Key']}")
                s3.delete_object(Bucket=bucket_name, Key=obj["Key"])
    else:
        print("✅ Aucun rapport PDF à supprimer")

    # Upload du nouveau fichier PDF
    s3_key = f"{s3_prefix}{filename}"
    s3.upload_file(filepath, bucket_name, s3_key)
    print(f"✅ Rapport PDF uploadé : s3://{bucket_name}/{s3_key}")
