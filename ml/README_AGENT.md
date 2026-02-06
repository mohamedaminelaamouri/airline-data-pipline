# 📊 YNO-ML: Système de Prédiction des Retards Aériens

## Objectif Global
Construire un pipeline ML qui prédit mensuellement les risques de retards aériens (par compagnie et aéroport) pour permettre des actions proactives (augmentation de personnel, maintenance, etc.).

## Architecture du Projet
```
yno-ml/
├── data/                           # Données d'entrée
│   └── Airline_Delay_Cause_Cpt.csv # CSV agrégé (year, month, carrier, airport, arr_flights, arr_del15)
│
├── src/yno_ml/                     # Cœur du pipeline
│   ├── data.py                     # Chargement CSV (CsvSource)
│   ├── schema.py                   # Validation colonnes
│   ├── features.py                 # Ingénierie: encodages, saisonnalité, lags, moyennes (NO LEAKAGE)
│   ├── split.py                    # Split temporel: train/val/test (70/20/10)
│   ├── train.py                    # Entraînement XGBoost + métriques
│   ├── metrics.py                  # ROC-AUC, PR-AUC, threshold metrics
│   ├── thresholds.py               # Cutoff optimal (min_recall=0.90)
│   ├── alerting.py                 # Scoring pour un mois donné → CSV probabilités
│   ├── notify.py                   # Webhook optionnel (Slack/Teams/Email)
│   ├── compare.py                  # Comparaison backends (sklearn only)
│   ├── multi_train.py              # Orchestrateur backends
│   └── __main__.py                 # CLI: train | alert | compare
│
├── scripts/
│   ├── train.py                    # Wrapper train
│   └── alert.py                    # Wrapper alert
│
├── models/
│   └── runs/                       # Versioned runs: YYYYMMDD_HHMMSS_sklearn/
│       ├── model.pkl               # XGBoost pipeline
│       ├── label_encoder_*.pkl     # Encodeurs carrier/airport
│       └── metrics.json            # Métadonnées + résultats
│
├── reports/
│   └── alerts_latest.csv           # Output: prédictions (carrier, airport, probability, prediction, risk_score, ...)
│
├── requirements.txt                # Dependencies: pandas, numpy, sklearn, xgboost
├── requirements-optional.txt       # Optional: pymongo (future), requests (webhook)
└── README.md                       # Documentation détaillée
```

## Pipeline Complet
1. **Entrée**: CSV avec colonnes requises: year, month, carrier, airport, arr_flights, arr_del15
2. **Transformation**: 
   - Target binaire: delay_rate > 0.20 → risque élevé (1) ou normal (0)
   - 11 features: encodages, saisonnalité (sin/cos), lags (1, 3, expanding), arr_flights
3. **Split temporel**: respecte l'ordre chronologique (pas de fuite vers futur)
4. **Entraînement**: XGBoost avec imputation NaN + pondération par √(arr_flights)
5. **Validation**: tuning cutoff sur validation (recall ≥ 0.90)
6. **Scoring**: prédictions probabilités pour toutes paires (carrier, airport) observées en historique
7. **Output**: CSV avec probabilités, prédictions binaires (0/1), risk_score (0-100)

## Commandes Principales

### Entraînement
```bash
python scripts/train.py \
  --backend sklearn \
  --data data/Airline_Delay_Cause_Cpt.csv \
  --out-root models/runs \
  --target-threshold 0.20 \
  --min-recall 0.90 \
  --sample-weight sqrt_flights

# Output: models/runs/YYYYMMDD_HHMMSS_sklearn/
# Recommanded cutoff écrit dans metrics.json
```

### Alertes
```bash
python scripts/alert.py \
  --year 2025 \
  --month 2 \
  --cutoff 0.17 \
  --history data/Airline_Delay_Cause_Cpt.csv \
  --out reports/alerts_latest.csv \
  --webhook-url https://hooks.slack.com/...  # Optionnel

# Output: reports/alerts_latest.csv (3600+ lignes de prédictions)
```

### Comparaison backends
```bash
python -m src.yno_ml compare \
  --backends sklearn \
  --data data/Airline_Delay_Cause_Cpt.csv \
  --out reports/backend_comparison.csv

# Output: CSV avec train_time, val_roc_auc, test_roc_auc, cutoff
```

## Métriques Clés
- **Validation ROC-AUC**: 0.832 (mesure discrimination globale)
- **Test ROC-AUC**: 0.863 (bon généralisation)
- **Test PR-AUC**: 0.749 (bon sur données déséquilibrées)
- **Recall cible**: 0.90 (capture 90% vrais retards élevés)
- **Cutoff recommandé**: 0.17 (probabilité seuil)

## Points Clés — À Respecter
1. **Pas de fuite de données**: features utilisent SEULEMENT infos du passé
2. **Split temporel**: ne pas mélanger train/val/test chronologiquement
3. **Données manquantes**: pairs (carrier, airport) jamais vues → défaut au global mean
4. **Encodeurs sauvegardés**: réutiliser les même LabelEncoders pour inference
5. **Métadonnées JSON**: chaque run enregistre config, splits, metrics, cutoff

## Prochaines Étapes
1. **Scheduling quotidien**: Task Scheduler (Windows) ou cron (Linux) → train + alert chaque jour
2. **MongoDB ingestion**: ajouter `MongoSource` au lieu de `CsvSource`
3. **Power BI**: connecter alerts_latest.csv et metrics.json pour dashboards
4. **Monitoring**: tracker historique métrics par jour (drift, degradation)
5. **Webhooks**: envoyer top N alertes à Slack/Teams/Email quotidiennement

## Fichiers Clés à Connaître
- `src/yno_ml/features.py`: logique feature engineering (START HERE for understanding)
- `src/yno_ml/train.py`: entraînement XGBoost
- `src/yno_ml/alerting.py`: scoring mois + CSV output
- `models/runs/*/metrics.json`: résultats + config per run
- `README.md`: documentation ML détaillée

## Dépannage Rapide
- ❌ "ModuleNotFoundError": pip install -r requirements.txt
- ❌ "No runs found": train d'abord (python scripts/train.py)
- ❌ "Feature leak detected": ne pas inclure arr_del15, arr_delay, etc. dans features
- ❌ "Empty output CSV": vérifier que historical pairs existent

## Status du Projet
✅ **PRODUCTION-READY**
- Tous les tests passent
- Structure clean, versioning des runs
- Output formaté pour Power BI
- Backend sklearn stable (Dask/Spark retirés pour compatibilité Windows)

---

**Comment utiliser ce document:**
Ce README_AGENT.md sert de contexte global pour tout agent IA travaillant sur ce projet. Fournissez-lui ce fichier pour qu'il comprenne immédiatement l'architecture, les commandes, et les bonnes pratiques du pipeline ML.
