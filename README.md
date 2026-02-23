# OriGene: A Self-Evolving Virtual Disease Biologist Automating Therapeutic Target Discovery

> **Important**: This is the OriGene, an open‑source, self-evolving multi-agent system that acts as a virtual disease biologist.
> We also introduce the TRQA Benchmark — a benchmark of 1,921 expert-level questions for evaluating biomedical AI agents.


## What's New
1.**Public online Launch** – OriGene is now live and available to try at https://origene.lglab.ac.cn/.

2.**Open‑Source Release** – The entire OriGene codebase and benchmark is now available, Fork away!

3.Officially presented at the 2025 World Artificial Intelligence Conference (**WAIC**).


## 1. OriGene Overview
Therapeutic target discovery remains one of the most critical yet intuition-driven stages in drug development. We present **OriGene**, a self-evolving multi-agent system that functions as a virtual disease biologist to 
identify and prioritize therapeutic targets at scale. 


## 2. Getting Started

Running OriGene requires two components: the **MCP Server** (OrigeneMCP) and the **OriGene agent** itself. We recommend setting up the MCP Server first, then configuring and running OriGene.

### Step 1: Deploy the MCP Server

OriGene relies on the MCP Server (OrigeneMCP), which aggregates more than 600 bioinformatics tools. The MCP server provides access to multiple databases including ChEMBL, PubChem, FDA, OpenTargets, NCBI, UniProt, PDB, Ensembl, UCSC, KEGG, STRING, TCGA, Monarch, ClinicalTrials, and more.

**Step-by-step deployment:**

a. **Clone the OrigeneMCP repository:**
```bash
git clone https://github.com/GENTEL-lab/OrigeneMCP.git
cd OrigeneMCP
```

b. **Install dependencies (requires `uv` package manager):**
```bash
# Install uv if you haven't already
pip install uv

# Create virtual environment
uv venv .venv --python=3.13
source .venv/bin/activate

# Install dependencies
uv sync
```

c. **Deploy the MCP service:**
```bash
# Copy configuration file
cp default.conf.toml local.conf.toml

# (Optional) Configure API keys in local.conf.toml if you need:
# - Tavily search: get your API key from https://tavily.com/
# - Jina search: get your API key from https://jina.ai/

# Deploy the service
export PYTHONPATH=`fab pypath`
uv run -m deploy.web
```

**Note:** 
- The MCP server runs on port **8789** by default. If this port is occupied, modify the port in `local.conf.toml`.
- Keep the MCP server running in a separate terminal while using OriGene.
- The server endpoint will be `http://127.0.0.1:8789` (or your custom port).

For more detailed information about OrigeneMCP deployment and usage, please refer to the [OrigeneMCP repository](https://github.com/GENTEL-lab/OrigeneMCP.git).

---

### Step 2: Configure and Run OriGene

Both deployment methods require configuring API keys. Edit the configuration file `src/local_deep_research/_settings/.secrets.toml` and fill in your actual API keys and MCP server URL.

OriGene is model-agnostic, so you can freely switch between different base models.

**Note**: For LLM inference, you can configure either OpenAI/DeepSeek APIs or use CloseAI as a fallback. If OpenAI or DeepSeek is not configured, CloseAI will automatically be used instead. You can also configure all three if desired.

#### API Key Configuration

> **Important**: All third-party API keys must be obtained directly from the respective service providers. This project does not provide any API keys. Users are responsible for managing their own API credentials and complying with each provider's terms of service.

| Service | Purpose | Registration |
|---------|---------|--------------|
| **SiliconFlow** | Text embedding | [siliconflow.cn](https://siliconflow.cn/) |
| **Volcano Engine** | Template embedding | [volcengine.com](https://www.volcengine.com/) |
| **OpenAI** | LLM inference | [openai.com](https://openai.com/) |
| **DeepSeek** | Reasoning model | [platform.deepseek.com](https://platform.deepseek.com/) |
| **CloseAI** | LLM inference (fallback for OpenAI/DeepSeek) | [closeai-asia.com](https://www.closeai-asia.com/) |

Configuration template (`src/local_deep_research/_settings/.secrets.toml`):

```toml
[mcp]          
server_url = "Enter your mcp url"

[embedding]          
api_key = "Enter your api key (match url : https://api.siliconflow.cn/v1/embeddings)"
cache   = "embedding_cache.pkl"

[template]
api_base = "https://ark.cn-beijing.volces.com/api/v3"
api_key  = "Enter your api key"


[openai]             
api_base = "https://api.openai.com/v1"
api_key  = "Enter your api key"

[deepseek]
api_base = "https://api.deepseek.com"
api_key  = "Enter your api key"

# CloseAI (optional, fallback for OpenAI and DeepSeek)
# If OpenAI or DeepSeek API is not configured, CloseAI will be used as fallback
# You can configure only CloseAI, or configure both CloseAI and OpenAI/DeepSeek
[closeai]
api_base = "https://api.openai-proxy.org/v1"
api_key  = "Enter your api key"
```

OriGene supports two deployment methods: **Docker** (recommended) and **Native Installation**. Choose the one that suits your environment.

---

#### Option A: Quick Start with Docker (Recommended)

For the easiest setup experience, we provide Docker-based deployment that handles all dependencies automatically.

**Prerequisites:**
- Docker Engine 20.10 or higher
- docker-compose 1.29 or higher
- Get Docker: https://docs.docker.com/get-docker/

**One-Command Deployment:**

```bash
# Clone and setup in one command
git clone https://github.com/GENTEL-lab/OriGene.git
cd OriGene
./setup.sh
```

Or step by step:

1. **Clone the repository:**

   ```bash
   git clone https://github.com/GENTEL-lab/OriGene.git
   cd OriGene
   ```

2. **Configure API keys and MCP connection:**

   ```bash
   # Edit the configuration file with your API keys
   nano src/local_deep_research/_settings/.secrets.toml
   # or use your preferred editor (vim, code, etc.)
   ```

   Update the `[mcp]` section with your MCP server URL:

   ```toml
   [mcp]          
   server_url = "http://host.docker.internal:8789"
   ```

   > **MCP Server Access in Docker**: Since OriGene runs inside a Docker container, it cannot use `127.0.0.1` to reach the host MCP server. Update the MCP server URL as follows:
   > - For Mac/Windows: Use `http://host.docker.internal:8789`
   > - For Linux: Use `http://172.17.0.1:8789`
   > - Or deploy MCP in Docker and use service name

3. **Build and verify environment:**

   ```bash
   # Quick check script (recommended for first-time setup)
   ./docker-check.sh

   # Or manually build and run checks
   docker-compose build
   docker-compose run --rm origene python -m local_deep_research.test.check_all
   ```

4. **Run OriGene:**

   **Using Makefile (Recommended):**

   ```bash
   # Run environment check
   make check

   # Interactive mode
   make start

   # Quick research
   make quick QUERY="What are therapeutic targets for Alzheimer's disease?"

   # Detailed research
   make detailed QUERY="Analyze molecular mechanisms of EGFR in lung cancer"

   # Run tests
   make test-e2e

   # See all available commands
   make help
   ```

   **Using docker-compose directly:**

   ```bash
   # Interactive mode
   docker-compose run --rm origene

   # Quick research (CLI)
   docker-compose run --rm origene python -m local_deep_research.main "your query here" --mode quick

   # Detailed research (CLI)
   docker-compose run --rm origene python -m local_deep_research.main "your query here" --mode detailed

   # Run end-to-end test
   docker-compose run --rm origene python -m local_deep_research.test.test_example
   ```

   **Important Notes:** 
   - All logs will be saved to the `./logs` directory
   - Embedding cache will be stored in the `./cache` directory

---

#### Option B: Native Installation (uv / conda)

If you prefer native installation without Docker, follow the instructions below.

1. **Clone the repository:**

   ```bash
   git clone https://github.com/GENTEL-lab/OriGene.git
   cd OriGene
   ```

2. **Configure MCP connection and API keys:**

   Edit the configuration file `src/local_deep_research/_settings/.secrets.toml` and fill in your MCP server URL and API keys (see [API Key Configuration](#api-key-configuration) above).

   ```toml
   [mcp]          
   server_url = "http://127.0.0.1:8789"  # Use your actual MCP server URL and port
   ```

   If you changed the port during MCP deployment, make sure to update the `server_url` accordingly.

3. **Install dependencies:**

   ```bash
   cd src
   uv sync
   ```

4. **Activate the virtual environment:**

   ```bash
   source ./.venv/bin/activate
   ```

5. **(Optional) Add the project root to `PYTHONPATH`:**

   ```bash
   export PYTHONPATH=$(pwd):$PYTHONPATH
   ```

6. **System Check & Testing:**

   Before running OriGene, you can verify your environment setup using the built-in check scripts:

   **Run all environment checks (recommended before first use):**
   ```bash
   uv run -m local_deep_research.test.check_all
   ```

   This will check:
   - Python version and all dependencies
   - Configuration files and API keys
   - MCP server connection
   - Core module imports

   **Run individual checks:**
   ```bash
   # Check dependencies only
   uv run -m local_deep_research.test.check_deps

   # Check API keys and configuration
   uv run -m local_deep_research.test.check_config

   # Check MCP server connection
   uv run -m local_deep_research.test.check_mcp

   # Check module imports
   uv run -m local_deep_research.test.check_modules
   ```

   **Run end-to-end test (includes MCP tool call and LLM query):**
   ```bash
   uv run -m local_deep_research.test.test_example
   ```

   Example output:
   ```text
   ======================================================================
                       OriGene Environment Check
   ======================================================================

   > testing dependencies...
   > ✓ Dependencies ready (58 packages checked)

   > checking LLM API keys...
   > ✓ LLM API keys ready (5 APIs configured)

   > checking MCP server connection...
   > ✓ MCP tool list ready (4 checks passed)

   > checking module imports...
   > ✓ All modules ready (15 modules checked)

   ======================================================================
   > ✓ SUCCESS! You can run OriGene now!
   ```

7. **Run OriGene:**

   Launch the interactive assistant:
   ```bash
   uv run -m local_deep_research.main
   ```

   You will see a prompt similar to the following:
   ```text
   Welcome to the Advanced Research System
   Type 'quit' to exit

   Select output type:
   1) Analysis (few minutes, answers questions, summarizes findings)
   2) Detailed Report (more time, generates a comprehensive report with deep analysis)
   Enter number (1 or 2):
   ```

   After selecting an output type, enter your research query and OriGene will return the results.

---

### Benchmark: Running and Scoring

**Using Docker:**

```bash
# Run benchmark evaluation
docker-compose run --rm origene python -m local_deep_research.evaluate_local

# Score the results (example for TRQA-lit-choice)
docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/TRQA_lit_choice/agent_answers_test.txt \
  --original_data benchmark/TRQA_lit_choice/TRQA-lit-choice-172-coreset.csv \
  --model_name "OriAgent"
```

**Using Native Installation:**

Run the benchmark to generate agent answers (you can use either command):

```bash
# From the project root (this directory), after activating the venv
uv run -m local_deep_research.evaluate_local

# Or using python
python -m local_deep_research.evaluate_local
```

Then score the generated results (replace paths if you changed dataset/output names):

```bash
# Example: score TRQA-lit-choice core set results
python local_deep_research/score_evaluation_results.py \
  --agent_results benchmark/TRQA_lit_choice/agent_answers_test.txt \
  --original_data benchmark/TRQA_lit_choice/TRQA-lit-choice-172-coreset.csv \
  --model_name "OriAgent"

# Or using uv
uv run -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/TRQA_lit_choice/agent_answers_test.txt \
  --original_data benchmark/TRQA_lit_choice/TRQA-lit-choice-172-coreset.csv \
  --model_name "OriAgent"
```

---

**Other Benchmarks:**

Using Docker:
```bash
# DbQA benchmark
docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/DbQA/agent_answers_testv2.txt \
  --original_data benchmark/DbQA/DbQA.csv \
  --model_name "OriAgent"

# GPQA benchmark
docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/GPQA/agent_answers_test.txt \
  --original_data benchmark/GPQA/GPQA-lit-choice.csv \
  --model_name "OriAgent"

# TRQA-lit short answer benchmark
docker-compose run --rm origene python -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/TRQA_lit_short_ans/agent_answers_test.txt \
  --original_data benchmark/TRQA_lit_short_ans/TRQA-lit-short-answer-1108.csv \
  --model_name "OriAgent"
```

Using Native Installation:
```bash
# DbQA benchmark
uv run -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/DbQA/agent_answers_testv2.txt \
  --original_data benchmark/DbQA/DbQA.csv \
  --model_name "OriAgent"

# GPQA benchmark
uv run -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/GPQA/agent_answers_test.txt \
  --original_data benchmark/GPQA/GPQA-lit-choice.csv \
  --model_name "OriAgent"

# TRQA-lit short answer benchmark
uv run -m local_deep_research.score_evaluation_results \
  --agent_results benchmark/TRQA_lit_short_ans/agent_answers_test.txt \
  --original_data benchmark/TRQA_lit_short_ans/TRQA-lit-short-answer-1108.csv \
  --model_name "OriAgent"
```

## 3. License

This code repository is licensed under [the Creative Commons Attribution-Non-Commercial ShareAlike International License, Version 4.0 (CC-BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/) (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at https://github.com/GENTEL-lab/OriGene/blob/main/LICENSE.

## 4. Contact

If you have any questions, please raise an issue or contact us at [shuangjia.zheng@sjtu.edu.cn](mailto:shuangjia.zheng@sjtu.edu.cn) or [zhongyuezhang@sjtu.edu.cn](mailto:zhongyuezhang@sjtu.edu.cn).

## 5. Acknowledgements

Thanks to DeepSeek, ChatGPT, Claude, and Gemini for providing powerful language models that made this project possible.

Special thanks to the human experts who assisted us in benchmarking and evaluating the agent's performance!


