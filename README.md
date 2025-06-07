#  Vélib' Data Pipeline with Apache Airflow, Railway & AWS S3

Ce projet déploie un pipeline de données complet autour du service Vélib’ Métropole à Paris. Il permet de collecter, transformer, stocker et analyser les données de disponibilité des vélos via un DAG Apache Airflow. L’infrastructure est hébergée sur [Railway](https://railway.app) : **à la fois le scheduler Airflow et la base de données PostgreSQL**. Les fichiers sont archivés sur AWS S3.

---

##  Objectifs du projet

-  **Collecte automatique** des données Vélib’ en temps réel via l’API opendata.paris.fr
-  **Transformation & nettoyage** des données JSON en format tabulaire (Pandas DataFrame)
-  **Insertion dans une base PostgreSQL Railway**
-  **Sauvegarde locale & envoi vers AWS S3** sous forme de fichiers CSV
-  **Génération automatique de rapports PDF** (graphiques & stats) également envoyés sur S3
-  **Orchestration complète et planification horaire via Apache Airflow**
-  **Export horaire vers S3 pour usage personnel ou intégration avec Power BI**

---

## 🎯 Fonctionnement

Chaque heure :
1. Les données sont extraites depuis l’API Vélib’.
2. Elles sont nettoyées et enrichies via `Pandas`.
3. Elles sont insérées dans une base PostgreSQL déployée sur Railway.
4. Elles sont exportées au format `.csv` (sauvegarde locale + upload vers AWS S3).
5. Un rapport PDF est généré avec des graphiques synthétiques et aussi envoyé sur S3.

🗂️ **Le fichier CSV courant peut être utilisé dans Power BI**, et  
📄 **le rapport PDF est téléchargeable à des fins de suivi ou de reporting personnel.**

---

## ⚙️ Technologies utilisées

- **Apache Airflow** (Dockerisé, déployé sur Railway)
- **Python 3.9+**
- **Railway** (déploiement du serveur Airflow **et** de la base PostgreSQL)
- **AWS S3** (stockage de fichiers)
- **Pandas / Matplotlib**
- **SQLAlchemy**
- **Requests** (API REST Vélib’)

---

## 📂 Structure du projet

velib-data-pipeline/
│
├── airflow/
│ ├── dags/
│ │ └── velib_dag.py # DAG principal Airflow
│ └── scripts/
│ ├── fetch.py # Requête API Vélib’
│ ├── transform.py # Nettoyage & enrichissement
│ ├── insert.py # Insertion SQL (Railway PostgreSQL)
│ ├── save.py # Sauvegarde CSV + S3
│ └── generate_report.py # Rapport PDF + Upload S3
│
├── Dockerfile # Environnement Airflow
├── entrypoint.sh # Lancement Webserver + Scheduler
├── requirements.txt # Dépendances Python
└── .env / Railway Variables # Clés AWS, URL DB, bucket S3...
## Rapport pdf
Le rapport contient :

Top 10 stations avec le plus de vélos

Top 10 stations vides

Répartition des états des stations

Plus grandes stations par capacité

##  API de téléchargement – FastAPI

Une API FastAPI légère est intégrée au projet pour permettre le **téléchargement à distance** des fichiers générés (rapport PDF et dernier CSV), directement depuis AWS S3.

Cette API est exposée sur Railway (port 8081) en parallèle du serveur Airflow (port 8080).

### 🔗 Endpoints disponibles

| Endpoint | Description |
|----------|-------------|
| `/download/report` | 📄 Télécharge le dernier rapport PDF (`report.pdf`) |
| `/download/csv`    | 📁 Télécharge le dernier fichier CSV (`velib_...csv`) |

> Exemple :  
> `https://<ton-projet>.railway.app:8081/download/report`  
> `https://<ton-projet>.railway.app:8081/download/csv`

---

###  Utilisations typiques

-  **Analyste ou décideur** : Télécharger et visualiser le rapport PDF synthétique (graphiques).
-  **Utilisateur Power BI / Excel** : Récupérer le dernier CSV pour créer des tableaux de bord interactifs.

---

### ⚙ Stack technique de l’API

- **FastAPI** : framework léger pour créer des endpoints REST
- **Uvicorn** : serveur ASGI rapide
- **Boto3** : SDK AWS pour récupérer les fichiers S3
- Exécutée en parallèle d'Airflow depuis `entrypoint.sh`

---
