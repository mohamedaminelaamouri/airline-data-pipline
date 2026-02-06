# %% [markdown]
# # Prediction des Retards Aeriens - Notebook d'Entrainement Complet
# 
# Ce notebook contient tout le code pour:
# 1. Charger et explorer les donnees
# 2. Feature Engineering
# 3. Entrainer un modele XGBoost Classifier
# 4. Evaluer avec visualisations completes
# 5. Sauvegarder le modele

# %% [markdown]
# ## 1. Installation des Dependances

# %%
# !pip install pandas numpy scikit-learn xgboost matplotlib seaborn

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    roc_auc_score, average_precision_score, roc_curve, 
    precision_recall_curve, confusion_matrix, classification_report,
    precision_recall_fscore_support
)
from xgboost import XGBClassifier
import warnings
warnings.filterwarnings('ignore')

# Configuration des graphiques
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 12

print("[OK] Librairies chargees!")

# %% [markdown]
# ## 2. Chargement des Donnees

# %%
# =============================================================================
# CHARGEMENT DES DONNEES - Menu Interactif
# =============================================================================

print("=" * 60)
print("CHARGEMENT DES DONNEES")
print("=" * 60)
print("\nChoisissez une option:")
print("  1. Uploader un fichier CSV")
print("  2. Utiliser un fichier deja present dans Colab")
print("")

choice = input("Votre choix (1 ou 2): ").strip()

if choice == "1":
    # Option 1: Upload manuel
    try:
        from google.colab import files
        print("\n[INFO] Uploadez votre fichier CSV:")
        uploaded = files.upload()
        filename = list(uploaded.keys())[0]
        df = pd.read_csv(filename)
        print(f"[OK] Fichier uploade: {filename}")
    except ImportError:
        print("[ERREUR] Google Colab non disponible.")
        raise
        
elif choice == "2":
    # Option 2: Chemin direct
    default_path = "/content/Airline_Delay_Cause.csv"
    print(f"\n[INFO] Chemin par defaut: {default_path}")
    csv_path = input(f"Entrez le chemin du CSV (ou appuyez Enter pour utiliser le defaut): ").strip()
    
    if csv_path == "":
        csv_path = default_path
    
    print(f"[INFO] Chargement depuis: {csv_path}")
    df = pd.read_csv(csv_path)
    
else:
    print("[ERREUR] Choix invalide. Veuillez entrer 1 ou 2.")
    raise ValueError("Choix invalide")

print(f"\n[OK] Donnees chargees: {len(df):,} lignes, {len(df.columns)} colonnes")

# %%
# Apercu des donnees
print("Apercu des donnees:")
display(df.head(10))

print("\nColonnes disponibles:")
print(df.columns.tolist())

print("\nStatistiques descriptives:")
display(df.describe())

# %% [markdown]
# ## 3. Exploration des Donnees (EDA)

# %%
# Verifier les colonnes necessaires
REQUIRED_COLS = ['year', 'month', 'carrier', 'airport', 'arr_flights', 'arr_del15']

# Adapter les noms de colonnes si necessaire
col_mapping = {
    'origin_airport': 'airport',
    'YEAR': 'year',
    'MONTH': 'month',
    'CARRIER': 'carrier',
    'AIRPORT': 'airport',
    'ARR_FLIGHTS': 'arr_flights',
    'ARR_DEL15': 'arr_del15'
}

for old, new in col_mapping.items():
    if old in df.columns and new not in df.columns:
        df = df.rename(columns={old: new})

# Verification
missing = set(REQUIRED_COLS) - set(df.columns)
if missing:
    print(f"[ATTENTION] Colonnes manquantes: {missing}")
    print(f"Colonnes disponibles: {df.columns.tolist()}")
else:
    print("[OK] Toutes les colonnes requises sont presentes")

# %%
# Distribution par annee
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Nombre d'enregistrements par annee
year_counts = df.groupby('year').size()
axes[0].bar(year_counts.index, year_counts.values, color='steelblue', edgecolor='black')
axes[0].set_xlabel('Annee')
axes[0].set_ylabel('Nombre d\'enregistrements')
axes[0].set_title('Distribution des Donnees par Annee')
axes[0].tick_params(axis='x', rotation=45)

# Taux de retard moyen par annee
df['delay_rate'] = df['arr_del15'] / df['arr_flights'].clip(lower=1)
yearly_delay = df.groupby('year')['delay_rate'].mean()
axes[1].plot(yearly_delay.index, yearly_delay.values, marker='o', linewidth=2, markersize=8, color='coral')
axes[1].axhline(y=0.20, color='red', linestyle='--', label='Seuil 20%')
axes[1].set_xlabel('Annee')
axes[1].set_ylabel('Taux de Retard Moyen')
axes[1].set_title('Evolution du Taux de Retard par Annee')
axes[1].legend()

plt.tight_layout()
plt.show()

# %%
# Saisonnalite mensuelle
monthly_delay = df.groupby('month')['delay_rate'].mean()

fig, ax = plt.subplots(figsize=(10, 5))
colors = ['#2ecc71' if x < 0.20 else '#e74c3c' for x in monthly_delay.values]
bars = ax.bar(monthly_delay.index, monthly_delay.values, color=colors, edgecolor='black')
ax.axhline(y=0.20, color='red', linestyle='--', linewidth=2, label='Seuil 20%')
ax.set_xlabel('Mois')
ax.set_ylabel('Taux de Retard Moyen')
ax.set_title('Saisonnalite des Retards par Mois')
ax.set_xticks(range(1, 13))
ax.set_xticklabels(['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Juin', 
                    'Juil', 'Aout', 'Sep', 'Oct', 'Nov', 'Dec'])
ax.legend()
plt.show()

print("Les mois en rouge ont un taux de retard > 20%")

# %%
# Top 10 compagnies avec le plus de retards
carrier_delay = df.groupby('carrier').agg({
    'delay_rate': 'mean',
    'arr_flights': 'sum'
}).sort_values('delay_rate', ascending=False)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Top 10 pires
top10_worst = carrier_delay.nlargest(10, 'delay_rate')
axes[0].barh(top10_worst.index, top10_worst['delay_rate'], color='salmon', edgecolor='black')
axes[0].axvline(x=0.20, color='red', linestyle='--', label='Seuil 20%')
axes[0].set_xlabel('Taux de Retard Moyen')
axes[0].set_title('Top 10 Compagnies - Plus de Retards')
axes[0].invert_yaxis()

# Top 10 meilleures
top10_best = carrier_delay.nsmallest(10, 'delay_rate')
axes[1].barh(top10_best.index, top10_best['delay_rate'], color='lightgreen', edgecolor='black')
axes[1].axvline(x=0.20, color='red', linestyle='--', label='Seuil 20%')
axes[1].set_xlabel('Taux de Retard Moyen')
axes[1].set_title('Top 10 Compagnies - Moins de Retards')
axes[1].invert_yaxis()

plt.tight_layout()
plt.show()

# %%
# Distribution du taux de retard
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Histogramme
axes[0].hist(df['delay_rate'].clip(upper=1), bins=50, color='steelblue', edgecolor='black', alpha=0.7)
axes[0].axvline(x=0.20, color='red', linestyle='--', linewidth=2, label='Seuil 20%')
axes[0].set_xlabel('Taux de Retard')
axes[0].set_ylabel('Frequence')
axes[0].set_title('Distribution du Taux de Retard')
axes[0].legend()

# Box plot par mois
df.boxplot(column='delay_rate', by='month', ax=axes[1])
axes[1].set_xlabel('Mois')
axes[1].set_ylabel('Taux de Retard')
axes[1].set_title('Distribution du Taux de Retard par Mois')
plt.suptitle('')  # Remove automatic title

plt.tight_layout()
plt.show()

# %% [markdown]
# ## 4. Feature Engineering

# %%
print("Debut du Feature Engineering...")

# Copier les donnees
data = df.copy()

# 4.1 Creer la variable cible (Target)
TARGET_THRESHOLD = 0.20
data['target'] = (data['delay_rate'] > TARGET_THRESHOLD).astype(int)

print(f"\nDistribution de la Target (seuil = {TARGET_THRESHOLD*100}%):")
print(data['target'].value_counts(normalize=True).round(3) * 100)

# Visualisation
fig, ax = plt.subplots(figsize=(8, 5))
colors = ['#2ecc71', '#e74c3c']
labels = ['Normal (0)', 'Risque (1)']
sizes = data['target'].value_counts().values
explode = (0, 0.1)
ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
       shadow=True, startangle=90)
ax.set_title('Distribution de la Variable Cible')
plt.show()

# %%
# 4.2 Encodage des variables categorielles
print("\nEncodage des variables categorielles...")

le_carrier = LabelEncoder()
le_airport = LabelEncoder()

data['carrier_encoded'] = le_carrier.fit_transform(data['carrier'].astype(str))
data['airport_encoded'] = le_airport.fit_transform(data['airport'].astype(str))

print(f"   Carriers: {len(le_carrier.classes_)} categories")
print(f"   Airports: {len(le_airport.classes_)} categories")

# %%
# 4.3 Features de saisonnalite
print("\nCreation des features de saisonnalite...")

data['month_sin'] = np.sin(2 * np.pi * data['month'] / 12)
data['month_cos'] = np.cos(2 * np.pi * data['month'] / 12)
data['is_summer'] = data['month'].isin([6, 7, 8]).astype(int)
data['is_winter'] = data['month'].isin([12, 1, 2]).astype(int)
data['is_holiday_season'] = data['month'].isin([11, 12]).astype(int)

# Visualisation sin/cos
fig, ax = plt.subplots(figsize=(10, 5))
months = np.arange(1, 13)
sin_vals = np.sin(2 * np.pi * months / 12)
cos_vals = np.cos(2 * np.pi * months / 12)
ax.plot(months, sin_vals, 'b-o', label='month_sin', linewidth=2)
ax.plot(months, cos_vals, 'r-o', label='month_cos', linewidth=2)
ax.set_xticks(months)
ax.set_xticklabels(['Jan', 'Fev', 'Mar', 'Avr', 'Mai', 'Juin', 
                    'Juil', 'Aout', 'Sep', 'Oct', 'Nov', 'Dec'])
ax.set_xlabel('Mois')
ax.set_ylabel('Valeur')
ax.set_title('Encodage Cyclique des Mois (sin/cos)')
ax.legend()
ax.grid(True)
plt.show()

# %%
# 4.4 Features temporelles (Lags)
print("\nCreation des features de lag...")

# Creer un index temporel
data['period'] = data['year'] * 12 + data['month']

# Trier les donnees
data = data.sort_values(['carrier', 'airport', 'period']).reset_index(drop=True)

# Lag features par paire (carrier + airport)
for lag in [1, 3]:
    col_name = f'pair_lag{lag}' if lag == 1 else 'pair_lag3_mean'
    data[col_name] = data.groupby(['carrier', 'airport'])['delay_rate'].shift(lag)

# Moyenne mobile des 3 derniers mois
data['pair_lag3_mean'] = data.groupby(['carrier', 'airport'])['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)

# Moyenne cumulative
data['pair_expanding_mean'] = data.groupby(['carrier', 'airport'])['delay_rate'].transform(
    lambda x: x.shift(1).expanding(min_periods=1).mean()
)

# Lag features par aeroport
data['airport_lag1'] = data.groupby('airport')['delay_rate'].shift(1)
data['airport_lag3_mean'] = data.groupby('airport')['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)
data['airport_expanding_mean'] = data.groupby('airport')['delay_rate'].transform(
    lambda x: x.shift(1).expanding(min_periods=1).mean()
)

# Lag features par carrier
data['carrier_lag1'] = data.groupby('carrier')['delay_rate'].shift(1)
data['carrier_lag3_mean'] = data.groupby('carrier')['delay_rate'].transform(
    lambda x: x.shift(1).rolling(3, min_periods=1).mean()
)
data['carrier_expanding_mean'] = data.groupby('carrier')['delay_rate'].transform(
    lambda x: x.shift(1).expanding(min_periods=1).mean()
)

# Log des vols
data['log_arr_flights'] = np.log1p(data['arr_flights'].clip(lower=0))

print("[OK] Features de lag creees!")

# %%
# 4.5 Visualisation des correlations
print("\nMatrice de correlation...")

FEATURE_COLS = [
    'year', 'month', 'month_sin', 'month_cos',
    'is_summer', 'is_winter', 'is_holiday_season',
    'carrier_encoded', 'airport_encoded',
    'arr_flights', 'log_arr_flights',
    'pair_lag1', 'pair_lag3_mean', 'pair_expanding_mean',
    'airport_lag1', 'airport_lag3_mean', 'airport_expanding_mean',
    'carrier_lag1', 'carrier_lag3_mean', 'carrier_expanding_mean'
]

# Matrice de correlation
corr_matrix = data[FEATURE_COLS + ['target']].corr()

fig, ax = plt.subplots(figsize=(16, 14))
mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
sns.heatmap(corr_matrix, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r',
            center=0, square=True, linewidths=0.5, ax=ax)
ax.set_title('Matrice de Correlation des Features')
plt.tight_layout()
plt.show()

# Correlation avec la target
print("\nCorrelation avec la Target:")
target_corr = corr_matrix['target'].drop('target').sort_values(ascending=False)
print(target_corr.round(3))

# %% [markdown]
# ## 5. Split Train/Validation/Test (Temporel)

# %%
print("Split temporel des donnees...")

# Split temporel
unique_periods = sorted(data['period'].unique())
n_periods = len(unique_periods)

n_train = int(n_periods * 0.70)
n_val = int(n_periods * 0.20)

train_periods = set(unique_periods[:n_train])
val_periods = set(unique_periods[n_train:n_train + n_val])
test_periods = set(unique_periods[n_train + n_val:])

train_mask = data['period'].isin(train_periods)
val_mask = data['period'].isin(val_periods)
test_mask = data['period'].isin(test_periods)

print(f"\nDistribution du Split:")
print(f"   Train:      {train_mask.sum():,} echantillons ({train_mask.mean()*100:.1f}%)")
print(f"   Validation: {val_mask.sum():,} echantillons ({val_mask.mean()*100:.1f}%)")
print(f"   Test:       {test_mask.sum():,} echantillons ({test_mask.mean()*100:.1f}%)")

# Visualisation
fig, ax = plt.subplots(figsize=(14, 5))

train_years = data.loc[train_mask].groupby('year').size()
val_years = data.loc[val_mask].groupby('year').size()
test_years = data.loc[test_mask].groupby('year').size()

x = sorted(data['year'].unique())
width = 0.25

ax.bar([i - width for i in range(len(x))], [train_years.get(y, 0) for y in x], 
       width, label='Train', color='steelblue')
ax.bar(range(len(x)), [val_years.get(y, 0) for y in x], 
       width, label='Validation', color='orange')
ax.bar([i + width for i in range(len(x))], [test_years.get(y, 0) for y in x], 
       width, label='Test', color='green')

ax.set_xlabel('Annee')
ax.set_ylabel('Nombre d\'echantillons')
ax.set_title('Distribution Temporelle du Split Train/Val/Test')
ax.set_xticks(range(len(x)))
ax.set_xticklabels(x, rotation=45)
ax.legend()
plt.tight_layout()
plt.show()

# %%
# Preparation des donnees
X_train = data.loc[train_mask, FEATURE_COLS]
y_train = data.loc[train_mask, 'target']

X_val = data.loc[val_mask, FEATURE_COLS]
y_val = data.loc[val_mask, 'target']

X_test = data.loc[test_mask, FEATURE_COLS]
y_test = data.loc[test_mask, 'target']

print(f"\nShapes:")
print(f"   X_train: {X_train.shape}")
print(f"   X_val:   {X_val.shape}")
print(f"   X_test:  {X_test.shape}")

# Distribution de la target par split
print(f"\nTaux de classe positive (Risque):")
print(f"   Train:      {y_train.mean()*100:.1f}%")
print(f"   Validation: {y_val.mean()*100:.1f}%")
print(f"   Test:       {y_test.mean()*100:.1f}%")

# %% [markdown]
# ## 6. Entrainement du Modele

# %%
print("Entrainement du modele XGBoost...")

# Ponderation des echantillons (avec gestion des NaN et valeurs non-positives)
arr_flights_train = X_train['arr_flights'].fillna(1).clip(lower=1)
sample_weights = np.sqrt(arr_flights_train).values

# Verification et nettoyage des poids
sample_weights = np.nan_to_num(sample_weights, nan=1.0, posinf=1.0, neginf=1.0)
sample_weights = np.clip(sample_weights, a_min=0.001, a_max=None)  # Assurer tous positifs

print(f"   Sample weights: min={sample_weights.min():.4f}, max={sample_weights.max():.4f}, nan={np.isnan(sample_weights).sum()}")

# Pipeline avec imputation
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

# Entrainement
import time
start_time = time.time()

pipeline.fit(X_train, y_train, model__sample_weight=sample_weights)

train_time = time.time() - start_time
print(f"\n[OK] Modele entraine en {train_time:.2f} secondes")

# %% [markdown]
# ## 7. Evaluation du Modele

# %%
# Predictions
print("Generation des predictions...")

proba_train = pipeline.predict_proba(X_train)[:, 1]
proba_val = pipeline.predict_proba(X_val)[:, 1]
proba_test = pipeline.predict_proba(X_test)[:, 1]

# Metriques
def compute_metrics(y_true, proba):
    return {
        'ROC-AUC': roc_auc_score(y_true, proba),
        'PR-AUC': average_precision_score(y_true, proba),
        'Positive Rate': y_true.mean()
    }

train_metrics = compute_metrics(y_train, proba_train)
val_metrics = compute_metrics(y_val, proba_val)
test_metrics = compute_metrics(y_test, proba_test)

print("\nMetriques par Split:")
metrics_df = pd.DataFrame({
    'Train': train_metrics,
    'Validation': val_metrics,
    'Test': test_metrics
}).round(4)
display(metrics_df)

# %%
# Courbe ROC
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# ROC Curve
for name, y_true, proba, color in [
    ('Train', y_train, proba_train, 'blue'),
    ('Validation', y_val, proba_val, 'orange'),
    ('Test', y_test, proba_test, 'green')
]:
    fpr, tpr, _ = roc_curve(y_true, proba)
    auc = roc_auc_score(y_true, proba)
    axes[0].plot(fpr, tpr, label=f'{name} (AUC={auc:.3f})', color=color, linewidth=2)

axes[0].plot([0, 1], [0, 1], 'k--', label='Aleatoire')
axes[0].set_xlabel('Taux de Faux Positifs (FPR)')
axes[0].set_ylabel('Taux de Vrais Positifs (TPR)')
axes[0].set_title('Courbe ROC')
axes[0].legend(loc='lower right')
axes[0].grid(True)

# Precision-Recall Curve
for name, y_true, proba, color in [
    ('Train', y_train, proba_train, 'blue'),
    ('Validation', y_val, proba_val, 'orange'),
    ('Test', y_test, proba_test, 'green')
]:
    precision, recall, _ = precision_recall_curve(y_true, proba)
    pr_auc = average_precision_score(y_true, proba)
    axes[1].plot(recall, precision, label=f'{name} (PR-AUC={pr_auc:.3f})', color=color, linewidth=2)

axes[1].set_xlabel('Recall')
axes[1].set_ylabel('Precision')
axes[1].set_title('Courbe Precision-Recall')
axes[1].legend(loc='lower left')
axes[1].grid(True)

plt.tight_layout()
plt.show()

# %%
# Distribution des probabilites
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for ax, (name, y_true, proba) in zip(axes, [
    ('Train', y_train, proba_train),
    ('Validation', y_val, proba_val),
    ('Test', y_test, proba_test)
]):
    ax.hist(proba[y_true == 0], bins=50, alpha=0.5, label='Normal (0)', color='green')
    ax.hist(proba[y_true == 1], bins=50, alpha=0.5, label='Risque (1)', color='red')
    ax.axvline(x=0.5, color='black', linestyle='--', label='Cutoff 0.5')
    ax.set_xlabel('Probabilite Predite')
    ax.set_ylabel('Frequence')
    ax.set_title(f'Distribution des Probabilites - {name}')
    ax.legend()

plt.tight_layout()
plt.show()

# %% [markdown]
# ## 8. Choix du Cutoff Optimal

# %%
print("Recherche du cutoff optimal pour ACCURACY...")

def find_optimal_cutoff_accuracy(y_true, proba):
    """Trouver le cutoff qui maximise l'accuracy"""
    best_acc = 0
    best_cutoff = 0.5
    
    for cutoff in np.arange(0.1, 0.9, 0.01):
        y_pred = (proba >= cutoff).astype(int)
        acc = (y_pred == y_true).mean()
        if acc > best_acc:
            best_acc = acc
            best_cutoff = cutoff
    
    # Calculer precision et recall au cutoff optimal
    y_pred = (proba >= best_cutoff).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    
    return best_cutoff, best_acc, recall, precision

# Trouver le cutoff optimal pour accuracy
optimal_cutoff, best_accuracy, achieved_recall, achieved_precision = find_optimal_cutoff_accuracy(y_val, proba_val)

print(f"\n[OK] Cutoff Optimal (pour Accuracy): {optimal_cutoff:.3f}")
print(f"     Accuracy:  {best_accuracy*100:.1f}%")
print(f"     Recall:    {achieved_recall*100:.1f}%")
print(f"     Precision: {achieved_precision*100:.1f}%")

# %%
# Visualisation du trade-off Precision/Recall
precision, recall, thresholds = precision_recall_curve(y_val, proba_val)

fig, ax = plt.subplots(figsize=(12, 6))

# Ajouter un 0 au debut de thresholds pour aligner
thresholds_plot = np.append(thresholds, 1)

ax.plot(thresholds_plot, precision, 'b-', label='Precision', linewidth=2)
ax.plot(thresholds_plot, recall, 'r-', label='Recall', linewidth=2)
ax.axvline(x=optimal_cutoff, color='green', linestyle='--', linewidth=2, 
           label=f'Cutoff Optimal ({optimal_cutoff:.2f})')
ax.axhline(y=0.90, color='gray', linestyle=':', alpha=0.5, label='Min Recall 90%')

ax.set_xlabel('Cutoff (Seuil de Decision)')
ax.set_ylabel('Score')
ax.set_title('Trade-off Precision vs Recall selon le Cutoff')
ax.legend(loc='center right')
ax.grid(True)
ax.set_xlim([0, 1])
ax.set_ylim([0, 1])

plt.tight_layout()
plt.show()

# %% [markdown]
# ## 9. Matrice de Confusion

# %%
# Predictions binaires avec le cutoff optimal
y_pred_val = (proba_val >= optimal_cutoff).astype(int)
y_pred_test = (proba_test >= optimal_cutoff).astype(int)

# Matrices de confusion
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for ax, (name, y_true, y_pred) in zip(axes, [
    ('Validation', y_val, y_pred_val),
    ('Test', y_test, y_pred_test)
]):
    cm = confusion_matrix(y_true, y_pred)
    cm_pct = cm / cm.sum() * 100
    
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax,
                xticklabels=['Normal (0)', 'Risque (1)'],
                yticklabels=['Normal (0)', 'Risque (1)'])
    
    # Ajouter les pourcentages
    for i in range(2):
        for j in range(2):
            ax.text(j + 0.5, i + 0.7, f'({cm_pct[i, j]:.1f}%)', 
                   ha='center', va='center', fontsize=10, color='gray')
    
    ax.set_xlabel('Predit')
    ax.set_ylabel('Reel')
    ax.set_title(f'Matrice de Confusion - {name}\n(Cutoff = {optimal_cutoff:.2f})')

plt.tight_layout()
plt.show()

# %%
# Classification Report
print("\nClassification Report - Test:")
print(classification_report(y_test, y_pred_test, 
                           target_names=['Normal (0)', 'Risque (1)']))

# Metriques detaillees
def detailed_metrics(y_true, y_pred, proba):
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    
    return {
        'True Positives (TP)': tp,
        'True Negatives (TN)': tn,
        'False Positives (FP)': fp,
        'False Negatives (FN)': fn,
        'Accuracy': (tp + tn) / (tp + tn + fp + fn),
        'Precision': tp / (tp + fp) if (tp + fp) > 0 else 0,
        'Recall (Sensitivity)': tp / (tp + fn) if (tp + fn) > 0 else 0,
        'Specificity': tn / (tn + fp) if (tn + fp) > 0 else 0,
        'F1-Score': 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0,
        'Balanced Accuracy': ((tp / (tp + fn)) + (tn / (tn + fp))) / 2,
        'ROC-AUC': roc_auc_score(y_true, proba),
        'PR-AUC': average_precision_score(y_true, proba)
    }

test_detailed = detailed_metrics(y_test, y_pred_test, proba_test)
print("\nMetriques Detaillees - Test:")
for metric, value in test_detailed.items():
    if isinstance(value, float):
        print(f"   {metric}: {value:.4f}")
    else:
        print(f"   {metric}: {value:,}")

# %% [markdown]
# ## 10. Importance des Features

# %%
# Extraire le modele XGBoost de la pipeline
xgb_model = pipeline.named_steps['model']

# Importance des features
feature_importance = pd.DataFrame({
    'feature': FEATURE_COLS,
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False)

print("Top 10 Features les plus importantes:")
display(feature_importance.head(10))

# Visualisation
fig, ax = plt.subplots(figsize=(10, 8))

colors = plt.cm.RdYlGn(np.linspace(0.8, 0.2, len(feature_importance)))
bars = ax.barh(feature_importance['feature'], feature_importance['importance'], 
               color=colors, edgecolor='black')

ax.set_xlabel('Importance')
ax.set_ylabel('Feature')
ax.set_title('Importance des Features (XGBoost)')
ax.invert_yaxis()

# Ajouter les valeurs
for bar, importance in zip(bars, feature_importance['importance']):
    ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
            f'{importance:.3f}', va='center', fontsize=9)

plt.tight_layout()
plt.show()

# %% [markdown]
# ## 11. Sauvegarde du Modele

# %%
import joblib
import json
from datetime import datetime

# Creer le dossier de sortie
output_dir = 'model_output'
import os
os.makedirs(output_dir, exist_ok=True)

# Sauvegarder le modele
model_path = f'{output_dir}/model.pkl'
joblib.dump(pipeline, model_path)
print(f"[OK] Modele sauvegarde: {model_path}")

# Sauvegarder les encodeurs
joblib.dump(le_carrier, f'{output_dir}/label_encoder_carrier.pkl')
joblib.dump(le_airport, f'{output_dir}/label_encoder_airport.pkl')
print(f"[OK] Encodeurs sauvegardes")

# Sauvegarder les metriques
metrics_output = {
    'run_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
    'target_threshold': TARGET_THRESHOLD,
    'optimal_cutoff': float(optimal_cutoff),
    'feature_columns': FEATURE_COLS,
    'splits': {
        'train': int(train_mask.sum()),
        'validation': int(val_mask.sum()),
        'test': int(test_mask.sum())
    },
    'metrics': {
        'train': {k: float(v) for k, v in train_metrics.items()},
        'validation': {k: float(v) for k, v in val_metrics.items()},
        'test': {k: float(v) for k, v in test_metrics.items()}
    },
    'test_detailed': {k: float(v) if isinstance(v, (float, np.float64)) else int(v) 
                      for k, v in test_detailed.items()},
    'feature_importance': feature_importance.to_dict('records')
}

with open(f'{output_dir}/metrics.json', 'w') as f:
    json.dump(metrics_output, f, indent=2)
print(f"[OK] Metriques sauvegardees: {output_dir}/metrics.json")

# %%
# Telecharger les fichiers (optionnel - seulement sur Colab)
try:
    from google.colab import files
    print("\nTelechargement des fichiers...")
    files.download(f'{output_dir}/model.pkl')
    files.download(f'{output_dir}/label_encoder_carrier.pkl')
    files.download(f'{output_dir}/label_encoder_airport.pkl')
    files.download(f'{output_dir}/metrics.json')
    print("\n[OK] Tous les fichiers ont ete telecharges!")
except ImportError:
    print("\n[INFO] Execution locale - pas de telechargement automatique")
    print(f"       Fichiers disponibles dans: {output_dir}/")

# %% [markdown]
# ## 12. Resume Final

# %%
print("=" * 80)
print("RESUME DE L'ENTRAINEMENT")
print("=" * 80)

print(f"""
OBJECTIF
   Predire si delay_rate > {TARGET_THRESHOLD*100}% (classification binaire)

DONNEES
   Total: {len(data):,} echantillons
   Train: {train_mask.sum():,} ({train_mask.mean()*100:.1f}%)
   Validation: {val_mask.sum():,} ({val_mask.mean()*100:.1f}%)
   Test: {test_mask.sum():,} ({test_mask.mean()*100:.1f}%)

MODELE
   Type: XGBoost Classifier
   Features: {len(FEATURE_COLS)}
   Temps d'entrainement: {train_time:.2f}s

PERFORMANCE (Test)
   ROC-AUC: {test_metrics['ROC-AUC']:.4f}
   PR-AUC: {test_metrics['PR-AUC']:.4f}
   Recall: {test_detailed['Recall (Sensitivity)']:.4f}
   Precision: {test_detailed['Precision']:.4f}
   F1-Score: {test_detailed['F1-Score']:.4f}
   Balanced Accuracy: {test_detailed['Balanced Accuracy']:.4f}

CUTOFF OPTIMAL: {optimal_cutoff:.3f}

TOP 3 FEATURES
""")

for i, row in feature_importance.head(3).iterrows():
    print(f"   {i+1}. {row['feature']}: {row['importance']:.4f}")

print("\n" + "=" * 80)
print("[OK] ENTRAINEMENT TERMINE AVEC SUCCES!")
print("=" * 80)
