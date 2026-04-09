# Vélib API Lambda

Remplace FastAPI + Uvicorn + Railway.

## Endpoints

| Endpoint | Description |
|---|---|
| GET /download/report | Dernier rapport PDF |
| GET /download/csv | Dernier CSV |
| GET /health | Status |

## Différences avec l'ancien système

| Ancien | Nouveau |
|---|---|
| FastAPI serveur permanent | Lambda (0 serveur) |
| Uvicorn sur Railway | API Gateway HTTP API |
| Coût fixe 24h/24 | Coût à l'usage |

## Variables d'environnement requises

| Variable | Description |
|---|---|
| S3_BUCKET | Nom du bucket S3 |
| AWS_REGION | Region AWS (eu-north-1) |