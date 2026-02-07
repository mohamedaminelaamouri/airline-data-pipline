# %% [markdown]
# # 🛫 Prédiction des Retards Aériens - Training Notebook v3
# 
# Ce notebook utilise le **nouveau schéma v3** avec:
# - Features pré-calculées dans ClickHouse (`gold_ml_features`)
# - Encoding stable (hash au lieu de LabelEncoder)
# - Parité garantie entre training et serving
#
# **Source des données**: ClickHouse `gold_ml_features`

# %%
# Imports
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Configuration des graphiques
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 11

print("=" * 80)
print("TRAINING NOTEBOOK v3 - ClickHouse Feature Store")
print("=" * 80)

# %% [markdown]
# ## 1. Connexion à ClickHouse

# %%
import clickhouse_connect

# Connexion à ClickHouse
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'localhost')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_HTTP_PORT', '8123'))

client = clickhouse_connect.get_client(
    host=CLICKHOUSE_HOST,
    port=CLICKHOUSE_PORT,
    database='airline_data'
)

print(f"✅ Connecté à ClickHouse: {CLICKHOUSE_HOST}:{CLICKHOUSE_PORT}")

# Vérifier le nombre de lignes
count = client.command("SELECT count() FROM gold_ml_features")
print(f"📊 Lignes dans gold_ml_features: {count:,}")

# %% [markdown]
# ## 2. Chargement des Données (Direct depuis ClickHouse)
# 
# **IMPORTANT**: Aucun feature engineering ici - toutes les features sont pré-calculées en SQL.

# %%
# Feature columns (v3 schema)
FEATURE_COLS = [
    "year", "month", "month_sin", "month_cos",
    "is_summer", "is_winter", "is_holiday_season",
    "carrier_id", "airport_id",
    "arr_flights", "log_arr_flights",
    "pair_lag1", "pair_lag3_mean", "pair_expanding_mean",
    "airport_lag1", "airport_lag3_mean", "airport_expanding_mean",
    "carrier_lag1", "carrier_lag3_mean", "carrier_expanding_mean",
]

TARGET_COL = "is_delayed"
TARGET_THRESHOLD = 0.20

# Charger les données
print("📥 Chargement des données depuis ClickHouse...")

query = f"""
SELECT 
    carrier, origin_airport as airport,
    {', '.join(FEATURE_COLS)},
    delay_rate, {TARGET_COL}
FROM gold_ml_features
WHERE year >= 2003
ORDER BY year, month, carrier, airport
"""

data = client.query_df(query)

print(f"✅ {len(data):,} lignes chargées")
print(f"📅 Période: {data['year'].min()} - {data['year'].max()}")
print(f"🔢 Features: {len(FEATURE_COLS)}")

# %%
# Aperçu des données
data.head(10)

# %%
# Types et valeurs manquantes
print("Types des colonnes:")
print(data.dtypes)
print("\nValeurs manquantes:")
print(data.isnull().sum())

# %% [markdown]
# ## 3. Exploration des Données (EDA)

# %%
# Distribution de la target
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Histogramme delay_rate
axes[0].hist(data['delay_rate'], bins=50, color='steelblue', edgecolor='black', alpha=0.7)
axes[0].axvline(TARGET_THRESHOLD, color='red', linestyle='--', linewidth=2, label=f'Seuil: {TARGET_THRESHOLD}')
axes[0].set_xlabel('Taux de Retard')
axes[0].set_ylabel('Fréquence')
axes[0].set_title('Distribution du Taux de Retard')
axes[0].legend()

# Répartition is_delayed
delayed_counts = data['is_delayed'].value_counts()
colors = ['#2ecc71', '#e74c3c']
axes[1].pie(delayed_counts, labels=['Non Retardé', 'Retardé'], 
            autopct='%1.1f%%', colors=colors, explode=(0, 0.05))
axes[1].set_title('Répartition des Classes')

plt.tight_layout()
plt.show()

print(f"\n📊 Statistiques Target:")
print(f"   - is_delayed=0: {(data['is_delayed']==0).sum():,} ({(data['is_delayed']==0).mean()*100:.1f}%)")
print(f"   - is_delayed=1: {(data['is_delayed']==1).sum():,} ({(data['is_delayed']==1).mean()*100:.1f}%)")

# %%
# Evolution temporelle
yearly_stats = data.groupby('year').agg({
    'delay_rate': 'mean',
    'is_delayed': 'mean',
    'carrier': 'count'
}).rename(columns={'carrier': 'count'})

fig, ax1 = plt.subplots(figsize=(14, 6))

ax1.bar(yearly_stats.index, yearly_stats['count'], alpha=0.3, color='steelblue', label='Nombre de vols')
ax1.set_ylabel('Nombre de Vols', color='steelblue')
ax1.tick_params(axis='y', labelcolor='steelblue')

ax2 = ax1.twinx()
ax2.plot(yearly_stats.index, yearly_stats['delay_rate'] * 100, 'o-', color='red', linewidth=2, label='Taux retard')
ax2.axhline(TARGET_THRESHOLD * 100, color='red', linestyle='--', alpha=0.5)
ax2.set_ylabel('Taux de Retard (%)', color='red')
ax2.tick_params(axis='y', labelcolor='red')

plt.title('Évolution des Retards par Année')
plt.xlabel('Année')
fig.legend(loc='upper right', bbox_to_anchor=(0.9, 0.9))
plt.tight_layout()
plt.show()

# %%
# Saisonnalité mensuelle
monthly_stats = data.groupby('month')['delay_rate'].mean() * 100

plt.figure(figsize=(12, 5))
bars = plt.bar(monthly_stats.index, monthly_stats.values, color='steelblue', edgecolor='black')

# Colorer les mois d'été/hiver
summer_months = [6, 7, 8]
winter_months = [12, 1, 2]
for i, bar in enumerate(bars):
    if monthly_stats.index[i] in summer_months:
        bar.set_color('#f39c12')
    elif monthly_stats.index[i] in winter_months:
        bar.set_color('#3498db')

plt.axhline(TARGET_THRESHOLD * 100, color='red', linestyle='--', label=f'Seuil: {TARGET_THRESHOLD*100}%')
plt.xlabel('Mois')
plt.ylabel('Taux de Retard Moyen (%)')
plt.title('Saisonnalité des Retards')
plt.xticks(range(1, 13), ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 
                          'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc'])
plt.legend()
plt.tight_layout()
plt.show()

# %% [markdown]
# ## 4. Préparation des Données

# %%
# Split temporel (Train/Validation/Test)
print("=" * 60)
print("SPLIT TEMPOREL")
print("=" * 60)

# Créer index de période
data['period'] = data['year'] * 12 + data['month']

# Définir les splits (70/20/10)
unique_periods = sorted(data['period'].unique())
n_periods = len(unique_periods)

n_train = int(n_periods * 0.70)
n_val = int(n_periods * 0.20)

train_periods = set(unique_periods[:n_train])
val_periods = set(unique_periods[n_train:n_train + n_val])
test_periods = set(unique_periods[n_train + n_val:])

# Créer les masques
train_mask = data['period'].isin(train_periods)
val_mask = data['period'].isin(val_periods)
test_mask = data['period'].isin(test_periods)

print(f"Train:      {train_mask.sum():,} échantillons ({train_mask.mean()*100:.1f}%)")
print(f"Validation: {val_mask.sum():,} échantillons ({val_mask.mean()*100:.1f}%)")
print(f"Test:       {test_mask.sum():,} échantillons ({test_mask.mean()*100:.1f}%)")

# Séparer X et y
X_train = data.loc[train_mask, FEATURE_COLS]
y_train = data.loc[train_mask, TARGET_COL]

X_val = data.loc[val_mask, FEATURE_COLS]
y_val = data.loc[val_mask, TARGET_COL]

X_test = data.loc[test_mask, FEATURE_COLS]
y_test = data.loc[test_mask, TARGET_COL]

print(f"\nBalance des classes:")
print(f"   Train:      {y_train.mean()*100:.1f}% positifs")
print(f"   Validation: {y_val.mean()*100:.1f}% positifs")
print(f"   Test:       {y_test.mean()*100:.1f}% positifs")

# %% [markdown]
# ## 5. Entraînement du Modèle

# %%
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from xgboost import XGBClassifier
import time

# Sample weights basés sur arr_flights
sample_weights = data.loc[train_mask, 'arr_flights'].values
sample_weights = np.nan_to_num(sample_weights, nan=1.0)
sample_weights = np.sqrt(np.clip(sample_weights, 1, None))

# Pipeline
print("=" * 60)
print("ENTRAINEMENT XGBOOST")
print("=" * 60)

pipeline = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('model', XGBClassifier(
        n_estimators=600,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        eval_metric='logloss',
        use_label_encoder=False
    ))
])

# Entraînement
start_time = time.time()
pipeline.fit(X_train, y_train, model__sample_weight=sample_weights)
train_time = time.time() - start_time

print(f"✅ Modèle entraîné en {train_time:.2f} secondes")

# %% [markdown]
# ## 6. Évaluation du Modèle

# %%
from sklearn.metrics import (
    roc_auc_score, average_precision_score, 
    classification_report, confusion_matrix,
    roc_curve, precision_recall_curve
)

# Prédictions
y_train_proba = pipeline.predict_proba(X_train)[:, 1]
y_val_proba = pipeline.predict_proba(X_val)[:, 1]
y_test_proba = pipeline.predict_proba(X_test)[:, 1]

# Métriques
print("=" * 60)
print("MÉTRIQUES D'ÉVALUATION")
print("=" * 60)

metrics = {}
for name, y_true, y_proba in [('Train', y_train, y_train_proba), 
                               ('Validation', y_val, y_val_proba),
                               ('Test', y_test, y_test_proba)]:
    metrics[name] = {
        'ROC-AUC': roc_auc_score(y_true, y_proba),
        'PR-AUC': average_precision_score(y_true, y_proba)
    }
    print(f"{name:12} - ROC-AUC: {metrics[name]['ROC-AUC']:.4f}, PR-AUC: {metrics[name]['PR-AUC']:.4f}")

# %%
# Courbes ROC et PR
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# ROC Curve
fpr, tpr, _ = roc_curve(y_test, y_test_proba)
axes[0].plot(fpr, tpr, 'b-', linewidth=2, label=f'ROC-AUC = {metrics["Test"]["ROC-AUC"]:.4f}')
axes[0].plot([0, 1], [0, 1], 'k--', alpha=0.5)
axes[0].set_xlabel('False Positive Rate')
axes[0].set_ylabel('True Positive Rate')
axes[0].set_title('Courbe ROC (Test)')
axes[0].legend()
axes[0].grid(True, alpha=0.3)

# PR Curve
precision, recall, _ = precision_recall_curve(y_test, y_test_proba)
axes[1].plot(recall, precision, 'g-', linewidth=2, label=f'PR-AUC = {metrics["Test"]["PR-AUC"]:.4f}')
axes[1].axhline(y_test.mean(), color='r', linestyle='--', alpha=0.5, label='Baseline')
axes[1].set_xlabel('Recall')
axes[1].set_ylabel('Precision')
axes[1].set_title('Courbe Precision-Recall (Test)')
axes[1].legend()
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# %% [markdown]
# ## 7. Optimisation du Seuil de Décision

# %%
# Trouver le seuil optimal
print("=" * 60)
print("OPTIMISATION DU SEUIL")
print("=" * 60)

cutoffs = np.arange(0.1, 0.9, 0.01)
best_cutoff = 0.5
best_acc = 0

for cutoff in cutoffs:
    acc = ((y_val_proba >= cutoff) == y_val).mean()
    if acc > best_acc:
        best_acc = acc
        best_cutoff = cutoff

optimal_cutoff = best_cutoff
print(f"✅ Seuil optimal: {optimal_cutoff:.3f}")
print(f"   Accuracy validation: {best_acc:.4f}")

# Appliquer sur test
y_test_pred = (y_test_proba >= optimal_cutoff).astype(int)

# %%
# Matrice de confusion
cm = confusion_matrix(y_test, y_test_pred)

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax,
            xticklabels=['Non Retardé', 'Retardé'],
            yticklabels=['Non Retardé', 'Retardé'])
ax.set_xlabel('Prédiction')
ax.set_ylabel('Réalité')
ax.set_title(f'Matrice de Confusion (cutoff={optimal_cutoff:.2f})')
plt.tight_layout()
plt.show()

# %%
# Rapport détaillé
print("\n" + "=" * 60)
print("RAPPORT DE CLASSIFICATION (Test)")
print("=" * 60)
print(classification_report(y_test, y_test_pred, target_names=['Non Retardé', 'Retardé']))

# %% [markdown]
# ## 8. Importance des Features

# %%
# Feature importance
xgb_model = pipeline.named_steps['model']

importance_df = pd.DataFrame({
    'feature': FEATURE_COLS,
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False)

print("\nTop 10 Features:")
display(importance_df.head(10))

# %%
# Visualisation
fig, ax = plt.subplots(figsize=(10, 8))

colors = plt.cm.RdYlGn(np.linspace(0.8, 0.2, len(importance_df)))
bars = ax.barh(importance_df['feature'], importance_df['importance'], 
               color=colors, edgecolor='black')

ax.set_xlabel('Importance')
ax.set_title('Importance des Features (XGBoost v3)')
ax.invert_yaxis()

for bar, importance in zip(bars, importance_df['importance']):
    ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
            f'{importance:.3f}', va='center', fontsize=9)

plt.tight_layout()
plt.show()

# %% [markdown]
# ## 9. Sauvegarde du Modèle

# %%
import joblib
import json

# Créer le dossier de sortie
output_dir = 'model_output_v3'
os.makedirs(output_dir, exist_ok=True)

# Sauvegarder le modèle
model_path = f'{output_dir}/xgboost_classifier_v3.pkl'
joblib.dump(pipeline, model_path)
print(f"✅ Modèle sauvegardé: {model_path}")

# Sauvegarder les métriques
metrics_output = {
    'run_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
    'feature_version': 'v3',
    'feature_columns': FEATURE_COLS,
    'target_threshold': TARGET_THRESHOLD,
    'optimal_cutoff': float(optimal_cutoff),
    'metrics': {
        'train': {k: float(v) for k, v in metrics['Train'].items()},
        'validation': {k: float(v) for k, v in metrics['Validation'].items()},
        'test': {k: float(v) for k, v in metrics['Test'].items()}
    },
    'confusion_matrix': {
        'TN': int(cm[0, 0]),
        'FP': int(cm[0, 1]),
        'FN': int(cm[1, 0]),
        'TP': int(cm[1, 1])
    },
    'feature_importance': importance_df.to_dict('records'),
    'notes': 'Features v3 from ClickHouse. No LabelEncoder - hash-based IDs.'
}

with open(f'{output_dir}/metrics_v3.json', 'w') as f:
    json.dump(metrics_output, f, indent=2)
print(f"✅ Métriques sauvegardées: {output_dir}/metrics_v3.json")

# Feature config pour le serving
feature_config = {
    'feature_columns': FEATURE_COLS,
    'feature_version': 'v3'
}
with open(f'{output_dir}/feature_config.json', 'w') as f:
    json.dump(feature_config, f, indent=2)
print(f"✅ Config features: {output_dir}/feature_config.json")

# %% [markdown]
# ## 10. Résumé Final

# %%
print("=" * 80)
print("RÉSUMÉ DE L'ENTRAÎNEMENT v3")
print("=" * 80)

tn, fp, fn, tp = cm.ravel()
accuracy = (tp + tn) / (tp + tn + fp + fn)
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

print(f"""
OBJECTIF
   Prédire si delay_rate > {TARGET_THRESHOLD*100}% (classification binaire)
   
SOURCE DES DONNÉES
   ClickHouse gold_ml_features (v3)
   Toutes les features pré-calculées en SQL
   
DONNÉES
   Total: {len(data):,} échantillons
   Train: {train_mask.sum():,} ({train_mask.mean()*100:.1f}%)
   Validation: {val_mask.sum():,} ({val_mask.mean()*100:.1f}%)
   Test: {test_mask.sum():,} ({test_mask.mean()*100:.1f}%)
   
MODÈLE
   Type: XGBoost Classifier
   Features: {len(FEATURE_COLS)} (v3 schema)
   Temps d'entraînement: {train_time:.2f}s
   
PERFORMANCE (Test)
   ROC-AUC: {metrics['Test']['ROC-AUC']:.4f}
   PR-AUC: {metrics['Test']['PR-AUC']:.4f}
   Accuracy: {accuracy:.4f}
   Precision: {precision:.4f}
   Recall: {recall:.4f}
   F1-Score: {f1:.4f}
   
CUTOFF OPTIMAL: {optimal_cutoff:.3f}

TOP 3 FEATURES
""")

for i, row in importance_df.head(3).iterrows():
    print(f"   {importance_df.index.get_loc(i)+1}. {row['feature']}: {row['importance']:.4f}")

print("\n" + "=" * 80)
print("✅ ENTRAÎNEMENT v3 TERMINÉ AVEC SUCCÈS!")
print("   - Features depuis ClickHouse (pas de LabelEncoder)")
print("   - Parité garantie avec le serving")
print("=" * 80)
