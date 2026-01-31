.PHONY: help venv install consumer cache streamlit ml-train ml-train-verbose ml-predict ml-install clean clean-docker

PY?=python3
VENV?=.venv
PYTHON:=$(shell if [ -x "$(VENV)/bin/python" ]; then echo "$(VENV)/bin/python"; else echo "$(PY)"; fi)

help:
	@echo "Targets:"
	@echo "  venv              Create local virtualenv (.venv)"
	@echo "  install           Install python dependencies"
	@echo "  ml-install        Install ML dependencies (yno-ml)"
	@echo "  consumer          Run Kafka->ClickHouse consumer (Script 1)"
	@echo "  cache             Run ClickHouse->MongoDB cache service (Script 2)"
	@echo "  ml-train          Run ML training pipeline (Script 3)"
	@echo "  ml-train-verbose  Run ML training with detailed logs"
	@echo "  ml-predict        Generate demo predictions (batch)"
	@echo "  streamlit         Run real-time Streamlit dashboard"
	@echo "  clean             Remove local envs/caches/logs"
	@echo "  clean-docker      Stop stack (keeps volumes)"

venv:
	$(PY) -m venv $(VENV)
	@echo "Activate with: source $(VENV)/bin/activate"

install:
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

ml-install:
	@echo "📦 Installing ML dependencies..."
	$(VENV)/bin/pip install -r yno-ml/requirements.txt
	@echo "✅ ML dependencies installed"

consumer:
	$(PYTHON) scripts/kafka_to_clickhouse.py

cache:
	$(PYTHON) scripts/clickhouse_to_mongodb.py

ml-train:
	@echo "🧠 Training ML model..."
	$(PYTHON) scripts/ml_training_pipeline.py --skip-predictions

ml-train-verbose:
	@echo "🧠 Training ML model (verbose logging)..."
	$(PYTHON) scripts/ml_training_pipeline.py --skip-predictions 2>&1 | tee logs/ml_train_$$(date +%Y%m%d_%H%M%S).log

ml-predict:
	@echo "🔮 Generating demo predictions..."
	$(PYTHON) scripts/batch_predictions_demo.py

streamlit:
	$(PYTHON) -m streamlit run visualization/realtime_app.py --server.port 8501 --server.address 0.0.0.0

clean:
	rm -rf .venv .venv-consumer .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -f logs/*.log

clean-docker:
	docker compose down
