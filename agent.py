"""
agent.py — Agent LangChain avec tools pour analyse Vélib'
Commit 3 Phase ML : feat(ml): LangChain agent with custom tools
"""
import os
import io
import json
import pandas as pd
import requests
import pytz
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentTrace:
    question: str = ""
    tools_called: list = field(default_factory=list)
    tool_results: dict = field(default_factory=dict)
    prompt_sent: str = ""
    raw_response: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    relevance_score: int = 0
    relevance_explanation: str = ""
    final_answer: str = ""

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
PARIS_TZ = pytz.timezone("Europe/Paris")


def _call_groq(messages: list, tools: list = None, max_tokens: int = 1000) -> dict:
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    response = requests.post(
        GROQ_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
        },
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def tool_get_station_info(station_name: str, df: pd.DataFrame) -> str:
    """Retourne les infos temps réel d'une station."""
    if df is None or df.empty:
        return json.dumps({"error": "Données non disponibles"})

    results = df[df["name"].str.contains(station_name.upper(), na=False)]
    if results.empty:
        return json.dumps({"error": f"Station '{station_name}' non trouvée"})

    row = results.iloc[0]
    return json.dumps({
        "station": row["name"],
        "velos_disponibles": int(row["numbikesavailable"]),
        "velos_electriques": int(row["ebike"]),
        "velos_mecaniques": int(row["mechanical"]),
        "bornes_disponibles": int(row["numdocksavailable"]),
        "taux_remplissage": f"{float(row['bike_ratio']):.0%}",
        "etat": "vide" if row["is_empty"] else "pleine" if row["is_full"] else "disponible",
    })


def tool_get_network_stats(df: pd.DataFrame) -> str:
    """Retourne les stats globales du réseau."""
    if df is None or df.empty:
        return json.dumps({"error": "Données non disponibles"})

    return json.dumps({
        "stations_actives": len(df),
        "velos_disponibles": int(df["numbikesavailable"].sum()),
        "velos_electriques": int(df["ebike"].sum()),
        "velos_mecaniques": int(df["mechanical"].sum()),
        "bornes_disponibles": int(df["numdocksavailable"].sum()),
        "taux_remplissage_moyen": f"{df['bike_ratio'].mean():.0%}",
        "stations_vides": int(df["is_empty"].sum()),
        "stations_pleines": int(df["is_full"].sum()),
        "top3_mieux_fournies": df.nlargest(3, "numbikesavailable")["name"].tolist(),
        "top3_plus_vides": df.nsmallest(3, "numbikesavailable")["name"].tolist(),
    })


def tool_search_history(query: str, qdrant_client) -> str:
    """Recherche dans l'historique via Qdrant."""
    if qdrant_client is None:
        return json.dumps({"error": "Historique non disponible"})
    try:
        from vector_store import semantic_search
        docs = semantic_search(query, qdrant_client, n_results=5)
        return json.dumps({"resultats": docs})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_detect_anomalies(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return json.dumps({"error": "Données non disponibles"})

    now = datetime.now(PARIS_TZ)
    heure = now.hour
    anomalies = []

    # Stations vides aux heures de pointe
    if 7 <= heure <= 9 or 17 <= heure <= 19:
        vides = df[df["is_empty"]]["name"].tolist()
        if vides:
            anomalies.append({
                "type": "stations_vides_heure_pointe",
                "heure": heure,
                "stations": vides,  # toutes les stations
                "count": len(vides),
            })

    # Stations avec très peu de bornes libres
    presque_pleines = df[df["numdocksavailable"] <= 2]
    if not presque_pleines.empty:
        anomalies.append({
            "type": "stations_presque_pleines",
            "stations": presque_pleines["name"].tolist(),  # toutes
            "count": len(presque_pleines),
        })

    # Stations vides
    vides = df[df["is_empty"]]
    if not vides.empty:
        anomalies.append({
            "type": "stations_vides",
            "stations": vides["name"].tolist(),
            "count": len(vides),
        })

    # Déséquilibre vélos électriques
    total_ebike = int(df["ebike"].sum())
    total_mechanical = int(df["mechanical"].sum())
    total = total_ebike + total_mechanical
    ratio_ebike = total_ebike / max(total, 1)
    if ratio_ebike < 0.2:
        anomalies.append({
            "type": "manque_velos_electriques",
            "ratio_actuel": f"{ratio_ebike:.0%}",
            "seuil": "20%",
        })

    return json.dumps({
        "source": "temps_reel",
        "heure_analyse": f"{heure}h",
        "total_stations": len(df),
        "anomalies": anomalies if anomalies else ["Aucune anomalie detectee"],
    }, ensure_ascii=False)


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_station_info",
            "description": "Obtenir les informations temps reel d'une station Velib specifique",
            "parameters": {
                "type": "object",
                "properties": {
                    "station_name": {
                        "type": "string",
                        "description": "Nom ou partie du nom de la station",
                    }
                },
                "required": ["station_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_network_stats",
            "description": "Obtenir les statistiques globales du reseau Velib en temps reel",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_history",
            "description": "Rechercher dans l'historique des donnees Velib pour repondre a des questions temporelles",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Question ou recherche sur l'historique",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_anomalies",
            "description": "Detecter les anomalies et comportements inhabituels sur le reseau",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def run_agent(question: str, df: pd.DataFrame, qdrant_client=None) -> tuple[str, AgentTrace]:
    trace = AgentTrace(question=question)

    if not GROQ_API_KEY:
        return "Cle Groq non configuree.", trace

    messages = [
    {
    "role": "system",
    "content": (
        "Tu es un agent expert en mobilite urbaine specialise dans le reseau Velib Paris. "
        "Tu utilises les tools disponibles pour repondre precisement aux questions. "
        "Reponds toujours en francais de maniere concise et utile. "
        "IMPORTANT : pour les questions sur les anomalies et l'etat actuel du reseau, "
        "utilise detect_anomalies et get_network_stats qui analysent les donnees temps reel. "
        "Pour les questions sur l'historique et les tendances, utilise search_history. "
        "Quand tu listes des stations, cite-les TOUTES sans truncation. "
        "Utilise plusieurs tools si necessaire pour donner une reponse complete."
        ),
    },
        {"role": "user", "content": question},
    ]

    try:
        response = _call_groq(messages, tools=TOOLS_SCHEMA)
        choice = response["choices"][0]
        message = choice["message"]

        # Tokens premier appel
        usage = response.get("usage", {})
        trace.prompt_tokens += usage.get("prompt_tokens", 0)
        trace.completion_tokens += usage.get("completion_tokens", 0)

        if not message.get("tool_calls"):
            answer = message.get("content", "Aucune reponse.")
            trace.final_answer = answer
            trace.raw_response = answer
            trace.total_tokens = trace.prompt_tokens + trace.completion_tokens
            return answer, trace

        messages.append(message)
        all_tool_data = []

        for tool_call in message["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            trace.tools_called.append(tool_name)

            try:
                args = json.loads(tool_call["function"]["arguments"])
            except Exception:
                args = {}

            if tool_name == "get_station_info":
                result = tool_get_station_info(args.get("station_name", ""), df)
            elif tool_name == "get_network_stats":
                result = tool_get_network_stats(df)
            elif tool_name == "search_history":
                result = tool_search_history(args.get("query", ""), qdrant_client)
            elif tool_name == "detect_anomalies":
                result = tool_detect_anomalies(df)
            else:
                result = json.dumps({"error": f"Tool {tool_name} inconnu"})

            trace.tool_results[tool_name] = json.loads(result)
            all_tool_data.append(f"[{tool_name}] {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

        # Prompt final reconstruit
        trace.prompt_sent = "\n".join([
            f"[{m['role'].upper()}] {m.get('content', '') or ''}"
            for m in messages
            if m.get("content")
        ])

        final_response = _call_groq(messages)
        answer = final_response["choices"][0]["message"].get("content", "Aucune reponse.")

        # Tokens second appel
        usage2 = final_response.get("usage", {})
        trace.prompt_tokens += usage2.get("prompt_tokens", 0)
        trace.completion_tokens += usage2.get("completion_tokens", 0)
        trace.total_tokens = trace.prompt_tokens + trace.completion_tokens
        trace.raw_response = answer
        trace.final_answer = answer

        # Vérification pertinence
        tool_data_str = "\n".join(all_tool_data)
        score, explanation = _verify_relevance(question, answer, tool_data_str)
        trace.relevance_score = score
        trace.relevance_explanation = explanation

        return answer, trace

    except Exception as e:
        error_msg = f"Erreur agent : {e}"
        trace.final_answer = error_msg
        return error_msg, trace

def _verify_relevance(question: str, answer: str, tool_data: str) -> tuple[int, str]:
    """
    Vérifie la pertinence de la réponse par rapport aux données réelles.
    Retourne (score 0-100, explication).
    """
    prompt = f"""Tu es un évaluateur de qualité pour un système IA Velib.
Evalue la pertinence de la réponse par rapport à la question et aux données.

Question : {question}

Données utilisées :
{tool_data}

Réponse générée :
{answer}

Réponds UNIQUEMENT avec un JSON valide :
{{
  "score": <entier entre 0 et 100>,
  "explication": "<1-2 phrases expliquant le score>"
}}

Critères :
- 90-100 : réponse précise, basée sur les données, sans hallucination
- 70-89 : réponse correcte mais incomplète
- 50-69 : réponse partiellement correcte
- 0-49 : réponse incorrecte ou hallucinée
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
                "max_tokens": 200,
                "temperature": 0.1,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        content = content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        data = json.loads(content)
        return int(data.get("score", 0)), data.get("explication", "")
    except Exception as e:
        return 0, f"Erreur évaluation : {e}"