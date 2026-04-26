# Vélib' Data Pipeline v2.1 — IA RAG & Agents

**AWS Lambda · Aurora Serverless v2 · S3 · API Gateway · Streamlit · Groq AI · Qdrant · RAG Hybride · Agent IA**

Pipeline de données automatisé autour du service Vélib' Métropole à Paris.
Le projet combine collecte de données temps réel, stockage historisé, dashboard interactif, génération de rapports PDF narratifs par IA, recherche sémantique, pipeline RAG avancé et assistant IA unifié avec routage automatique.

> L'application Streamlit reste accessible publiquement même lorsque l'infrastructure AWS est arrêtée. Dans ce mode, elle utilise directement l'API Vélib' Open Data.

---

## Objectif du projet

Ce projet vise à démontrer une architecture complète de **Data Engineering + IA Générative** :

- ingestion de données temps réel ;
- historisation cloud ;
- dashboard analytique ;
- recherche sémantique ;
- pipeline RAG hybride ;
- agent IA avec outils métier ;
- assistant IA unifié capable de router automatiquement les questions ;
- génération de rapports PDF ;
- évaluation automatique de la pertinence des réponses.

Le projet est conçu pour être valorisable dans un contexte professionnel de type :

> Développement d'une application IA Gen RAG / Agents avec LLMs, embeddings, base vectorielle, orchestration d'outils, génération de rapports et évaluation de qualité.

---

## Dashboard Streamlit

Le dashboard est accessible sans AWS actif grâce à la source directe API Vélib'.

**Fonctionnalités principales :**

- données en temps réel depuis l'API Vélib' `opendata.paris.fr` ;
- carte interactive des stations Vélib' ;
- graphiques top stations, types de vélos, état du réseau ;
- recherche de station avec détails en temps réel ;
- filtres par type de vélo, état et nombre minimum de vélos ;
- historique d'une station depuis S3 ou Aurora lorsque disponible ;
- téléchargement CSV ;
- génération de rapport PDF IA ;
- assistant IA unifié ;
- chatbot RAG historique ;
- agent IA avec tools ;
- recherche sémantique Qdrant.

---

## Nouveautés v2.1 — Refactorisation IA, RAG et Agent unifié

Cette version ajoute une architecture IA plus professionnelle et modulaire.

### 1. Modularisation du projet

Les fichiers Python applicatifs ont été déplacés dans une structure `src/` :

```text
src/
├── ai/
│   ├── agent.py
│   ├── assistant.py
│   ├── chatbot.py
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

Le fichier `app.py` reste le point d'entrée principal Streamlit.

---

### 2. Centralisation des appels Groq

Un nouveau fichier a été ajouté :

```text
llm_client.py
```

Il centralise :

- les appels Groq ;
- le parsing JSON des réponses LLM ;
- l'extraction des tokens ;
- l'évaluation automatique de pertinence ;
- la gestion d'erreurs LLM.

Avant, plusieurs fichiers appelaient directement `requests.post(...)` vers Groq.
Désormais, les appels LLM passent par :

```python
from llm_client import call_llm_text, call_llm_json, call_llm, verify_relevance
```

Cela rend le code plus maintenable, plus testable et plus professionnel.

---

### 3. Assistant IA unifié

Un nouvel assistant a été ajouté :

```text
src/ai/assistant.py
```

Il devient le point d'entrée IA principal côté interface.

L'assistant choisit automatiquement le bon mode de réponse selon la question utilisateur :

| Type de question | Traitement utilisé |
|---|---|
| Disponibilité actuelle | données temps réel |
| Station spécifique | tool station info |
| Anomalies actuelles | tool anomalies + statistiques réseau |
| Historique / tendances | pipeline RAG historique |
| Recherche exploratoire | recherche sémantique Qdrant |
| Rapport / synthèse | génération de rapport IA |
| Question générale | synthèse à partir des données disponibles |

Exemples :

```text
Y a-t-il des anomalies maintenant ?
```

→ utilise `detect_anomalies` + `get_network_stats`

```text
Bastille est-elle souvent vide le matin ?
```

→ utilise le RAG historique

```text
Fais-moi un rapport sur l'état actuel du réseau
```

→ utilise statistiques + anomalies + rapport PDF

---

### 4. Routeur d'intention

Un nouveau module :

```text
src/ai/router.py
```

Il classe automatiquement les questions en intentions :

```text
realtime
anomaly
historical
semantic
report
general
```

Le routage peut fonctionner :

- en mode rapide par règles ;
- ou en mode LLM si activé.

Par défaut, le mode par règles est utilisé pour limiter les coûts et accélérer les réponses.

---

### 5. Tools IA centralisés

Un nouveau module :

```text
src/ai/tools.py
```

Il regroupe les outils métier utilisés par l'assistant :

- `get_station_info_tool` ;
- `get_network_stats_tool` ;
- `detect_anomalies_tool` ;
- `search_history_rag_tool` ;
- `semantic_search_tool` ;
- `generate_report_tool`.

Ces tools permettent à l'assistant de fonctionner comme un vrai agent métier spécialisé Vélib'.

---

### 6. Prompts centralisés

Un nouveau module :

```text
src/ai/prompts.py
```

Il contient :

- le prompt système de l'assistant ;
- le prompt de routage ;
- le prompt de synthèse finale.

Cela évite de disperser les prompts dans plusieurs fichiers.

---

### 7. Évaluation de pertinence dans l'assistant unifié

L'assistant unifié intègre maintenant une évaluation globale de la pertinence.

Pour chaque réponse, le système calcule :

- un score entre 0 et 100 ;
- une explication courte ;
- une comparaison entre la réponse finale et les résultats des outils utilisés.

Exemple d'affichage :

```text
Pertinence : 92/100
La réponse reprend correctement les données des outils et ne semble pas halluciner.
```

Dans le cas d'une question historique, l'assistant récupère aussi la pertinence issue du pipeline RAG lorsque disponible.

---

## Architecture IA v2.1

```text
Utilisateur
   ↓
Streamlit UI
   ↓
Assistant IA unifié
   ↓
Routeur d'intention
   ├── realtime   → get_station_info / get_network_stats
   ├── anomaly    → detect_anomalies + get_network_stats
   ├── historical → RAG historique
   ├── semantic   → Qdrant semantic search
   ├── report     → stats + anomalies + PDF report
   └── general    → synthèse générale
   ↓
LLM Groq / Llama 3.3
   ↓
Réponse finale + score de pertinence
```

---

## Pipeline RAG

Le pipeline RAG historique reste séparé dans :

```text
src/ai/rag.py
```

Il utilise plusieurs techniques avancées :

- génération HyDE ;
- recherche lexicale BM25 ;
- recherche vectorielle par embeddings ;
- fusion RRF ;
- MMR pour diversifier les résultats ;
- reranking LLM optionnel ;
- citations des sources ;
- score de pertinence.

Pipeline :

```text
Question
  ↓
HyDE expansion
  ↓
BM25 + Cosine similarity
  ↓
RRF Fusion
  ↓
MMR
  ↓
Reranking LLM optionnel
  ↓
Contexte sourcé
  ↓
Réponse LLM
  ↓
Évaluation de pertinence
```

---

## Base vectorielle

Le projet utilise Qdrant pour la recherche sémantique :

```text
src/ai/vector_store.py
```

Fonctions principales :

- chargement de l'historique depuis S3 ;
- transformation des lignes de données en documents textuels ;
- embeddings avec `sentence-transformers/all-MiniLM-L6-v2` ;
- stockage dans Qdrant ;
- recherche sémantique ;
- extraction simple de station depuis une question utilisateur.

---

## Endpoints API AWS

Les endpoints changent à chaque déploiement. Pour les obtenir :

```bash
cd infrastructure/
terraform output api_endpoint
```

| Endpoint | Description |
|---|---|
| `GET {api_endpoint}/health` | Statut de l'API |
| `GET {api_endpoint}/download/csv` | Dernier CSV |
| `GET {api_endpoint}/download/report` | Dernier rapport PDF IA |

---

## Architecture cloud

```text
API Vélib' opendata.paris.fr
        ↓ toutes les heures via EventBridge
Lambda Pipeline Python 3.12
    ├── fetch.py          → stations récupérées
    ├── transform.py      → nettoyage + enrichissement
    ├── insert.py         → Aurora Serverless v2 append-only + snapshot_id
    ├── save.py           → S3 partitionné year=/month=/day=/
    └── ai_report.py      → analyse Groq AI + PDF → S3

Lambda API + API Gateway
    ├── GET /health
    ├── GET /download/csv
    └── GET /download/report

Streamlit Dashboard
    ├── Source API Vélib' directe
    ├── Source AWS S3 si disponible
    ├── Assistant IA unifié
    ├── RAG historique
    ├── Agent IA
    └── Recherche sémantique Qdrant
```

---

## Structure du projet

```text
velib-data-pipeline/
├── app.py                         ← point d'entrée Streamlit
├── config.py                      ← variables de configuration
├── llm_client.py                  ← client LLM centralisé Groq
├── requirements.txt               ← dépendances Streamlit
├── deploy-velib.sh                ← script de déploiement Lambda
│
├── src/
│   ├── ai/
│   │   ├── agent.py               ← agent IA avec tools Groq
│   │   ├── assistant.py           ← assistant IA unifié
│   │   ├── chatbot.py             ← chatbot simple sur contexte courant
│   │   ├── prompts.py             ← prompts centralisés
│   │   ├── rag.py                 ← moteur RAG hybride
│   │   ├── router.py              ← routage d'intention
│   │   ├── tools.py               ← tools métier IA
│   │   └── vector_store.py        ← Qdrant + embeddings
│   │
│   ├── data/
│   │   ├── data_loader.py         ← chargement API + S3
│   │   ├── filters.py             ← logique de filtrage
│   │   ├── history.py             ← historique Aurora / S3
│   │   └── snapshot.py            ← capture snapshots + refresh index IA
│   │
│   ├── reports/
│   │   └── report_generator.py    ← génération PDF IA
│   │
│   └── ui/
│       └── ui.py                  ← composants Streamlit
│
├── lambdas/
│   ├── pipeline/
│   │   ├── handler.py             ← point d'entrée Lambda pipeline
│   │   ├── fetch.py               ← collecte Open Data
│   │   ├── transform.py           ← nettoyage des données
│   │   ├── insert.py              ← insertion Aurora
│   │   ├── save.py                ← upload S3 Hive partitionné
│   │   ├── ai_report.py           ← rapport PDF narratif Groq
│   │   ├── secrets_helper.py      ← gestion secrets AWS
│   │   └── requirements.txt
│   │
│   └── api/
│       ├── handler.py             ← endpoints download
│       └── requirements.txt
│
└── infrastructure/
    ├── main.tf                    ← Terraform IaC complet
    ├── build_layer.sh             ← build Lambda Layer via Docker
    └── terraform.tfvars           ← variables non versionnées
```

---

## Migration v1 → v2

| Avant | Après |
|---|---|
| Railway + Airflow | AWS Lambda + EventBridge |
| FastAPI + Uvicorn | API Gateway + Lambda |
| PostgreSQL Railway | Aurora Serverless v2 |
| DROP TABLE chaque run | Append-only + snapshot_id |
| S3 fichier unique écrasé | S3 Hive partitionné |
| Aucune alerte | CloudWatch + SNS email |
| Docker + entrypoint.sh | Lambda Layers auto-buildés via Docker |
| Rapport PDF statique | Rapport narratif Groq AI |
| NAT Gateway ~$1/jour | Supprimé — Aurora public |
| Dashboard simple | Dashboard Streamlit + IA Gen |

---

## Migration v2 → v2.1

| Avant v2 | Après v2.1 |
|---|---|
| Fichiers Python à la racine | Architecture modulaire `src/` |
| Appels Groq répétés | `llm_client.py` centralisé |
| Chatbot, RAG et agent séparés | Assistant IA unifié avec routage |
| RAG accessible dans un onglet séparé | RAG utilisable comme tool par l'assistant |
| Prompts dispersés | `prompts.py` centralisé |
| Pas de routeur d'intention global | `router.py` avec intentions |
| Tools éparpillés | `tools.py` centralisé |
| Pertinence dans RAG/agent uniquement | Pertinence globale assistant unifié |

---

## Coûts estimés

| Service | Coût/mois |
|---|---:|
| Lambda | Gratuit avec free tier |
| API Gateway | Gratuit avec free tier |
| S3 | < $0.05 |
| EventBridge | Gratuit |
| NAT Gateway | $0 — supprimé |
| Aurora Serverless v2 | ~$0.06/heure quand active |
| Groq API | Gratuit selon quota disponible |
| Streamlit Cloud | Gratuit |
| Qdrant Cloud | Gratuit selon quota disponible |
| **Total au repos** | **~$0/mois** |

> Aurora ne coûte que pendant les sessions actives. Faire `terraform destroy` après chaque session permet de ramener le coût au repos à environ $0.

---

## Déploiement

### Prérequis

- AWS CLI configuré avec `aws configure` ;
- Terraform >= 1.6 ;
- Docker pour builder le Lambda Layer ;
- compte Streamlit Cloud ;
- clé Groq ;
- Qdrant Cloud optionnel pour la recherche sémantique.

### Lancer l'infrastructure

```bash
chmod +x ~/velib-data-pipeline/infrastructure/build_layer.sh
cd infrastructure/
terraform init
terraform apply -var-file="terraform.tfvars"
```

### Déployer le code Lambda

```bash
chmod +x ~/velib-data-pipeline-git/deploy-velib.sh
./deploy-velib.sh
```

Le script récupère automatiquement les endpoints Aurora et API Gateway depuis Terraform, met à jour les variables d'environnement Lambda et lance le pipeline.

### Déclencher le pipeline manuellement

```bash
aws lambda invoke \
  --function-name velib-pipeline-prod-pipeline \
  --region eu-north-1 \
  --payload '{}' \
  response.json && cat response.json
```

### Stopper pour économiser

```bash
cd infrastructure/
terraform destroy
```

---

## Variables d'environnement

### Lambda

| Variable | Description |
|---|---|
| `POSTGRES_URL` | URL Aurora récupérée depuis Terraform |
| `S3_BUCKET` | Nom du bucket S3 |
| `GROQ_API_KEY` | Clé API Groq |
| `SNS_ALERT_TOPIC_ARN` | ARN du topic SNS alertes |

### Streamlit Cloud

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Clé Groq pour chatbot, RAG, agent et assistant |
| `AWS_ACCESS_KEY_ID` | Accès S3 optionnel |
| `AWS_SECRET_ACCESS_KEY` | Accès S3 optionnel |
| `S3_BUCKET` | Bucket S3 optionnel |
| `POSTGRES_URL` | URL Aurora optionnelle |
| `API_ENDPOINT` | URL API Gateway optionnelle |
| `QDRANT_URL` | URL Qdrant optionnelle |
| `QDRANT_API_KEY` | Clé Qdrant optionnelle |
| `GROQ_MODEL` | Modèle Groq, par défaut `llama-3.3-70b-versatile` |

> Les variables optionnelles activent des fonctionnalités supplémentaires. Le dashboard fonctionne sans AWS actif grâce à l'API Vélib' directe.

---

## Données collectées

| Champ | Description |
|---|---|
| `station_id` | Identifiant unique station |
| `name` | Nom de la station |
| `numbikesavailable` | Vélos disponibles |
| `mechanical` | Vélos mécaniques |
| `ebike` | Vélos électriques |
| `numdocksavailable` | Bornes disponibles |
| `bike_ratio` | Taux de remplissage |
| `is_empty` | Station vide |
| `is_full` | Station pleine |
| `snapshot_id` | Identifiant du run horaire |
| `run_at` | Timestamp du run |
| `hour` | Heure du snapshot |
| `weekday` | Jour de la semaine |
| `is_weekend` | Indicateur week-end |

---

## Fonctionnalités IA détaillées

### Assistant IA unifié

- routage automatique ;
- réponse synthétique ;
- appels aux tools métier ;
- utilisation du RAG si historique nécessaire ;
- utilisation de Qdrant si recherche sémantique ;
- évaluation de pertinence globale.

### RAG historique

- HyDE ;
- BM25 ;
- embeddings ;
- cosine similarity ;
- RRF ;
- MMR ;
- reranking LLM ;
- citations ;
- pertinence.

### Agent IA

- tools Groq ;
- choix automatique des fonctions ;
- statistiques réseau ;
- station info ;
- anomalies ;
- recherche historique.

### Recherche sémantique

- Qdrant ;
- embeddings SentenceTransformers ;
- recherche de patterns ;
- extraction de station depuis la requête.

### Rapports IA

- PDF généré avec ReportLab ;
- synthèse LLM ;
- statistiques globales ;
- top stations ;
- points d'attention.

---

## Roadmap

### Phase 1 — Backend AWS Serverless

- [x] Lambda pipeline horaire automatique
- [x] Aurora Serverless v2 avec historique append-only
- [x] API Gateway endpoints health, csv, report
- [x] S3 Hive partitionné compatible Athena
- [x] CloudWatch Alarms + SNS email alerts
- [x] Terraform IaC complet + Lambda Layer auto-buildé
- [x] Aurora public — suppression NAT Gateway

### Phase 2 — Refactorisation et architecture IA

- [x] Modularisation du projet dans `src/`
- [x] Centralisation des appels Groq dans `llm_client.py`
- [x] Nettoyage des imports après déplacement des modules
- [x] Préparation d'une architecture maintenable data / ai / ui / reports

### Phase 3 — IA Générative + Dashboard

- [x] Rapport PDF narratif avec Groq AI
- [x] Dashboard Streamlit interactif
- [x] Chatbot Ask Vélib Data
- [x] Recherche et filtres de stations
- [x] Historique d'une station depuis Aurora ou S3
- [x] RAG historique avancé
- [x] Recherche sémantique Qdrant
- [x] Agent IA avec tools
- [x] Assistant IA unifié avec routage automatique
- [x] Évaluation de pertinence dans l'assistant unifié

### Phase 4 — Améliorations futures

- [ ] RAG documentaire PDF/DOCX
- [ ] API FastAPI locale pour exposer l'assistant
- [ ] Docker Compose local Streamlit + Qdrant
- [ ] Dataset d'évaluation RAG avec questions/réponses attendues
- [ ] Monitoring autonome des anomalies
- [ ] Forecasting disponibilité des stations
- [ ] Tests unitaires sur router, tools et RAG
- [ ] Documentation technique avec diagrammes d'architecture

---

## Commandes utiles

### Lancer Streamlit

```bash
streamlit run app.py
```

### Vérifier la compilation Python

```bash
python -m compileall app.py src llm_client.py
```

### Vérifier qu'il ne reste pas d'appels Groq directs hors client central

```bash
find . \
  -path "./infrastructure" -prune -o \
  -path "./lambdas" -prune -o \
  -name "*.py" -type f -print \
  | xargs grep -n "requests.post"
```

Le résultat attendu est uniquement :

```text
./llm_client.py:...
```

### Vérifier les anciens imports cassés

```bash
find . \
  -path "./infrastructure" -prune -o \
  -path "./lambdas" -prune -o \
  -name "*.py" -type f -print \
  | xargs grep -n "from rag\|from vector_store\|from chatbot\|from history\|from snapshot\|from report_generator\|from agent"
```

---

## Exemple de commits associés

### Refactorisation LLM et architecture

```bash
git commit -m "refactor(llm): centraliser les appels Groq et modulariser le projet"
```

### Assistant IA unifié

```bash
git commit -m "feat(ai): unifier l'assistant IA avec routage RAG et tools"
```

### Pertinence assistant

```bash
git commit -m "feat(ai): ajouter l'évaluation de pertinence à l'assistant unifié"
```

---

## Résumé CV

> Développement d'une application Data + IA Générative pour l'analyse du réseau Vélib' : pipeline AWS serverless, dashboard Streamlit, base vectorielle Qdrant, RAG hybride BM25/embeddings/RRF/MMR, agent IA avec tools, assistant unifié avec routage automatique, génération de rapports PDF et évaluation automatique de la pertinence des réponses LLM.
