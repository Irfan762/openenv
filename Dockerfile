FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY . .

# Upgrade pip and install base dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.10.0 \
    openai==1.55.0 \
    requests==2.33.0

# Install the local package - use standard pip install instead of -e
RUN cd /app/artifacts/openenv-datacleaning && pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1

EXPOSE 7860

# Run uvicorn directly pointing to the installed package
CMD ["python", "-m", "uvicorn", "openenv_datacleaning.server:app", "--host", "0.0.0.0", "--port", "7860"]
