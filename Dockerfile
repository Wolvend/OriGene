# OriGene Docker Image
# Multi-stage build for optimized image size

FROM python:3.13-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy project files
COPY src/ /app/src/

# Create virtual environment and install dependencies
WORKDIR /app/src
RUN uv venv .venv --python=3.13 && \
    . .venv/bin/activate && \
    uv sync

# Final stage - minimal runtime image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/src/.venv /app/src/.venv

# Copy application code
COPY src/ /app/src/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV PATH="/app/src/.venv/bin:$PATH"

# Create directories for logs and cache
RUN mkdir -p /app/logs /app/cache

# Set working directory to src
WORKDIR /app/src

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command - run environment checks
CMD ["/app/src/.venv/bin/python", "-m", "local_deep_research.test.check_all"]
