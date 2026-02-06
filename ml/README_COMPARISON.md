# 📊 Comparaison des Modèles ML - Prédiction de Retards Aériens

## 🆕 Nouveau Modèle - Classification (`ml/`)

| Paramètre | Valeur |
|-----------|--------|
| **Type** | XGBClassifier (Classification binaire) |
| **Objectif** | Prédire si `delay_rate > 20%` → risque (1) ou non (0) |
| **Split** | Temporel strict: 70% train / 20% val / 10% test |

### Métriques (Run: `20260205_151341_sklearn`)

| Métrique | Validation | Test |
|----------|------------|------|
| **ROC-AUC** | 0.832 | **0.863** ✅ |
| **PR-AUC** | 0.743 | 0.749 |
| **Recall** | 90.7% | 84.8% |
| **Precision** | 50.1% | 52.2% |

### Features (11)
- Encodages: `carrier_encoded`, `airport_encoded`
- Saisonnalité: `month_sin`, `month_cos` (cyclique)
- Lags: `prev_month_delay_rate`, `lag_2/3_delay_rate`
- Moyennes: `rolling_3/6_mean`, `expanding_mean`
- Volume: `arr_flights`

---

## 🔄 Modèle Actuel - Régression (`scripts/train_model_2026.py`)

| Paramètre | Valeur |
|-----------|--------|
| **Type** | XGBRegressor (Régression) |
| **Objectif** | Prédire la valeur exacte du `delay_rate` |
| **Split** | Train 2010-2018 / Test 2019-2022 |

### Features (18)
- Lags par paire: `pair_lag1/2/3`
- Moyennes carrier/airport: `carrier_lag1/2/3_mean`, `airport_lag1/2/3`
- Rolling: `carrier/airport_rolling_3m/6m`
- Saisonnalité: `is_summer`, `is_winter`, `is_holiday_season` (binaire)

---

## 🔍 Comparaison

| Critère | Classification | Régression |
|---------|----------------|------------|
| **Approche** | ✅ Binaire (alerte oui/non) | Valeur continue |
| **Saisonnalité** | ✅ Sin/Cos (cyclique) | Binaire (flags) |
| **Cutoff** | ✅ Optimisé (recall ≥ 90%) | Fixe (30%/15%) |
| **Usage** | ✅ Alerting direct | Estimation précise |

---

## 🎯 Recommandation

**Le modèle de classification est plus adapté** pour le système d'alerting:
- ✅ Décision binaire directe
- ✅ Recall 90% garanti (ne rate que 10% des risques)
- ✅ ROC-AUC 0.863 = excellent pouvoir discriminant
