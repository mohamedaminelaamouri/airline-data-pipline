.PHONY: help install start stop logs load-data init-db clean clean-docker

help:
	@echo "Targets:"
	@echo "  install           Install Python dependencies"
	@echo "  start             Start Docker services"
	@echo "  stop              Stop Docker services"
	@echo "  logs              View logs (all services)"
	@echo "  init-db           Initialize ClickHouse tables"
	@echo "  load-data         Load historical data"
	@echo "  pipeline          Run Medallion pipeline"
	@echo "  train             Train ML model"
	@echo "  clean             Remove cache files"
	@echo "  clean-docker      Remove Docker volumes"

install:
	pip install -r requirements.txt
	pip install -r requirements-ml-api.txt

start:
	docker compose up -d

stop:
	docker compose down

logs:
	docker compose logs -f

init-db:
	docker exec clickhouse clickhouse-client --query "$$(cat config/clickhouse/init.sql)"

load-data:
	python scripts/load_historical_data.py

pipeline:
	python scripts/medallion_pipeline.py

train:
	python scripts/train_model_production.py

monitor:
	python realtime_app.py

clean:
	rm -rf .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -f logs/*.log

clean-docker:
	docker compose down -v
