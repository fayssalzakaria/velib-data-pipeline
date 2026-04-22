"""
rag.py — RAG avancé avec Hybrid Search + Reranking + MMR + HyDE + Citations
"""
import io
import os
import json
import math
import numpy as np
import pandas as pd
import requests
import pytz
from datetime import datetime

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PARIS_TZ = pytz.timezone("Europe/Paris")


def _load_history_df() -> pd.DataFrame:
    engine_url = os.environ.get("POSTGRES_URL", "")
    if engine_url:
        try:
            from sqlalchemy import create_engine
            engine = create_engine(engine_url, pool_pre_ping=True)
            with engine.connect() as conn:
                return pd.read_sql(
                    "SELECT * FROM velib_data ORDER BY run_at DESC LIMIT 5000",
                    conn,
                )
        except Exception:
            pass

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


def _build_documents(df: pd.DataFrame) -> list[dict]:
    """
    Retourne une liste de dicts avec text + metadata pour chaque ligne.
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

            heure = run_at_paris.hour
            jour = run_at_paris.strftime("%A")
            periode = (
                "matin" if 6 <= heure < 12
                else "apres-midi" if 12 <= heure < 18
                else "soir" if 18 <= heure < 22
                else "nuit"
            )

            text = (
                f"Station: {row['name']}\n"
                f"Date: {run_at_paris.strftime('%Y-%m-%d %H:%M')}\n"
                f"Heure: {heure}h ({periode})\n"
                f"Jour: {jour}\n"
                f"Velos disponibles: {int(row['numbikesavailable'])}\n"
                f"Velos electriques: {int(row['ebike'])}\n"
                f"Velos mecaniques: {int(row['mechanical'])}\n"
                f"Bornes disponibles: {int(row['numdocksavailable'])}\n"
                f"Taux de remplissage: {float(row['bike_ratio']):.0%}\n"
                f"Station vide: {'oui' if row['is_empty'] else 'non'}\n"
                f"Station pleine: {'oui' if row['is_full'] else 'non'}\n"
            )

            documents.append({
                "text": text,
                "metadata": {
                    "station": str(row.get("name", "")),
                    "snapshot_id": str(row.get("snapshot_id", "")),
                    "run_at": run_at_paris.strftime("%Y-%m-%d %H:%M"),
                    "hour": heure,
                    "weekday": jour,
                    "periode": periode,
                    "numbikesavailable": int(row.get("numbikesavailable", 0)),
                    "bike_ratio": float(row.get("bike_ratio", 0)),
                    "is_empty": bool(row.get("is_empty", False)),
                    "is_full": bool(row.get("is_full", False)),
                }
            })
        except Exception:
            continue

    return documents


def _hyde_expand_query(question: str) -> str:
    """
    HyDE — génère une réponse hypothétique pour améliorer la recherche.
    La réponse hypothétique est ensuite utilisée comme query d'embedding.
    """
    try:
        prompt = f"""Tu es un expert Velib Paris. Génère une réponse courte et factuelle
à cette question comme si tu avais les données. Cette réponse sera utilisée
pour rechercher des documents similaires, pas pour être affichée.

Question : {question}

Réponse hypothétique (2-3 phrases factuelles sur les vélos/stations) :"""

        response = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.3,
            },
            timeout=15,
        )
        response.raise_for_status()
        hypothetical = response.json()["choices"][0]["message"]["content"]
        # Combine question + réponse hypothétique pour un meilleur embedding
        return f"{question}\n{hypothetical}"
    except Exception:
        return question


def _bm25_search(query: str, documents: list[dict], top_k: int = 20) -> list[tuple[int, float]]:
    """
    BM25 — recherche lexicale sur les documents.
    Retourne liste de (index, score).
    """
    try:
        from rank_bm25 import BM25Okapi

        tokenized_corpus = [
            doc["text"].lower().split()
            for doc in documents
        ]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        scores = bm25.get_scores(tokenized_query)

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
    except Exception:
        return []


def _cosine_search(query_expanded: str, documents: list[dict], top_k: int = 20) -> list[tuple[int, float]]:
    """
    Recherche par similarité cosine avec sentence-transformers.
    Retourne liste de (index, score).
    """
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        corpus_texts = [doc["text"] for doc in documents]
        corpus_embeddings = model.encode(corpus_texts, show_progress_bar=False)
        query_embedding = model.encode([query_expanded], show_progress_bar=False)[0]

        # Similarité cosine
        norms_corpus = np.linalg.norm(corpus_embeddings, axis=1)
        norm_query = np.linalg.norm(query_embedding)
        similarities = np.dot(corpus_embeddings, query_embedding) / (
            norms_corpus * norm_query + 1e-10
        )

        ranked = sorted(enumerate(similarities), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
    except Exception:
        return []


def _reciprocal_rank_fusion(
    bm25_results: list[tuple[int, float]],
    cosine_results: list[tuple[int, float]],
    k: int = 60,
) -> list[tuple[int, float]]:
    """
    RRF — fusionne les rankings BM25 et cosine.
    Score RRF = 1/(k + rank_bm25) + 1/(k + rank_cosine)
    """
    rrf_scores: dict[int, float] = {}

    for rank, (idx, _) in enumerate(bm25_results):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (k + rank + 1)

    for rank, (idx, _) in enumerate(cosine_results):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (k + rank + 1)

    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)


def _mmr_rerank(
    query_embedding: np.ndarray,
    candidates: list[tuple[int, float]],
    documents: list[dict],
    top_k: int = 8,
    lambda_param: float = 0.7,
) -> list[int]:
    # Déduplique par station pour éviter les doublons
    seen_stations = set()
    fused_deduped = []
    for idx, score in fused:
        station = documents[idx]["metadata"].get("station", "")
        if station not in seen_stations:
            seen_stations.add(station)
        fused_deduped.append((idx, score))
    fused = fused_deduped
    """
    MMR — Maximal Marginal Relevance.
    Sélectionne les documents pertinents ET diversifiés.
    lambda_param : 1.0 = pertinence pure, 0.0 = diversité pure
    """
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

        candidate_indices = [idx for idx, _ in candidates[:30]]
        candidate_texts = [documents[i]["text"] for i in candidate_indices]
        candidate_embeddings = model.encode(candidate_texts, show_progress_bar=False)

        selected = []
        remaining = list(range(len(candidate_indices)))

        while len(selected) < top_k and remaining:
            if not selected:
                # Premier doc — le plus pertinent
                cosine_scores = np.dot(candidate_embeddings, query_embedding) / (
                    np.linalg.norm(candidate_embeddings, axis=1)
                    * np.linalg.norm(query_embedding)
                    + 1e-10
                )
                best = remaining[np.argmax([cosine_scores[i] for i in remaining])]
            else:
                best_score = -float("inf")
                best = None

                for i in remaining:
                    # Pertinence avec la query
                    relevance = np.dot(candidate_embeddings[i], query_embedding) / (
                        np.linalg.norm(candidate_embeddings[i])
                        * np.linalg.norm(query_embedding)
                        + 1e-10
                    )

                    # Similarité max avec les docs déjà sélectionnés
                    max_sim = max(
                        np.dot(candidate_embeddings[i], candidate_embeddings[s]) / (
                            np.linalg.norm(candidate_embeddings[i])
                            * np.linalg.norm(candidate_embeddings[s])
                            + 1e-10
                        )
                        for s in selected
                    )

                    # Score MMR
                    mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

                    if mmr_score > best_score:
                        best_score = mmr_score
                        best = i

            selected.append(best)
            remaining.remove(best)

        return [candidate_indices[i] for i in selected]

    except Exception:
        return [idx for idx, _ in candidates[:top_k]]


def _rerank_with_llm(
    question: str,
    candidates: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """
    Reranking léger par LLM — évalue la pertinence de chaque doc.
    Utilisé sur les top candidats après MMR.
    """
    if len(candidates) <= top_k:
        return candidates

    try:
        docs_str = "\n\n".join([
            f"[Doc {i+1}] {doc['text'][:300]}"
            for i, doc in enumerate(candidates)
        ])

        prompt = f"""Tu dois classer ces documents par pertinence pour répondre à la question.
Réponds UNIQUEMENT avec un JSON : {{"ordre": [1, 3, 2, ...]}}

Question : {question}

Documents :
{docs_str}

Classe les {len(candidates)} documents du plus au moins pertinent."""

        response = requests.post(
            GROQ_URL,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {GROQ_API_KEY}",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 100,
                "temperature": 0.1,
            },
            timeout=15,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        content = content.strip().replace("```json", "").replace("```", "")
        order = json.loads(content)["ordre"]
        reranked = [candidates[i - 1] for i in order if 0 < i <= len(candidates)]
        return reranked[:top_k]
    except Exception:
        return candidates[:top_k]


def hybrid_search(
    question: str,
    documents: list[dict],
    top_k: int = 8,
    use_hyde: bool = True,
    use_mmr: bool = True,
    use_rerank: bool = True,
) -> tuple[list[dict], dict]:
    """
    Pipeline complet :
    HyDE → BM25 + Cosine → RRF → MMR → Reranking LLM
    Retourne (documents_selectionnés, trace)
    """
    trace = {
        "hyde_query": "",
        "bm25_top5": [],
        "cosine_top5": [],
        "rrf_top5": [],
        "mmr_selected": [],
        "final_docs": [],
        "techniques_used": [],
    }

    if not documents:
        return [], trace

    # Étape 1 — HyDE
    if use_hyde and GROQ_API_KEY:
        expanded_query = _hyde_expand_query(question)
        trace["hyde_query"] = expanded_query
        trace["techniques_used"].append("HyDE")
    else:
        expanded_query = question

    # Étape 2 — BM25
    bm25_results = _bm25_search(question, documents, top_k=30)
    trace["bm25_top5"] = [
        documents[idx]["metadata"]["station"]
        for idx, _ in bm25_results[:5]
    ]
    trace["techniques_used"].append("BM25")

    # Étape 3 — Cosine similarity
    cosine_results = _cosine_search(expanded_query, documents, top_k=30)
    trace["cosine_top5"] = [
        documents[idx]["metadata"]["station"]
        for idx, _ in cosine_results[:5]
    ]
    trace["techniques_used"].append("Cosine Similarity")

    # Étape 4 — RRF fusion
    fused = _reciprocal_rank_fusion(bm25_results, cosine_results)
    trace["rrf_top5"] = [
        documents[idx]["metadata"]["station"]
        for idx, _ in fused[:5]
    ]
    trace["techniques_used"].append("RRF Fusion")

    # Étape 5 — MMR
    if use_mmr:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            query_embedding = model.encode([expanded_query], show_progress_bar=False)[0]
            mmr_indices = _mmr_rerank(query_embedding, fused, documents, top_k=min(15, len(fused)))
            candidates = [documents[i] for i in mmr_indices]
            trace["mmr_selected"] = [d["metadata"]["station"] for d in candidates[:5]]
            trace["techniques_used"].append("MMR")
        except Exception:
            candidates = [documents[idx] for idx, _ in fused[:15]]
    else:
        candidates = [documents[idx] for idx, _ in fused[:15]]

    # Étape 6 — Reranking LLM
    if use_rerank and GROQ_API_KEY and len(candidates) > top_k:
        final_docs = _rerank_with_llm(question, candidates, top_k=top_k)
        trace["techniques_used"].append("LLM Reranking")
    else:
        final_docs = candidates[:top_k]

    trace["final_docs"] = [
        f"{d['metadata']['station']} ({d['metadata']['run_at']})"
        for d in final_docs
    ]

    return final_docs, trace


def build_rag_index(df: pd.DataFrame = None):
    """
    Construit l'index en mémoire.
    Retourne (documents, nb_documents) — on stocke les docs bruts pour hybrid search.
    """
    if df is None or df.empty:
        df = _load_history_df()

    if df.empty:
        return None, 0

    documents = _build_documents(df)
    return documents, len(documents)


def ask_rag(question: str, documents) -> tuple[str, dict]:
    """
    RAG avancé avec pipeline complet.
    Retourne (réponse, trace).
    """
    if not documents:
        return "Index RAG non disponible. Capturez des snapshots d'abord.", {}

    # Pipeline hybrid search
    final_docs, search_trace = hybrid_search(question, documents)

    if not final_docs:
        return "Aucune donnee pertinente trouvee.", search_trace

    # Construction du contexte avec citations
    context_parts = []
    for i, doc in enumerate(final_docs):
        meta = doc["metadata"]
        citation = f"[Source {i+1}: {meta['station']} — {meta['run_at']} — snapshot {meta['snapshot_id']}]"
        context_parts.append(f"{citation}\n{doc['text']}")

    context = "\n\n".join(context_parts)

    prompt = f"""Tu es un expert en mobilite urbaine specialise dans le reseau Velib Paris.
Reponds en francais de maniere concise et precise.

INSTRUCTIONS :
- Utilise UNIQUEMENT les donnees ci-dessous
- Pour chaque affirmation, cite la source entre crochets [Source N]
- Si une information n'est pas dans les donnees, dis-le clairement
- Ne fais pas d'hypotheses sur des donnees non fournies

Donnees historiques :
{context}

Question : {question}
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
                "max_tokens": 600,
                "temperature": 0.2,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"]

        # Tokens
        usage = data.get("usage", {})
        search_trace["tokens"] = {
            "prompt": usage.get("prompt_tokens", 0),
            "completion": usage.get("completion_tokens", 0),
            "total": usage.get("total_tokens", 0),
        }
        search_trace["sources_used"] = [
            f"{d['metadata']['station']} — {d['metadata']['run_at']}"
            for d in final_docs
        ]

        return answer, search_trace

    except Exception as e:
        return f"Erreur Groq : {e}", search_trace


def ask_rag_with_qdrant_context(question: str, documents, qdrant_docs: list) -> tuple[str, dict]:
    # Mots-clés indiquant une question temps réel
    realtime_keywords = ["anomalie", "maintenant", "actuellement", "en ce moment", "disponible", "vide", "pleine"]
    is_realtime = any(kw in question.lower() for kw in realtime_keywords)

    # Si question temps réel ET Qdrant a des docs — utilise Qdrant directement (plus rapide)
    if is_realtime and qdrant_docs:
        context = "\n".join(f"- {d}" for d in qdrant_docs)
        prompt = f"""Tu es un expert Velib Paris. Reponds en francais uniquement avec ces donnees.
Si la station n'est pas dans les donnees, dis-le clairement.

Donnees :
{context}

Question : {question}"""
        try:
            response = requests.post(
                GROQ_URL,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_API_KEY}"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "max_tokens": 400, "temperature": 0.2},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"], {"fast_path": True, "reason": "question temps reel"}
        except Exception as e:
            pass

    if documents:
        return ask_rag(question, documents)

    if qdrant_docs:
        context = "\n".join(f"- {d}" for d in qdrant_docs)
        prompt = f"""Tu es un expert Velib Paris. Reponds en francais uniquement avec ces donnees.
Cite les informations importantes.

Donnees :
{context}

Question : {question}"""
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
                    "temperature": 0.2,
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"], {}
        except Exception as e:
            return f"Erreur Groq : {e}", {}

    return "Aucune donnee disponible. Capturez des snapshots.", {}