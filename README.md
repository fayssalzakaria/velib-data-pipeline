# Vélib' Data Pipeline v2.0

**AWS Lambda · Aurora Serverless v2 · S3 · API Gateway · Streamlit · Groq AI**

Pipeline de données automatisé autour du service Vélib' Métropole à Paris.
Collecte horaire, stockage cloud historisé, rapports PDF narratifs générés par IA,
et dashboard interactif en temps réel.

---

## Dashboard Streamlit

Le dashboard est accessible publiquement sans AWS actif.

**Fonctionnalités :**

- Données en temps réel depuis l'API Vélib' opendata.paris.fr
- Carte interactive des 1509 stations de Paris
- Graphiques top stations, types de vélos, état du réseau
- Recherche de station avec détails en temps réel
- Filtres par type de vélo, état, nombre minimum de vélos
- Chatbot "Ask Vélib Data" propulsé par Groq (Llama 3.3)
- Historique d'une station depuis Aurora (si AWS actif)
- Téléchargement CSV et rapport PDF

---

## Endpoints API

Les endpoints changent à chaque déploiement. Pour les obtenir :

```bash
cd infrastructure/
terraform output api_endpoint
```

| Endpoint | Description |
|---|---|
| GET {api_endpoint}/health | Status |
| GET {api_endpoint}/download/csv | Dernier CSV |
| GET {api_endpoint}/download/report | Dernier rapport PDF IA |

---

## Architecture

```
API Vélib' opendata.paris.fr
        ↓ toutes les heures (EventBridge)
Lambda Pipeline (Python 3.12)
    ├── fetch.py          → 1509 stations récupérées
    ├── transform.py      → nettoyage + enrichissement
    ├── insert.py         → Aurora Serverless v2 (append-only + snapshot_id)
    ├── save.py           → S3 partitionné year=/month=/day=/
    └── ai_report.py      → analyse Groq AI + PDF → S3

Lambda API + API Gateway
    ├── GET /health
    ├── GET /download/csv
    └── GET /download/report

Streamlit Dashboard (Streamlit Cloud)
    ├── Source API Vélib' directe (gratuit, toujours disponible)
    └── Source AWS S3 (snapshots historiques, AWS requis)
```

---

## Structure du projet

```
velib-data-pipeline/
├── app.py                    ← point d'entrée Streamlit
├── ui.py                     ← composants interface
├── data_loader.py            ← chargement API + S3
├── filters.py                ← logique de filtrage
├── chatbot.py                ← intégration Groq
├── history.py                ← historique Aurora
├── config.py                 ← variables de configuration
├── requirements.txt          ← dépendances Streamlit
├── deploy-velib.sh           ← script de déploiement Lambda
├── lambdas/
│   ├── pipeline/
│   │   ├── handler.py        ← point d'entrée Lambda pipeline
│   │   ├── fetch.py          ← collecte opendata
│   │   ├── transform.py      ← nettoyage des données
│   │   ├── insert.py         ← insertion Aurora (append-only)
│   │   ├── save.py           ← upload S3 Hive partitionné
│   │   ├── ai_report.py      ← rapport PDF narratif Groq
│   │   ├── secrets_helper.py ← gestion secrets AWS
│   │   └── requirements.txt
│   └── api/
│       ├── handler.py        ← endpoints download
│       └── requirements.txt
└── infrastructure/
    ├── main.tf               ← Terraform IaC complet
    ├── build_layer.sh        ← build Lambda Layer via Docker
    └── terraform.tfvars      ← variables (non versionné)
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
| Rapport PDF statique | Rapport narratif Groq AI (Llama 3.3) |
| NAT Gateway ~$1/jour | Supprimé — Aurora public |
| Pas d'interface | Dashboard Streamlit interactif |

---

## Coûts estimés

| Service | Coût/mois |
|---|---|
| Lambda | Gratuit (free tier) |
| API Gateway | Gratuit (free tier) |
| S3 | < $0.05 |
| EventBridge | Gratuit |
| NAT Gateway | $0 — supprimé |
| Aurora Serverless v2 | ~$0.06/heure quand active |
| Groq API (Llama 3.3) | Gratuit |
| Streamlit Cloud | Gratuit |
| **Total au repos** | **~$0/mois** |

> Aurora ne coûte que pendant les sessions actives. Faire `terraform destroy` après chaque session ramène le coût à $0.

---

## Déploiement

### Prérequis

- AWS CLI configuré (`aws configure`)
- Terraform >= 1.6
- Docker (pour builder le Lambda Layer)

### Lancer l'infrastructure

```bash
cd infrastructure/
terraform init
terraform apply -var-file="terraform.tfvars"
```

### Déployer le code Lambda

```bash
./deploy-velib.sh
```

Le script récupère automatiquement les endpoints Aurora et API Gateway depuis Terraform, met à jour les variables d'environnement Lambda, et lance le pipeline.

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

### Lambda (gérées par deploy-velib.sh)

| Variable | Description |
|---|---|
| `POSTGRES_URL` | URL Aurora (récupérée depuis Terraform) |
| `S3_BUCKET` | Nom du bucket S3 |
| `GROQ_API_KEY` | Clé API Groq |
| `SNS_ALERT_TOPIC_ARN` | ARN topic SNS alertes |

### Streamlit (secrets Streamlit Cloud)

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Clé API Groq pour le chatbot |
| `AWS_ACCESS_KEY_ID` | Accès S3 (optionnel) |
| `AWS_SECRET_ACCESS_KEY` | Accès S3 (optionnel) |
| `S3_BUCKET` | Nom du bucket S3 (optionnel) |
| `POSTGRES_URL` | URL Aurora pour l'historique (optionnel) |
| `API_ENDPOINT` | URL API Gateway pour le PDF (optionnel) |

> Les variables marquées "optionnel" activent des fonctionnalités supplémentaires mais le dashboard fonctionne sans elles.

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
| `run_at` | Timestamp UTC du run |

---

## Roadmap

### Phase 1 — Backend AWS Serverless
- [x] Lambda pipeline horaire automatique
- [x] Aurora Serverless v2 avec historique complet (append-only)
- [x] API Gateway endpoints (health, csv, report)
- [x] S3 Hive partitionné compatible Athena
- [x] CloudWatch Alarms + SNS email alerts
- [x] Terraform IaC complet + Lambda Layer auto-buildé
- [x] Aurora public — suppression NAT Gateway (~$0/mois au repos)

### Phase 3 — IA Générative + Dashboard
- [x] Rapport PDF narratif avec Groq AI (Llama 3.3-70b)
- [x] Dashboard Streamlit interactif
- [x] Chatbot "Ask Vélib Data" en langage naturel
- [x] Recherche et filtres de stations
- [x] Historique d'une station depuis Aurora
- [ ] Agent de monitoring autonome
- [ ] Forecasting disponibilité des stations