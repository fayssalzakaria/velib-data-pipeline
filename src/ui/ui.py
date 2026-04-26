import os
from datetime import datetime
from src.ai.assistant import run_unified_assistant
import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

from config import API_ENDPOINT, PARIS_TIMEZONE, SOURCE_API, SOURCE_S3
from src.ai.chatbot import ask_groq, build_context
from src.data.history import get_station_history, get_available_stations
from src.data.snapshot import capture_snapshot_aws, capture_snapshot_s3
from src.ai.vector_store import extract_station_from_query, build_qdrant_index, ask_with_qdrant

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
                from src.reports.report_generator import generate_pdf_report
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
                from src.data.snapshot import refresh_ai_indexes
                refresh_ai_indexes()
                st.rerun()
            else:
                st.error(message)

    elif s3_active:
        st.info("Snapshot sauvegarde dans S3.")
        if st.button("Capturer snapshot S3", type="primary"):
            with st.spinner("Capture en cours..."):
                success, message = capture_snapshot_s3()
            if success:
                st.success(message)
                st.cache_data.clear()
                from src.data.snapshot import refresh_ai_indexes
                refresh_ai_indexes()
                st.rerun()
            else:
                st.error(message)

    else:
        st.warning("AWS non configure — snapshots non persistants.")
        if st.button("Capturer snapshot local", type="primary"):
            with st.spinner("Capture en cours..."):
                success, message = capture_snapshot_s3()
            if success:
                st.success(message)
                from src.data.snapshot import refresh_ai_indexes
                refresh_ai_indexes()
                st.rerun()
            else:
                st.error(message)

    st.divider()


def _get_qdrant_client_cached():
    if "qdrant_client" not in st.session_state:
        with st.spinner("Connexion Qdrant Cloud..."):
            client, n = build_qdrant_index()
            st.session_state.qdrant_client = client
            st.session_state.qdrant_docs = n
    return st.session_state.get("qdrant_client"), st.session_state.get("qdrant_docs", 0)


def _render_rag_content(df_filtered=None):
    st.info("Pour les questions sur l'etat actuel d'une station (anomalies, disponibilite), utilisez l'onglet Agent IA qui a acces aux donnees temps reel.")
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

    if "rag_documents" not in st.session_state:
        with st.spinner("Chargement des documents RAG..."):
            from src.ai.rag import build_rag_index
            docs, n_docs = build_rag_index()
            st.session_state.rag_documents = docs
            st.session_state.rag_docs = n_docs

    if st.session_state.rag_documents:
        col1, col2 = st.columns([3, 1])
        with col1:
            rag_docs = st.session_state.get("rag_docs", 0)
            st.caption(
                f"Index RAG : {rag_docs} documents — "
                f"HyDE + BM25 + Cosine + RRF + MMR + Reranking"
            )
        with col2:
            if st.button("Rafraichir index"):
                for key in ["rag_documents", "rag_docs"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []
    if "rag_traces" not in st.session_state:
        st.session_state.rag_traces = []

    for i, msg in enumerate(st.session_state.rag_messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

        if msg["role"] == "assistant" and i // 2 < len(st.session_state.rag_traces):
            trace = st.session_state.rag_traces[i // 2]
            if trace:
                with st.expander("Details du pipeline RAG", expanded=False):
                    st.caption(f"Techniques : {' → '.join(trace.get('techniques_used', []))}")

                    col1, col2, col3 = st.columns(3)
                    tokens = trace.get("tokens", {})
                    col1.metric("Tokens total", tokens.get("total", 0))
                    col2.metric("Prompt tokens", tokens.get("prompt", 0))
                    col3.metric("Completion tokens", tokens.get("completion", 0))

                    if trace.get("hyde_query"):
                        with st.expander("Query HyDE expandée"):
                            st.text(trace["hyde_query"])

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if trace.get("bm25_top5"):
                            st.caption("Top 5 BM25 :")
                            for s in trace["bm25_top5"]:
                                st.caption(f"  • {s}")
                    with col_b:
                        if trace.get("cosine_top5"):
                            st.caption("Top 5 Cosine :")
                            for s in trace["cosine_top5"]:
                                st.caption(f"  • {s}")

                    if trace.get("final_docs"):
                        st.caption("Sources finales utilisées :")
                        for s in trace["final_docs"]:
                            st.caption(f"  • {s}")

    question = st.chat_input(
        "Ex: Bastille est-elle souvent vide le matin ?",
        key="rag_input",
    )

    if question:
        st.session_state.rag_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Pipeline RAG en cours — HyDE + BM25 + Cosine + RRF + MMR + Reranking..."):
                from src.ai.rag import ask_rag_with_qdrant_context
                from src.ai.vector_store import semantic_search
                qdrant_client, _ = _get_qdrant_client_cached()
                qdrant_docs = semantic_search(question, qdrant_client, n_results=10) if qdrant_client else []
                response, trace = ask_rag_with_qdrant_context(
                    question,
                    st.session_state.get("rag_documents"),
                    qdrant_docs,
                )
                st.session_state.rag_traces.append(trace)
            st.write(response)
            if trace and trace.get("relevance_score") is not None:
                score = trace["relevance_score"]
                color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                st.markdown(
                    f"**Pertinence : <span style='color:{color}'>{score}/100</span>** — {trace.get('relevance_explanation','')}",
                    unsafe_allow_html=True,
                )
            st.session_state.rag_messages.append({"role": "assistant", "content": response})
        st.rerun()

def _render_agent_content(df_filtered):
    qdrant_client, _ = _get_qdrant_client_cached()
    rag_documents = st.session_state.get("rag_documents")

    if "agent_messages" not in st.session_state:
        st.session_state.agent_messages = []
    if "agent_traces" not in st.session_state:
        st.session_state.agent_traces = []

    for i, msg in enumerate(st.session_state.agent_messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

        if msg["role"] == "assistant" and i // 2 < len(st.session_state.agent_traces):
            trace = st.session_state.agent_traces[i // 2]
            with st.expander("Details de l'execution", expanded=False):
                col1, col2, col3 = st.columns(3)
                col1.metric("Tokens total", trace.total_tokens)
                col2.metric("Prompt tokens", trace.prompt_tokens)
                col3.metric("Completion tokens", trace.completion_tokens)

                st.caption(f"Tools utilises : {', '.join(trace.tools_called) if trace.tools_called else 'aucun'}")

                if trace.tool_results:
                    for tool_name, result in trace.tool_results.items():
                        with st.expander(f"Resultat : {tool_name}"):
                            if tool_name == "search_history":
                                techniques = result.get("techniques_utilisees", [])
                                if techniques:
                                    st.caption(f"Techniques : {' → '.join(techniques)}")
                                sources = result.get("sources", [])
                                if sources:
                                    st.caption("Sources :")
                                    for s in sources:
                                        st.caption(f"  • {s}")
                            else:
                                st.json(result)

                if trace.prompt_sent:
                    with st.expander("Prompt envoye au LLM"):
                        st.text(trace.prompt_sent[:2000])

                score = trace.relevance_score
                color = "green" if score >= 80 else "orange" if score >= 50 else "red"
                st.markdown(
                    f"**Pertinence : <span style='color:{color}'>{score}/100</span>**",
                    unsafe_allow_html=True,
                )
                if trace.relevance_explanation:
                    st.caption(trace.relevance_explanation)

    question = st.chat_input(
        "Ex: Y a-t-il des anomalies ? Analyse Bastille sur l'historique.",
        key="agent_input",
    )

    if question:
        st.session_state.agent_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Agent en cours — HyDE + BM25 + Cosine + RRF + MMR si historique requis..."):
                from src.ai.agent import run_agent
                response, trace = run_agent(
                    question, df_filtered, qdrant_client, rag_documents
                )
                st.session_state.agent_traces.append(trace)
            st.write(response)
            st.session_state.agent_messages.append(
                {"role": "assistant", "content": response}
            )
        st.rerun()

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
        response, sem_trace = ask_with_qdrant(query, qdrant_client)

    st.write(response)

    if sem_trace.get("relevance_score") is not None:
        score = sem_trace["relevance_score"]
        color = "green" if score >= 80 else "orange" if score >= 50 else "red"
        st.caption(f"Tokens : {sem_trace.get('tokens', 0)}")
        st.markdown(
            f"**Pertinence : <span style='color:{color}'>{score}/100</span>** — {sem_trace.get('relevance_explanation','')}",
            unsafe_allow_html=True,
        )


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

        def _clear_ai_state():
            try:
                from src.ai.vector_store import _get_qdrant_client, COLLECTION_NAME
                client = _get_qdrant_client()
                if client:
                    client.delete_collection(COLLECTION_NAME)
            except Exception:
                pass
            st.cache_data.clear()
            for key in ["rag_engine", "rag_docs", "rag_documents", "qdrant_client", "qdrant_docs"]:
                if key in st.session_state:
                    del st.session_state[key]

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
                _clear_ai_state()
                st.rerun()

        elif action == "Tout supprimer":
            if st.sidebar.button("Confirmer suppression totale", type="secondary"):
                for key in keys:
                    s3.delete_object(Bucket=bucket, Key=key)
                st.sidebar.success("Tous les snapshots supprimes")
                _clear_ai_state()
                st.rerun()

    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

def _render_unified_assistant_content(df_filtered):
    st.info(
        "Assistant IA unifié : il choisit automatiquement entre temps réel, anomalies, RAG historique et recherche sémantique."
    )

    qdrant_client, _ = _get_qdrant_client_cached()

    if "rag_documents" not in st.session_state:
        try:
            with st.spinner("Chargement de l'index RAG historique..."):
                from src.ai.rag import build_rag_index
                docs, n_docs = build_rag_index()
                st.session_state.rag_documents = docs
                st.session_state.rag_docs = n_docs
        except Exception:
            st.session_state.rag_documents = None
            st.session_state.rag_docs = 0

    if "unified_messages" not in st.session_state:
        st.session_state.unified_messages = []

    if "unified_traces" not in st.session_state:
        st.session_state.unified_traces = []

    for i, msg in enumerate(st.session_state.unified_messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

        if msg["role"] == "assistant":
            trace_index = i // 2
            if trace_index < len(st.session_state.unified_traces):
                trace = st.session_state.unified_traces[trace_index]

                with st.expander("Détails assistant IA", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Intention", trace.intent)
                    col2.metric("Confiance", f"{trace.confidence:.0%}")
                    col3.metric("Tools", len(trace.tools_used))

                    st.caption(f"Raison du routage : {trace.routing_reason}")

                    if trace.tools_used:
                        st.caption(f"Outils utilisés : {', '.join(trace.tools_used)}")

                    if trace.tokens:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Tokens total", trace.tokens.get("total", 0))
                        c2.metric("Prompt", trace.tokens.get("prompt", 0))
                        c3.metric("Completion", trace.tokens.get("completion", 0))

                    if trace.tool_results:
                        for tool_name, result in trace.tool_results.items():
                            with st.expander(f"Résultat outil : {tool_name}"):
                                st.json(result)

    question = st.chat_input(
        "Ex: Y a-t-il des anomalies maintenant ? Bastille est-elle souvent vide le matin ?",
        key="unified_assistant_input",
    )

    if question:
        st.session_state.unified_messages.append(
            {"role": "user", "content": question}
        )

        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Assistant IA en cours..."):
                from src.ai.vector_store import semantic_search

                qdrant_docs = (
                    semantic_search(question, qdrant_client, n_results=10)
                    if qdrant_client
                    else []
                )

                response, trace = run_unified_assistant(
                    question,
                    df_filtered,
                    qdrant_client=qdrant_client,
                    rag_documents=st.session_state.get("rag_documents"),
                    qdrant_docs=qdrant_docs,
                    use_llm_router=False,
                )

                st.session_state.unified_traces.append(trace)

            st.write(response)

            st.session_state.unified_messages.append(
                {"role": "assistant", "content": response}
            )

        st.rerun()

def render_ai_tabs(df_filtered):
    st.subheader("Intelligence Artificielle")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Assistant IA",
        "Chatbot RAG",
        "Agent IA",
        "Recherche sémantique",
    ])

    with tab1:
        st.caption("Assistant unifié avec routage automatique vers les bons outils")
        _render_unified_assistant_content(df_filtered)

    with tab2:
        st.caption("Posez des questions sur l'historique des stations")
        _render_rag_content(df_filtered)

    with tab3:
        st.caption("L'agent choisit automatiquement les bons outils")
        st.caption("Tools : get_station_info · get_network_stats · search_history · detect_anomalies")
        _render_agent_content(df_filtered)

    with tab4:
        st.caption("Recherche sémantique sur les patterns historiques")
        _render_semantic_content()

    st.divider()