.PHONY: dev install lint test

install:
	pip install -r requirements.txt

dev:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-debug:
	LOG_LEVEL=debug uvicorn main:app --reload --host 0.0.0.0 --port 8000

lint:
	ruff check app/

test:
	pytest tests/ -v

docker-build:
	docker build -t genai-backend .

docker-run:
	docker run -p 8000:8000 --env-file .env genai-backend
