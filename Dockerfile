FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy package structure from artifacts/openenv-datacleaning
COPY artifacts/openenv-datacleaning/pyproject.toml .
COPY artifacts/openenv-datacleaning/src/ src/
COPY artifacts/openenv-datacleaning/openenv.yaml .

# Install the package
RUN pip install --no-cache-dir -e ".[dev]"

# Also install dependencies for inference script
RUN pip install --no-cache-dir openai requests

ENV PORT=7860
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "openenv_datacleaning.server:app", "--host", "0.0.0.0", "--port", "7860"]
