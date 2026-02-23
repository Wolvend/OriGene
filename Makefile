# OriGene Makefile - Simplified Docker commands

.PHONY: help build start check test clean config

# Default target
help:
	@echo "OriGene Docker Management Commands"
	@echo "==================================="
	@echo ""
	@echo "Setup & Configuration:"
	@echo "  make config         - Create configuration from template"
	@echo "  make build          - Build Docker image"
	@echo "  make check          - Run environment checks"
	@echo "  make test           - Run Docker tests"
	@echo ""
	@echo "Running OriGene:"
	@echo "  make start          - Start interactive mode"
	@echo "  make quick QUERY=\"your question\"  - Run quick research"
	@echo "  make detailed QUERY=\"your question\" - Run detailed research"
	@echo ""
	@echo "Testing & Validation:"
	@echo "  make test-mcp       - Test MCP connection"
	@echo "  make test-config    - Test configuration"
	@echo "  make test-deps      - Test dependencies"
	@echo "  make test-e2e       - Run end-to-end test"
	@echo ""
	@echo "Benchmarks:"
	@echo "  make benchmark      - Run benchmark evaluation"
	@echo "  make score-trqa     - Score TRQA benchmark"
	@echo "  make score-gpqa     - Score GPQA benchmark"
	@echo "  make score-dbqa     - Score DbQA benchmark"
	@echo ""
	@echo "Maintenance:"
	@echo "  make logs           - View container logs"
	@echo "  make shell          - Open shell in container"
	@echo "  make clean          - Remove containers and volumes"
	@echo "  make clean-all      - Remove everything including images"
	@echo ""

# Configuration
config:
	@if [ ! -f "src/local_deep_research/_settings/.secrets.toml" ]; then \
		echo "❌ Configuration file not found: src/local_deep_research/_settings/.secrets.toml"; \
		echo "⚠️  Please edit this file and add your API keys"; \
	else \
		echo "✓ Configuration file already exists"; \
	fi

# Build
build:
	@echo "Building OriGene Docker image..."
	docker-compose build

# Check environment
check:
	@./docker-check.sh

# Test
test:
	@./docker-test.sh

# Start interactive mode
start:
	docker-compose run --rm origene

# Quick research
quick:
	@if [ -z "$(QUERY)" ]; then \
		echo "Error: Please provide a QUERY"; \
		echo "Usage: make quick QUERY=\"your research question\""; \
		exit 1; \
	fi
	docker-compose run --rm origene python -m local_deep_research.main "$(QUERY)" --mode quick

# Detailed research
detailed:
	@if [ -z "$(QUERY)" ]; then \
		echo "Error: Please provide a QUERY"; \
		echo "Usage: make detailed QUERY=\"your research question\""; \
		exit 1; \
	fi
	docker-compose run --rm origene python -m local_deep_research.main "$(QUERY)" --mode detailed

# Individual checks
test-deps:
	docker-compose run --rm origene python -m local_deep_research.test.check_deps

test-config:
	docker-compose run --rm origene python -m local_deep_research.test.check_config

test-mcp:
	docker-compose run --rm origene python -m local_deep_research.test.check_mcp

test-modules:
	docker-compose run --rm origene python -m local_deep_research.test.check_modules

test-e2e:
	docker-compose run --rm origene python -m local_deep_research.test.test_example

# Benchmarks
benchmark:
	docker-compose run --rm origene python -m local_deep_research.evaluate_local

score-trqa:
	docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
		--agent_results benchmark/TRQA_lit_choice/agent_answers_test.txt \
		--original_data benchmark/TRQA_lit_choice/TRQA-lit-choice-172-coreset.csv \
		--model_name "OriAgent"

score-gpqa:
	docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
		--agent_results benchmark/GPQA/agent_answers_test.txt \
		--original_data benchmark/GPQA/GPQA-lit-choice.csv \
		--model_name "OriAgent"

score-dbqa:
	docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
		--agent_results benchmark/DbQA/agent_answers_testv2.txt \
		--original_data benchmark/DbQA/DbQA.csv \
		--model_name "OriAgent"

# Maintenance
logs:
	docker-compose logs origene

shell:
	docker-compose run --rm origene bash

clean:
	docker-compose down -v
	@echo "Containers and volumes removed"

clean-all:
	docker-compose down -v --rmi all
	@echo "Containers, volumes, and images removed"

# Directory setup
dirs:
	@mkdir -p logs cache
	@echo "✓ Created logs/ and cache/ directories"
