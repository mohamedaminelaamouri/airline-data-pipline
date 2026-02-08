#!/bin/bash

# Airline Data Pipeline - Quickstart Script
# Author: Antigravity

set -e

echo "Demarrage du deploiement Airline Data Pipeline..."

# 1. Installation des dependances
echo "Installation des dependances Python..."
pip install -r requirements.txt
pip install -r requirements-ml-api.txt

# 2. Configuration Env
if [ ! -f ".env" ]; then
    echo "Creation du fichier .env depuis .env.example..."
    cp .env.example .env
fi

# 3. Lancement Docker
echo "Lancement des conteneurs Docker (Attente de 30s)..."
docker compose up -d

# Attente pour que ClickHouse soit pret
sleep 30

# 4. Initialisation DB et Donnees
echo "Initialisation de la base de donnees ClickHouse..."
docker exec clickhouse clickhouse-client --query "$(cat config/clickhouse/init.sql)"

echo "Chargement des donnees historiques (796K records)..."
python scripts/load_historical_data.py

echo "Execution du pipeline Medallion (Bronze -> Silver -> Gold)..."
python scripts/medallion_pipeline.py

echo "Entrainement du modele ML XGBoost..."
python scripts/train_model_production.py

echo "Deploiement termine avec succes !"
echo "-------------------------------------------------------"
echo "Acces aux services :"
echo " - React UI (ML Dashboard) : 3000"
echo " - FastAPI (Backend) : 8001"
echo " - Apache NiFi (ETL) : 8080"
echo " - ClickHouse : 8123"
echo "-------------------------------------------------------"
echo "Pour le monitoring Kafka en local : python realtime_app.py"
