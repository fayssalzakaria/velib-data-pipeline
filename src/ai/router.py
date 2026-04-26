"""
router.py — Routage automatique des questions utilisateur
"""

from llm_client import call_llm_json
from src.ai.prompts import ROUTER_PROMPT


KEYWORDS_REALTIME = [
    "maintenant",
    "actuellement",
    "en ce moment",
    "disponible",
    "disponibles",
    "combien de vélo",
    "combien de velos",
    "station",
]

KEYWORDS_ANOMALY = [
    "anomalie",
    "anomalies",
    "vide",
    "vides",
    "pleine",
    "pleines",
    "critique",
    "critiques",
    "déséquilibre",
    "desequilibre",
]

KEYWORDS_HISTORICAL = [
    "historique",
    "souvent",
    "tendance",
    "tendances",
    "évolution",
    "evolution",
    "hier",
    "semaine",
    "week-end",
    "weekend",
    "matin",
    "soir",
    "midi",
    "comparaison",
    "compare",
]

KEYWORDS_REPORT = [
    "rapport",
    "bilan",
    "synthèse",
    "synthese",
    "résumé",
    "resume",
    "pdf",
]


def classify_question_rule_based(question: str) -> dict:
    """
    Classification simple sans LLM.
    Sert de fallback rapide et économique.
    """
    q = question.lower()

    if any(kw in q for kw in KEYWORDS_REPORT):
        return {
            "intent": "report",
            "confidence": 0.75,
            "reason": "La question demande un rapport ou une synthèse.",
        }

    if any(kw in q for kw in KEYWORDS_ANOMALY):
        return {
            "intent": "anomaly",
            "confidence": 0.8,
            "reason": "La question mentionne des anomalies ou stations critiques.",
        }

    if any(kw in q for kw in KEYWORDS_HISTORICAL):
        return {
            "intent": "historical",
            "confidence": 0.8,
            "reason": "La question concerne une tendance ou un historique.",
        }

    if any(kw in q for kw in KEYWORDS_REALTIME):
        return {
            "intent": "realtime",
            "confidence": 0.65,
            "reason": "La question semble porter sur l'état actuel du réseau.",
        }

    return {
        "intent": "general",
        "confidence": 0.5,
        "reason": "Aucune intention spécifique détectée par règles.",
    }


def classify_question(question: str, use_llm: bool = False) -> dict:
    """
    Route la question vers une intention.

    Par défaut, utilise les règles pour éviter un appel LLM inutile.
    Si use_llm=True, demande une classification au modèle.
    """
    rule_result = classify_question_rule_based(question)

    if not use_llm:
        return rule_result

    try:
        prompt = f"""
Question utilisateur :
{question}
"""

        data, _ = call_llm_json(
            prompt,
            system_prompt=ROUTER_PROMPT,
            max_tokens=150,
            temperature=0.1,
            timeout=15,
        )

        intent = data.get("intent", rule_result["intent"])
        confidence = float(data.get("confidence", rule_result["confidence"]))
        reason = data.get("reason", rule_result["reason"])

        valid_intents = {
            "realtime",
            "anomaly",
            "historical",
            "semantic",
            "report",
            "general",
        }

        if intent not in valid_intents:
            return rule_result

        return {
            "intent": intent,
            "confidence": max(0.0, min(1.0, confidence)),
            "reason": reason,
        }

    except Exception:
        return rule_result