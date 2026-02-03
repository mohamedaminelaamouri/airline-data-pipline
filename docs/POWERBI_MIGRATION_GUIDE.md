# 📊 GUIDE DE MIGRATION POWER BI → CLICKHOUSE GOLD

## ⚠️ IMPORTANT : La table `ml_predictions` reste INCHANGÉE

---

## 🎯 OBJECTIF

Remplacer toutes les mesures DAX par des colonnes pré-calculées dans ClickHouse.
Les visuels Power BI fonctionneront directement après le chargement des nouvelles tables.

---

## 📋 ÉTAPES DE MIGRATION

### ÉTAPE 1 : Supprimer les anciennes sources de données

Dans Power BI Desktop :
1. **Accueil** → **Transformer les données** → **Éditeur Power Query**
2. Supprimer ces tables (clic droit → Supprimer) :
   - `FlightData` (ancienne table de vols)
   - `Airports` (ancienne table aéroports)
   - ❌ **NE PAS SUPPRIMER** : `MLPredictions` ou toute table liée aux prédictions ML

### ÉTAPE 2 : Ajouter les nouvelles tables Gold

1. **Accueil** → **Obtenir des données** → **ODBC**
2. Sélectionner le DSN : `ClickHouse_Airline`
3. Importer ces 4 tables :
   - `gold_flights_monthly`
   - `gold_flights_yearly`
   - `gold_delay_causes`
   - `gold_airport_summary`

---

## 📊 MAPPING COMPLET : MESURES DAX → COLONNES CLICKHOUSE

### TABLEAU PRINCIPAL : `gold_flights_monthly`

| # | Mesure DAX (à supprimer) | Colonne ClickHouse | Usage dans visuels |
|---|--------------------------|--------------------|--------------------|
| 1 | `Total Flights` | `total_flights` | Cartes, graphiques |
| 2 | `Total Delayed Flights` | `total_delayed` | Cartes, graphiques |
| 3 | `Global Delay Rate` | `delay_rate` | KPI, jauges (×100 pour %) |
| 4 | `delay rate %` | `delay_rate` | Idem |
| 5 | `Total Delay Cost USD` | `total_delay_cost_usd` | Cartes financières |
| 6 | `Total Delay Cost Billions` | `total_delay_cost_usd / 1e9` | Mesure simple |
| 7 | `Performance Score Global` | `performance_score` | Jauges, KPI |
| 8 | `Avg Delay Minutes` | `avg_delay_minutes` | Cartes |
| 9 | `Cancellation Rate` | `cancellation_rate` | KPI (×100 pour %) |
| 10 | `Diversion Rate` | `diversion_rate` | KPI (×100 pour %) |
| 11 | `On-Time Performance` | `on_time_rate` | KPI (×100 pour %) |
| 12 | `Delay Cost per Flight` | `delay_cost_per_flight` | Cartes |
| 13 | `Avg Cost Per Delayed Flight` | `avg_cost_per_delayed` | Cartes |
| 14 | `Severe Delays` | `severe_delays` | Cartes |
| 15 | `Severe Delay Rate` | `severe_delay_rate` | KPI (×100 pour %) |
| 16 | `Total Delay Causes` | `total_delay_causes` | Cartes |
| 17 | `Carrier Cause %` | `carrier_cause_pct` | Graphiques causes (×100) |
| 18 | `Weather Cause %` | `weather_cause_pct` | Graphiques causes (×100) |
| 19 | `NAS Cause %` | `nas_cause_pct` | Graphiques causes (×100) |
| 20 | `Security Cause %` | `security_cause_pct` | Graphiques causes (×100) |
| 21 | `Late Aircraft Cause %` | `late_aircraft_cause_pct` | Graphiques causes (×100) |
| 22 | `Delay Counts` | `total_delay_causes` | Identique à #16 |

### TABLEAU YTD : `gold_flights_yearly`

| # | Mesure DAX (à supprimer) | Colonne ClickHouse | Usage |
|---|--------------------------|--------------------| ------|
| 23 | `Delayed Flights YTD` | `ytd_total_delayed` | Cartes YTD |
| 24 | `Delay Cost YTD` | `ytd_delay_cost_usd` | Cartes financières YTD |
| 25 | `YTD Delay Rate` | `ytd_delay_rate` | KPI YTD (×100 pour %) |
| 26 | `YTD Flights` | `ytd_total_flights` | Cartes YTD |

### TABLEAU CAUSES : `gold_delay_causes`

| # | Mesure DAX (à supprimer) | Colonne ClickHouse | Filtre |
|---|--------------------------|--------------------| -------|
| 27 | `carrier` (cause) | `cause_count` | WHERE `cause_code` = 'carrier_ct' |
| 28 | `Weather` | `cause_count` | WHERE `cause_code` = 'weather_ct' |
| 29 | `NAS` | `cause_count` | WHERE `cause_code` = 'nas_ct' |
| 30 | `Security` | `cause_count` | WHERE `cause_code` = 'security_ct' |
| 31 | `Late Aircraft` | `cause_count` | WHERE `cause_code` = 'late_aircraft_ct' |

### TABLEAU AÉROPORTS : `gold_airport_summary`

| # | Mesure DAX (à supprimer) | Colonne ClickHouse | Usage |
|---|--------------------------|--------------------| ------|
| 32 | `Airport Delay Rate` | `delay_rate` | Cartes aéroport |
| 33 | `Airport Performance Score` | `performance_score` | Jauges aéroport |
| 34 | `Airport Delay Cost` | `delay_cost_usd` | Cartes financières |

---

## 🔧 MESURES DAX SIMPLIFIÉES À CONSERVER

Ces mesures restent en DAX mais sont **très légères** car elles utilisent les données pré-calculées :

### Mesures de formatage (texte)

```dax
// Display Month - Formatage texte
Display Month = FORMAT(DATE([year], [month], 1), "MMMM YYYY")

// Delay Cost in 2025 - Formatage
Delay Cost in 2025 = FORMAT([total_delay_cost_usd], "$#,##0.00")

// Performance Status - Texte conditionnel
Performance Status = 
SWITCH(
    TRUE(),
    [performance_score] >= 85, "Excellent",
    [performance_score] >= 75, "Bon",
    [performance_score] >= 65, "Moyen",
    "Critique"
)

// Alert Status - Texte conditionnel
Alert Status = 
SWITCH(
    TRUE(),
    [delay_rate] > 0.30, "🔴 Alerte Critique",
    [delay_rate] > 0.20, "🟠 Attention",
    [delay_rate] > 0.15, "🟡 Surveillance",
    "🟢 Normal"
)
```

### Mesures de comparaison MoM (légères)

```dax
// MoM Change - Utilise les données Gold pré-calculées
MoM Change = 
VAR CurrentRate = SELECTEDVALUE(gold_flights_monthly[delay_rate])
VAR PrevMonth = SELECTEDVALUE(gold_flights_monthly[month]) - 1
VAR PrevYear = IF(PrevMonth = 0, SELECTEDVALUE(gold_flights_monthly[year]) - 1, SELECTEDVALUE(gold_flights_monthly[year]))
VAR AdjustedMonth = IF(PrevMonth = 0, 12, PrevMonth)
VAR PrevRate = CALCULATE(
    SELECTEDVALUE(gold_flights_monthly[delay_rate]),
    gold_flights_monthly[year] = PrevYear,
    gold_flights_monthly[month] = AdjustedMonth
)
RETURN CurrentRate - PrevRate

// MoM Change Display
MoM Change Display = 
VAR Change = [MoM Change]
RETURN 
IF(Change > 0, "↑ +" & FORMAT(Change * 100, "0.0") & "%",
IF(Change < 0, "↓ " & FORMAT(Change * 100, "0.0") & "%",
"→ 0%"))

// Delay Trend
Delay Trend = IF([MoM Change] > 0, "📈 En hausse", IF([MoM Change] < 0, "📉 En baisse", "➡️ Stable"))
```

### Mesures de ranking dynamique

```dax
// Airline Performance Rank
Airline Performance Rank = 
RANKX(
    ALL(gold_flights_monthly[carrier]),
    CALCULATE(AVERAGE(gold_flights_monthly[delay_rate])),
    ,
    ASC
)

// Worst Airline This Month
Worst Airline This Month = 
TOPN(1,
    SUMMARIZE(gold_flights_monthly, gold_flights_monthly[carrier_name]),
    CALCULATE(SUM(gold_flights_monthly[delay_rate])),
    DESC
)

// Worst Airport This Month  
Worst Airport This Month = 
TOPN(1,
    SUMMARIZE(gold_flights_monthly, gold_flights_monthly[airport_name]),
    CALCULATE(SUM(gold_flights_monthly[delay_rate])),
    DESC
)
```

### Mesures avec SELECTEDVALUE (contexte filtre)

```dax
// Airline Delay Rate - Pour contexte slicer
Airline Delay Rate = 
CALCULATE(
    AVERAGE(gold_flights_monthly[delay_rate]),
    FILTER(gold_flights_monthly, 
           gold_flights_monthly[carrier] = SELECTEDVALUE(gold_flights_monthly[carrier]))
)

// Airline Delay Cost
Airline Delay Cost = 
CALCULATE(
    SUM(gold_flights_monthly[total_delay_cost_usd]),
    FILTER(gold_flights_monthly,
           gold_flights_monthly[carrier] = SELECTEDVALUE(gold_flights_monthly[carrier]))
)

// Airline Cost Millions
Airline Cost Millions = [Airline Delay Cost] / 1000000

// Total Flights by Airline
Total Flights by Airline = 
CALCULATE(
    SUM(gold_flights_monthly[total_flights]),
    ALLSELECTED(gold_flights_monthly)
)
```

---

## 🎨 CONFIGURATION DES VISUELS

### Cartes KPI

| Visuel | Champ à utiliser | Table |
|--------|------------------|-------|
| Total Vols | `total_flights` (SUM) | gold_flights_monthly |
| Vols Retardés | `total_delayed` (SUM) | gold_flights_monthly |
| Taux de Retard | `delay_rate` (AVERAGE) × 100 | gold_flights_monthly |
| Score Performance | `performance_score` (AVERAGE) | gold_flights_monthly |
| Coût Total | `total_delay_cost_usd` (SUM) | gold_flights_monthly |

### Graphiques temporels (évolution par mois)

| Axe X | Valeurs | Table |
|-------|---------|-------|
| `year`, `month` ou `month_key` | `delay_rate`, `total_flights`, etc. | gold_flights_monthly |

### Graphiques causes de retard

| Axe X | Valeurs | Table |
|-------|---------|-------|
| `cause_name` | `cause_count` ou `cause_pct` | gold_delay_causes |

### Carte géographique

| Latitude | Longitude | Bulle/Couleur | Table |
|----------|-----------|---------------|-------|
| `latitude` | `longitude` | `delay_rate` ou `total_flights` | gold_airport_summary |

### Tableaux par compagnie/aéroport

| Lignes | Colonnes | Table |
|--------|----------|-------|
| `carrier_name` | `total_flights`, `delay_rate`, `performance_score` | gold_flights_monthly |
| `airport_name` | `total_flights`, `delay_rate`, `performance_score` | gold_airport_summary |

---

## 🔗 RELATIONS ENTRE TABLES

Dans **Modèle** → créer ces relations :

```
gold_flights_monthly[carrier] → gold_flights_yearly[carrier]
gold_flights_monthly[airport] → gold_flights_yearly[airport]
gold_flights_monthly[year] → gold_flights_yearly[year]
gold_flights_monthly[month] → gold_flights_yearly[month]

gold_flights_monthly[carrier] → gold_delay_causes[carrier]
gold_flights_monthly[airport] → gold_delay_causes[airport]
gold_flights_monthly[year] → gold_delay_causes[year]
gold_flights_monthly[month] → gold_delay_causes[month]

gold_flights_monthly[airport] → gold_airport_summary[airport]
gold_flights_monthly[year] → gold_airport_summary[year]
gold_flights_monthly[month] → gold_airport_summary[month]
```

---

## ✅ CHECKLIST DE MIGRATION

### Avant de supprimer

- [ ] Faire une sauvegarde du fichier .pbix actuel
- [ ] Noter les visuels et leurs mesures actuelles
- [ ] S'assurer que les tables Gold ont des données

### Suppression

- [ ] Supprimer la table `FlightData`
- [ ] Supprimer la table `Airports`
- [ ] Supprimer toutes les mesures DAX liées (sauf ML)
- [ ] ❌ **NE PAS** supprimer `MLPredictions`
- [ ] ❌ **NE PAS** supprimer `Predicted Delay Rate DEBUG`

### Import des nouvelles tables

- [ ] Importer `gold_flights_monthly`
- [ ] Importer `gold_flights_yearly`
- [ ] Importer `gold_delay_causes`
- [ ] Importer `gold_airport_summary`

### Configuration

- [ ] Créer les relations entre tables
- [ ] Recréer les mesures DAX légères (formatage, ranking, MoM)
- [ ] Reconfigurer chaque visuel avec les nouveaux champs

### Test

- [ ] Vérifier chaque carte KPI
- [ ] Vérifier chaque graphique
- [ ] Vérifier les filtres/slicers
- [ ] Vérifier que les données ML fonctionnent toujours

---

## 📝 RÉSUMÉ DES SUPPRESSIONS

### Mesures à SUPPRIMER (remplacées par colonnes Gold)

| # | Mesure | Remplacée par |
|---|--------|---------------|
| 1 | Global Delay Rate | `gold_flights_monthly.delay_rate` |
| 2 | Total Flights | `gold_flights_monthly.total_flights` |
| 3 | Total Delayed Flights | `gold_flights_monthly.total_delayed` |
| 4 | Total Delay Cost USD | `gold_flights_monthly.total_delay_cost_usd` |
| 5 | Performance Score Global | `gold_flights_monthly.performance_score` |
| 6 | Avg Delay Minutes | `gold_flights_monthly.avg_delay_minutes` |
| 7 | Cancellation Rate | `gold_flights_monthly.cancellation_rate` |
| 8 | Diversion Rate | `gold_flights_monthly.diversion_rate` |
| 9 | On-Time Performance | `gold_flights_monthly.on_time_rate` |
| 10 | Total Delay Causes | `gold_flights_monthly.total_delay_causes` |
| 11 | Carrier Cause % | `gold_flights_monthly.carrier_cause_pct` |
| 12 | Weather Cause % | `gold_flights_monthly.weather_cause_pct` |
| 13 | NAS Cause % | `gold_flights_monthly.nas_cause_pct` |
| 14 | Security Cause % | `gold_flights_monthly.security_cause_pct` |
| 15 | Late Aircraft Cause % | `gold_flights_monthly.late_aircraft_cause_pct` |
| 16 | Severe Delays | `gold_flights_monthly.severe_delays` |
| 17 | Severe Delay Rate | `gold_flights_monthly.severe_delay_rate` |
| 18 | Delay Cost per Flight | `gold_flights_monthly.delay_cost_per_flight` |
| 19 | Avg Cost Per Delayed Flight | `gold_flights_monthly.avg_cost_per_delayed` |
| 20 | Delayed Flights YTD | `gold_flights_yearly.ytd_total_delayed` |
| 21 | Delay Cost YTD | `gold_flights_yearly.ytd_delay_cost_usd` |
| 22 | YTD Delay Rate | `gold_flights_yearly.ytd_delay_rate` |
| 23 | YTD Flights | `gold_flights_yearly.ytd_total_flights` |
| 24 | carrier (cause count) | `gold_delay_causes.cause_count` |
| 25 | Weather (cause count) | `gold_delay_causes.cause_count` |
| 26 | NAS (cause count) | `gold_delay_causes.cause_count` |
| 27 | Security (cause count) | `gold_delay_causes.cause_count` |
| 28 | Late Aircraft (cause count) | `gold_delay_causes.cause_count` |
| 29 | delay rate % | `gold_flights_monthly.delay_rate` |
| 30 | Delay Counts | `gold_flights_monthly.total_delay_causes` |

### Mesures à CONSERVER en DAX léger

| # | Mesure | Raison |
|---|--------|--------|
| 1 | Display Month | Formatage texte |
| 2 | Delay Cost in 2025 | Formatage texte |
| 3 | Performance Status | SWITCH texte |
| 4 | Alert Status | SWITCH texte |
| 5 | MoM Change | Comparaison relative |
| 6 | MoM Change Display | Formatage texte |
| 7 | Delay Trend | IF texte |
| 8 | Airline Performance Rank | RANKX dynamique |
| 9 | Worst Airline This Month | TOPN dynamique |
| 10 | Worst Airport This Month | TOPN dynamique |
| 11 | Airline Delay Rate | SELECTEDVALUE contexte |
| 12 | Airline Delay Cost | SELECTEDVALUE contexte |
| 13 | Airline Cost Millions | Dérivé simple |
| 14 | Total Flights by Airline | ALLSELECTED |

### ⛔ MESURES À NE PAS TOUCHER (ML)

| Mesure | Raison |
|--------|--------|
| Predicted Delay Rate DEBUG | Utilise ml_predictions |
| Toute mesure référençant MLPredictions | Reste inchangée |

---

## 🚀 COMMANDES SQL POUR VÉRIFIER LES DONNÉES

Avant de migrer, vérifiez que les tables Gold ont des données :

```sql
-- Vérifier le nombre de lignes
SELECT 'gold_flights_monthly' as tbl, count() as rows FROM airline_data.gold_flights_monthly
UNION ALL
SELECT 'gold_flights_yearly', count() FROM airline_data.gold_flights_yearly
UNION ALL
SELECT 'gold_delay_causes', count() FROM airline_data.gold_delay_causes
UNION ALL
SELECT 'gold_airport_summary', count() FROM airline_data.gold_airport_summary;

-- Vérifier un échantillon de KPIs
SELECT 
    year, month, carrier_name,
    total_flights, total_delayed,
    round(delay_rate * 100, 2) as delay_pct,
    round(performance_score, 1) as perf_score
FROM airline_data.gold_flights_monthly
LIMIT 10;
```

---

**Document généré le 2026-02-01**
**Projet : Ynov Data Pipeline - Migration BI**
