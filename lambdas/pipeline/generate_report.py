import io
import logging
import os
from datetime import datetime

import pytz
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from insert import get_latest_snapshot
from save import save_report_to_s3

logger = logging.getLogger(__name__)


def generate_visual_report(snapshot_id: str) -> str:
    logger.info(f"Génération rapport PDF snapshot {snapshot_id}...")

    df = get_latest_snapshot()
    if df.empty:
        logger.warning("Pas de données.")
        return ""

    paris_tz = pytz.timezone("Europe/Paris")
    snap_str = datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Titre
    elements.append(Paragraph(f"Rapport Vélib — {snap_str}", styles["Title"]))
    elements.append(Spacer(1, 20))

    # Stats globales
    elements.append(Paragraph("Statistiques globales", styles["Heading2"]))
    stats = [
        ["Stations actives", str(df["station_id"].nunique())],
        ["Vélos disponibles", str(int(df["numbikesavailable"].sum()))],
        ["Bornes disponibles", str(int(df["numdocksavailable"].sum()))],
        ["Taux remplissage moyen", f"{df['bike_ratio'].mean():.1%}"],
        ["Stations vides", str(int(df["is_empty"].sum()))],
        ["Stations pleines", str(int(df["is_full"].sum()))],
        ["Snapshot ID", snapshot_id],
    ]
    t = Table(stats, colWidths=[250, 200])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1D9E75")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1EFE8")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 30))

    # Top 10 stations mieux fournies
    elements.append(Paragraph("Top 10 stations les mieux fournies", styles["Heading2"]))
    top10 = df.nlargest(10, "numbikesavailable")[["name", "numbikesavailable", "numdocksavailable"]]
    data = [["Station", "Vélos dispo", "Bornes dispo"]] + top10.values.tolist()
    t2 = Table(data, colWidths=[250, 100, 100])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#185FA5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E6F1FB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 30))

    # Top 10 stations les plus vides
    elements.append(Paragraph("Top 10 stations les plus vides", styles["Heading2"]))
    empty10 = df.nsmallest(10, "numbikesavailable")[["name", "numbikesavailable", "numdocksavailable"]]
    data2 = [["Station", "Vélos dispo", "Bornes dispo"]] + empty10.values.tolist()
    t3 = Table(data2, colWidths=[250, 100, 100])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#A32D2D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FCEBEB")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t3)

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    logger.info(f"PDF généré ({len(pdf_bytes):,} bytes)")
    return save_report_to_s3(pdf_bytes, snapshot_id)
