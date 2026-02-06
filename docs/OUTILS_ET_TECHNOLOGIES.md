# Outils et Technologies du Projet

## Vue d'Ensemble

Ce projet de pipeline de donnees pour la prediction des retards aeriens utilise **24 outils/technologies** repartis en 9 categories.

---

## 1. Data Pipeline

| Outil | Role |
|-------|------|
| **Apache Kafka** | Message broker pour le streaming de donnees en temps reel. Recoit les donnees de retards et les distribue aux consommateurs. |
| **Apache Zookeeper** | Coordination des services Kafka. Gere la configuration du cluster. |
| **Apache NiFi** | Orchestration des flux de donnees (ETL no-code). Genere, transforme et route les donnees vers Kafka/ClickHouse. |
| **ClickHouse** | Base de donnees analytique (OLAP). Stocke les donnees historiques et les predictions ML. Ultra-rapide pour les requetes agregees. |
| **MongoDB** | Base de donnees NoSQL. Stocke les metadonnees du modele ML et configurations. |

---

## 2. Connecteurs Python (Data Pipeline)

| Outil | Role |
|-------|------|
| **clickhouse-connect** | Driver Python pour se connecter a ClickHouse. Execute les requetes SQL et insere les donnees. |
| **kafka-python** | Client Python pour produire et consommer des messages Kafka. |
| **pymongo** | Driver Python pour MongoDB. Gere les metadonnees du modele. |

---

## 3. Conteneurisation

| Outil | Role |
|-------|------|
| **Docker** | Conteneurisation des services. Chaque composant tourne dans un container isole. |
| **Docker Compose** | Orchestration multi-containers. Definit et lance tous les services avec une seule commande. |

---

## 4. Machine Learning

| Outil | Role |
|-------|------|
| **XGBoost** | Modele de classification principal. Predit si le taux de retard depasse 20%. |
| **LightGBM** | Alternative a XGBoost pour comparaison lors du hyperparameter tuning. |
| **Scikit-learn** | Preprocessing (LabelEncoder, SimpleImputer), metriques (ROC-AUC, confusion matrix), pipeline ML. |
| **Pandas** | Manipulation des dataframes, feature engineering, agregations. |
| **NumPy** | Calculs numeriques, operations sur arrays. |
| **Joblib** | Serialisation/deserialisation des modeles ML (fichiers .pkl). |

---

## 5. API & Backend

| Outil | Role |
|-------|------|
| **FastAPI** | API REST pour exposer les predictions ML et statistiques. Endpoints: `/predict`, `/stats/classification`, etc. |
| **Uvicorn** | Serveur ASGI pour executer FastAPI. |
| **Pydantic** | Validation des donnees d'entree/sortie de l'API. |

---

## 6. Visualisation & Reporting

| Outil | Role |
|-------|------|
| **Streamlit** | Dashboard interactif en temps reel. Affiche les metriques, alertes, et consomme Kafka. |
| **Matplotlib** | Graphiques statiques (courbes ROC, histogrammes, bar charts). |
| **Seaborn** | Visualisations statistiques (heatmaps, matrices de correlation). |
| **Power BI** | Outil de Business Intelligence. Creation de rapports interactifs et tableaux de bord pour l'analyse des retards. |

---

## 7. Developpement & IDE

| Outil | Role |
|-------|------|
| **Python 3.x** | Langage principal du projet. |
| **Google Colab** | Environnement d'entrainement ML avec GPU gratuit. |
| **Jupyter/IPython** | Format notebook pour l'exploration et l'experimentation. |
| **VS Code** | Editeur de code principal. Extensions Python, Docker, et Git integrees. |

---

## 8. Versioning & Collaboration

| Outil | Role |
|-------|------|
| **Git** | Systeme de controle de version. Gere l'historique des modifications du code, branches, et collaboration. |
| **GitHub** | Hebergement du repository distant. Permet le partage du code et le suivi des issues. |

---

## Architecture du Projet

```
ynov-data-pipeline-main/
├── docker-compose.yml     # Orchestration Docker
├── ml/                    # Code ML
│   ├── src/yno_ml/       # Modules (features, train, alerting)
│   ├── models/runs/      # Modeles entraines (.pkl)
│   └── notebooks/        # Notebooks Colab
├── ml_api/               # API FastAPI
├── scripts/              # Scripts d'integration
├── streamlit_app/        # Dashboard temps reel
├── nifi/                 # Configuration NiFi
└── data/                 # Donnees brutes
```

---

## Flux de Donnees

```
CSV Brut → NiFi → Kafka → ClickHouse (Bronze/Silver/Gold)
                              ↓
                     ML Training (XGBoost)
                              ↓
                     Predictions → ClickHouse (ml_predictions)
                              ↓
                     FastAPI → Streamlit Dashboard
```

---

## Resume

| Categorie | Nombre d'outils |
|-----------|-----------------|
| Data Pipeline | 5 |
| Connecteurs Python | 3 |
| Conteneurisation | 2 |
| Machine Learning | 6 |
| API & Backend | 3 |
| Visualisation & Reporting | 4 |
| Developpement & IDE | 4 |
| Versioning | 2 |
| **TOTAL** | **24** |
