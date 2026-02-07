# 🚀 Guide de Déploiement - Airline Delay Prediction

Ce guide permet d'installer et exécuter le projet sur une **nouvelle machine** en moins de 10 minutes.

---

## 📋 Prérequis

### Logiciels Requis
| Logiciel | Version Min. | Téléchargement |
|----------|--------------|----------------|
| **Docker Desktop** | 4.0+ | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| **Git** | 2.30+ | [git-scm.com](https://git-scm.com/) |

### Configuration Requise
- **RAM** : 8 GB minimum (16 GB recommandé)
- **Disque** : 10 GB d'espace libre
- **Ports libres** : 3005, 8001, 8080, 8123, 8501, 9092, 27017

---

## 🔧 Installation (5 minutes)

### Étape 1 : Cloner le Repository
```bash
git clone https://github.com/VOTRE_USERNAME/ynov-data-pipeline.git
cd ynov-data-pipeline
```

### Étape 2 : Lancer Docker Desktop
1. Ouvrir **Docker Desktop**
2. Attendre que le moteur Docker soit "Running" (icône verte)

### Étape 3 : Démarrer les Services
```bash
docker compose up -d
```

> ⏱️ **Première exécution** : ~3-5 minutes (téléchargement des images + installation des dépendances)

---

## ✅ Vérification (1 minute)

### Vérifier que tous les conteneurs tournent
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

**Résultat attendu :**
```
NAMES                STATUS
ml-api               Up X minutes (healthy)
ml-platform-ui       Up X minutes
mongodb              Up X minutes (healthy)
clickhouse           Up X minutes (healthy)
kafka                Up X minutes (healthy)
zookeeper            Up X minutes (healthy)
nifi                 Up X minutes
streamlit-realtime   Up X minutes
```

### Tester l'API
```bash
curl http://localhost:8001/health
```
**Résultat attendu :** `{"status":"ok"}`

---

## 🌐 URLs de l'Application

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend React** | http://localhost:3005 | Interface de prédiction principale |
| **API Documentation** | http://localhost:8001/docs | Swagger UI (FastAPI) |
| **Streamlit Dashboard** | http://localhost:8501 | Monitoring temps réel |
| **Apache NiFi** | http://localhost:8080 | Gestion des flux de données |
| **ClickHouse** | http://localhost:8123 | Base de données OLAP |

---

## 🎯 Scénario de Démonstration

### 1. Ouvrir le Frontend
1. Aller sur http://localhost:3005
2. Naviguer vers l'onglet **"Prediction"**

### 2. Tester une Prédiction Simple
- **Carrier** : `AA` (American Airlines)
- **Airport** : `ATL` (Atlanta)
- **Mois** : `7` (Juillet)
- **Année** : `2026`
- Cliquer sur **"Predict Delay"**

### 3. Résultat Attendu
- Risk Category : `critical` ou `high`
- Probabilité : ~0.78

### 4. Tester la Batch Prediction
- Basculer sur l'onglet "Batch"
- Soumettre plusieurs vols simultanément

---

## 🛑 Arrêter les Services

```bash
docker compose down
```

Pour un arrêt complet avec suppression des données :
```bash
docker compose down -v
```

---

## 🔥 Dépannage Rapide

### Problème : L'API ne répond pas
```bash
# Vérifier les logs
docker logs ml-api --tail 50
```

### Problème : Port déjà utilisé
```bash
# Trouver le processus qui utilise le port (exemple: 8001)
netstat -ano | findstr :8001
# Tuer le processus
taskkill /PID <PID> /F
```

### Problème : Conteneur qui redémarre en boucle
```bash
# Forcer la reconstruction
docker compose down
docker compose up -d --build
```

### Problème : Pas assez de mémoire
1. Ouvrir Docker Desktop → Settings → Resources
2. Augmenter Memory à 8 GB minimum
3. Redémarrer Docker Desktop

---

## 📁 Structure du Projet

```
ynov-data-pipeline/
├── ml_api/              # API FastAPI (Backend)
├── ml_platform_ui/      # Interface React (Frontend)
├── ml/                  # Modèles ML et training
├── scripts/             # Scripts de pipeline de données
├── data/                # Données historiques
├── docker-compose.yml   # Configuration Docker
└── docs/                # Documentation
```

---

## 👨‍💻 Identifiants par Défaut

| Service | Login | Mot de passe |
|---------|-------|--------------|
| NiFi | admin | adminadminadmin |

---

**Bonne présentation ! 🎓**
