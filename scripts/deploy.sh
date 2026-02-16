#!/bin/bash
set -e

# Secure Agent Deployment Script

echo "====================================="
echo "Secure Agent Deployment"
echo "====================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Docker
echo -e "${YELLOW}Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi
echo -e "${GREEN}Docker found${NC}"

# Check Docker Compose
echo -e "${YELLOW}Checking Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose first.${NC}"
    exit 1
fi
echo -e "${GREEN}Docker Compose found${NC}"

# Check .env file
echo -e "${YELLOW}Checking environment configuration...${NC}"
if [ ! -f .env ]; then
    echo -e "${YELLOW}.env file not found. Creating from example...${NC}"
    cp .env.example .env
    echo -e "${RED}Please edit .env with your configuration before running the system!${NC}"
    echo -e "${YELLOW}At minimum, set:${NC}"
    echo "  - REDIS_PASSWORD"
    echo "  - LITELM_MASTER_KEY"
    echo "  - Your LLM API keys"
    exit 1
fi
echo -e "${GREEN}.env file found${NC}"

# Validate environment
echo -e "${YELLOW}Validating environment variables...${NC}"
source .env

if [[ "$REDIS_PASSWORD" == *"change_this"* ]]; then
    echo -e "${RED}REDIS_PASSWORD is still set to default. Please change it in .env${NC}"
    exit 1
fi

if [[ "$LITELM_MASTER_KEY" == *"change_this"* ]]; then
    echo -e "${RED}LITELM_MASTER_KEY is still set to default. Please change it in .env${NC}"
    exit 1
fi
echo -e "${GREEN}Environment validated${NC}"

# Build images
echo -e "${YELLOW}Building Docker images...${NC}"
docker-compose build

# Start services
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo -e "${YELLOW}Waiting for services to start...${NC}"
sleep 5

# Health check
echo -e "${YELLOW}Running health check...${NC}"
if curl -s http://localhost:8080/health > /dev/null; then
    echo -e "${GREEN}System is healthy!${NC}"
else
    echo -e "${YELLOW}Gateway not responding yet. Check logs with 'docker-compose logs'${NC}"
fi

echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""
echo "Useful commands:"
echo "  View logs:        docker-compose logs -f"
echo "  Stop services:    docker-compose down"
echo "  Restart:          docker-compose restart"
echo "  Health check:     curl http://localhost:8080/health"
echo ""
