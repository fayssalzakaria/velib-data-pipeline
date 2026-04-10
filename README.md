#  Vélib' Data Pipeline v2.0
**AWS Lambda · Aurora Serverless v2 · S3 · API Gateway · EventBridge**

Pipeline de données automatisé autour du service Vélib' Métropole à Paris.  
Collecte horaire, stockage cloud historisé, rapports PDF et API de téléchargement.

---

##  Endpoints

| Endpoint | Description |
|---|---|
| `GET` https://v52sw2rux7.execute-api.eu-north-1.amazonaws.com/health | Status |
| `GET` https://v52sw2rux7.execute-api.eu-north-1.amazonaws.com/download/csv | Dernier CSV |
| `GET` https://v52sw2rux7.execute-api.eu-north-1.amazonaws.com/download/report | Dernier PDF |

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
| Docker + entrypoint.sh | Lambda Layers |

---

##  Coûts estimés

| Service | Coût/mois |
|---|---|
| Lambda pipeline (720 runs) | ~$1.50 |
| Aurora Serverless v2 | ~$10 |
| NAT Gateway | ~$3 |
| S3 + API Gateway | < $0.10 |
| **Total** | **~$15/mois** |

---

##  Déploiement

### Prérequis

- AWS CLI configuré (`aws configure`)
- Terraform >= 1.6
- Python 3.12

### Lancer l'infrastructure

```bash
cd infrastructure/
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### Déclencher le pipeline manuellement

```bash
aws lambda invoke \
  --function-name velib-pipeline-prod-pipeline \
  --region eu-north-1 \
  --payload '{}' \
  response.json && cat response.json
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

- [x] Lambda pipeline horaire automatique
- [x] Aurora Serverless v2 avec historique complet
- [x] API Gateway endpoints
- [x] S3 Hive partitionné compatible Athena
- [x] CloudWatch Alarms + SNS email alerts
- [x] Terraform IaC complet

###  Phase 3 — IA Générative

- [ ] Rapport PDF avec analyse narrative (Claude API)
- [ ] Chatbot "Ask Vélib Data" — questions en langage naturel
- [ ] Agent de monitoring autonome
- [ ] Forecasting disponibilité des stations