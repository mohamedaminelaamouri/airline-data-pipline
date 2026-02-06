# Analyse Ligne par Ligne du Projet

Ce document explique chaque fichier du projet ligne par ligne.

---

## 1. medallion_schema.sql (Schema ClickHouse)

### Lignes 1-18: En-tete et diagramme

```sql
-- MEDALLION ARCHITECTURE: Bronze → Silver → Gold
```
**Explication:** L'architecture Medallion est un pattern de data engineering ou les donnees passent par 3 couches:
- **Bronze**: Donnees brutes (telles quelles du CSV)
- **Silver**: Donnees nettoyees (sans NULL, validees)
- **Gold**: Donnees enrichies (features ML, KPIs)

---

### Lignes 20-21: Creation de la base

```sql
CREATE DATABASE IF NOT EXISTS airline_data;
USE airline_data;
```
**Explication:**
- `CREATE DATABASE IF NOT EXISTS` → Cree la base seulement si elle n'existe pas
- `USE airline_data` → Selectionne cette base pour les commandes suivantes

---

### Lignes 30-69: Table BRONZE (Donnees brutes)

```sql
CREATE TABLE IF NOT EXISTS bronze_flights (
    id String DEFAULT generateUUIDv4(),
    year Nullable(UInt16),
    month Nullable(UInt8),
    carrier Nullable(String),
    ...
) ENGINE = MergeTree()
ORDER BY (ingestion_timestamp, id);
```

**Ligne par ligne:**

| Ligne | Code | Explication |
|-------|------|-------------|
| 32 | `id String DEFAULT generateUUIDv4()` | ID unique auto-genere pour chaque ligne |
| 35 | `year Nullable(UInt16)` | Annee (peut etre NULL), entier 16 bits (0-65535) |
| 36 | `month Nullable(UInt8)` | Mois (peut etre NULL), entier 8 bits (0-255) |
| 39 | `carrier Nullable(String)` | Code compagnie (peut etre NULL) |
| 47 | `arr_flights Nullable(UInt32)` | Nombre de vols arrives |
| 48 | `arr_del15 Nullable(UInt32)` | Vols en retard de +15min |
| 64 | `source_file String DEFAULT ''` | Fichier source (tracabilite) |
| 65 | `ingestion_timestamp DateTime` | Date/heure d'insertion |
| 67 | `ENGINE = MergeTree()` | Moteur de stockage ClickHouse (le plus performant) |
| 68 | `ORDER BY (ingestion_timestamp, id)` | Index primaire pour recherches rapides |

**Pourquoi Nullable?** Les donnees brutes peuvent avoir des valeurs manquantes.

---

### Lignes 82-127: Table SILVER (Donnees nettoyees)

```sql
CREATE TABLE IF NOT EXISTS silver_flights (
    year UInt16,  -- Plus de Nullable!
    delay_rate Float32,
    ...
) ENGINE = ReplacingMergeTree(cleaned_at)
ORDER BY (year, month, carrier, airport)
PARTITION BY year;
```

**Differences avec Bronze:**

| Aspect | Bronze | Silver |
|--------|--------|--------|
| NULL | Oui | Non |
| delay_rate | N/A | Calcule |
| Engine | MergeTree | ReplacingMergeTree |
| Partition | Non | Par annee |

**Ligne 103:**
```sql
delay_rate Float32  -- = arr_del15 / arr_flights
```
→ Taux de retard calcule: nombre de retards / nombre de vols

**Ligne 124:**
```sql
ENGINE = ReplacingMergeTree(cleaned_at)
```
→ Si une ligne avec le meme (year, month, carrier, airport) est inseree, l'ancienne est remplacee (deduplication automatique)

---

### Lignes 137-189: Table GOLD_BI (Pour Power BI)

```sql
CREATE TABLE IF NOT EXISTS gold_bi (
    delay_rate Float32,
    on_time_rate Float32,  -- 1 - delay_rate
    carrier_delay_pct Float32,
    delay_rate_mom_change Float32,  -- Month-over-Month
    carrier_rank_by_delay UInt16,
    ...
);
```

**KPIs precalcules:**

| Colonne | Formule | Usage |
|---------|---------|-------|
| `on_time_rate` | 1 - delay_rate | % vols a l'heure |
| `carrier_delay_pct` | carrier_ct / arr_del15 | % retards compagnie |
| `delay_rate_mom_change` | delay_rate - delay_rate_m-1 | Evolution mois/mois |
| `carrier_rank_by_delay` | RANK() | Classement compagnies |

**Pourquoi?** Power BI peut afficher ces KPIs directement sans calcul.

---

### Lignes 199-264: Table GOLD_ML_FEATURES (Pour XGBoost)

```sql
CREATE TABLE IF NOT EXISTS gold_ml_features (
    -- TARGET
    delay_rate Float32,
    
    -- Lag Features
    pair_lag1 Float32,   -- Retard mois M-1
    pair_lag12 Float32,  -- Retard meme mois annee precedente
    
    -- Rolling Averages
    carrier_rolling_3m Float32,
    
    -- Features temporelles
    month_sin Float32,   -- sin(2*pi*month/12)
    is_summer UInt8,
    ...
);
```

**Features expliquees:**

| Feature | Calcul | Pourquoi |
|---------|--------|----------|
| `pair_lag1` | delay_rate du mois precedent | Le passe recent predit le futur |
| `pair_lag12` | delay_rate meme mois annee -1 | Saisonnalite annuelle |
| `month_sin/cos` | Encodage cyclique | Janvier (1) proche de Decembre (12) |
| `is_summer` | 1 si mois in [6,7,8] | Saison de pointe |
| `carrier_rolling_3m` | Moyenne 3 derniers mois | Tendance recente |

---

### Lignes 274-313: Table ML_PREDICTIONS

```

---

## 2. train_model_local.py (Entrainement ML)

### Lignes 7-17: Imports

```python
import pandas as pd               # Manipulation de donnees
import numpy as np                # Calculs numeriques
from sklearn.preprocessing import LabelEncoder   # Encodage categoriel
from sklearn.impute import SimpleImputer         # Remplissage valeurs manquantes
from sklearn.metrics import roc_auc_score        # Metrique ML
from xgboost import XGBClassifier                # Le modele!
import joblib                     # Sauvegarde modele
```

---

### Lignes 23-30: Configuration

```python
BASE_DIR = Path(__file__).parent.parent          # Racine du projet
DATA_FILE = BASE_DIR / "data" / "Airline_Delay_Cause_Cpt.csv"
OUTPUT_DIR = BASE_DIR / "ml" / "models" / "runs" / "production"
TARGET_THRESHOLD = 0.20   # Seuil: >20% retard = Risque
```

**Explication:** 
- `Path(__file__).parent.parent` → Remonte de 2 niveaux (scripts → projet)
- `TARGET_THRESHOLD = 0.20` → Si delay_rate > 20%, c'est un risque

---

### Lignes 50-58: Calcul de la target

```python
df['delay_rate'] = df['arr_del15'] / df['arr_flights'].clip(lower=1)
data['target'] = (data['delay_rate'] > TARGET_THRESHOLD).astype(int)
```

| delay_rate | Target | Signification |
|------------|--------|---------------|
| 0.15 | 0 | Normal |
| 0.25 | 1 | Risque |
| 0.35 | 1 | Risque |

---

### Lignes 61-64: Encodage categoriel

```python
le_carrier = LabelEncoder()
data['carrier_encoded'] = le_carrier.fit_transform(data['carrier'].astype(str))
```

**Avant:** carrier = "AA", "DL", "UA"
**Apres:** carrier_encoded = 0, 1, 2

Le modele ne peut pas lire les strings, il a besoin de nombres.

---

### Lignes 67-71: Features de saisonnalite

```python
data['month_sin'] = np.sin(2 * np.pi * data['month'] / 12)
data['month_cos'] = np.cos(2 * np.pi * data['month'] / 12)
data['is_summer'] = data['month'].isin([6, 7, 8]).astype(int)
```

**Pourquoi sin/cos?** Encodage cyclique:
- Janvier (1) doit etre "proche" de Decembre (12)
- Avec sin/cos, c'est le cas!

| Mois | month_sin | month_cos |
|------|-----------|-----------|
| 1 (Jan) | 0.50 | 0.87 |
| 6 (Jun) | 0.00 | -1.00 |
| 12 (Dec) | -0.50 | 0.87 |

---

### Lignes 77-97: Lag Features (le coeur du modele!)

```python
# Lag 1: valeur du mois precedent
data['pair_lag1'] = data.groupby(['carrier', 'airport'])['delay_rate'].shift(1)

# Moyenne mobile 3 mois
data['pair_lag3_mean'] = data.groupby(['carrier', 'airport'])['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean())
```

**Exemple concret:**

| Mois | delay_rate | pair_lag1 | pair_lag3_mean |
|------|------------|-----------|----------------|
| Jan | 0.20 | NaN | NaN |
| Fev | 0.25 | 0.20 | 0.20 |
| Mar | 0.30 | 0.25 | 0.225 |
| Avr | 0.22 | 0.30 | 0.25 |

**C'est LA feature la plus importante!** Le passe predit le futur.

---

### Lignes 116-127: Split temporel

```python
unique_periods = sorted(data['period'].unique())
n_train = int(n_periods * 0.70)   # 70% train
n_val = int(n_periods * 0.20)     # 20% validation
# 10% test
```

**IMPORTANT:** Split temporel, pas aleatoire!
- Train: 2003-2017 (70%)
- Validation: 2018-2020 (20%)
- Test: 2021-2022 (10%)

Pourquoi? On predit le FUTUR, pas le passe.

---

### Lignes 139-147: Imputation et poids

```python
imputer = SimpleImputer(strategy='median')
X_train_imp = imputer.fit_transform(X_train)

sample_weights = np.sqrt(X_train['arr_flights'].fillna(1).clip(lower=1)).values
```

- **Imputer**: Remplace les NaN par la mediane
- **sample_weights**: Les vols avec plus de trafic comptent plus

---

### Lignes 154-168: Entrainement XGBoost

```python
model = XGBClassifier(
    n_estimators=600,      # 600 arbres
    max_depth=5,           # Profondeur max de chaque arbre
    learning_rate=0.05,    # Vitesse d'apprentissage
    subsample=0.8,         # 80% des donnees par arbre
    colsample_bytree=0.8,  # 80% des features par arbre
    random_state=42,       # Reproductibilite
    n_jobs=-1,             # Utiliser tous les CPU
)
model.fit(X_train_imp, y_train, sample_weight=sample_weights)
```

**XGBoost = eXtreme Gradient Boosting:**
- Construit 600 arbres de decision
- Chaque arbre corrige les erreurs du precedent
- Tres efficace sur les donnees tabulaires

---

### Lignes 182-191: Recherche du cutoff optimal

```python
def find_optimal_cutoff_accuracy(y_true, proba):
    for cutoff in np.arange(0.1, 0.9, 0.01):
        y_pred = (proba >= cutoff).astype(int)
        acc = (y_pred == y_true).mean()
        if acc > best_acc:
            best_cutoff = cutoff
```

**Explication:**
- Le modele predit une probabilite (ex: 0.72)
- Il faut choisir un seuil pour dire "Risque" ou "Normal"
- On teste tous les seuils de 0.1 a 0.9
- On garde celui qui maximise l'accuracy

Resultat: **cutoff = 0.47**

---

### Lignes 200-203: Calcul des metriques

```python
tn, fp, fn, tp = confusion_matrix(y_test, y_pred_test).ravel()
precision = tp / (tp + fp)   # Parmi les alertes, combien vraies?
recall = tp / (tp + fn)      # Parmi les risques, combien detectes?
```

**Matrice de confusion:**
```
            Predit Normal   Predit Risque
Reel Normal     TN=26045       FP=1804
Reel Risque     FN=6330        TP=4594
```

---

### Lignes 217-220: Sauvegarde

```python
joblib.dump(model, OUTPUT_DIR / "model.pkl")
joblib.dump(imputer, OUTPUT_DIR / "imputer.pkl")
joblib.dump(le_carrier, OUTPUT_DIR / "label_encoder_carrier.pkl")
```

**Fichiers sauvegardes:**
| Fichier | Contenu |
|---------|---------|
| model.pkl | Le modele XGBoost entraine |
| imputer.pkl | L'imputer pour les NaN |
| label_encoder_*.pkl | Les encodeurs pour carrier/airport |
| metrics.json | Toutes les metriques |sql
CREATE TABLE IF NOT EXISTS ml_predictions (
    predicted_delay_rate Float32,
    risk_score Float32,
    risk_category String,  -- 'low', 'medium', 'high', 'critical'
    
    -- Explicabilite SHAP
    top_feature_1 String,
    top_feature_1_importance Float32,
    
    model_version String,
    ...
);
```

**Structure des predictions:**

| Colonne | Type | Exemple |
|---------|------|---------|
| `predicted_delay_rate` | Float | 0.72 (72%) |
| `risk_score` | Float | 72.0 |
| `risk_category` | String | "critical" |
| `top_feature_1` | String | "pair_lag1" |
| `model_version` | String | "v1.0_20260205" |

---

## Resume de l'Architecture

```
CSV Brut
    ↓
bronze_flights (NULL OK, doublons OK)
    ↓ Nettoyage: suppression NULL, validation
silver_flights (propre, deduplique)
    ↓ Agregation
    ├── gold_bi (KPIs pour Power BI)
    └── gold_ml_features (Features pour ML)
            ↓ XGBoost
        ml_predictions (Predictions 2026)
```
