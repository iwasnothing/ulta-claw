#!/bin/bash
# Health check script for Secure Agent

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "Secure Agent Health Check"
echo "=========================="
echo ""

# Function to check service health
check_service() {
    local service=$1
    local check_command=$2

    echo -n "Checking $service... "

    if eval "$check_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

# Check services
echo "Services:"
check_service "Redis" "docker-compose exec redis redis-cli -a \$REDIS_PASSWORD ping" || true
check_service "Squid" "docker-compose exec squid squid -k check" || true
check_service "LiteLLM" "curl -s http://localhost:4000/health" || true
check_service "Gateway" "curl -s http://localhost:8080/health" || true
check_service "Agent" "docker-compose ps agent | grep -q 'Up'" || true

echo ""
echo "Details:"
echo "--------"

# Redis details
echo -n "Redis queue length: "
if docker-compose exec redis redis-cli -a $REDIS_PASSWORD llen agent:queue 2>/dev/null; then
    :
else
    echo "N/A"
fi

# Gateway health
echo ""
echo "Gateway status:"
curl -s http://localhost:8080/health 2>/dev/null || echo "  Gateway not responding"

echo ""
echo "Docker containers:"
docker-compose ps
