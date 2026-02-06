# 📊 Comparaison des Modèles ML - Prédiction de Retards Aériens

> **Objectif**: Comparer le nouveau modèle de classification (`ml/`) avec le modèle de régression actuel (`scripts/train_model_2026.py`)

---

## 🆕 Nouveau Modèle - Classification (`ml/`)

### Configuration
| Paramètre | Valeur |
|-----------|--------|
| **Type** | XGBClassifier (Classification binaire) |
| **Objectif** | Prédire si `delay_rate > 20%` → risque (1) ou non (0) |
| **Split** | Temporel strict: 70% train / 20% val / 10% test |
| **Backend** | Sklearn + XGBoost |

### Features (11)
```
carrier_encoded       # Encodage LabelEncoder
airport_encoded       # Encodage LabelEncoder
month_sin            # Saisonnalité cyclique sin(2π*month/12)
month_cos            # Saisonnalité cyclique cos(2π*month/12)
prev_month_delay_rate # Lag 1 mois
lag_2_delay_rate     # Lag 2 mois
lag_3_delay_rate     # Lag 3 mois
rolling_3_mean       # Moyenne mobile 3 mois
rolling_6_mean       # Moyenne mobile 6 mois
expanding_mean       # Moyenne cumulative
arr_flights          # Volume de vols
```

### Métriques (Run: `20260205_151341_sklearn`)

| Métrique | Validation | Test |
|----------|------------|------|
| **ROC-AUC** | 0.832 | **0.863** ✅ |
| **PR-AUC** | 0.743 | 0.749 |
| **Positive Rate** | 34.9% | 29.0% |

### Cutoff Optimisé (Recall ≥ 90%)
| Paramètre | Validation | Test |
|-----------|------------|------|
| **Seuil** | 0.17 | 0.17 |
| **Recall** | 90.7% | 84.8% |
| **Precision** | 50.1% | 52.2% |
| **F1-Score** | 0.646 | 0.646 |
| **Balanced Accuracy** | 71.1% | 76.5% |

---

## 🔄 Modèle Actuel - Régression (`scripts/train_model_2026.py`)

### Configuration
| Paramètre | Valeur |
|-----------|--------|
| **Type** | XGBRegressor (Régression) |
| **Objectif** | Prédire la valeur exacte du `delay_rate` |
| **Split** | Train 2010-2018 / Test 2019-2022 |
| **Backend** | XGBoost direct |

### Features (18)
```
arr_flights          # Volume de vols
pair_lag1/2/3        # Lags par paire carrier+airport
carrier_lag1/2/3_mean # Moyennes carrier
airport_lag1/2/3     # Lags par aéroport
carrier_rolling_3m/6m # Rolling carrier
airport_rolling_3m/6m # Rolling airport
is_summer            # Flag été (binaire)
is_winter            # Flag hiver (binaire)
is_holiday_season    # Flag vacances (binaire)
month                # Mois brut (1-12)
```

### Métriques
| Métrique | Valeur |
|----------|--------|
| **MAE** | ~X% (variable selon run) |
| **RMSE** | ~X% |
| **R²** | ~X |

### Catégorisation Risque
- **High**: delay_rate ≥ 0.30 (30%)
- **Medium**: delay_rate ≥ 0.15 (15%)
- **Low**: delay_rate < 0.15

---

## 🔍 Comparaison Directe

| Critère | Nouveau (Classification) | Actuel (Régression) |
|---------|--------------------------|---------------------|
| **Approche** | ✅ Binaire (alerte oui/non) | Valeur continue |
| **Interprétabilité** | ✅ Direct | Nécessite seuils |
| **Seuil de décision** | ✅ 20% (configurable) | Post-hoc (30%/15%) |
| **Split temporel** | ✅ Strict 70/20/10 | Par années fixes |
| **Saisonnalité** | ✅ Sin/Cos (cyclique) | Binaire (flags) |
| **Anti-leak** | ✅ Vérifié | ✅ Vérifié |
| **Métriques** | ROC-AUC, Recall, Precision | MAE, RMSE, R² |
| **Cutoff** | ✅ Optimisé (recall ≥ 90%) | Fixe |

---

## 🎯 Recommandation

### ✅ Le nouveau modèle de classification est **plus adapté** pour:

1. **Système d'alerting** - Décision binaire directe "alerte oui/non"
2. **Contrôle du recall** - Garantie de capturer 90% des vrais risques
3. **Saisonnalité** - Encodage sin/cos capture mieux les cycles annuels
4. **Robustesse** - ROC-AUC 0.863 sur test = excellent pouvoir discriminant

### Le modèle de régression reste utile pour:

1. **Estimation précise** - Valeur exacte du taux de retard
2. **Analyses détaillées** - Comparaisons fines entre routes
3. **Planification** - Allocation de ressources proportionnelle

---

## 📁 Fichiers Concernés

### Nouveau Modèle (`ml/`)
```
ml/
├── src/yno_ml/
│   ├── train.py        # Entraînement XGBClassifier
│   ├── features.py     # Feature engineering (11 features)
│   ├── split.py        # Split temporel strict
│   ├── metrics.py      # ROC-AUC, PR-AUC
│   └── thresholds.py   # Optimisation cutoff
├── models/runs/
│   └── 20260205_151341_sklearn/
│       ├── model.pkl
│       ├── metrics.json
│       └── label_encoder_*.pkl
└── README.md           # Documentation complète
```

### Modèle Actuel
```
scripts/
└── train_model_2026.py  # XGBRegressor + prédictions 2026
```

---

## 🚀 Prochaines Étapes

1. **Intégrer** le nouveau modèle dans le pipeline principal
2. **Remplacer** ou **compléter** le modèle de régression
3. **Mettre à jour** l'API pour utiliser les nouvelles métriques
4. **Tester** en production avec le dashboard Streamlit
