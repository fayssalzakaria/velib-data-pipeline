# 🚲 Vélib' Data Pipeline  
**Apache Airflow • Railway • AWS S3**

Un pipeline de données complet autour du service Vélib’ Métropole à Paris, avec automatisation horaire, archivage cloud et rapports visuels.

---

## 🎯 Objectifs du projet

- 🔄 Collecte automatique des données en temps réel via l’API [opendata.paris.fr](https://opendata.paris.fr).
- 🧼 Transformation des données brutes en tableaux exploitables (`pandas`).
- 🗄️ Insertion dans une base PostgreSQL hébergée sur Railway.
- 💾 Sauvegarde CSV locale + envoi automatique sur AWS S3.
- 📊 Génération de rapports PDF (stats + graphiques).
- ⏰ Orchestration horaire via Apache Airflow (Dockerisé).
- 🔗 Intégration facile dans Power BI / Excel / outils analytiques.

---

## ⚙️ Technologies utilisées

| Technologie       | Usage principal                            |
|-------------------|---------------------------------------------|
| **Apache Airflow**| Orchestration & planification               |
| **Railway**       | Hébergement Airflow + base PostgreSQL       |
| **AWS S3**        | Stockage cloud CSV & rapports PDF           |
| **Python 3.9+**   | Langage principal                           |
| **Pandas / Matplotlib** | Traitement & visualisation           |
| **FastAPI / Uvicorn**   | API de téléchargement à distance     |
| **SQLAlchemy**    | Interaction base de données                 |

---

## 🛠️ Fonctionnement du pipeline

> 📅 **Planification :** toutes les heures

1. 📡 Récupération des données via l'API Vélib’.
2. 🧼 Nettoyage et enrichissement des données (format tabulaire).
3. 🗃️ Insertion dans PostgreSQL (Railway).
4. 📥 Sauvegarde CSV (locale + S3).
5. 🧾 Génération d’un rapport PDF (graphique + stats).
6. ☁️ Envoi des fichiers dans AWS S3.

---

## 🗂️ Structure du projet
```
velib-data-pipeline/
├── airflow/
│ ├── dags/
│ │ └── velib_dag.py # DAG Airflow principal
│ └── scripts/
│ ├── fetch.py # API Vélib’
│ ├── transform.py # Nettoyage / enrichissement
│ ├── insert.py # PostgreSQL (Railway)
│ ├── save.py # CSV + upload S3
│ └── generate_report.py # PDF + S3
│
├── Dockerfile # Image Airflow personnalisée
├── entrypoint.sh # Lancement webserver + scheduler
├── requirements.txt # Dépendances Python
└── .env / Variables Railway # URL DB, clés AWS, bucket, etc.
```
yaml
Copier
Modifier

---

## 📈 Rapport PDF – Contenu

Le rapport PDF généré automatiquement contient :

### ✅ Synthèse visuelle :

- **Top 10 stations les mieux fournies**
- **Top 10 stations les plus vides**
- **Top 10 stations les plus grandes** (capacités totales)
- **Répartition des états des stations** :
  - 🔴 Vides
  - 🟢 Pleines
  - 🟡 Partielles
- **Types de vélos disponibles** :
  - 🚲 Mécaniques
  - ⚡ Électriques

### ✅ Statistiques globales :

- Nombre de stations
- Nombre total de vélos
- Nombre total de bornes
- Taux de remplissage moyen

---

## 📦 Fichiers téléchargeables

- 📄 [Dernier rapport PDF](https://velib-data-pipeline-production.up.railway.app/download/report)
- 📊 [Dernier fichier CSV](https://velib-data-pipeline-production.up.railway.app/download/csv)

---

## 🌐 Interface Airflow

👉 **Lien pour accéder à l’interface Airflow**  
🔗 [https://velib-data-pipeline-production.up.railway.app](https://velib-data-pipeline-production.up.railway.app)

---

## ⚡ API de téléchargement – FastAPI

| Endpoint             | Description                                    |
|----------------------|------------------------------------------------|
| `/download/report`   | Télécharge le rapport PDF le plus récent       |
| `/download/csv`      | Télécharge le fichier CSV le plus récent       |

> 🔧 API FastAPI servie par `Uvicorn`, déployée en parallèle d’Airflow.

---

## 👤 Cas d’usage

- 👨‍💼 **Décideur / Analyste** : Consulter les rapports visuels.
- 📊 **Power BI / Excel** : Charger automatiquement les fichiers CSV.
- 🔁 **Usage personnel** : Suivre en temps réel l’état du réseau Vélib’.
