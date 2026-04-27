# Vélib' Data Pipeline v2.2 — Data & IA Générative

**AWS Lambda · Aurora Serverless v2 · S3 · API Gateway · Streamlit · FastAPI · Groq · Qdrant · LangChain · RAG · Agents IA**

Projet d’analyse du réseau Vélib’ combinant **Data Engineering**, **dashboard temps réel** et **IA générative**.  
L’application collecte les données Vélib’, les historise, les visualise dans Streamlit et propose un assistant IA capable d’utiliser du RAG, des tools métier, de la recherche sémantique et une évaluation de pertinence.

> Le dashboard Streamlit fonctionne même sans infrastructure AWS active : il utilise directement l’API Open Data Vélib’.

---

## Objectif

Ce projet démontre une architecture complète autour de :

- ingestion de données temps réel ;
- historisation cloud ;
- dashboard analytique ;
- assistant IA RAG/Agents ;
- recherche sémantique Qdrant ;
- intégration LLM via Groq ;
- intégration LangChain ;
- API REST FastAPI ;
- analyse NLP des questions ;
- génération de rapports PDF ;
- évaluation automatique de pertinence.

---

## Fonctionnalités principales

### Dashboard Streamlit

- données temps réel depuis l’API Vélib’ `opendata.paris.fr` ;
- carte interactive des stations ;
- filtres par type de vélo, état et nombre de vélos disponibles ;
- graphiques réseau : top stations, vélos mécaniques/électriques, stations vides/pleines ;
- recherche de station avec détails temps réel ;
- historique d’une station depuis S3 ou Aurora lorsque disponible ;
- téléchargement CSV ;
- génération de rapports PDF IA ;
- assistant IA unifié ;
- RAG historique ;
- agent IA avec tools ;
- recherche sémantique Qdrant ;
- affichage du raisonnement NLP de l’assistant.

### Assistant IA unifié

L’assistant choisit automatiquement le bon traitement selon la question :

| Intention | Traitement |
|---|---|
| `realtime` | données temps réel |
| `anomaly` | détection d’anomalies + statistiques réseau |
| `historical` | RAG historique |
| `semantic` | recherche sémantique Qdrant |
| `report` | statistiques + anomalies + rapport PDF |
| `general` | synthèse générale |

Exemples :

```text
Y a-t-il des anomalies maintenant ?
```

→ utilise `detect_anomalies` + `get_network_stats`

```text
Bastille est-elle souvent vide le matin ?
```

→ utilise le RAG historique

---

## Nouveautés v2.2

### Modularisation

Les fichiers applicatifs sont organisés dans `src/` :

```text
src/
├── ai/
│   ├── agent.py
│   ├── assistant.py
│   ├── chatbot.py
│   ├── langchain_assistant.py
│   ├── nlp_utils.py
│   ├── prompts.py
│   ├── rag.py
│   ├── router.py
│   ├── tools.py
│   └── vector_store.py
│
├── data/
│   ├── data_loader.py
│   ├── filters.py
│   ├── history.py
│   └── snapshot.py
│
├── reports/
│   └── report_generator.py
│
└── ui/
    └── ui.py
```

### Client LLM centralisé

Le fichier `llm_client.py` centralise :

- les appels Groq ;
- le parsing JSON ;
- le suivi des tokens ;
- la gestion d’erreurs ;
- l’évaluation de pertinence.

Les modules IA utilisent maintenant :

```python
from llm_client import call_llm_text, call_llm_json, call_llm, verify_relevance
```

### NLP visible dans Streamlit

Un module `src/ai/nlp_utils.py` analyse les questions utilisateur :

- normalisation du texte ;
- extraction de mots-clés ;
- détection d’expressions temporelles ;
- aide au routage d’intention.

Dans l’interface, l’utilisateur peut voir comment l’assistant travaille :

```text
Question utilisateur
→ normalisation NLP
→ mots-clés extraits
→ expressions temporelles
→ intention détectée
→ tools utilisés
→ réponse finale
→ score de pertinence
```

### LangChain

Le module `src/ai/langchain_assistant.py` ajoute une intégration LangChain avec Groq afin de démontrer l’usage d’un framework IA moderne.

### API REST FastAPI

Une API locale expose l’assistant IA :

```text
api/main.py
```

Endpoints :

| Endpoint | Description |
|---|---|
| `GET /health` | vérification de l’API |
| `POST /route` | routage d’intention |
| `POST /ask` | assistant IA unifié |
| `POST /ask/langchain` | chaîne LangChain + Groq |
| `POST /nlp/analyze` | analyse NLP d’un texte |

Lancement :

```bash
python -m uvicorn api.main:app --reload --port 8000
```

Documentation interactive :

```text
http://127.0.0.1:8000/docs
```

---

## Pipeline RAG

Le RAG historique est implémenté dans :

```text
src/ai/rag.py
```

Il combine :

- HyDE ;
- BM25 ;
- embeddings SentenceTransformers ;
- similarité cosinus ;
- RRF ;
- MMR ;
- reranking LLM optionnel ;
- citations ;
- évaluation de pertinence.

Pipeline :

```text
Question
  ↓
HyDE
  ↓
BM25 + recherche vectorielle
  ↓
RRF
  ↓
MMR
  ↓
Reranking optionnel
  ↓
Contexte sourcé
  ↓
Réponse LLM
  ↓
Score de pertinence
```

---

## Base vectorielle

Le projet utilise Qdrant dans :

```text
src/ai/vector_store.py
```

Rôles principaux :

- indexation des snapshots historiques ;
- transformation des lignes en documents textuels ;
- embeddings avec `sentence-transformers/all-MiniLM-L6-v2` ;
- recherche sémantique ;
- extraction de station depuis une question utilisateur.

---

## Architecture globale

```text
API Vélib' Open Data
        ↓
Pipeline AWS Lambda / EventBridge
        ↓
Aurora Serverless v2 + S3
        ↓
Streamlit Dashboard
        ↓
Assistant IA unifié
        ↓
Router NLP
   ├── temps réel
   ├── anomalies
   ├── RAG historique
   ├── recherche Qdrant
   ├── rapport PDF
   └── LangChain / Groq
        ↓
Réponse finale + pertinence
```

---

## Architecture cloud AWS

```text
API Vélib'
   ↓ toutes les heures
Lambda Pipeline
   ├── fetch.py
   ├── transform.py
   ├── insert.py → Aurora Serverless v2
   ├── save.py   → S3 partitionné
   └── ai_report.py → rapport PDF IA

API Gateway + Lambda API
   ├── GET /health
   ├── GET /download/csv
   └── GET /download/report
```

---

## Structure du projet

```text
velib-data-pipeline/
├── app.py
├── config.py
├── llm_client.py
├── requirements.txt
├── deploy-velib.sh
│
├── api/
│   ├── main.py
│   └── README.md
│
├── src/
│   ├── ai/
│   ├── data/
│   ├── reports/
│   └── ui/
│
├── lambdas/
│   ├── pipeline/
│   └── api/
│
└── infrastructure/
    ├── main.tf
    ├── build_layer.sh
    └── terraform.tfvars
```

---

## Variables d’environnement

### Streamlit / API locale

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | clé Groq |
| `GROQ_MODEL` | modèle Groq, par défaut `llama-3.3-70b-versatile` |
| `QDRANT_URL` | URL Qdrant optionnelle |
| `QDRANT_API_KEY` | clé Qdrant optionnelle |
| `AWS_ACCESS_KEY_ID` | accès S3 optionnel |
| `AWS_SECRET_ACCESS_KEY` | accès S3 optionnel |
| `S3_BUCKET` | bucket S3 optionnel |
| `POSTGRES_URL` | URL Aurora optionnelle |
| `API_ENDPOINT` | endpoint API Gateway optionnel |

En local, un fichier `.env` peut être utilisé. Il ne doit pas être versionné.

---

## Déploiement AWS

### Prérequis

- AWS CLI ;
- Terraform ;
- Docker ;
- clé Groq ;
- compte Streamlit Cloud.

### Lancer l’infrastructure

```bash
cd infrastructure/
terraform init
terraform apply -var-file="terraform.tfvars"
```

### Déployer les Lambdas

```bash
./deploy-velib.sh
```

### Stopper l’infrastructure

```bash
cd infrastructure/
terraform destroy
```

---

## Commandes utiles

### Lancer Streamlit

```bash
streamlit run app.py
```

### Lancer l’API FastAPI

```bash
python -m uvicorn api.main:app --reload --port 8000
```

### Vérifier la compilation

```bash
python -m compileall app.py src api llm_client.py
```

### Vérifier que Groq est centralisé

```bash
find . \\
  -path "./infrastructure" -prune -o \\
  -path "./lambdas" -prune -o \\
  -name "*.py" -type f -print \\
  | xargs grep -n "requests.post"
```

Résultat attendu :

```text
./llm_client.py:...
```

---

## Roadmap

### Réalisé

- [x] pipeline AWS serverless ;
- [x] historisation Aurora + S3 ;
- [x] dashboard Streamlit ;
- [x] rapport PDF IA ;
- [x] client LLM centralisé ;
- [x] RAG hybride ;
- [x] Qdrant ;
- [x] agent IA avec tools ;
- [x] assistant IA unifié ;
- [x] routage d’intention ;
- [x] analyse NLP visible ;
- [x] évaluation de pertinence ;
- [x] API REST FastAPI ;
- [x] intégration LangChain.

### À venir

- [ ] RAG documentaire PDF/DOCX ;
- [ ] Docker Compose Streamlit + Qdrant + FastAPI ;
- [ ] dataset d’évaluation RAG ;
- [ ] tests unitaires ;
- [ ] forecasting de disponibilité ;
- [ ] monitoring autonome des anomalies.

