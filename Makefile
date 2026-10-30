.PHONY: install dev run test

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt

dev:
	.venv/bin/uvicorn app.main:app --reload

test:
	.venv/bin/pytest tests/ -v

run:
	.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
