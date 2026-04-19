"""
vector_store.py — Qdrant Cloud vector store pour les données Vélib'
Persistent, gratuit, compatible Python 3.14
"""
import io
import os
import uuid
import pandas as pd
import pytz

PARIS_TZ = pytz.timezone("Europe/Paris")
S3_BUCKET = os.environ.get("S3_BUCKET", "velib-pipeline-fz-prod-data")
QDRANT_URL = os.environ.get("QDRANT_URL", "")
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
COLLECTION_NAME = "velib_snapshots"


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


def _get_qdrant_client():
    if not QDRANT_URL or not QDRANT_API_KEY:
        return None
    try:
        from qdrant_client import QdrantClient
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    except Exception:
        return None


def _collection_exists(client) -> bool:
    try:
        collections = client.get_collections().collections
        return any(c.name == COLLECTION_NAME for c in collections)
    except Exception:
        return False


def _collection_count(client) -> int:
    try:
        return client.count(COLLECTION_NAME).count
    except Exception:
        return 0


def build_chroma_index(df: pd.DataFrame = None):
    """
    Construit ou charge l'index Qdrant.
    Retourne (client, nb_documents)
    """
    try:
        from sentence_transformers import SentenceTransformer
        from qdrant_client.models import Distance, VectorParams, PointStruct

        client = _get_qdrant_client()
        if client is None:
            return None, 0

        if df is None or df.empty:
            df = _load_history_from_s3()

        if df.empty:
            return None, 0

        # Crée la collection si elle n'existe pas
        if not _collection_exists(client):
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(
                    size=384,
                    distance=Distance.COSINE,
                ),
            )

        existing_count = _collection_count(client)

        # Encode et indexe les documents
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        texts = []
        payloads = []
        for _, row in df.iterrows():
            text = _row_to_text(row)
            if text:
                texts.append(text)
                payloads.append({
                    "station": str(row.get("name", "")),
                    "hour": int(row.get("hour", 0)),
                    "weekday": str(row.get("weekday", "")),
                    "is_empty": bool(row.get("is_empty", False)),
                    "snapshot_id": str(row.get("snapshot_id", "")),
                })

        if not texts:
            return client, existing_count

        embeddings = model.encode(texts, show_progress_bar=False)

        points = [
            PointStruct(
                import hashlib
                id=hashlib.md5(
                    f"{payload.get('snapshot_id', '')}{payload.get('station', '')}".encode()
                ).hexdigest(),  
                vector=embedding.tolist(),
                payload={**payload, "text": text},
            )
            for text, embedding, payload in zip(texts, embeddings, payloads)
        ]

        batch_size = 100
        for i in range(0, len(points), batch_size):
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points[i:i+batch_size],
            )

        total = _collection_count(client)
        return client, total

    except Exception as e:
        return None, 0


def semantic_search(query: str, client, n_results: int = 8) -> list:
    """Recherche sémantique dans Qdrant."""
    if client is None:
        return []
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode([query])[0].tolist()

        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            limit=n_results,
        )
        return [r.payload.get("text", "") for r in results]
    except Exception:
        return []


def ask_with_chroma(question: str, client) -> str:
    """Répond à une question avec Qdrant + Groq."""
    import requests as req
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return "Cle Groq non configuree."

    docs = semantic_search(question, client, n_results=8)
    if not docs:
        return "Aucune donnee pertinente trouvee dans l'historique."

    context = "\n".join(f"- {d}" for d in docs)

    prompt = f"""Tu es un expert en mobilite urbaine a Paris specialise dans le reseau Velib.
Reponds en francais de maniere concise et precise en te basant sur les donnees suivantes.

Donnees historiques pertinentes :
{context}

Question : {question}

Reponds directement sans introduction.
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