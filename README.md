#  Vélib' Data Pipeline v2.0
**AWS Lambda · Aurora Serverless v2 · S3 · API Gateway · EventBridge**

Pipeline de données automatisé autour du service Vélib' Métropole à Paris.  
Collecte horaire, stockage cloud historisé, rapports PDF et API de téléchargement.

---

## Endpoints

> Les endpoints changent à chaque déploiement. Pour les obtenir :
> ```bash
> cd infrastructure/
> terraform output api_endpoint
> ```

| Endpoint | Description |
|---|---|
| `GET` {api_endpoint}/health | Status |
| `GET` {api_endpoint}/download/csv | Dernier CSV |
| `GET` {api_endpoint}/download/report | Dernier PDF IA |

---

##  Architecture

```
API Vélib' opendata.paris.fr
↓ toutes les heures
EventBridge Scheduler
↓
Lambda Pipeline (Python 3.12)
├── fetch.py             → 1509 stations récupérées
├── transform.py         → nettoyage + enrichissement
├── insert.py            → Aurora Serverless v2 (append-only + snapshot_id)
├── save.py              → S3 partitionné year=/month=/day=/
└── generate_report.py  → PDF reportlab → S3

Lambda API + API Gateway
├── GET /health
├── GET /download/csv
└── GET /download/report
```

---

##  Structure

```
velib-data-pipeline/
├── lambdas/
│   ├── pipeline/
│   │   ├── handler.py
│   │   ├── fetch.py             ← collecte opendata
│   │   ├── transform.py         ← nettoyage
│   │   ├── insert.py            ← Aurora
│   │   ├── save.py              ← S3 Hive
|   |   ├── ai_report.py         
│   │   ├── generate_report.py   ← PDF
│   │   ├── secrets_helper.py
│   │   └── requirements.txt
│   └── api/
│       ├── handler.py
│       └── requirements.txt
└── infrastructure/
    └── main.tf
```

---

##  Migration v1 → v2

| Avant | Après |
|---|---|
| Railway + Airflow | AWS Lambda + EventBridge |
| FastAPI + Uvicorn | API Gateway + Lambda |
| PostgreSQL Railway | Aurora Serverless v2 |
| DROP TABLE chaque run | Append-only + snapshot_id |
| S3 fichier unique écrasé | S3 Hive partitionné |
| Aucune alerte | CloudWatch + SNS email |
| Docker + entrypoint.sh | Lambda Layers auto-buildés |
| Rapport PDF statique | Rapport narratif Groq API (Llama 3.3)  Gratuit |
| NAT Gateway ~$1/jour | Supprimé — Aurora public |

---

##  Coûts estimés

| Service | Coût/mois |
|---|---|
| Lambda | Gratuit (free tier) |
| API Gateway | Gratuit (free tier) |
| S3 | < $0.05 |
| EventBridge | Gratuit |
| NAT Gateway | $0 — supprimé  |
| Aurora Serverless v2 | ~$0.06/heure quand active |
| Groq API (Llama 3.3) | Gratuit |
| **Total au repos** | **~$0/mois** |

---

##  Déploiement

### Prérequis

- AWS CLI configuré (`aws configure`)
- Terraform >= 1.6
- Python 3.12
- Docker (pour builder le Lambda Layer)

### Lancer l'infrastructure

```bash
cd infrastructure/
terraform init
terraform apply -var-file="terraform.tfvars"
```

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

##  Données collectées

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

##  Roadmap


###  Phase 1 — Backend AWS Serverless
- [x] Lambda pipeline
- [x] Aurora Serverless v2 append-only
- [x] API Gateway endpoints
- [x] S3 Hive partitionné
- [x] CloudWatch + SNS alertes
- [x] Terraform IaC complet + Lambda Layer auto-buildé
- [x] Aurora public — suppression NAT Gateway

###  Phase 3 — IA Générative (en cours)
- [x] Rapport PDF narratif avec Groq AI
- [ ] Chatbot "Ask Vélib Data" — text-to-SQL
- [ ] Agent de monitoring autonome
- [ ] Forecasting disponibilité des stations