from datetime import datetime
import os
from history import get_station_history
import pandas as pd
import plotly.express as px
import pytz
import streamlit as st

from chatbot import ask_groq, build_context
from config import API_ENDPOINT, PARIS_TIMEZONE, SOURCE_API, SOURCE_S3


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
    st.sidebar.success(f"{len(df)} stations chargées")

    if source == SOURCE_API:
        st.caption("Source : opendata.paris.fr — temps réel")
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


def render_search(df_filtered):
    st.subheader("Recherche de station")

    search = st.text_input(
        "Nom de la station",
        placeholder="Ex: Bastille, Nation, Republique...",
    )

    if not search:
        return

    results = df_filtered[df_filtered["name"].str.contains(search.upper(), na=False)]

    if results.empty:
        st.warning(f"Aucune station trouvee pour '{search}'")
        return

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
        st.info("Coordonnées non disponibles pour ce snapshot.")

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
                "numbikesavailable": "Vélos",
                "name": "Station",
                "ebike": "Électriques",
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
            labels={"numbikesavailable": "Vélos", "name": "Station"},
        )
        fig2.update_layout(yaxis={"autorange": "reversed"}, height=400)
        st.plotly_chart(fig2, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Types de vélos")
        bike_data = pd.DataFrame(
            {
                "Type": ["Mécaniques", "Électriques"],
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
        st.subheader("État des stations")
        status_data = pd.DataFrame(
            {
                "État": ["Vides", "Pleines", "Partielles"],
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
            names="État",
            color_discrete_sequence=["#A32D2D", "#1D9E75", "#EF9F27"],
        )
        st.plotly_chart(fig4, use_container_width=True)

    st.divider()


def render_chatbot(df_filtered):
    st.subheader("Ask Vélib Data")

    context = build_context(df_filtered)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    if question := st.chat_input(
        "Ex: Quelle station a le plus de vélos électriques ?"
    ):
        st.session_state.messages.append({"role": "user", "content": question})

        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Analyse en cours..."):
                response = ask_groq(question, context)
            st.write(response)
            st.session_state.messages.append(
                {"role": "assistant", "content": response}
            )

    st.divider()


def render_downloads(df_filtered):
    st.subheader("Téléchargements")

    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        if API_ENDPOINT:
            st.link_button(
                "Rapport PDF (AWS)",
                f"{API_ENDPOINT}/download/report",
                use_container_width=True,
            )
        else:
            st.info("API_ENDPOINT non configuré")

    with col_dl2:
        csv_bytes = df_filtered.to_csv(index=False, sep=";").encode("utf-8")
        st.download_button(
            "Télécharger CSV",
            data=csv_bytes,
            file_name="velib_latest.csv",
            mime="text/csv",
            use_container_width=True,
        )


def render_last_update():
    paris_tz = pytz.timezone(PARIS_TIMEZONE)
    now = datetime.now(paris_tz).strftime("%Y-%m-%d %H:%M")
    st.caption(f"Dernière mise à jour : {now}")
def render_history():
    st.subheader("Historique d'une station")

    postgres_url = os.environ.get("POSTGRES_URL", "")

    if not postgres_url:
        st.info("Connectez AWS (POSTGRES_URL) pour voir l'historique.")
        return

    col1, col2 = st.columns([3, 1])

    with col1:
        station_name = st.text_input(
            "Nom de la station",
            placeholder="Ex: Bastille",
            key="history_search",
        )

    with col2:
        hours = st.selectbox(
            "Periode",
            [6, 12, 24, 48],
            index=2,
            format_func=lambda x: f"{x}h",
        )

    if not station_name:
        return

    with st.spinner("Chargement historique..."):
        df_history = get_station_history(station_name, hours)

    if df_history.empty:
        st.warning("Aucune donnee historique. AWS doit etre actif.")
        return

    import plotly.express as px

    fig = px.line(
        df_history,
        x="run_at",
        y=["numbikesavailable", "ebike", "mechanical"],
        labels={
            "run_at": "Heure",
            "value": "Nombre",
            "variable": "Type",
        },
        color_discrete_map={
            "numbikesavailable": "#1D9E75",
            "ebike":             "#185FA5",
            "mechanical":        "#EF9F27",
        },
    )
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.divider()