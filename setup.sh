#!/bin/bash
# OriGene One-Command Setup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}"
echo "=========================================="
echo "  OriGene One-Command Setup"
echo "=========================================="
echo -e "${NC}"

# Check prerequisites
echo -e "${YELLOW}[1/5] Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ docker-compose is not installed${NC}"
    echo "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker: $(docker --version)${NC}"
echo -e "${GREEN}✓ docker-compose: $(docker-compose --version)${NC}"

# Create necessary directories
echo -e "\n${YELLOW}[2/5] Creating required directories...${NC}"
mkdir -p logs cache
echo -e "${GREEN}✓ Created logs/ and cache/ directories${NC}"

# Check if configuration file exists
echo -e "\n${YELLOW}[3/5] Checking configuration file...${NC}"

if [ ! -f "src/local_deep_research/_settings/.secrets.toml" ]; then
    echo -e "${RED}❌ Configuration file not found${NC}"
    echo -e "${BLUE}Config file: src/local_deep_research/_settings/.secrets.toml${NC}"
    echo ""
    echo -e "${RED}Important: Please edit the configuration file and fill in your API keys${NC}"
    echo ""
    echo "Required API keys:"
    echo "  - SiliconFlow (text embedding): https://siliconflow.cn/"
    echo "  - Volcano Engine (template embedding): https://www.volcengine.com/"
    echo "  - OpenAI/DeepSeek/CloseAI (LLM inference, choose one)"
    echo ""
    echo -e "${YELLOW}After configuration, please re-run this script${NC}"
    echo ""
    echo "Open the config file with your editor:"
    echo "  nano src/local_deep_research/_settings/.secrets.toml"
    echo "  vim src/local_deep_research/_settings/.secrets.toml"
    echo "  code src/local_deep_research/_settings/.secrets.toml"
    exit 1
else
    echo -e "${GREEN}✓ Configuration file found${NC}"
    
    # Check for placeholder values
    if grep -q "your-.*-api-key-here" "src/local_deep_research/_settings/.secrets.toml"; then
        echo -e "${RED}⚠️  Warning: Configuration contains placeholder values, please fill in real API keys${NC}"
        echo -e "${YELLOW}Continue building? (y/N)${NC}"
        read -r response
        if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
            echo "Cancelled"
            exit 0
        fi
    fi
fi

# Build Docker image
echo -e "\n${YELLOW}[4/5] Building Docker image...${NC}"
echo "This may take 5-10 minutes, please wait..."
docker-compose build

echo -e "${GREEN}✓ Docker image built successfully${NC}"

# Run environment check
echo -e "\n${YELLOW}[5/5] Running environment checks...${NC}"
docker-compose run --rm origene python -m local_deep_research.test.check_all

# Success message
echo ""
echo -e "${GREEN}=========================================="
echo "  🎉 Setup complete!"
echo "==========================================${NC}"
echo ""
echo "You can now start using OriGene!"
echo ""
echo -e "${BLUE}Quick start commands:${NC}"
echo ""
echo "  # Interactive mode"
echo "  make start"
echo "  # or"
echo "  docker-compose run --rm origene"
echo ""
echo "  # Quick research"
echo "  make quick QUERY=\"What are therapeutic targets for Alzheimer's disease?\""
echo ""
echo "  # Detailed research"
echo "  make detailed QUERY=\"Analyze molecular mechanisms of EGFR in lung cancer\""
echo ""
echo -e "${BLUE}See all commands:${NC}"
echo "  make help"
echo ""
echo -e "${BLUE}Documentation:${NC}"
echo "  - README.md"
echo ""
echo -e "${GREEN}Enjoy using OriGene!${NC}"
