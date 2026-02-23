#!/bin/bash
# OriGene Docker End-to-End Test Script

set -e

echo "=========================================="
echo "  OriGene Docker E2E Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${YELLOW}Running: ${test_name}${NC}"
    
    if eval "$test_command"; then
        echo -e "${GREEN}✓ PASSED: ${test_name}${NC}\n"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗ FAILED: ${test_name}${NC}\n"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Ensure we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Error: Dockerfile not found. Please run this script from the OriGene root directory.${NC}"
    exit 1
fi

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose is not installed${NC}"
    exit 1
fi

if [ ! -f "src/local_deep_research/_settings/.secrets.toml" ]; then
    echo -e "${RED}Error: Configuration file not found${NC}"
    echo "Please configure your API keys in: src/local_deep_research/_settings/.secrets.toml"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}\n"

# Test 1: Docker build
run_test "Docker Build" "docker-compose build --quiet origene"

# Test 2: Container start
run_test "Container Health" "docker-compose run --rm origene python -c 'import sys; sys.exit(0)'"

# Test 3: Python version check
run_test "Python Version Check" \
    "docker-compose run --rm origene python --version | grep -q '3.13'"

# Test 4: Dependency check
run_test "Dependency Check" \
    "docker-compose run --rm origene python -m local_deep_research.test.check_deps"

# Test 5: Module import check
run_test "Module Import Check" \
    "docker-compose run --rm origene python -m local_deep_research.test.check_modules"

# Test 6: Configuration file accessibility
run_test "Configuration File Check" \
    "docker-compose run --rm origene python -c 'from pathlib import Path; assert Path(\"/app/src/local_deep_research/_settings/.secrets.toml\").exists()'"

# Test 7: Volume mounts
run_test "Volume Mount Check" \
    "docker-compose run --rm origene bash -c 'test -d /app/logs && test -d /app/cache'"

# Test 8: CLI help
run_test "CLI Help Command" \
    "docker-compose run --rm origene python -m local_deep_research.main --help 2>&1 | grep -q 'Research mode'"


# Summary
echo "=========================================="
echo "  Test Summary"
echo "=========================================="
echo -e "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: ${TESTS_PASSED}${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed: ${TESTS_FAILED}${NC}"
    echo ""
    echo -e "${RED}Some tests failed. Please review the errors above.${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Your Docker setup is working correctly."
    echo ""
    echo "Next steps:"
    echo "1. Configure your API keys in src/local_deep_research/_settings/.secrets.toml"
    echo "2. Run full environment check: ./docker-check.sh"
    echo "3. Start using OriGene: docker-compose run --rm origene"
fi
