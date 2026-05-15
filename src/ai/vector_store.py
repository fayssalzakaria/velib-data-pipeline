"""
vector_store.py — Qdrant Cloud vector store pour les données Vélib'
Persistent, gratuit, compatible Python 3.14
"""
import io
import os
import uuid
import pandas as pd
import pytz
import hashlib
import json
from llm_client import call_llm_text, verify_relevance
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


def build_qdrant_index(df: pd.DataFrame = None):
    """
    Connexion rapide a Qdrant — reindexe seulement si collection vide ou absente.
    """
    try:
        from sentence_transformers import SentenceTransformer
        from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType

        client = _get_qdrant_client()
        if client is None:
            return None, 0

        # Si collection existe et a des points — retourne immediatement
        if _collection_exists(client):
            count = _collection_count(client)
            if count > 0:
                return client, count

        # Collection vide ou absente — charge les donnees et indexe
        if df is None or df.empty:
            df = _load_history_from_s3()

        if df.empty:
            return client, 0

        # Cree la collection
        if not _collection_exists(client):
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE),
            )
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="station",
                field_schema=PayloadSchemaType.KEYWORD,
            )

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
            return client, 0

        embeddings = model.encode(texts, show_progress_bar=False)

        points = [
            PointStruct(
                id=hashlib.md5(
                    f"{p.get('snapshot_id','')}{p.get('station','')}".encode()
                ).hexdigest(),
                vector=embedding.tolist(),
                payload={**p, "text": text},
            )
            for text, embedding, p in zip(texts, embeddings, payloads)
        ]

        batch_size = 100
        for i in range(0, len(points), batch_size):
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points[i:i+batch_size],
            )

        return client, _collection_count(client)

    except Exception as e:
        return None, 0


def semantic_search(query: str, client, n_results: int = 8) -> list:
    """Recherche sémantique dans Qdrant."""
    if client is None:
        return []

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode(query).tolist()

        station = extract_station_from_query(query, client)

        if station:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_embedding,
                limit=n_results,
                with_payload=True,
                query_filter={
                    "must": [
                        {
                            "key": "station",
                            "match": {"value": station},
                        }
                    ]
                },
            )
        else:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_embedding,
                limit=n_results,
                with_payload=True,
            )

        return [
            r.payload.get("text", "")
            for r in results.points
            if getattr(r, "payload", None)
        ]

    except Exception as e:
        return [f"DEBUG semantic_search erreur : {e}"]

def ask_with_qdrant(question: str, client) -> tuple[str, dict]:
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return "Cle Groq non configuree.", {}

    docs = semantic_search(question, client, n_results=8)
    if not docs:
        return "Aucune donnee pertinente trouvee dans l'historique.", {}

    context = "\n".join(f"- {d}" for d in docs)
    prompt = f"""Tu es un expert Velib Paris. Reponds en francais uniquement avec ces donnees.

Donnees :
{context}

Question : {question}

Reponds directement sans introduction."""

    try:
        answer, tokens = call_llm_text(
            prompt,
            max_tokens=500,
            temperature=0.3,
            timeout=30,
        )

        # Verification pertinence
        score, explanation = _verify_relevance_semantic(question, answer, context[:500])

        return answer, {
            "tokens": tokens.get("total_tokens", 0),
            "relevance_score": score,
            "relevance_explanation": explanation,
        }
    except Exception as e:
        return f"Erreur Groq : {e}", {}


def _verify_relevance_semantic(question: str, answer: str, context: str) -> tuple[int, str]:
    return verify_relevance(
        question=question,
        answer=answer,
        context=context,
        evaluator_name="recherche sémantique Vélib",
    )

def extract_station_from_query(query: str, client) -> str | None:
    if client is None:
        return None

    try:
        import re
        import unicodedata

        def normalize(text: str) -> str:
            text = text.upper().strip()
            text = unicodedata.normalize("NFKD", text)
            text = "".join(c for c in text if not unicodedata.combining(c))
            text = re.sub(r"[^A-Z0-9\s\-]", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text

        stop_words = {
            "INFO", "INFORMATION", "INFORMATIONS", "SUR", "LA", "LE", "LES",
            "DE", "DES", "DU", "D", "UN", "UNE", "ET", "A", "AU", "AUX",
            "STATION", "DETAIL", "DETAILS", "DONNEE", "DONNEES"
        }

        points, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=5000,
            with_payload=True,
            with_vectors=False,
        )

        stations = set()
        for p in points:
            payload = getattr(p, "payload", {}) or {}
            station = payload.get("station")
            if station:
                stations.add(station)

        q_norm = normalize(query)
        q_words = [
            w for w in q_norm.split()
            if len(w) > 2 and w not in stop_words
        ]

        if not q_words:
            return None

        best_match = None
        best_score = -1

        for station in stations:
            station_norm = normalize(station)
            station_words = set(station_norm.split())

            score = 0

            # Bonus énorme si le nom complet apparaît dans la requête
            if station_norm in q_norm:
                score += 100

            # Mots exacts en commun
            common_words = set(q_words) & station_words
            score += len(common_words) * 15

            # Bonus mot important présent dans la station
            for word in q_words:
                if word in station_norm:
                    score += 5

            # Bonus fort si le dernier mot distinctif matche
            if q_words and q_words[-1] in station_norm:
                score += 20

            # Léger malus si la station est beaucoup plus longue
            score -= max(0, len(station_words) - len(set(q_words)))

            if score > best_score:
                best_score = score
                best_match = station

        return best_match if best_score >= 20 else None

    except Exception:
        return None