# Guide de Redémarrage du Projet - Airline Delay Pipeline

## Analyse Complète du Projet

### Architecture Simplifiée

```
┌─────────────────────────────────────────────────────────┐
│                  FLUX DE DONNÉES                         │
└─────────────────────────────────────────────────────────┘

1. DONNÉES HISTORIQUES (CSV)
   └─> data/Airline_Delay_Cause_Cpt.csv (478,109 lignes)
   └─> data/airports_gps.csv (421 aéroports)

2. INGESTION → CLICKHOUSE
   └─> scripts/load_historical_data.py
   └─> Table: airline_data.flights

3. ARCHITECTURE MEDALLION (Bronze/Silver/Gold)
   └─> Bronze: flights (données brutes)
   └─> Silver: silver_flights (nettoyées)
   └─> Gold: gold_bi, gold_ml_features (agrégées)

4. STREAMING TEMPS RÉEL (optionnel)
   └─> NiFi → Kafka → ClickHouse
   └─> Topic: airline-delays

5. INTERFACES
   └─> Streamlit (Port 8501) - Monitoring Kafka
   └─> React Dashboard (Port 3000) - ML Prédictions
   └─> FastAPI (Port 8001) - API ML
```

---

## Fichiers ESSENTIELS

### Configuration
- `docker-compose.yml` ✅ **ESSENTIEL** - Lance tous les services
- `.env.example` - Template des variables d'environnement
- `requirements.txt` ✅ **ESSENTIEL** - Dépendances Python principales
- `requirements-ml-api.txt` - Dépendances API ML

### Données
- `data/Airline_Delay_Cause_Cpt.csv` ✅ **ESSENTIEL** - Données historiques
- `data/airports_gps.csv` ✅ **ESSENTIEL** - Géolocalisation aéroports

### Scripts Principaux
- `scripts/load_historical_data.py` ✅ **ESSENTIEL** - Charger les CSV
- `scripts/medallion_pipeline.py` ✅ **ESSENTIEL** - Bronze → Silver → Gold
- `realtime_app.py` ✅ **ESSENTIEL** - Dashboard Streamlit

### Configuration ClickHouse
- `config/clickhouse/init.sql` ✅ **ESSENTIEL** - Schéma initial
- `config/clickhouse/medallion_schema.sql` ✅ **ESSENTIEL** - Tables Medallion

---

## Fichiers NON-ESSENTIELS (à supprimer)

### Documentation Obsolète
- ❌ `ClickHouse_Migration_Architecture.md` - Migration annulée
- ❌ `docs/POWER_BI_GUIDE.md` - Power BI externe au pipeline
- ❌ `docs/PROJECT_COMPLETE.md` - Archive
- ❌ `docs/MONGODB_CACHE.md` - MongoDB optionnel

### Scripts Obsolètes
- ❌ `scripts/test_ml_prerequisites.py` - Tests déjà effectués
- ❌ `scripts/compare_models.py` - Archive
- ❌ `scripts/train_model_2026_v2.py` - Version v1 suffit
- ❌ `scripts/refresh_silver.py` - Redondant avec medallion_pipeline
- ❌ `scripts/refresh_silver.sql` - Redondant

### Répertoires Vides/Archives
- ❌ `logs/` - Créé automatiquement
- ❌ `data/processed/` - Créé automatiquement
- ❌ `data/raw/` - Non utilisé
- ❌ `reports/` - Archive

### NiFi (si non utilisé)
- ❌ `nifi/flows/` - Seulement si streaming temps réel
- ❌ `scripts/kafka_to_clickhouse.py` - Seulement si Kafka

### ML UI (si non utilisé)
- ❌ `ml_ui/` - Dashboard React optionnel
- ❌ `ml_api/` - API ML optionnelle

---

## PROCÉDURE DE REDÉMARRAGE

### Étape 1: Nettoyer le Projet

```powershell
# Supprimer fichiers obsolètes
Remove-Item "ClickHouse_Migration_Architecture.md" -Force
Remove-Item "docs\POWER_BI_GUIDE.md" -Force
Remove-Item "docs\PROJECT_COMPLETE.md" -Force
Remove-Item "docs\MONGODB_CACHE.md" -Force
Remove-Item "scripts\test_ml_prerequisites.py" -Force
Remove-Item "scripts\compare_models.py" -Force
Remove-Item "scripts\train_model_2026_v2.py" -Force
Remove-Item "scripts\refresh_silver.py" -Force
Remove-Item "scripts\refresh_silver.sql" -Force

# Supprimer répertoires vides
Remove-Item "reports" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "data\processed" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "data\raw" -Recurse -Force -ErrorAction SilentlyContinue
```

### Étape 2: Vérifier les Données

```powershell
# Vérifier que les CSV existent
Get-Item "data\Airline_Delay_Cause_Cpt.csv"
Get-Item "data\airports_gps.csv"

# Afficher taille
(Get-Item "data\Airline_Delay_Cause_Cpt.csv").Length / 1MB
```

### Étape 3: Lancer Docker

```powershell
# Démarrer uniquement les services essentiels
docker compose up -d zookeeper kafka clickhouse nifi

# Vérifier l'état
docker compose ps

# Attendre que ClickHouse soit prêt (30-60 secondes)
Start-Sleep -Seconds 60
```

### Étape 4: Charger les Données Historiques

```powershell
# Charger les CSV dans ClickHouse
python scripts\load_historical_data.py

# Vérifier le chargement
curl -s "http://localhost:8123/" -d "SELECT count() FROM airline_data.flights"
```

### Étape 5: Exécuter le Pipeline Medallion

```powershell
# Option 1: Rafraîchir uniquement Bronze → Silver
python scripts\medallion_pipeline.py --silver-only

# Option 2: Rafraîchir Bronze → Silver → Gold (BI + ML)
python scripts\medallion_pipeline.py
```

### Étape 6: Lancer Streamlit (Interface de Monitoring)

```powershell
# Installer dépendances
pip install -r requirements.txt

# Lancer le dashboard
streamlit run realtime_app.py
```

**URL:** http://localhost:8501

---

## SERVICES OPTIONNELS

### Si vous voulez le streaming Kafka temps réel:

```powershell
# 1. NiFi est déjà lancé (port 8080)
# 2. Créer un flow NiFi pour envoyer à Kafka
# 3. Lancer le consumer:
python scripts\kafka_to_clickhouse.py
```

### Si vous voulez l'API ML + React Dashboard:

```powershell
# Lancer les services ML
docker compose up -d ml_api ml_ui mongodb

# API ML: http://localhost:8001
# React UI: http://localhost:3000
```

---

## VÉRIFICATIONS POST-DÉMARRAGE

### 1. Vérifier ClickHouse

```powershell
# Nombre de lignes
curl -s "http://localhost:8123/" -d "SELECT count() FROM airline_data.flights"
# Résultat attendu: 478109

# Tables existantes
curl -s "http://localhost:8123/" -d "SHOW TABLES FROM airline_data"
```

### 2. Vérifier Kafka (si utilisé)

```powershell
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Résultat attendu: airline-delays
```

### 3. Vérifier NiFi

**URL:** http://localhost:8080/nifi  
**Login:** admin / adminadminadmin

### 4. Vérifier Streamlit

**URL:** http://localhost:8501  
**Onglets:**
- Vue d'ensemble
- Temps Réel (si Kafka actif)
- Analyses
- Comparaisons
- Données

---

## STRUCTURE MINIMALE DU PROJET

```
ynov-data-pipeline-main/
├── docker-compose.yml          ✅ GARDER
├── requirements.txt            ✅ GARDER
├── realtime_app.py            ✅ GARDER
├── ARCHITECTURE_GLOBALE.md    ✅ GARDER
├── README.md                  ✅ GARDER
├── GUIDE_REDEMARRAGE.md       ✅ GARDER (ce fichier)
│
├── config/
│   └── clickhouse/
│       ├── init.sql           ✅ GARDER
│       └── medallion_schema.sql ✅ GARDER
│
├── data/
│   ├── Airline_Delay_Cause_Cpt.csv ✅ GARDER
│   └── airports_gps.csv       ✅ GARDER
│
└── scripts/
    ├── load_historical_data.py      ✅ GARDER
    ├── medallion_pipeline.py        ✅ GARDER
    ├── load_airports_gps.py         ✅ GARDER (optionnel)
    ├── kafka_to_clickhouse.py       ⚠️ Si Kafka utilisé
    └── train_model_2026.py          ⚠️ Si ML utilisé
```

---

## COMMANDES UTILES

### Docker

```powershell
# Voir les logs d'un service
docker compose logs -f clickhouse

# Redémarrer un service
docker compose restart clickhouse

# Arrêter tout
docker compose down

# Supprimer volumes (ATTENTION: perte de données)
docker compose down -v
```

### ClickHouse

```powershell
# Se connecter au client ClickHouse
docker exec -it clickhouse clickhouse-client

# Requête directe HTTP
curl -s "http://localhost:8123/" -d "SELECT database, table, formatReadableSize(total_bytes) FROM system.tables WHERE database='airline_data'"
```

### Python

```powershell
# Créer environnement virtuel
python -m venv venv
.\venv\Scripts\Activate.ps1

# Installer dépendances
pip install -r requirements.txt
```

---

## DÉPANNAGE

### Problème 1: ClickHouse ne démarre pas

```powershell
# Vérifier les logs
docker compose logs clickhouse

# Solution: Augmenter la mémoire
# Modifier docker-compose.yml: mem_limit: 3072m
```

### Problème 2: Kafka ne démarre pas

```powershell
# Zookeeper doit démarrer d'abord
docker compose up -d zookeeper
Start-Sleep -Seconds 30
docker compose up -d kafka
```

### Problème 3: "Table does not exist"

```powershell
# Recharger le schéma
curl -s "http://localhost:8123/" --data-binary @config/clickhouse/medallion_schema.sql
```

### Problème 4: Streamlit ne trouve pas les données

```powershell
# Vérifier que flights existe
curl -s "http://localhost:8123/" -d "SELECT count() FROM airline_data.flights"

# Si 0: recharger les données
python scripts\load_historical_data.py
```

---

## RÉSUMÉ: DÉMARRAGE MINIMAL

**Pour un démarrage rapide avec le minimum:**

```powershell
# 1. Lancer ClickHouse seul
docker compose up -d clickhouse

# 2. Attendre 60 secondes
Start-Sleep -Seconds 60

# 3. Charger les données
python scripts\load_historical_data.py

# 4. Rafraîchir Silver
python scripts\medallion_pipeline.py --silver-only

# 5. Lancer Streamlit
streamlit run realtime_app.py
```

**Temps total:** ~5 minutes  
**Mémoire utilisée:** ~2GB

---

## CONTACT & SUPPORT

- Architecture globale: [ARCHITECTURE_GLOBALE.md](ARCHITECTURE_GLOBALE.md)
- README principal: [README.md](README.md)
- Schéma Medallion: [config/clickhouse/medallion_schema.sql](config/clickhouse/medallion_schema.sql)
