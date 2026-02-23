#!/bin/bash
# OriGene Docker Environment Check Script

echo "=========================================="
echo "  OriGene Environment Check (Docker)"
echo "=========================================="
echo ""

# Check Docker installation
if ! command -v docker &> /dev/null; then
    echo "❌ Docker: Not installed"
    echo "   Install from: https://docs.docker.com/get-docker/"
    exit 1
else
    DOCKER_VERSION=$(docker --version)
    echo "✓ Docker: $DOCKER_VERSION"
fi

# Check docker-compose installation
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose: Not installed"
    echo "   Install from: https://docs.docker.com/compose/install/"
    exit 1
else
    COMPOSE_VERSION=$(docker-compose --version)
    echo "✓ docker-compose: $COMPOSE_VERSION"
fi

# Check configuration file
if [ -f "src/local_deep_research/_settings/.secrets.toml" ]; then
    echo "✓ Configuration file: Found"
    
    # Basic validation of configuration
    if grep -q "your-.*-api-key-here" "src/local_deep_research/_settings/.secrets.toml"; then
        echo "⚠️  Warning: Configuration contains placeholder values"
        echo "   Please update your API keys in .secrets.toml"
    fi
else
    echo "❌ Configuration file: Not found"
    echo "   Please edit: src/local_deep_research/_settings/.secrets.toml"
    exit 1
fi

# Check directories
mkdir -p logs cache
echo "✓ Log directory: logs/"
echo "✓ Cache directory: cache/"

echo ""
echo "=========================================="
echo "  Running container environment check..."
echo "=========================================="
echo ""

# Build and run check
docker-compose build --quiet origene
docker-compose run --rm origene python -m local_deep_research.test.check_all

echo ""
echo "=========================================="
echo "  Check completed!"
echo "=========================================="
