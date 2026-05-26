.PHONY: help up down build logs restart clean ingest-kb test lint

# ── Default ──
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Docker ──
up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

build: ## Build all containers
	docker compose build

logs: ## Tail logs for all services
	docker compose logs -f

restart: ## Restart all services
	docker compose restart

clean: ## Remove all containers, volumes, and images
	docker compose down -v --rmi local

# ── Database ──
db-migrate: ## Run database migrations
	docker compose exec postgres psql -U voiceai -d voiceai -f /docker-entrypoint-initdb.d/001_initial.sql

db-shell: ## Open PostgreSQL shell
	docker compose exec postgres psql -U voiceai -d voiceai

redis-shell: ## Open Redis CLI
	docker compose exec redis redis-cli

# ── AI Brain ──
ingest-kb: ## Ingest knowledge base documents into vector DB
	docker compose exec ai-brain python -m knowledge_ingestion --dir /app/knowledge-base

# ── Testing ──
test: ## Run all tests
	cd services/ai-brain && python -m pytest tests/ -v
	cd services/auth-service && python -m pytest tests/ -v
	cd services/ticket-service && python -m pytest tests/ -v

test-load: ## Run load tests with Locust
	cd tests/load && locust -f locustfile.py

# ── Linting ──
lint: ## Lint all Python code
	ruff check services/ shared/
	ruff format --check services/ shared/

lint-fix: ## Fix linting issues
	ruff check --fix services/ shared/
	ruff format services/ shared/

# ── Frontend ──
fe-dev: ## Start frontend dev server
	cd frontend/dashboard && npm run dev

fe-build: ## Build frontend for production
	cd frontend/dashboard && npm run build

fe-install: ## Install frontend dependencies
	cd frontend/dashboard && npm install
