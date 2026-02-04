# 🚀 GUIDE DE DÉPLOIEMENT PROFESSIONNEL - GITHUB CODESPACES

Ce guide fournit les instructions étape par étape pour déployer et exécuter l'intégralité du pipeline **Airline Data Pipeline** dans un environnement cloud GitHub Codespaces.

---

## 🛠️ 1. Prérequis sur Codespaces

Pour une exécution fluide de l'ensemble des services Docker (NiFi, Kafka, ClickHouse, MongoDB, etc.), il est **impératif** de choisir la configuration suivante :

- **Type de Machine :** 4-Core (8 GB RAM) minimum.
- **Recommandé :** 8-Core (16 GB RAM) pour éviter les ralentissements sur NiFi et ClickHouse.
- **Espace Disque :** 32 GB.

---

## 🏗️ 2. Installation Initiale

Une fois votre Codespace ouvert, suivez ces commandes dans le terminal :

```bash
# 1. Installer les dépendances Python locales (pour les serveurs et scripts)
make install

# 2. Copier le fichier d'environnement
cp .env.example .env
```

---

## 🐳 3. Lancement des Services (Docker)

Le projet utilise Docker Compose pour orchestrer 8 services.

```bash
# Démarrer tous les services en arrière-plan
docker compose up -d

# Vérifier que tout tourne (attendre ~30s pour ClickHouse et NiFi)
docker compose ps
```

---

## 💾 4. Initialisation des Données

Il est crucial de suivre cet ordre précis pour peupler le pipeline :

```bash
# 1. Créer les tables dans ClickHouse
make init-db

# 2. Charger les données historiques (318K+ lignes)
# Temps estimé : 2-3 minutes
make load-data

# 3. Exécuter le pipeline Medallion (Dédoublonnage + Nettoyage Silver)
python scripts/medallion_pipeline.py

# 4. Entraîner le modèle ML pour les prédictions 2026
# Temps estimé : 1 minute
python scripts/train_model_2026.py
```

---

## 🌐 5. Accès aux Interfaces (Port Forwarding)

GitHub Codespaces va automatiquement détecter les ports ouverts. Assurez-vous qu'ils sont en mode **"Public"** dans l'onglet "Ports" si vous voulez y accéder depuis votre navigateur.

| Interface | Port | Description |
|-----------|------|-------------|
| **Streamlit** | `8501` | Monitoring Temps Réel & Forecast 2026 (Violet Theme) |
| **React UI** | `3000` | Dashboard ML Predictions (Insights Approfondis) |
| **FastAPI** | `8001` | Documentation API Swagger (`/docs`) |
| **Apache NiFi** | `8080` | Orchestration des flux (admin / adminadminadmin) |
| **ClickHouse** | `8123` | Console SQL / API HTTP |

---

## ⚡ 6. Simulation Temps Réel (Optionnel)

Pour tester la détection de statut Kafka sur le dashboard Streamlit :

1. Ouvrez NiFi sur le port `8080`.
2. Importez le template `nifi/flows/streaming_flow__v_(1).json`.
3. Démarrez le processeur "PublishKafka".
4. Le dashboard Streamlit passera automatiquement en mode **ONLINE** pour Kafka.

---

## ⚠️ 7. Dépannage (Troubleshooting)

- **NiFi ne démarre pas :** Vérifiez si votre RAM est saturée (`free -m`). Si oui, redémarrez avec moins de services ou une machine plus puissante.
- **ClickHouse Connection Refused :** ClickHouse met environ 30s à s'initialiser. Attendez avant de lancer `make init-db`.
- **Ports non accessibles :** Dans VS Code (web), allez dans l'onglet **Ports**, clic droit sur le port `8501` -> **Port Visibility** -> **Public**.

---

## 📂 8. Structure des Commandes (Makefile)

- `make start` : Lance Docker.
- `make stop` : Arrête Docker.
- `make clean` : Réinitialise tout (supprime les volumes de données).
- `make logs` : Affiche les logs en temps réel.

---

*Fait avec ❤️ par Antigravity pour le projet Airline Data Pipeline.*
