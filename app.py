import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import boto3
import os
import io
from datetime import datetime
import pytz

#config

st.set_page_config(
    page_title="Vélib' Dashboard",
    page_icon="🚲",
    layout="wide",
)

S3_BUCKET = os.environ.get("S3_BUCKET", "velib-pipeline-prod-data")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
API_ENDPOINT = os.environ.get("API_ENDPOINT", "")

#Fonctions
@st.cache_data(ttl=300)
def load_latest_csv():
    """Charge le dernier CSV depuis S3."""
    try:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
        paginator = s3.get_paginator("list_objects_v2")
        latest_key = None
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="velib/data/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".csv"):
                    if latest_key is None or key > latest_key:
                        latest_key = key

        if not latest_key:
            return None

        obj = s3.get_object(Bucket=S3_BUCKET, Key=latest_key)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()), sep=";")
        return df
    except Exception as e:
        st.error(f"Erreur chargement données : {e}")
        return None


def ask_groq(question: str, context: str) -> str:
    """Pose une question à Groq avec le contexte des données."""
    if not GROQ_API_KEY:
        return "Clé Groq non configurée."

    prompt = f"""
Tu es un expert en mobilité urbaine à Paris spécialisé dans le réseau Vélib'.
Réponds en français de manière concise et utile.

Données actuelles du réseau :
{context}

Question de l'utilisateur : {question}

Réponds directement sans introduction.
"""

    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erreur Groq : {e}"



# HEADER

st.title(" Vélib' Dashboard Paris")
st.caption(f"Données en temps réel — Réseau Vélib' Métropole")

df = load_latest_csv()

if df is None:
    st.error("Impossible de charger les données. Vérifiez la connexion S3.")
    st.stop()

# Stats globales
paris_tz = pytz.timezone("Europe/Paris")
now = datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Stations actives", df["station_id"].nunique())
col2.metric("Vélos disponibles", f"{int(df['numbikesavailable'].sum()):,}")
col3.metric("Bornes disponibles", f"{int(df['numdocksavailable'].sum()):,}")
col4.metric("Stations vides", int(df["is_empty"].sum()))
col5.metric("Taux de remplissage", f"{df['bike_ratio'].mean():.1%}")

st.divider()

# CARTE


st.subheader(" Carte des stations")

if "coordonnees_geo" in df.columns:
    try:
        df[["lat", "lon"]] = df["coordonnees_geo"].str.split(",", expand=True).astype(float)
        map_df = df[["name", "lat", "lon", "numbikesavailable", "numdocksavailable"]].dropna()
        st.map(map_df, latitude="lat", longitude="lon", size="numbikesavailable")
    except Exception:
        st.info("Coordonnées non disponibles dans ce snapshot.")
else:
    st.info("Les coordonnées géographiques ne sont pas dans les données actuelles.")

st.divider()


# GRAPHIQUES


col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏆 Top 10 stations les mieux fournies")
    top10 = df.nlargest(10, "numbikesavailable")[["name", "numbikesavailable", "ebike", "mechanical"]]
    fig = px.bar(
        top10,
        x="numbikesavailable",
        y="name",
        orientation="h",
        color="ebike",
        color_continuous_scale="teal",
        labels={"numbikesavailable": "Vélos dispo", "name": "Station", "ebike": "Électriques"},
    )
    fig.update_layout(yaxis={"autorange": "reversed"}, height=400)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader(" Top 10 stations les plus vides")
    empty10 = df.nsmallest(10, "numbikesavailable")[["name", "numbikesavailable", "numdocksavailable"]]
    fig2 = px.bar(
        empty10,
        x="numbikesavailable",
        y="name",
        orientation="h",
        color="numbikesavailable",
        color_continuous_scale="reds",
        labels={"numbikesavailable": "Vélos dispo", "name": "Station"},
    )
    fig2.update_layout(yaxis={"autorange": "reversed"}, height=400)
    st.plotly_chart(fig2, use_container_width=True)

# Répartition mécanique / électrique
st.subheader(" Répartition des types de vélos")
col_a, col_b = st.columns(2)

with col_a:
    bike_data = pd.DataFrame({
        "Type": ["Mécaniques", "Électriques"],
        "Nombre": [int(df["mechanical"].sum()), int(df["ebike"].sum())]
    })
    fig3 = px.pie(bike_data, values="Nombre", names="Type",
                  color_discrete_sequence=["#185FA5", "#1D9E75"])
    st.plotly_chart(fig3, use_container_width=True)

with col_b:
    status_data = pd.DataFrame({
        "État": ["Vides", "Pleines", "Partielles"],
        "Nombre": [
            int(df["is_empty"].sum()),
            int(df["is_full"].sum()),
            len(df) - int(df["is_empty"].sum()) - int(df["is_full"].sum())
        ]
    })
    fig4 = px.pie(status_data, values="Nombre", names="État",
                  color_discrete_sequence=["#A32D2D", "#1D9E75", "#EF9F27"])
    st.plotly_chart(fig4, use_container_width=True)

st.divider()

# CHATBOT

st.subheader("💬 Ask Vélib Data — Posez vos questions")

context = f"""
- Stations actives : {df['station_id'].nunique()}
- Vélos disponibles : {int(df['numbikesavailable'].sum())}
- Bornes disponibles : {int(df['numdocksavailable'].sum())}
- Taux de remplissage moyen : {df['bike_ratio'].mean():.1%}
- Stations vides : {int(df['is_empty'].sum())}
- Stations pleines : {int(df['is_full'].sum())}
- Vélos mécaniques : {int(df['mechanical'].sum())}
- Vélos électriques : {int(df['ebike'].sum())}
- Top 3 mieux fournies : {', '.join(df.nlargest(3, 'numbikesavailable')['name'].tolist())}
- Top 3 plus vides : {', '.join(df.nsmallest(3, 'numbikesavailable')['name'].tolist())}
"""

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if question := st.chat_input("Ex: Quelle station a le plus de vélos électriques ?"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours..."):
            response = ask_groq(question, context)
        st.write(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

st.divider()

# TELECHARGEMENTS

st.subheader(" Téléchargements")

col_dl1, col_dl2 = st.columns(2)

with col_dl1:
    if API_ENDPOINT:
        st.link_button(
            " Télécharger le rapport PDF",
            f"{API_ENDPOINT}/download/report",
            use_container_width=True,
        )

with col_dl2:
    csv_bytes = df.to_csv(index=False, sep=";").encode("utf-8")
    st.download_button(
        " Télécharger le CSV",
        data=csv_bytes,
        file_name="velib_latest.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption(f"Dernière mise à jour : {now}")