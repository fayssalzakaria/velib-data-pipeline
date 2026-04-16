import streamlit as st

from config import SOURCE_API
from data_loader import load_from_api, load_from_s3
from filters import apply_filters

from ui import (
    render_chatbot,
    render_charts,
    render_downloads,
    render_last_update,
    render_map,
    render_metrics,
    render_search,
    render_sidebar,
    render_source_info,
    render_history,
)

st.set_page_config(
    page_title="Vélib' Dashboard",
    page_icon="",
    layout="wide",
)

st.title("Vélib' Dashboard Paris")

source, filtre_type, filtre_etat, filtre_min_velos, sidebar_count = render_sidebar()

if source == SOURCE_API:
    with st.spinner("Chargement depuis l'API Vélib'..."):
        df = load_from_api()
    render_source_info(source, df)
else:
    with st.spinner("Chargement depuis AWS S3..."):
        df, info = load_from_s3()

    if df is None:
        st.error(f"Erreur S3 : {info}")
        st.info("Basculez sur l'API Vélib dans la sidebar.")
        st.stop()

    render_source_info(source, df, info)

if df is None or df.empty:
    st.error("Aucune donnée disponible.")
    st.stop()

df_filtered = apply_filters(df, filtre_type, filtre_etat, filtre_min_velos)

sidebar_count.info(f"{len(df_filtered)} stations après filtres")

render_metrics(df_filtered)
render_search(df_filtered)
render_history()
render_map(df_filtered)
render_charts(df_filtered)
render_chatbot(df_filtered)
render_downloads(df_filtered)
render_last_update()