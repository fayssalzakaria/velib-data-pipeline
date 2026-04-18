"""
rag.py — RAG avec LlamaIndex sur données Vélib'
Commit 1 Phase ML : feat(ml): RAG chatbot with LlamaIndex
"""
import os
import io
import pandas as pd
from datetime import datetime
import pytz

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
PARIS_TZ = pytz.timezone("Europe/Paris")


def _load_history_df() -> pd.DataFrame:
    """Charge l'historique depuis S3 ou Aurora."""
    from history import _load_from_s3, _load_from_aurora

    # Essaie Aurora
    engine_url = os.environ.get("POSTGRES_URL", "")
    if engine_url:
        try:
            from sqlalchemy import create_engine, text
            engine = create_engine(engine_url, pool_pre_ping=True)
            with engine.connect() as conn:
                return pd.read_sql(
                    "SELECT * FROM velib_data ORDER BY run_at DESC LIMIT 5000",
                    conn
                )
        except Exception:
            pass

    # Fallback S3
    try:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
        bucket = os.environ.get("S3_BUCKET", "velib-pipeline-fz-prod-data")
        paginator = s3.get_paginator("list_objects_v2")
        dfs = []
        for page in paginator.paginate(Bucket=bucket, Prefix="velib/history/"):
            for obj in page.get("Contents", []):
                response = s3.get_object(Bucket=bucket, Key=obj["Key"])
                df = pd.read_csv(io.BytesIO(response["Body"].read()), sep=";")
                dfs.append(df)
        if dfs:
            return pd.concat(dfs, ignore_index=True)
    except Exception:
        pass

    return pd.DataFrame()


def _build_documents(df: pd.DataFrame) -> list:
    """
    Convertit le DataFrame en documents textuels pour LlamaIndex.
    Chaque document = résumé d'un snapshot pour une station.
    """
    if df.empty:
        return []

    df["run_at"] = pd.to_datetime(df["run_at"], utc=True, errors="coerce")
    documents = []

    for _, row in df.iterrows():
        try:
            run_at = row["run_at"]
            if hasattr(run_at, "tz_convert"):
                run_at_paris = run_at.tz_convert(PARIS_TZ)
            else:
                run_at_paris = run_at

            text = (
                f"Station: {row['name']}\n"
                f"Date: {run_at_paris.strftime('%Y-%m-%d %H:%M')}\n"
                f"Heure: {run_at_paris.hour}h\n"
                f"Jour: {run_at_paris.strftime('%A')}\n"
                f"Velos disponibles: {int(row['numbikesavailable'])}\n"
                f"Velos electriques: {int(row['ebike'])}\n"
                f"Velos mecaniques: {int(row['mechanical'])}\n"
                f"Bornes disponibles: {int(row['numdocksavailable'])}\n"
                f"Taux de remplissage: {float(row['bike_ratio']):.0%}\n"
                f"Station vide: {'oui' if row['is_empty'] else 'non'}\n"
                f"Station pleine: {'oui' if row['is_full'] else 'non'}\n"
            )
            documents.append(text)
        except Exception:
            continue

    return documents


def build_rag_index(df: pd.DataFrame = None):
    """
    Construit un index LlamaIndex en mémoire.
    Retourne (query_engine, nb_documents)
    """
    try:
        from llama_index.core import VectorStoreIndex, Document, Settings
        from llama_index.llms.groq import Groq
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding

        if df is None or df.empty:
            df = _load_history_df()

        if df.empty:
            return None, 0

        docs_texts = _build_documents(df)
        if not docs_texts:
            return None, 0

        documents = [Document(text=t) for t in docs_texts]

        # Embedding local (gratuit, pas d'API)
        embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

        # LLM Groq
        llm = Groq(
            model="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
        )

        Settings.llm = llm
        Settings.embed_model = embed_model

        index = VectorStoreIndex.from_documents(documents)
        query_engine = index.as_query_engine(
            similarity_top_k=5,
            response_mode="compact",
        )

        return query_engine, len(documents)

    except Exception as e:
        return None, 0


def ask_rag(question: str, query_engine) -> str:
    """Pose une question au RAG engine."""
    if query_engine is None:
        return "Index RAG non disponible. Capturez des snapshots d'abord."
    try:
        prompt = f"""
Tu es un expert en mobilite urbaine a Paris specialise dans le reseau Velib.
Reponds en francais de maniere concise et utile.
Utilise les donnees disponibles pour repondre precisement.

Question : {question}
"""
        response = query_engine.query(prompt)
        return str(response)
    except Exception as e:
        return f"Erreur RAG : {e}"