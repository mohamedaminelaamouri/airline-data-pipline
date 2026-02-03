.PHONY: help install start stop logs load-data init-db clean

help:
	@echo "Targets:"
	@echo "  install           Install Python dependencies"
	@echo "  start             Start Docker services"
	@echo "  stop              Stop Docker services"
	@echo "  logs              View logs (all services)"
	@echo "  init-db           Initialize ClickHouse tables"
	@echo "  load-data         Load historical data"
	@echo "  clean             Remove Docker volumes"

install:
	pip install -r requirements.txt
	pip install -r requirements-streamlit.txt
	cd backend && pip install -r requirements.txt

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

clean:
	docker compose down -v

streamlit:
	$(PYTHON) -m streamlit run visualization/realtime_app.py --server.port 8501 --server.address 0.0.0.0

clean:
	rm -rf .venv .venv-consumer .pytest_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -f logs/*.log

clean-docker:
	docker compose down
