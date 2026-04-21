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
    """Détecte les stations avec comportement inhabituel."""
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
                "stations": vides[:5],
                "count": len(vides),
            })

    # Stations avec très peu de bornes libres
    presque_pleines = df[df["numdocksavailable"] <= 2]
    if not presque_pleines.empty:
        anomalies.append({
            "type": "stations_presque_pleines",
            "stations": presque_pleines["name"].tolist()[:5],
            "count": len(presque_pleines),
        })

    # Déséquilibre vélos électriques/mécaniques
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
        "heure_analyse": f"{heure}h",
        "anomalies": anomalies if anomalies else ["Aucune anomalie detectee"],
    })


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


def run_agent(question: str, df: pd.DataFrame, qdrant_client=None) -> str:
    """
    Agent LangChain-style avec tool calling Groq.
    Choisit automatiquement le bon tool selon la question.
    """
    if not GROQ_API_KEY:
        return "Cle Groq non configuree."

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un agent expert en mobilite urbaine specialise dans le reseau Velib Paris. "
                "Tu utilises les tools disponibles pour repondre precisement aux questions. "
                "Reponds toujours en francais de maniere concise et utile. "
                "Utilise plusieurs tools si necessaire pour donner une reponse complete."
            ),
        },
        {"role": "user", "content": question},
    ]

    try:
        # Premier appel — l'agent choisit ses tools
        response = _call_groq(messages, tools=TOOLS_SCHEMA)
        choice = response["choices"][0]
        message = choice["message"]

        # Pas de tool call — réponse directe
        if not message.get("tool_calls"):
            return message.get("content", "Aucune reponse generee.")

        # Exécute les tools appelés
        messages.append(message)

        for tool_call in message["tool_calls"]:
            tool_name = tool_call["function"]["name"]
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

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

        # Deuxième appel — génère la réponse finale avec les résultats des tools
        final_response = _call_groq(messages)
        return final_response["choices"][0]["message"].get("content", "Aucune reponse.")

    except Exception as e:
        return f"Erreur agent : {e}"