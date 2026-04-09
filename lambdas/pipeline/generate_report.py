import io
import logging
import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
import pytz

from insert import get_latest_snapshot
from save import save_report_to_s3

logger = logging.getLogger(__name__)


def generate_visual_report(snapshot_id: str) -> str:
    logger.info(f"Génération rapport PDF snapshot {snapshot_id}...")

    df = get_latest_snapshot()
    if df.empty:
        logger.warning("Pas de données pour le rapport.")
        return ""

    df.columns = [col.strip() for col in df.columns]
    paris_tz   = pytz.timezone("Europe/Paris")
    snap_str   = datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M")

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:

        # Top 10 mieux fournies
        top = df.sort_values("numbikesavailable", ascending=False).head(10).set_index("name")["numbikesavailable"]
        fig, ax = plt.subplots(figsize=(10, 6))
        top.plot(kind="barh", color="#5DCAA5", ax=ax)
        ax.set_title(f"Top 10 stations — {snap_str}")
        ax.invert_yaxis(); plt.tight_layout()
        pdf.savefig(fig); plt.close(fig)

        # Top 10 plus vides
        empty = df.sort_values("numbikesavailable").head(10).set_index("name")["numbikesavailable"]
        fig, ax = plt.subplots(figsize=(10, 6))
        empty.plot(kind="barh", color="#F09995", ax=ax)
        ax.set_title(f"Stations les plus vides — {snap_str}")
        ax.invert_yaxis(); plt.tight_layout()
        pdf.savefig(fig); plt.close(fig)

        # Répartition états
        status = pd.Series({
            "Vides":     int(df["is_empty"].sum()),
            "Pleines":   int(df["is_full"].sum()),
            "Partielles": len(df) - int(df["is_empty"].sum()) - int(df["is_full"].sum()),
        })
        fig, ax = plt.subplots(figsize=(6, 6))
        status.plot(kind="pie", autopct="%1.1f%%", startangle=90,
                    colors=["#F09995", "#5DCAA5", "#FAC775"], ax=ax)
        ax.set_title(f"Répartition — {snap_str}"); ax.set_ylabel("")
        plt.tight_layout(); pdf.savefig(fig); plt.close(fig)

        # Stats globales
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.05, 0.85, (
            f"Statistiques — {snap_str}\n\n"
            f"Stations  : {df['station_id'].nunique()}\n"
            f"Vélos     : {int(df['numbikesavailable'].sum()):,}\n"
            f"Bornes    : {int(df['numdocksavailable'].sum()):,}\n"
            f"Remplissage moyen : {df['bike_ratio'].mean():.1%}\n"
            f"Snapshot  : {snapshot_id}"
        ), fontsize=13, va="top", fontfamily="monospace", transform=ax.transAxes)
        ax.axis("off"); pdf.savefig(fig); plt.close(fig)

    pdf_bytes = buf.getvalue()
    logger.info(f"PDF généré ({len(pdf_bytes):,} bytes)")
    return save_report_to_s3(pdf_bytes, snapshot_id)