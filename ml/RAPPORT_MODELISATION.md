# Rapport de Modelisation ML - Prediction des Retards Aeriens

## Vue d'Ensemble

| Element | Valeur |
|---------|--------|
| **Objectif** | Predire si le taux de retard > 20% (classification binaire) |
| **Modele** | XGBoost Classifier |
| **Accuracy** | **78.9%** |
| **ROC-AUC** | 0.808 |
| **Temps d'entrainement** | 7.55 secondes |

---

## Donnees

| Split | Echantillons | Pourcentage | Periode |
|-------|--------------|-------------|---------|
| Train | 216,019 | 68% | Anciennes |
| Validation | 63,225 | 20% | Milieu |
| Test | 38,773 | 12% | Recentes |

**Total: 318,017 lignes** (2003-2022)

---

## Performance du Modele

### Metriques Principales

| Metrique | Valeur | Interpretation |
|----------|--------|----------------|
| **ROC-AUC** | 0.808 | Bonne separation des classes |
| **Accuracy** | 78.9% | 79% des predictions correctes |
| **Precision** | 71.1% | 71% des alertes sont vraies |
| **Recall** | 42.3% | 42% des risques detectes |
| **F1-Score** | 0.53 | Equilibre precision/recall |

### Matrice de Confusion (Test)

```
                    Predit
                 Normal  Risque
Reel  Normal     25,970   1,879   (93% bien classes)
      Risque      6,299   4,625   (42% detectes)
```

### Cutoff Optimal

**Cutoff: 0.46** (optimise pour Accuracy)

| Probabilite | Categorie | Action |
|-------------|-----------|--------|
| >= 0.75 | **Critical** | Alerte immediate |
| >= 0.60 | **High** | Surveillance renforcee |
| >= 0.46 | **Medium** | Attention requise |
| < 0.46 | **Low** | Fonctionnement normal |

---

## Features Utilisees (20)

### Top 10 par Importance

| Rang | Feature | Importance | Description |
|------|---------|------------|-------------|
| 1 | pair_lag1 | 21.7% | Retard mois precedent (route) |
| 2 | carrier_lag1 | 11.6% | Retard mois precedent (compagnie) |
| 3 | airport_lag1 | 8.9% | Retard mois precedent (aeroport) |
| 4 | month_cos | 6.8% | Saisonnalite cyclique |
| 5 | pair_lag3_mean | 6.6% | Moyenne 3 mois (route) |
| 6 | month_sin | 6.5% | Saisonnalite cyclique |
| 7 | month | 6.3% | Mois de l'annee |
| 8 | is_winter | 5.4% | Saison hivernale |
| 9 | airport_lag3_mean | 4.4% | Moyenne 3 mois (aeroport) |
| 10 | is_summer | 4.2% | Saison estivale |

**Conclusion:** Le passe recent (lags) est le meilleur predicteur!

---

## Comparaison des Approches

### Notebooks Testes

| Version | Temps | Accuracy | ROC-AUC | Verdict |
|---------|-------|----------|---------|---------|
| training_complete.py | 8 sec | **78.9%** | 0.808 | **PRODUCTION** |
| training_pro.py | 5-10 min | ~70% | ~0.81 | Alternative |
| training_improved.py | 60 min | 68% | 0.814 | Non recommande |

### Pourquoi training_complete.py?

1. **Rapide** - 8 secondes vs 60 minutes
2. **Stable** - Pas de problemes NaN
3. **Optimal** - 78.9% accuracy atteint
4. **Simple** - Facile a maintenir

---

## Limites et Ameliorations Futures

### Limites Actuelles

| Limite | Impact |
|--------|--------|
| Pas de donnees meteo | Cause majeure manquante |
| Recall 42% | On rate ~58% des risques |
| Donnees historiques uniquement | Pas de temps reel |

### Ameliorations Potentielles

| Amelioration | Gain Potentiel | Effort |
|--------------|----------------|--------|
| Ajouter donnees meteo | +5-10% | Eleve |
| Evenements (vacances, etc.) | +3-5% | Moyen |
| Hyperparameter tuning | +1-2% | Faible |

### Performance Maximum Estimee

```
Actuel (sans meteo):     78.9% accuracy
Maximum sans meteo:      ~82-85%
Maximum avec meteo:      ~90-92%
```

---

## Integration Pipeline

### Architecture

```
CSV Brut --> NiFi --> Kafka --> ClickHouse
                                    |
                          ML Training (XGBoost)
                                    |
                          Predictions --> ClickHouse (ml_predictions)
                                    |
                          FastAPI --> Streamlit/Power BI
```

### Fichiers du Modele

| Fichier | Contenu |
|---------|---------|
| model.pkl | Modele XGBoost entraine |
| label_encoder_carrier.pkl | Encodeur compagnies (30) |
| label_encoder_airport.pkl | Encodeur aeroports (421) |
| metrics.json | Metriques et configuration |

### Script d'Integration

```bash
python scripts/integrate_classification_model.py
```

Genere ~34,000 predictions pour 2026 (toutes routes x 12 mois).

---

## Technologies Utilisees

| Categorie | Outils |
|-----------|--------|
| ML | XGBoost, Scikit-learn, Pandas, NumPy |
| Pipeline | Kafka, NiFi, ClickHouse, MongoDB |
| API | FastAPI, Uvicorn |
| Dashboard | Streamlit, Power BI |
| Infra | Docker, Docker Compose |

---

## Conclusion

Le modele XGBoost atteint **78.9% d'accuracy** et **0.808 ROC-AUC**, ce qui est **optimal** pour les donnees disponibles. Des ameliorations significatives necessiteraient l'ajout de donnees externes (meteo, evenements).

**Statut: PRET POUR LA PRODUCTION**
