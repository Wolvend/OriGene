#!/bin/bash
# OriGene Docker Quick Start Script

set -e

echo "=========================================="
echo "  OriGene Docker Deployment Script"
echo "=========================================="
echo ""

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker compose (v2+) or docker-compose (v1) is installed
# Prefer docker compose (v2) as it's newer and better maintained
COMPOSE_CMD=""
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Error: Docker Compose is not installed"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Check if .secrets.toml exists
if [ ! -f "src/local_deep_research/_settings/.secrets.toml" ]; then
    echo "⚠️  Warning: Configuration file not found"
    echo ""
    echo "Please edit the configuration file and add your API keys:"
    echo "  nano src/local_deep_research/_settings/.secrets.toml"
    echo ""
    exit 1
fi

# Create necessary directories
mkdir -p logs cache

echo "✓ Prerequisites check passed"
echo "✓ Using: $COMPOSE_CMD"
echo ""
echo "Building Docker image..."
$COMPOSE_CMD build

echo ""
echo "=========================================="
echo "  Build completed successfully!"
echo "=========================================="
echo ""
echo "Available commands:"
echo ""
echo "1. Run environment check:"
echo "   $COMPOSE_CMD run --rm origene python -m local_deep_research.test.check_all"
echo ""
echo "2. Run interactive mode:"
echo "   $COMPOSE_CMD run --rm origene"
echo ""
echo "3. Run quick research (CLI):"
echo "   $COMPOSE_CMD run --rm origene python -m local_deep_research.main \"your query here\" --mode quick"
echo ""
echo "4. Run detailed research (CLI):"
echo "   $COMPOSE_CMD run --rm origene python -m local_deep_research.main \"your query here\" --mode detailed"
echo ""
echo "5. Run end-to-end test:"
echo "   $COMPOSE_CMD run --rm origene python -m local_deep_research.test.test_example"
echo ""
echo "=========================================="
echo ""
echo "First-time users should run environment check (option 1)"
echo ""
