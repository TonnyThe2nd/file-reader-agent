.PHONY: install api test lint clean

install:
	pip install -r requirements.txt

api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	python -m pytest -v

lint:
	ruff check app tests

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
