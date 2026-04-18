"""
vector_store.py — ChromaDB vector store pour les données Vélib'
Commit 2 Phase ML : feat(ml): ChromaDB embeddings + semantic search
"""
import io
import os
import json
import hashlib
import pandas as pd
import pytz
from datetime import datetime

PARIS_TZ = pytz.timezone("Europe/Paris")
S3_BUCKET = os.environ.get("S3_BUCKET", "velib-pipeline-fz-prod-data")
CHROMA_S3_KEY = "velib/vectorstore/chroma_data.json"


def _get_s3():
    try:
        import boto3
        return boto3.client(
            "s3",
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
            region_name=os.environ.get("AWS_REGION", "eu-north-1"),
        )
    except Exception:
        return None


def _load_history_from_s3() -> pd.DataFrame:
    """Charge tous les snapshots depuis S3."""
    s3 = _get_s3()
    if s3 is None:
        return pd.DataFrame()
    try:
        paginator = s3.get_paginator("list_objects_v2")
        dfs = []
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="velib/history/"):
            for obj in page.get("Contents", []):
                response = s3.get_object(Bucket=S3_BUCKET, Key=obj["Key"])
                df = pd.read_csv(io.BytesIO(response["Body"].read()), sep=";")
                dfs.append(df)
        if not dfs:
            return pd.DataFrame()
        return pd.concat(dfs, ignore_index=True)
    except Exception:
        return pd.DataFrame()


def _row_to_text(row) -> str:
    """Convertit une ligne en texte descriptif pour l'embedding."""
    try:
        run_at = pd.to_datetime(row["run_at"], utc=True)
        run_at_paris = run_at.tz_convert(PARIS_TZ)
        heure = run_at_paris.hour
        jour = run_at_paris.strftime("%A")
        periode = (
            "matin" if 6 <= heure < 12
            else "apres-midi" if 12 <= heure < 18
            else "soir" if 18 <= heure < 22
            else "nuit"
        )
        etat = (
            "vide" if row["is_empty"]
            else "pleine" if row["is_full"]
            else "partiellement remplie"
        )
        return (
            f"La station {row['name']} le {jour} a {heure}h ({periode}) "
            f"avait {int(row['numbikesavailable'])} velos disponibles "
            f"dont {int(row['ebike'])} electriques et {int(row['mechanical'])} mecaniques. "
            f"Elle etait {etat} avec un taux de remplissage de "
            f"{float(row['bike_ratio']):.0%}. "
            f"Il y avait {int(row['numdocksavailable'])} bornes libres."
        )
    except Exception:
        return ""


def build_chroma_index(df: pd.DataFrame = None):
    """
    Construit un index ChromaDB en mémoire.
    Retourne la collection ChromaDB.
    """
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer

        if df is None or df.empty:
            df = _load_history_from_s3()

        if df.empty:
            return None, 0

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        client = chromadb.Client()

        try:
            client.delete_collection("velib")
        except Exception:
            pass

        collection = client.create_collection("velib")

        texts = []
        ids = []
        metadatas = []

        for i, row in df.iterrows():
            text = _row_to_text(row)
            if not text:
                continue
            doc_id = hashlib.md5(
                f"{row.get('snapshot_id','')}{row.get('name','')}".encode()
            ).hexdigest()
            texts.append(text)
            ids.append(doc_id)
            metadatas.append({
                "station": str(row.get("name", "")),
                "hour": int(row.get("hour", 0)),
                "weekday": str(row.get("weekday", "")),
                "is_empty": bool(row.get("is_empty", False)),
                "is_full": bool(row.get("is_full", False)),
                "numbikesavailable": int(row.get("numbikesavailable", 0)),
            })

        if not texts:
            return None, 0

        embeddings = model.encode(texts).tolist()

        batch_size = 500
        for i in range(0, len(texts), batch_size):
            collection.add(
                documents=texts[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                ids=ids[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
            )

        return collection, len(texts)

    except Exception as e:
        return None, 0


def semantic_search(query: str, collection, n_results: int = 5) -> list:
    """
    Recherche sémantique dans ChromaDB.
    Retourne les documents les plus pertinents.
    """
    if collection is None:
        return []
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode([query]).tolist()
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
        )
        return results.get("documents", [[]])[0]
    except Exception:
        return []


def ask_with_chroma(question: str, collection) -> str:
    """
    Répond à une question en utilisant ChromaDB + Groq.
    """
    import requests as req
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return "Cle Groq non configuree."

    docs = semantic_search(question, collection, n_results=8)
    if not docs:
        return "Aucune donnee pertinente trouvee dans l'historique."

    context = "\n".join(f"- {d}" for d in docs)

    prompt = f"""Tu es un expert en mobilite urbaine a Paris specialise dans le reseau Velib.
Reponds en francais de maniere concise et precise en te basant sur les donnees suivantes.

Donnees historiques pertinentes :
{context}

Question : {question}

Reponds directement sans introduction. Si les donnees ne permettent pas de repondre precisement, dis-le.
"""
    try:
        response = req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {groq_key}",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.3,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Erreur Groq : {e}"