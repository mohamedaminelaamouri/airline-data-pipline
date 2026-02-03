# 🎯 TABLEAU RAPIDE : Mesure DAX → Colonne Gold

## ✅ SUPPRIMER ces mesures DAX et utiliser directement la colonne Gold

### 📊 Table `gold_flights_monthly` (Table principale)

| N° | Mesure DAX à SUPPRIMER | → Colonne Gold à utiliser | Type agrégation |
|----|------------------------|---------------------------|-----------------|
| 1 | `Total Flights` | `total_flights` | SUM |
| 2 | `Total Delayed Flights` | `total_delayed` | SUM |
| 3 | `Global Delay Rate` | `delay_rate` | AVERAGE (×100 pour %) |
| 4 | `delay rate %` | `delay_rate` | AVERAGE (×100 pour %) |
| 5 | `Total Delay Cost USD` | `total_delay_cost_usd` | SUM |
| 6 | `Performance Score Global` | `performance_score` | AVERAGE |
| 7 | `Avg Delay Minutes` | `avg_delay_minutes` | AVERAGE |
| 8 | `Cancellation Rate` | `cancellation_rate` | AVERAGE (×100 pour %) |
| 9 | `Diversion Rate` | `diversion_rate` | AVERAGE (×100 pour %) |
| 10 | `On-Time Performance` | `on_time_rate` | AVERAGE (×100 pour %) |
| 11 | `Severe Delays` | `severe_delays` | SUM |
| 12 | `Severe Delay Rate` | `severe_delay_rate` | AVERAGE (×100 pour %) |
| 13 | `Delay Cost per Flight` | `delay_cost_per_flight` | AVERAGE |
| 14 | `Avg Cost Per Delayed Flight` | `avg_cost_per_delayed` | AVERAGE |
| 15 | `Total Delay Causes` | `total_delay_causes` | SUM |
| 16 | `Carrier Cause %` | `carrier_cause_pct` | AVERAGE (×100 pour %) |
| 17 | `Weather Cause %` | `weather_cause_pct` | AVERAGE (×100 pour %) |
| 18 | `NAS Cause %` | `nas_cause_pct` | AVERAGE (×100 pour %) |
| 19 | `Security Cause %` | `security_cause_pct` | AVERAGE (×100 pour %) |
| 20 | `Late Aircraft Cause %` | `late_aircraft_cause_pct` | AVERAGE (×100 pour %) |
| 21 | `Delay Counts` | `total_delay_causes` | SUM |

---

### 📅 Table `gold_flights_yearly` (Données YTD)

| N° | Mesure DAX à SUPPRIMER | → Colonne Gold à utiliser | Type agrégation |
|----|------------------------|---------------------------|-----------------|
| 22 | `Delayed Flights YTD` | `ytd_total_delayed` | MAX (ou valeur directe) |
| 23 | `Delay Cost YTD` | `ytd_delay_cost_usd` | MAX |
| 24 | `YTD Delay Rate` | `ytd_delay_rate` | MAX (×100 pour %) |
| 25 | `YTD Flights` | `ytd_total_flights` | MAX |

---

### 🔍 Table `gold_delay_causes` (Détail par cause)

| N° | Mesure DAX à SUPPRIMER | → Colonne Gold | Filtre sur `cause_code` |
|----|------------------------|----------------|-------------------------|
| 26 | `carrier` (volume cause) | `cause_count` | = 'carrier_ct' |
| 27 | `Weather` | `cause_count` | = 'weather_ct' |
| 28 | `NAS` | `cause_count` | = 'nas_ct' |
| 29 | `Security` | `cause_count` | = 'security_ct' |
| 30 | `Late Aircraft` | `cause_count` | = 'late_aircraft_ct' |
| 31 | `Delay Cause % by Airline` | `cause_pct` | (filtré par slicer) |

**Colonnes utiles dans cette table :**
- `cause_name` : Nom lisible (Airline Issue, Bad Weather, Air Traffic, Security, Late Plane)
- `cause_category` : Catégorie (Controllable, Uncontrollable, System)

---

### 🗺️ Table `gold_airport_summary` (Vue aéroport + géo)

| N° | Mesure DAX à SUPPRIMER | → Colonne Gold | Type agrégation |
|----|------------------------|----------------|-----------------|
| 32 | `Airport Delay Rate` | `delay_rate` | AVERAGE (×100 pour %) |
| 33 | `Airport Performance Score` | `performance_score` | AVERAGE |
| 34 | `Airport Delay Cost` | `delay_cost_usd` | SUM |

**Colonnes géo pour cartes :**
- `latitude` : Pour visualisation carte
- `longitude` : Pour visualisation carte

---

## 🔧 MESURES DAX LÉGÈRES À RECRÉER

Ces mesures restent en DAX car elles nécessitent une logique Power BI :

```
┌─────────────────────────────┬──────────────────────────────────────────────┐
│ Mesure                      │ Pourquoi en DAX                              │
├─────────────────────────────┼──────────────────────────────────────────────┤
│ Display Month               │ FORMAT() pour affichage texte                │
│ Performance Status          │ SWITCH() pour texte conditionnel             │
│ Alert Status                │ SWITCH() multi-conditions                    │
│ MoM Change                  │ DATEADD() comparaison relative               │
│ MoM Change Display          │ FORMAT() + IF()                              │
│ Delay Trend                 │ IF() texte conditionnel                      │
│ Airline Performance Rank    │ RANKX() ranking dynamique                    │
│ Worst Airline This Month    │ TOPN() sélection dynamique                   │
│ Worst Airport This Month    │ TOPN() sélection dynamique                   │
│ Airline Delay Rate          │ SELECTEDVALUE() contexte filtre              │
│ Airline Delay Cost          │ SELECTEDVALUE() contexte filtre              │
│ Total Flights by Airline    │ ALLSELECTED() contexte visuel                │
│ Airline Cost Millions       │ Formatage simple (/1e6)                      │
│ Airline Delay Cost Formatted│ FORMAT() texte                               │
│ Total Delay Cost Billions   │ Formatage simple (/1e9)                      │
└─────────────────────────────┴──────────────────────────────────────────────┘
```

---

## ⛔ NE PAS TOUCHER (ML)

| Mesure | Table source |
|--------|--------------|
| `Predicted Delay Rate DEBUG` | ml_predictions |
| Toute mesure avec "Predict" | ml_predictions |

---

## 📋 ACTIONS DANS POWER BI

### Étape 1 : Supprimer l'ancienne table
1. Aller dans **Modèle** → clic droit sur `FlightData` → **Supprimer**
2. Idem pour `Airports` (l'ancienne)

### Étape 2 : Importer les nouvelles tables
1. **Accueil** → **Obtenir des données** → **ODBC** → DSN `ClickHouse_Airline`
2. Cocher : `gold_flights_monthly`, `gold_flights_yearly`, `gold_delay_causes`, `gold_airport_summary`

### Étape 3 : Reconfigurer les visuels
Pour chaque visuel, remplacer l'ancien champ par le nouveau :

| Ancien champ | Nouveau champ |
|--------------|---------------|
| [Total Flights] | gold_flights_monthly[total_flights] |
| [Global Delay Rate] | gold_flights_monthly[delay_rate] |
| ... | ... |

### Étape 4 : Créer les mesures DAX légères
Copier-coller les formules DAX depuis le guide complet.

---

**Résultat attendu :** Tous les visuels fonctionnent directement avec les colonnes pré-calculées, sans charge DAX !
