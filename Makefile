.PHONY: install dev run docker-up docker-down

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

dev:
	.venv/bin/uvicorn app.main:app --reload

run:
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
