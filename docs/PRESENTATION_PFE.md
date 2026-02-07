# ✈️ Airline Delay Prediction System
## Soutenance de Projet de Fin d'Études (PFE)

---

## 1. 🎯 Contexte & Objectif

### Le Problème
- Les retards aériens coûtent des milliards aux compagnies chaque année.
- Prédire ces retards permet d'optimiser la flotte et d'informer les passagers.

### La Mission
- Construire un **pipeline de données E2E** (End-to-End).
- Intégrer un modèle de **Machine Learning** fiable.
- Fournir une **interface temps-réel** pour les opérateurs.

---

## 2. 🏗️ Architecture Technique (Medallion)

### 🥉 Bronze (Raw)
- Ingestion brute depuis Kafka/CSV.
- Stockage : **ClickHouse** (Performance OLAP).

### 🥈 Silver (Cleaned)
- Nettoyage, typage, déduplication.
- Calcul du `delay_rate`.

### 🥇 Gold (Production Ready)
- **Gold BI** : Agrégats pour dashboards PowerBI.
- **Gold ML** : Feature Engineering complexe (lags, moyennes glissantes).

---

## 3. 🧠 Le Cœur ML (Machine Learning)

### Le Modèle
- **Algo** : XGBoost Classifier.
- **Performance** : ROC-AUC ~0.72 (Test).
- **Features** : 20 variables (Historique retards, Météo saisonnière, Trafic aéroport).

### Le Défi Technique Majeur 🔧
> **"L'enfer est dans les détails : Le Hash Mismatch"**

- **Problème** : ClickHouse utilisait `cityHash64()` pour mélanger les IDs. Python utilisait `hash()`.
- **Conséquence** : Le modèle en prod ne reconnaissait plus les aéroports (IDs différents).
- **Solution** : Implémentation de `CityHash64` en Python pour une parité binaire parfaite **Offline/Online**.

---

## 4. ⚡ Architecture Hybride & Scalable

![Architecture](https://mermaid.ink/img/pako:eNptkMFOwzAMhl_F8gktYxcO4LAJcQA0tBvcpC41W9uksZPEVVT13XHa0Q4Iic_299_2F9oZcyxoZ_hX91b9mD21LzSv54uB0dE4tK9wO_-8Xj9uP2C9hfsF3D_B4wzKEnZlDbut_4G2hNqS_0JdwG4bdlVDBxvhcAOnCjZlD6cyjms4l7ApRziVcFDD6xL25QCHMvYX8LyA_a7-Y6i_1d_O4LAF1bQ_fI5y-o-j6Xm0iY0ZJ5NMnI0zicbZONM4y8bZJNMsG2eTzLJsnE0y67JxjiSrdJzNMs_G2SLzYpxdIq_G2SXyZpxdIh_G2SXyY5xdIv_G2SXy47g_f0f7tO76B1v5hQE?type=png)

1. **Batch Layer (ClickHouse)** : Traite les pétaoctets de données historiques.
2. **Serving Layer (MongoDB)** : Sert les features en <10ms pour l'API.
3. **API (FastAPI)** : Interface entre le modèle et le monde réel.

---

## 5. 📱 Démonstration (Live Demo)

### Scénarios
1. **Single Prediction** : Analyse d'un vol spécifique (AA / ATL / Juillet 2026).
2. **Batch Processing** : Traitement de masse pour la planification.
3. **Alerting** : Détection des risques critiques.

---

## 6. 🚀 Conclusion & Avenir

### Résultats
✅ Pipeline Production-Ready.
✅ API Sécurisée et Documentée.
✅ Interface Utilisateur Moderne.

### Roadmap
- [ ] Ajouter la météo temps réel (API externe).
- [ ] Déployer sur Kubernetes (K8s) pour l'auto-scaling.
- [ ] Améliorer le modèle (Réduire l'overfitting).

### Merci de votre attention ! 
**Questions ?**
