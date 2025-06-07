import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from sqlalchemy import create_engine
import boto3
import pytz

def generate_visual_report():
    print(" Génération du rapport PDF global...")

    engine = create_engine(os.environ["POSTGRES_URL"])
    query = "SELECT * FROM velib_data ORDER BY \"Derniere_Actualisation_UTC\" DESC"
    df = pd.read_sql(query, engine)

    if df.empty:
        print(" Pas de données disponibles")
        return

    # Convertir la colonne UTC en datetime si ce n’est pas déjà fait
    df["Derniere_Actualisation_UTC"] = pd.to_datetime(df["Derniere_Actualisation_UTC"], utc=True)
    paris_tz = pytz.timezone("Europe/Paris")
    df["timestamp_local"] = df["Derniere Actualisation UTC"].dt.tz_convert(paris_tz)

    snapshot_time = df["timestamp_local"].max()
    snapshot_str = snapshot_time.strftime('%Y-%m-%d %H:%M')
    timestamp_suffix = snapshot_time.strftime('%Y%m%d_%H%M')

    report_dir = "/opt/airflow/reports"
    os.makedirs(report_dir, exist_ok=True)
    pdf_path = os.path.join(report_dir, "report.pdf")

    with PdfPages(pdf_path) as pdf:
        # --- Graphe 1 : Top 10 stations les mieux fournies ---
        top_stations = (
            df.sort_values(by="numbikesavailable", ascending=False)
              .head(10)
              .set_index("name")["numbikesavailable"]
        )
        plt.figure(figsize=(10, 6))
        top_stations.plot(kind='barh', color='skyblue')
        plt.xlabel("Nombre de vélos disponibles")
        plt.title(f" Top 10 stations Vélib’ – {snapshot_str} (heure locale)")
        plt.gca().invert_yaxis()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # --- Graphe 2 : Stations les plus vides ---
        top_empty = (
            df.sort_values(by="numbikesavailable", ascending=True)
              .head(10)
              .set_index("name")["numbikesavailable"]
        )
        plt.figure(figsize=(10, 6))
        top_empty.plot(kind='barh', color='lightcoral')
        plt.xlabel("Nombre de vélos disponibles")
        plt.title(f" Stations les plus vides – {snapshot_str}")
        plt.grid(axis='x')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # --- Graphe 3 : Répartition des états des stations ---
        status_counts = pd.Series({
            "Vides (0 vélo)": df["is_empty"].sum(),
            "Pleines (0 dock)": df["is_full"].sum(),
            "Partielles": len(df) - df["is_empty"].sum() - df["is_full"].sum()
        })
        plt.figure(figsize=(6, 6))
        status_counts.plot(kind='pie', autopct='%1.1f%%', startangle=90)
        plt.title(f" Répartition des stations – {snapshot_str}")
        plt.ylabel("")
        plt.tight_layout()
        pdf.savefig()
        plt.close()

        # --- Graphe 4 : Plus grandes stations ---
        df["capacity"] = df["numbikesavailable"] + df["numdocksavailable"]
        top_capacity = (
            df.sort_values(by="capacity", ascending=False)
              .head(10)
              .set_index("name")["capacity"]
        )
        plt.figure(figsize=(10, 6))
        top_capacity.plot(kind='barh', color='orange')
        plt.xlabel("Capacité totale (vélos + docks)")
        plt.title(f"🏗️ Plus grandes stations – {snapshot_str}")
        plt.gca().invert_yaxis()
        plt.tight_layout()
        pdf.savefig()
        plt.close()

    print(f" Rapport global PDF généré : {pdf_path}")
    upload_report_pdf_to_s3(pdf_path, "report.pdf")

def upload_report_pdf_to_s3(filepath, filename):
    print(f"☁️ Upload du fichier : {filename} ...")
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
        region_name=os.environ.get('AWS_REGION', 'eu-north-1')
    )
    bucket_name = os.environ['S3_BUCKET']
    s3_prefix = "velib/reports/"
    s3_key = f"{s3_prefix}{filename}"
    s3.upload_file(filepath, bucket_name, s3_key)
    print(f" Upload terminé : s3://{bucket_name}/{s3_key}")
