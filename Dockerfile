FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire project structure
COPY . .

# Install dependencies from root pyproject.toml if exists, otherwise install packages directly
RUN if [ -f "artifacts/openenv-datacleaning/pyproject.toml" ]; then \
    cd artifacts/openenv-datacleaning && pip install --no-cache-dir -e ".[dev]"; \
    else pip install --no-cache-dir fastapi uvicorn pydantic openai requests; fi

# Ensure openenv_datacleaning is in the path
ENV PYTHONPATH="/app/artifacts/openenv-datacleaning/src:${PYTHONPATH}"

ENV PORT=7860
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

# Run the server
CMD ["sh", "-c", "cd /app/artifacts/openenv-datacleaning && python -m uvicorn openenv_datacleaning.server:app --host 0.0.0.0 --port 7860"]
