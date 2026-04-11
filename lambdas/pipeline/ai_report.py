"""
ai_report.py — Analyse narrative des données Vélib' via Gemini API
Commit 1 Phase 3: feat(ai): narrative PDF report with Gemini
"""
import os
import io
import logging
from datetime import datetime

import pytz
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from insert import get_latest_snapshot
from save import save_report_to_s3

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"



def _call_groq(prompt: str) -> str:
    """Appelle l'API Groq et retourne le texte généré."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY non défini — analyse IA désactivée")
        return "Analyse IA non disponible."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Erreur Groq API : {e}")
        return "Analyse IA temporairement indisponible."


def _build_prompt(stats: dict) -> str:
    """Construit le prompt pour Gemini."""
    return f"""
Tu es un expert en mobilité urbaine à Paris. Analyse ces données du réseau Vélib' 
et génère un rapport professionnel en français avec :

1. Une synthèse globale du réseau (2-3 phrases)
2. Points d'attention (stations critiques vides ou pleines)
3. Recommandations pour les usagers
4. Tendances observées

Données actuelles ({stats['snapshot_time']}) :
- Stations actives : {stats['total_stations']}
- Vélos disponibles : {stats['total_bikes']}
- Bornes disponibles : {stats['total_docks']}
- Taux de remplissage moyen : {stats['avg_ratio']:.1%}
- Stations vides : {stats['empty_stations']}
- Stations pleines : {stats['full_stations']}
- Vélos mécaniques : {stats['mechanical']}
- Vélos électriques : {stats['ebike']}
- Top 3 stations les mieux fournies : {stats['top3_full']}
- Top 3 stations les plus vides : {stats['top3_empty']}
- Heure : {stats['hour']}h, Jour : {stats['weekday']}

Sois concis, professionnel et utile pour un usager Vélib'.
Réponds uniquement en français.
"""


def generate_ai_report(snapshot_id: str) -> str:
    """
    Génère un rapport PDF enrichi avec analyse narrative Gemini.
    Remplace generate_visual_report() pour la Phase 3.
    """
    logger.info(f"Génération rapport IA snapshot {snapshot_id}...")

    df = get_latest_snapshot()
    if df.empty:
        logger.warning("Pas de données.")
        return ""

    paris_tz = pytz.timezone("Europe/Paris")
    now = datetime.now(paris_tz)
    snap_str = now.strftime("%Y-%m-%d %H:%M")

    # Calcul des stats
    df["capacity"] = df["numbikesavailable"] + df["numdocksavailable"]
    top3_full  = df.nlargest(3, "numbikesavailable")["name"].tolist()
    top3_empty = df.nsmallest(3, "numbikesavailable")["name"].tolist()

    stats = {
        "snapshot_time":  snap_str,
        "total_stations": df["station_id"].nunique(),
        "total_bikes":    int(df["numbikesavailable"].sum()),
        "total_docks":    int(df["numdocksavailable"].sum()),
        "avg_ratio":      float(df["bike_ratio"].mean()),
        "empty_stations": int(df["is_empty"].sum()),
        "full_stations":  int(df["is_full"].sum()),
        "mechanical":     int(df["mechanical"].sum()),
        "ebike":          int(df["ebike"].sum()),
        "top3_full":      ", ".join(top3_full),
        "top3_empty":     ", ".join(top3_empty),
        "hour":           now.hour,
        "weekday":        now.strftime("%A"),
    }

    # Appel Gemini
    logger.info("Appel Gemini API...")
    prompt = _build_prompt(stats)
    ai_analysis = _call_groq(prompt)
    logger.info("Analyse Gemini reçue.")

    # Génération PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()

    # Style personnalisé
    style_ai = ParagraphStyle(
        "AIAnalysis",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        spaceAfter=12,
        textColor=colors.HexColor("#2C2C2A"),
    )
    style_section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#185FA5"),
        spaceAfter=8,
        spaceBefore=16,
    )

    elements = []

    # En-tête
    elements.append(Paragraph(
        f"🚲 Rapport Vélib' — Analyse IA",
        styles["Title"]
    ))
    elements.append(Paragraph(
        f"Généré le {snap_str} · Snapshot {snapshot_id}",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 20))

    # Analyse narrative Gemini
    elements.append(Paragraph("Analyse du réseau", style_section))
    for ligne in ai_analysis.split("\n"):
        if ligne.strip():
            elements.append(Paragraph(ligne.strip(), style_ai))
    elements.append(Spacer(1, 20))

    # Stats globales
    elements.append(Paragraph("Statistiques globales", style_section))
    stats_table = [
        ["Indicateur", "Valeur"],
        ["Stations actives",        str(stats["total_stations"])],
        ["Vélos disponibles",       str(stats["total_bikes"])],
        ["Bornes disponibles",      str(stats["total_docks"])],
        ["Taux de remplissage",     f"{stats['avg_ratio']:.1%}"],
        ["Stations vides",          str(stats["empty_stations"])],
        ["Stations pleines",        str(stats["full_stations"])],
        ["Vélos mécaniques",        str(stats["mechanical"])],
        ["Vélos électriques",       str(stats["ebike"])],
    ]
    t = Table(stats_table, colWidths=[9*cm, 7*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#185FA5")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#E6F1FB")]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("PADDING",       (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 20))

    # Top stations
    elements.append(Paragraph("Top 10 stations les mieux fournies", style_section))
    top10 = df.nlargest(10, "numbikesavailable")[["name", "numbikesavailable", "ebike"]]
    data_top = [["Station", "Vélos dispo", "dont électriques"]] + [
        [row["name"], str(row["numbikesavailable"]), str(row["ebike"])]
        for _, row in top10.iterrows()
    ]
    t2 = Table(data_top, colWidths=[9*cm, 4*cm, 4*cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#1D9E75")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#E1F5EE")]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("PADDING",       (0, 0), (-1, -1), 6),
    ]))
    elements.append(t2)
    elements.append(Spacer(1, 20))

    # Top stations vides
    elements.append(Paragraph("Top 10 stations les plus vides", style_section))
    empty10 = df.nsmallest(10, "numbikesavailable")[["name", "numbikesavailable", "numdocksavailable"]]
    data_empty = [["Station", "Vélos dispo", "Bornes dispo"]] + [
        [row["name"], str(row["numbikesavailable"]), str(row["numdocksavailable"])]
        for _, row in empty10.iterrows()
    ]
    t3 = Table(data_empty, colWidths=[9*cm, 4*cm, 4*cm])
    t3.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#A32D2D")),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#FCEBEB")]),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#B4B2A9")),
        ("PADDING",       (0, 0), (-1, -1), 6),
    ]))
    elements.append(t3)

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    logger.info(f"Rapport IA généré ({len(pdf_bytes):,} bytes)")
    return save_report_to_s3(pdf_bytes, snapshot_id)