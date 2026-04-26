"""
assistant.py — Assistant IA unifié Vélib

L'assistant route automatiquement les questions vers :
- données temps réel
- anomalies
- RAG historique
- recherche sémantique
- rapport
"""

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from llm_client import call_llm_text
from src.ai.prompts import FINAL_SYNTHESIS_PROMPT
from src.ai.router import classify_question
from src.ai.tools import (
    detect_anomalies_tool,
    generate_report_tool,
    get_network_stats_tool,
    get_station_info_tool,
    search_history_rag_tool,
    semantic_search_tool,
    tool_result_to_text,
)


@dataclass
class AssistantTrace:
    question: str
    intent: str = ""
    confidence: float = 0.0
    routing_reason: str = ""
    tools_used: list[str] = field(default_factory=list)
    tool_results: dict[str, Any] = field(default_factory=dict)
    tokens: dict[str, int] = field(default_factory=dict)
    final_answer: str = ""


def _extract_possible_station(question: str, df: pd.DataFrame) -> str | None:
    """
    Détection simple d'une station mentionnée dans la question.
    On évite un appel LLM supplémentaire.
    """
    if df is None or df.empty or "name" not in df.columns:
        return None

    q = question.upper()

    stations = sorted(
        df["name"].dropna().unique().tolist(),
        key=len,
        reverse=True,
    )

    for station in stations:
        if station and station in q:
            return station

    # fallback par mots distinctifs
    words = [w for w in q.split() if len(w) >= 4]
    best_station = None
    best_score = 0

    for station in stations:
        score = sum(1 for w in words if w in station)
        if score > best_score:
            best_score = score
            best_station = station

    return best_station if best_score >= 1 else None


def _synthesize_answer(
    question: str,
    intent: str,
    tool_results_text: str,
) -> tuple[str, dict[str, int]]:
    prompt = f"""
Question utilisateur :
{question}

Intention détectée :
{intent}

Résultats des outils :
{tool_results_text}

Produis la réponse finale.
"""

    return call_llm_text(
        prompt,
        system_prompt=FINAL_SYNTHESIS_PROMPT,
        max_tokens=700,
        temperature=0.2,
        timeout=30,
    )


def run_unified_assistant(
    question: str,
    df: pd.DataFrame,
    *,
    qdrant_client=None,
    rag_documents=None,
    qdrant_docs=None,
    use_llm_router: bool = False,
) -> tuple[str, AssistantTrace]:
    """
    Point d'entrée principal de l'assistant IA unifié.
    """
    trace = AssistantTrace(question=question)

    routing = classify_question(question, use_llm=use_llm_router)
    intent = routing.get("intent", "general")

    trace.intent = intent
    trace.confidence = routing.get("confidence", 0.0)
    trace.routing_reason = routing.get("reason", "")

    tool_outputs = {}

    try:
        if intent == "realtime":
            station = _extract_possible_station(question, df)

            if station:
                result = get_station_info_tool(station, df)
                trace.tools_used.append("get_station_info")
                tool_outputs["get_station_info"] = result
            else:
                result = get_network_stats_tool(df)
                trace.tools_used.append("get_network_stats")
                tool_outputs["get_network_stats"] = result

        elif intent == "anomaly":
            anomalies = detect_anomalies_tool(df)
            stats = get_network_stats_tool(df)

            trace.tools_used.extend(["detect_anomalies", "get_network_stats"])
            tool_outputs["detect_anomalies"] = anomalies
            tool_outputs["get_network_stats"] = stats

        elif intent == "historical":
            answer, rag_trace = search_history_rag_tool(
                question,
                rag_documents,
                qdrant_client=qdrant_client,
                qdrant_docs=qdrant_docs,
            )

            trace.tools_used.append("search_history_rag")
            tool_outputs["search_history_rag"] = {
                "answer": answer,
                "trace": rag_trace,
            }

            # Si le RAG donne déjà une réponse bien formée, on la retourne directement.
            trace.tool_results = tool_outputs
            trace.final_answer = answer
            return answer, trace

        elif intent == "semantic":
            semantic_result = semantic_search_tool(
                question,
                qdrant_client,
                n_results=8,
            )

            trace.tools_used.append("semantic_search")
            tool_outputs["semantic_search"] = semantic_result

        elif intent == "report":
            stats = get_network_stats_tool(df)
            anomalies = detect_anomalies_tool(df)
            report = generate_report_tool(df)

            trace.tools_used.extend(
                ["get_network_stats", "detect_anomalies", "generate_report"]
            )
            tool_outputs["get_network_stats"] = stats
            tool_outputs["detect_anomalies"] = anomalies
            tool_outputs["generate_report"] = {
                k: v for k, v in report.items() if k != "pdf_bytes"
            }

        else:
            stats = get_network_stats_tool(df)
            trace.tools_used.append("get_network_stats")
            tool_outputs["get_network_stats"] = stats

        trace.tool_results = tool_outputs

        tool_results_text = "\n\n".join(
            f"[{name}]\n{tool_result_to_text(result)}"
            for name, result in tool_outputs.items()
        )

        answer, tokens = _synthesize_answer(
            question,
            intent,
            tool_results_text,
        )

        trace.tokens = tokens
        trace.final_answer = answer

        return answer, trace

    except Exception as e:
        error = f"Erreur assistant IA : {e}"
        trace.final_answer = error
        return error, trace