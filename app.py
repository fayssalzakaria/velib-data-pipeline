import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
import io
import pytz
from datetime import datetime

st.set_page_config(
    page_title="Vélib' Dashboard",
    page_icon="",
    layout="wide",
)

# SIDEBAR — Configuration

st.sidebar.title("Configuration")
source = st.sidebar.radio(
    "Source des donnees",
    ["API Velib (temps reel)", "AWS S3 (dernier snapshot)"],
    index=0,
)
st.sidebar.divider()

st.sidebar.subheader("Filtres")

filtre_type = st.sidebar.selectbox(
    "Type de velo",
    ["Tous", "Mecaniques uniquement", "Electriques uniquement"]
)

filtre_etat = st.sidebar.multiselect(
    "Etat des stations",
    ["Disponibles", "Vides", "Pleines"],
    default=["Disponibles", "Vides", "Pleines"]
)

filtre_min_velos = st.sidebar.slider(
    "Minimum de velos disponibles",
    min_value=0,
    max_value=50,
    value=0,
)

st.sidebar.divider()
sidebar_count = st.sidebar.empty()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
API_ENDPOINT = os.environ.get("API_ENDPOINT", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "velib-pipeline-prod-data")


# CHARGEMENT DES DONNEES
@st.cache_data(ttl=300)
def load_from_api():
    """Charge depuis l'API Vélib' opendata.paris.fr"""
    all_records = []
    for start in range(0, 2000, 1000):
        params = {
            "dataset": "velib-disponibilite-en-temps-reel",
            "rows": 1000,
            "start": start,
        }
        r = requests.get(
            "https://opendata.paris.fr/api/records/1.0/search/",
            params=params,
            timeout=30,
        )
        records = r.json().get("records", [])
        all_records.extend(records)
        if len(records) < 1000:
            break

    rows = []
    for rec in all_records:
        f = rec.get("fields", {})
        rows.append({
            "station_id":        f.get("stationcode"),
            "name":              f.get("name", "").upper(),
            "numbikesavailable": int(f.get("numbikesavailable", 0)),
            "mechanical":        int(f.get("mechanical", 0)),
            "ebike":             int(f.get("ebike", 0)),
            "numdocksavailable": int(f.get("numdocksavailable", 0)),
            "is_full":           f.get("numdocksavailable", 1) == 0,
            "is_empty":          f.get("numbikesavailable", 1) == 0,
            "bike_ratio":        round(
                int(f.get("numbikesavailable", 0)) /
                max(int(f.get("numbikesavailable", 0)) + int(f.get("numdocksavailable", 0)), 1),
                2
            ),
            "lat": f.get("coordonnees_geo", [None, None])[0] if f.get("coordonnees_geo") else None,
            "lon": f.get("coordonnees_geo", [None, None])[1] if f.get("coordonnees_geo") else None,
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_from_s3():
    """Charge depuis AWS S3"""
    try:
        import boto3
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
            return None, "Aucun fichier CSV dans S3."
        obj = s3.get_object(Bucket=S3_BUCKET, Key=latest_key)
        df = pd.read_csv(io.BytesIO(obj["Body"].read()), sep=";")
        return df, latest_key
    except Exception as e:
        return None, str(e)


def ask_groq(question: str, context: str) -> str:
    if not GROQ_API_KEY:
        return "Clé Groq non configurée dans les secrets Streamlit."
    try:
        response = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": f"""
Tu es un expert en mobilité urbaine à Paris spécialisé dans le réseau Vélib'.
Réponds en français de manière concise et utile.

Données actuelles :
{context}

Question : {question}
"""}],
                "max_tokens": 500,
                "temperature": 0.7,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erreur Groq : {e}"

# CHARGEMENT

st.title(" Vélib' Dashboard Paris")

if source == "API Vélib' (temps réel)":
    with st.spinner("Chargement depuis l'API Vélib'..."):
        df = load_from_api()
    st.sidebar.success(f"{len(df)} stations chargées")
    st.caption("Source : opendata.paris.fr — temps réel")
else:
    with st.spinner("Chargement depuis AWS S3..."):
        df, info = load_from_s3()
    if df is None:
        st.error(f"Erreur S3 : {info}")
        st.info("Basculez sur 'API Vélib' (temps réel)' dans la sidebar.")
        st.stop()
    st.sidebar.success(f"{len(df)} stations chargées")
    st.caption(f"Source : AWS S3 — {info}")

if df is None or df.empty:
    st.error("Aucune donnée disponible.")
    st.stop()
df_filtered = df.copy()

if filtre_type == "Mecaniques uniquement":
    df_filtered = df_filtered[df_filtered["mechanical"] > 0]
elif filtre_type == "Electriques uniquement":
    df_filtered = df_filtered[df_filtered["ebike"] > 0]

etats_selectionnes = []
if "Vides" in filtre_etat:
    etats_selectionnes.append(df_filtered["is_empty"] == True)
if "Pleines" in filtre_etat:
    etats_selectionnes.append(df_filtered["is_full"] == True)
if "Disponibles" in filtre_etat:
    etats_selectionnes.append(
        (df_filtered["is_empty"] == False) & (df_filtered["is_full"] == False)
    )

if etats_selectionnes:
    import functools
    mask = functools.reduce(lambda a, b: a | b, etats_selectionnes)
    df_filtered = df_filtered[mask]

df_filtered = df_filtered[df_filtered["numbikesavailable"] >= filtre_min_velos]
sidebar_count.info(f"{len(df_filtered)} stations apres filtres")


# METRICS


paris_tz = pytz.timezone("Europe/Paris")
now = datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Stations", df_filtered["station_id"].nunique())
col2.metric("Velos dispo", f"{int(df_filtered['numbikesavailable'].sum()):,}")
col3.metric("Bornes dispo", f"{int(df_filtered['numdocksavailable'].sum()):,}")
col4.metric("Stations vides", int(df_filtered["is_empty"].sum()))
col5.metric("Remplissage", f"{df_filtered['bike_ratio'].mean():.1%}")
st.divider()

st.subheader("Recherche de station")

search = st.text_input("Nom de la station", placeholder="Ex: Bastille, Nation, Republique...")

if search:
    results = df[df["name"].str.contains(search.upper(), na=False)]
    if results.empty:
        st.warning(f"Aucune station trouvee pour '{search}'")
    else:
        for _, row in results.iterrows():
            with st.expander(f"{row['name']}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Velos dispo", int(row["numbikesavailable"]))
                c2.metric("Dont electriques", int(row["ebike"]))
                c3.metric("Bornes dispo", int(row["numdocksavailable"]))
                c4.metric("Remplissage", f"{row['bike_ratio']:.0%}")

                if row["is_empty"]:
                    st.error("Station vide")
                elif row["is_full"]:
                    st.warning("Station pleine")
                else:
                    st.success("Station disponible")
#carte

st.subheader(" Carte des stations")

if "lat" in df.columns and df["lat"].notna().any():
    map_df = df[["name", "lat", "lon", "numbikesavailable"]].dropna()
    st.map(map_df, latitude="lat", longitude="lon", size="numbikesavailable", color="#1D9E75")
else:
    st.info("Coordonnées non disponibles pour ce snapshot.")

st.divider()

#GRAPHIQUES

col_left, col_right = st.columns(2)

with col_left:
    st.subheader(" Top 10 mieux fournies")
    top10 = df.nlargest(10, "numbikesavailable")[["name", "numbikesavailable", "ebike"]]
    fig = px.bar(
        top10, x="numbikesavailable", y="name", orientation="h",
        color="ebike", color_continuous_scale="teal",
        labels={"numbikesavailable": "Vélos", "name": "Station", "ebike": "Électriques"},
    )
    fig.update_layout(yaxis={"autorange": "reversed"}, height=400)
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.subheader(" Top 10 plus vides")
    empty10 = df.nsmallest(10, "numbikesavailable")[["name", "numbikesavailable"]]
    fig2 = px.bar(
        empty10, x="numbikesavailable", y="name", orientation="h",
        color="numbikesavailable", color_continuous_scale="reds",
        labels={"numbikesavailable": "Vélos", "name": "Station"},
    )
    fig2.update_layout(yaxis={"autorange": "reversed"}, height=400)
    st.plotly_chart(fig2, use_container_width=True)

col_a, col_b = st.columns(2)

with col_a:
    st.subheader(" Types de vélos")
    bike_data = pd.DataFrame({
        "Type": ["Mécaniques", "Électriques"],
        "Nombre": [int(df["mechanical"].sum()), int(df["ebike"].sum())]
    })
    fig3 = px.pie(bike_data, values="Nombre", names="Type",
                  color_discrete_sequence=["#185FA5", "#1D9E75"])
    st.plotly_chart(fig3, use_container_width=True)

with col_b:
    st.subheader(" État des stations")
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

#CHATBOT

st.subheader(" Ask Vélib Data")

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
            " Rapport PDF (AWS)",
            f"{API_ENDPOINT}/download/report",
            use_container_width=True,
        )
    else:
        st.info("API_ENDPOINT non configuré")

with col_dl2:
    csv_bytes = df.to_csv(index=False, sep=";").encode("utf-8")
    st.download_button(
        " Télécharger CSV",
        data=csv_bytes,
        file_name="velib_latest.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption(f"Dernière mise à jour : {now}")