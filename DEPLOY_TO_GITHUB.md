# 🚀 Déployer vers Nouveau Repo GitHub

## Étapes Rapides

### 1️⃣ Créer le Repo sur GitHub

**Option A: Via Interface Web** (recommandé)
1. Aller sur https://github.com/new
2. **Repository name:** `airline-delay-prediction` (ou autre nom)
3. **Description:** `Real-time airline delay prediction pipeline with ML (NiFi, Kafka, ClickHouse, MongoDB, XGBoost)`
4. **Visibility:** Public ou Private
5. ✅ **NE PAS** cocher "Initialize with README" (vous avez déjà un README)
6. ✅ **NE PAS** ajouter .gitignore (vous en avez déjà un)
7. Cliquer **"Create repository"**

**Option B: Via GitHub CLI**
```bash
# Installer GitHub CLI: https://cli.github.com/
gh auth login
gh repo create airline-delay-prediction --public --source=. --remote=origin
```

---

### 2️⃣ Ajouter le Remote et Pousser

**Une fois le repo créé sur GitHub, copier l'URL puis:**

```powershell
# Ajouter le remote (remplacer YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/airline-delay-prediction.git

# Vérifier
git remote -v

# Pousser vers GitHub
git push -u origin main
```

**Exemple complet:**
```powershell
# Si votre username GitHub est "johndoe"
git remote add origin https://github.com/johndoe/airline-delay-prediction.git
git branch -M main
git push -u origin main
```

---

### 3️⃣ Vérifier le Push

Aller sur: `https://github.com/YOUR_USERNAME/airline-delay-prediction`

Vous devriez voir:
- ✅ 58 fichiers
- ✅ README.md affiché
- ✅ Documentation dans `/docs`
- ✅ Scripts dans `/scripts`

---

## 📊 Statistiques du Projet

```
58 files
664,171 lines of code
Components:
├─ Docker services: 7 (Zookeeper, Kafka, NiFi, ClickHouse, MongoDB, Kafka-UI, Streamlit)
├─ Python scripts: 8 (3 main pipelines + 5 ML utilities)
├─ Documentation: 9 files (3000+ lines)
├─ ML module: 15 files (yno-ml/)
└─ Data: 348K+ records (2003-2025)
```

---

## 🎯 Prochaines Étapes (Scénario A)

Après avoir poussé sur GitHub:

### Phase 1: Architecture Médaillon ClickHouse
- [ ] Créer tables Bronze/Silver/Gold
- [ ] Migrer script Kafka → Bronze
- [ ] Créer script Bronze → Silver
- [ ] Supprimer MongoDB cache (remplacer par vues matérialisées)

### Phase 2: App Web Interactive
- [ ] Backend FastAPI (API REST)
- [ ] Frontend React/Vue
- [ ] MongoDB pour ML artifacts uniquement
- [ ] Real-time scoring endpoint

### Phase 3: Production-Ready Features
- [ ] Tests unitaires (pytest)
- [ ] CI/CD (GitHub Actions)
- [ ] Monitoring (Prometheus + Grafana)
- [ ] Logging centralisé (Loki)
- [ ] Security (Vault, SSL)

---

## 🔧 Commandes Utiles

```powershell
# Voir les remotes
git remote -v

# Changer l'URL si erreur
git remote set-url origin https://github.com/NOUVEAU_USERNAME/NOUVEAU_REPO.git

# Pousser une branche spécifique
git push origin main

# Forcer le push (attention!)
git push -f origin main

# Cloner ailleurs pour tester
git clone https://github.com/YOUR_USERNAME/airline-delay-prediction.git test-clone
cd test-clone
docker compose up -d
```

---

## 📝 Description GitHub Suggérée

**Title:** Airline Delay Prediction - Real-Time ML Pipeline

**Description:**
```
🛫 Production-ready data pipeline for airline delay prediction using modern data engineering stack

🏗️ Architecture:
• NiFi → Kafka → ClickHouse → MongoDB → Streamlit
• XGBoost ML model (ROC-AUC 0.738, 348K records)
• Real-time streaming + Batch ML training
• Docker-compose orchestration

📊 Features:
• 3 core scripts (Kafka consumer, Cache service, ML training)
• Real-time dashboard (Streamlit)
• Comprehensive documentation (3000+ lines)
• Ready for Power BI integration

🚀 Tech Stack:
• Data: NiFi, Kafka, ClickHouse, MongoDB
• ML: XGBoost, scikit-learn, pandas
• Viz: Streamlit, Plotly
• Infra: Docker, Python 3.11

⭐ Perfect for:
• Data Engineering portfolio
• ML Engineering showcase
• Real-time analytics demos
```

**Topics (tags):**
```
data-engineering, machine-learning, kafka, clickhouse, mongodb, 
nifi, xgboost, streamlit, docker, real-time-analytics, 
airline-industry, mlops, data-pipeline
```

---

## 🎨 Badge Suggestions

Ajouter au README.md:

```markdown
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Docker](https://img.shields.io/badge/docker-compose-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-brightgreen.svg)
```

---

## ⚠️ Notes Importantes

### Fichiers à NE PAS commiter (déjà dans .gitignore):
- ✅ `.env` (credentials)
- ✅ `models/ml_runs/*` (modèles ML lourds)
- ✅ `logs/*.log` (logs temporaires)
- ✅ `data/processed/*` (données générées)
- ✅ `__pycache__/` (cache Python)

### Si besoin de credentials:
Créer `.env.example` (déjà fait) et documenter dans README.

---

## 🆘 En Cas de Problème

### Erreur: "remote origin already exists"
```powershell
git remote remove origin
git remote add origin https://github.com/YOUR_USERNAME/NEW_REPO.git
```

### Erreur: "Authentication failed"
```powershell
# Utiliser Personal Access Token au lieu du mot de passe
# Créer token sur: https://github.com/settings/tokens
# Lors du push, utiliser le token comme mot de passe
```

### Erreur: "Large files"
```powershell
# Vérifier les gros fichiers
git ls-files -s | awk '$4 > 100000000 {print $4, $5}'

# Si besoin, utiliser Git LFS
git lfs install
git lfs track "*.csv"
git add .gitattributes
git commit -m "Add Git LFS"
```

---

Bon push ! 🚀
