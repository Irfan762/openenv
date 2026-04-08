FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy entire project
COPY . .

# First install the base dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.32.0 \
    pydantic>=2.10.0 \
    openai>=1.55.0 \
    requests>=2.33.0 \
    pytest>=8.0 \
    httpx>=0.28.0

# Install the openenv-datacleaning package
WORKDIR /app/artifacts/openenv-datacleaning
RUN pip install --no-cache-dir -e .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/artifacts/openenv-datacleaning/src:/app:${PYTHONPATH}
ENV PORT=7860

# Work from openenv package directory for server startup
WORKDIR /app/artifacts/openenv-datacleaning

# Expose port
EXPOSE 7860

# Start the server
CMD ["python", "-m", "uvicorn", "openenv_datacleaning.server:app", "--host", "0.0.0.0", "--port", "7860"]
