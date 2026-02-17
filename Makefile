.PHONY: help build up down restart logs test clean setup install-cli install-gateway

help:
	@echo "Secure Agent Architecture - Available Commands:"
	@echo "  make setup      - Setup environment files"
	@echo "  make build      - Build all Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make logs       - View logs"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Remove all containers and volumes"
	@echo "  make install-cli - Install CLI dependencies"
	@echo "  make install-gateway - Build gateway locally"

setup:
	@echo "Creating .env file from template..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env file - please edit with your values!"; \
	else \
		echo ".env file already exists"; \
	fi

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

test:
	@echo "Running health check..."
	docker-compose exec gateway curl -s http://localhost:8080/health || echo "Gateway not ready yet"

clean:
	docker-compose down -v
	docker system prune -f

install-cli:
	@echo "Installing CLI dependencies..."
	cd cli && pip install -r requirements.txt

install-gateway:
	@echo "Building gateway for ARM64..."
	ARCH="aarch64-unknown-linux-gnu" docker-compose build gateway

# Development targets
dev-gateway:
	cd gateway && cargo run

dev-agent:
	cd agent && python -m agent.main

# Security checks
security-check:
	@echo "Checking for exposed credentials..."
	@grep -r "password.*=" config/ 2>/dev/null | grep -v ".example" | grep -v "\$$" && echo "WARNING: Hardcoded passwords found!" || echo "No hardcoded passwords found"
	@echo "Checking for exposed API keys..."
	@grep -r "api_key.*=" config/ 2>/dev/null | grep -v ".example" | grep -v "\$$" && echo "WARNING: Hardcoded API keys found!" || echo "No hardcoded API keys found"
