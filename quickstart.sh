#!/bin/bash

# Airline Data Pipeline - Quickstart Script for Codespaces
# Author: Antigravity

set -e

echo "🚀 Démarrage du déploiement Airline Data Pipeline..."

# 1. Installation des dépendances
echo "📦 Installation des dépendances Python..."
pip install -r requirements.txt
pip install -r requirements-streamlit.txt
if [ -f "ml_api/requirements.txt" ]; then
    pip install -r ml_api/requirements.txt
fi

# 2. Configuration Env
if [ ! -f ".env" ]; then
    echo "📄 Création du fichier .env depuis .env.example..."
    cp .env.example .env
fi

# 3. Lancement Docker
echo "🐳 Lancement des conteneurs Docker (Attente de 30s)..."
docker compose up -d

# Attente pour que ClickHouse soit prêt
sleep 30

# 4. Initialisation DB et Données
echo "💾 Initialisation de la base de données ClickHouse..."
docker exec clickhouse clickhouse-client --query "$(cat config/clickhouse/init.sql)"

echo "📥 Chargement des données historiques (796K records)..."
python scripts/load_historical_data.py

echo "🔄 Exécution du pipeline Medallion (Bronze -> Silver)..."
python scripts/medallion_pipeline.py

echo "🧠 Entraînement du modèle ML XGBoost (Prédictions 2026)..."
python scripts/train_model_2026.py

echo "✅ Déploiement terminé avec succès !"
echo "-------------------------------------------------------"
echo "Accédez aux services via ces ports :"
echo " - Streamlit (Monitoring/Forecast) : 8501"
echo " - React UI (ML Dashboard) : 3000"
echo " - FastAPI (Backend) : 8001"
echo " - Apache NiFi (ETL) : 8080"
echo "-------------------------------------------------------"
echo "Exécutez 'streamlit run realtime_app.py' pour voir le dashboard de monitoring."
