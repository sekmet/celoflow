FROM python:3.13-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml README.md uv.lock* contextwise-0.3.0-py3-none-any.whl ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

COPY . .

# Data directory for persistent storage
RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/info || exit 1

CMD ["uv", "run", "python", "main.py"]
