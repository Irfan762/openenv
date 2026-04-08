FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy entire project
COPY . .

# Install the openenv-datacleaning package in editable mode
WORKDIR /app/artifacts/openenv-datacleaning
RUN pip install --no-cache-dir -e ".[dev]"

# Install additional dependencies
RUN pip install --no-cache-dir openai requests

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

# Work from app root
WORKDIR /app

# Expose port
EXPOSE 7860

# Start the server
CMD ["uvicorn", "openenv_datacleaning.server:app", "--host", "0.0.0.0", "--port", "7860"]
