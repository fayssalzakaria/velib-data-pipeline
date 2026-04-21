import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

from chatbot import ask_groq, build_context
from config import API_ENDPOINT, PARIS_TIMEZONE, SOURCE_API, SOURCE_S3
from history import get_station_history, get_available_stations
from snapshot import capture_snapshot_aws, capture_snapshot_local
from vector_store import extract_station_from_query, build_chroma_index, ask_with_chroma


def render_sidebar():
    st.sidebar.title("Configuration")

    source = st.sidebar.radio(
        "Source des donnees",
        [SOURCE_API, SOURCE_S3],
        index=0,
    )

    st.sidebar.divider()
    st.sidebar.subheader("Filtres")

    filtre_type = st.sidebar.selectbox(
        "Type de velo",
        ["Tous", "Mecaniques uniquement", "Electriques uniquement"],
    )

    filtre_etat = st.sidebar.selectbox(
        "Etat des stations",
        ["Tous", "Disponibles", "Vides", "Pleines"],
        index=0,
    )

    filtre_min_velos = st.sidebar.slider(
        "Minimum de velos disponibles",
        min_value=0,
        max_value=50,
        value=0,
    )

    st.sidebar.divider()
    sidebar_count = st.sidebar.empty()

    return source, filtre_type, filtre_etat, filtre_min_velos, sidebar_count


def render_source_info(source: str, df, info: str | None = None):
    st.sidebar.success(f"{len(df)} stations chargees")

    if source == SOURCE_API:
        st.caption("Source : opendata.paris.fr — temps reel")
    else:
        st.caption(f"Source : AWS S3 — {info}")


def render_metrics(df_filtered):
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Stations", len(df_filtered))
    col2.metric("Velos dispo", f"{int(df_filtered['numbikesavailable'].sum()):,}")
    col3.metric("Bornes dispo", f"{int(df_filtered['numdocksavailable'].sum()):,}")
    col4.metric("Stations vides", int(df_filtered["is_empty"].sum()))
    col5.metric("Remplissage", f"{df_filtered['bike_ratio'].mean():.1%}")
    st.divider()

def render_map(df_filtered):
    st.subheader("Carte des stations")

    if "lat" in df_filtered.columns and df_filtered["lat"].notna().any():
        map_df = df_filtered[["name", "lat", "lon", "numbikesavailable"]].dropna()
        st.map(
            map_df,
            latitude="lat",
            longitude="lon",
            size="numbikesavailable",
            color="#1D9E75",
        )
    else:
        st.info("Coordonnees non disponibles pour ce snapshot.")

    st.divider()

def render_charts(df_filtered):
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Top 10 mieux fournies")
        top10 = df_filtered.nlargest(10, "numbikesavailable")[
            ["name", "numbikesavailable", "ebike"]
        ]
        fig = px.bar(
            top10,
            x="numbikesavailable",
            y="name",
            orientation="h",
            color="ebike",
            color_continuous_scale="teal",
            labels={
                "numbikesavailable": "Velos",
                "name": "Station",
                "ebike": "Electriques",
            },
        )
        fig.update_layout(yaxis={"autorange": "reversed"}, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Top 10 plus vides")
        empty10 = df_filtered.nsmallest(10, "numbikesavailable")[
            ["name", "numbikesavailable"]
        ]
        fig2 = px.bar(
            empty10,
            x="numbikesavailable",
            y="name",
            orientation="h",
            color="numbikesavailable",
            color_continuous_scale="reds",
            labels={"numbikesavailable": "Velos", "name": "Station"},
        )
        fig2.update_layout(yaxis={"autorange": "reversed"}, height=400)
        st.plotly_chart(fig2, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Types de velos")
        bike_data = pd.DataFrame(
            {
                "Type": ["Mecaniques", "Electriques"],
                "Nombre": [
                    int(df_filtered["mechanical"].sum()),
                    int(df_filtered["ebike"].sum()),
                ],
            }
        )
        fig3 = px.pie(
            bike_data,
            values="Nombre",
            names="Type",
            color_discrete_sequence=["#185FA5", "#1D9E75"],
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.subheader("Etat des stations")
        status_data = pd.DataFrame(
            {
                "Etat": ["Vides", "Pleines", "Partielles"],
                "Nombre": [
                    int(df_filtered["is_empty"].sum()),
                    int(df_filtered["is_full"].sum()),
                    len(df_filtered)
                    - int(df_filtered["is_empty"].sum())
                    - int(df_filtered["is_full"].sum()),
                ],
            }
        )
        fig4 = px.pie(
            status_data,
            values="Nombre",
            names="Etat",
            color_discrete_sequence=["#A32D2D", "#1D9E75", "#EF9F27"],
        )
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()

def render_chatbot(df_filtered):
    st.subheader("Ask Velib Data")

    context = build_context(df_filtered)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if question := st.chat_input("Ex: Quelle station a le plus de velos electriques ?"):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                response = ask_groq(question, context)
            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

    st.divider()

def render_downloads(df_filtered):
    st.subheader("Telechargements")

    col_dl1, col_dl2, col_dl3 = st.columns(3)

    with col_dl1:
        if API_ENDPOINT:
            st.link_button(
                "Rapport PDF (AWS)",
                f"{API_ENDPOINT}/download/report",
                use_container_width=True,
            )
        else:
            st.info("API AWS non configure")

    with col_dl2:
        if st.button("Generer rapport PDF", use_container_width=True):
            with st.spinner("Generation du rapport..."):
                from report_generator import generate_pdf_report
                pdf_bytes = generate_pdf_report(df_filtered)
            st.download_button(
                "Telecharger le PDF",
                data=pdf_bytes,
                file_name=f"velib_rapport_{datetime.now(pytz.timezone('Europe/Paris')).strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

    with col_dl3:
        csv_bytes = df_filtered.to_csv(index=False, sep=";").encode("utf-8")
        st.download_button(
            "Telecharger CSV",
            data=csv_bytes,
            file_name="velib_latest.csv",
            mime="text/csv",
            use_container_width=True,
        )

def render_last_update():
    paris_tz = pytz.timezone(PARIS_TIMEZONE)
    now = datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M")
    st.caption(f"Derniere mise a jour : {now}")

def render_station_detail(df_filtered):
    st.subheader("Recherche et historique de station")

    col1, col2 = st.columns([3, 1])

    with col1:
        search = st.text_input(
            "Nom de la station",
            placeholder="Ex: Bastille, Nation, Mairie de Clichy...",
            key="station_search",
        )

    with col2:
    hours = st.selectbox(
        "Historique",
        [6, 12, 24, 48, 72, 168, 720],
        index=2,
        format_func=lambda x: f"{x}h" if x < 168 else ("7 jours" if x == 168 else "30 jours"),
    )   

    if not search:
        return

    results = df_filtered[df_filtered["name"].str.contains(search.upper(), na=False)]

    if results.empty:
        st.warning(f"Aucune station trouvee pour '{search}'")
        return

    # Selectbox si plusieurs stations matchent
    station_names = sorted(results["name"].unique().tolist())
    if len(station_names) > 1:
        station_name = st.selectbox("Choisir une station", station_names)
    else:
        station_name = station_names[0]

    row = results[results["name"] == station_name].iloc[0]

    # Données temps réel
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Velos dispo", int(row["numbikesavailable"]))
    c2.metric("Dont electriques", int(row["ebike"]))
    c3.metric("Bornes dispo", int(row["numdocksavailable"]))
    c4.metric("Remplissage", f"{row['bike_ratio']:.0%}")

    if row["is_empty"]:
        st.error("Station vide en ce moment")
    elif row["is_full"]:
        st.warning("Station pleine en ce moment")
    else:
        st.success("Station disponible")

    # Historique automatique
    with st.spinner(f"Chargement historique {station_name}..."):
        df_history = get_station_history(station_name, hours)

    if df_history.empty:
        st.info("Aucun historique disponible. Capturez des snapshots pour voir l'evolution.")
        st.divider()
        return

    st.caption(f"Evolution sur les {hours} dernieres heures — {len(df_history)} snapshots")

    fig = px.line(
        df_history,
        x="run_at",
        y=["numbikesavailable", "ebike", "mechanical"],
        labels={"run_at": "Heure", "value": "Nombre", "variable": "Type"},
        color_discrete_map={
            "numbikesavailable": "#1D9E75",
            "ebike": "#185FA5",
            "mechanical": "#EF9F27",
        },
    )
    fig.update_layout(height=300, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

def render_snapshot_button(source: str):
    st.subheader("Capturer un snapshot")

    postgres_url = os.environ.get("POSTGRES_URL", "")
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    pipeline_lambda = os.environ.get("PIPELINE_LAMBDA", "")
    s3_bucket = os.environ.get("S3_BUCKET", "")

    s3_active = bool(aws_key and s3_bucket)
    aws_active = bool(postgres_url and aws_key and pipeline_lambda)

    if aws_active:
        st.info("Aurora active — snapshot dans Aurora et S3.")
        if st.button("Lancer le pipeline AWS", type="primary"):
            with st.spinner("Pipeline en cours..."):
                success, message = capture_snapshot_aws()
            if success:
                st.success(message)
                st.cache_data.clear()
                st.cache_data.clear()
                from snapshot import refresh_ai_indexes
                refresh_ai_indexes()
                st.rerun()
            else:
                st.error(message)

    elif s3_active:
        st.info("Snapshot sauvegarde dans S3.")
        if st.button("Capturer snapshot S3", type="primary"):
            with st.spinner("Capture en cours..."):
                success, message = capture_snapshot_local()
            if success:
                st.success(message)
                st.cache_data.clear()
                from snapshot import refresh_ai_indexes
                refresh_ai_indexes()
                st.rerun()
            else:
                st.error(message)

    else:
        st.warning("AWS non configure — snapshots non persistants.")
        if st.button("Capturer snapshot local", type="primary"):
            with st.spinner("Capture en cours..."):
                success, message = capture_snapshot_local()
            if success:
                st.success(message)
                from snapshot import refresh_ai_indexes
                refresh_ai_indexes()
                st.rerun()
            else:
                st.error(message)

    st.divider()


def _get_qdrant_client_cached():
    if "qdrant_client" not in st.session_state:
        with st.spinner("Connexion Qdrant Cloud..."):
            client, n = build_chroma_index()
            st.session_state.qdrant_client = client
            st.session_state.qdrant_docs = n
    return st.session_state.get("qdrant_client"), st.session_state.get("qdrant_docs", 0)


def _render_rag_content(df_filtered=None):
    has_history = False
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
        bucket = os.environ.get("S3_BUCKET", "")
        if bucket:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix="velib/history/")
            has_history = resp.get("KeyCount", 0) > 0
    except Exception:
        pass

    if not has_history:
        st.info("Capturez des snapshots pour activer le RAG.")
        render_chatbot(df_filtered)
        return

    if "rag_engine" not in st.session_state:
        with st.spinner("Construction de l'index RAG..."):
            from rag import build_rag_index
            engine, n_docs = build_rag_index()
            st.session_state.rag_engine = engine
            st.session_state.rag_docs = n_docs

    if st.session_state.rag_engine:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"Index RAG : {st.session_state.rag_docs} snapshots indexes")
        with col2:
            if st.button("Rafraichir index"):
                for key in ["rag_engine", "rag_docs"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []

    for msg in st.session_state.rag_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    question = st.chat_input(
        "Ex: Bastille est-elle souvent vide le matin ?",
        key="rag_input",
    )

    if question:
        st.session_state.rag_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Recherche dans l'historique..."):
                from rag import ask_rag_with_qdrant_context
                from vector_store import semantic_search
                qdrant_client, _ = _get_qdrant_client_cached()
                qdrant_docs = semantic_search(question, qdrant_client, n_results=10) if qdrant_client else []
                response = ask_rag_with_qdrant_context(
                    question, st.session_state.rag_engine, qdrant_docs
                )
            st.write(response)
            st.session_state.rag_messages.append({"role": "assistant", "content": response})


def _render_agent_content(df_filtered):
    qdrant_client, _ = _get_qdrant_client_cached()

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []

    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    question = st.chat_input(
        "Ex: Y a-t-il des anomalies sur le reseau ?",
        key="agent_input",
    )

    if question:
        st.session_state.agent_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Agent en cours d'analyse..."):
                from agent import run_agent
                response = run_agent(question, df_filtered, qdrant_client)
            st.write(response)
            st.session_state.agent_messages.append({"role": "assistant", "content": response})


def _render_semantic_content():
    qdrant_client, qdrant_docs = _get_qdrant_client_cached()

    if qdrant_client is None:
        st.info("Qdrant non configure ou pas de snapshots disponibles.")
        return

    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Index Qdrant : {qdrant_docs} documents")
    with col2:
        if st.button("Rafraichir Qdrant"):
            for key in ["qdrant_client", "qdrant_docs"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    query = st.text_input(
        "Recherche",
        placeholder="Ex: stations vides le matin, patterns weekend...",
        key="qdrant_search",
    )

    if not query:
        return

    with st.spinner("Recherche semantique..."):
        response = ask_with_chroma(query, qdrant_client)

    st.write(response)


def render_snapshot_manager():
    st.sidebar.divider()
    st.sidebar.subheader("Gestion snapshots")

    s3_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    bucket = os.environ.get("S3_BUCKET", "")

    if not s3_key or not bucket:
        st.sidebar.info("AWS non configure.")
        return

    try:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
        paginator = s3.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix="velib/history/"):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        st.sidebar.info(f"{len(keys)} snapshots en S3")

        if not keys:
            return

        action = st.sidebar.selectbox(
            "Action",
            ["Choisir", "Supprimer les plus anciens", "Tout supprimer"],
            key="snapshot_action",
        )

        if action == "Supprimer les plus anciens":
            n = st.sidebar.number_input(
                "Garder les N derniers",
                min_value=1,
                max_value=len(keys),
                value=min(24, len(keys)),
            )
            if st.sidebar.button("Supprimer", type="secondary"):
                to_delete = sorted(keys)[:-n]
                for key in to_delete:
                    s3.delete_object(Bucket=bucket, Key=key)
                st.sidebar.success(f"{len(to_delete)} snapshots supprimes")
                st.cache_data.clear()
                for key in ["rag_engine", "rag_docs", "qdrant_client", "qdrant_docs"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        elif action == "Tout supprimer":
            if st.sidebar.button("Confirmer suppression totale", type="secondary"):
                for key in keys:
                    s3.delete_object(Bucket=bucket, Key=key)
                st.sidebar.success("Tous les snapshots supprimes")
                st.cache_data.clear()
                for key in ["rag_engine", "rag_docs", "qdrant_client", "qdrant_docs"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

def render_ai_tabs(df_filtered):
    st.subheader("Intelligence Artificielle")

    tab1, tab2, tab3 = st.tabs([
        "Chatbot RAG",
        "Agent IA",
        "Recherche semantique",
    ])

    with tab1:
        st.caption("Posez des questions sur l'historique des stations")
        _render_rag_content(df_filtered)

    with tab2:
        st.caption("L'agent choisit automatiquement les bons outils")
        st.caption("Tools : get_station_info · get_network_stats · search_history · detect_anomalies")
        _render_agent_content(df_filtered)

    with tab3:
        st.caption("Recherche semantique sur les patterns historiques")
        _render_semantic_content()

    st.divider()