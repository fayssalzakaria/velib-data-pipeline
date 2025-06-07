import os
from datetime import datetime
import boto3
import pytz
import pandas as pd  # ← assure-toi que pandas est bien importé ici

def save_csv(df):
    # Chemin local
    output_dir = "/opt/airflow/data"
    os.makedirs(output_dir, exist_ok=True)

    # Nom de fichier basé sur la date
    paris_tz = pytz.timezone("Europe/Paris")
    timestamp = datetime.now(paris_tz)
    heure_locale_str = timestamp.strftime("%Y%m%d_%H%M")
    filename = f"velib_{heure_locale_str}.csv"

    filepath = os.path.join(output_dir, filename)

    # Formatage en texte lisible
    df["Derniere_Actualisation_UTC"] = df["Derniere_Actualisation_UTC"].dt.strftime('%Y-%m-%d %H:%M:%S')
    df["Derniere_Actualisation_Heure_locale"] = df["Derniere_Actualisation_Heure_locale"].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Sauvegarde locale
    df.to_csv(filepath, index=False, sep=';')
    print(f"✅ Données sauvegardées localement : {filepath}")

    # Préparation S3
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        region_name=os.environ.get('AWS_REGION', 'eu-north-1')
    )
    bucket_name = os.environ['S3_BUCKET']
    s3_prefix = "velib/"

    # Suppression des anciens fichiers S3
    print("🧹 Suppression des anciens fichiers S3...")
    response = s3.list_objects_v2(Bucket=bucket_name, Prefix=s3_prefix)
    if "Contents" in response:
        for obj in response["Contents"]:
            print(f"🗑️ Suppression : {obj['Key']}")
            s3.delete_object(Bucket=bucket_name, Key=obj["Key"])
    else:
        print("ℹ️ Aucun fichier à supprimer")

    # Upload du fichier
    s3.upload_file(filepath, bucket_name, f"{s3_prefix}{filename}")
    print(f"✅ Nouveau fichier uploadé sur S3 : s3://{bucket_name}/{s3_prefix}{filename}")
