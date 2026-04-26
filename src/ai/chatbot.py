import requests

from config import GROQ_API_KEY
from llm_client import call_llm_text


def build_context(df) -> str:
    return f"""
- Stations actives : {df['station_id'].nunique()}
- Vélos disponibles : {int(df['numbikesavailable'].sum())}
- Bornes disponibles : {int(df['numdocksavailable'].sum())}
- Taux de remplissage moyen : {df['bike_ratio'].mean():.1%}
- Stations vides : {int(df['is_empty'].sum())}
- Stations pleines : {int(df['is_full'].sum())}
- Vélos mécaniques : {int(df['mechanical'].sum())}
- Vélos électriques : {int(df['ebike'].sum())}
- Top 3 mieux fournies : {', '.join(df.nlargest(3, 'numbikesavailable')['name'].tolist())}
- Top 3 plus vides : {', '.join(df.nsmallest(3, 'numbikesavailable')['name'].tolist())}
"""


def ask_groq(question: str, context: str) -> str:
    if not GROQ_API_KEY:
        return "Clé Groq non configurée dans les secrets Streamlit."

    prompt = f"""
Tu es un expert en mobilité urbaine à Paris spécialisé dans le réseau Vélib'.
Réponds en français de manière concise et utile.

Données actuelles :
{context}

Question : {question}
"""

    try:
        answer, _ = call_llm_text(
            prompt,
            max_tokens=500,
            temperature=0.7,
            timeout=30,
        )
        return answer

    except Exception as e:
        return f"Erreur Groq : {e}"