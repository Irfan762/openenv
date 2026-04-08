FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY . .

# Install the openenv-datacleaning package with all dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.10.0 \
    openai==1.55.0 \
    requests==2.33.0

# Install the openenv-datacleaning package from artifacts
RUN pip install --no-cache-dir -e ./artifacts/openenv-datacleaning

ENV PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["python", "/app/start_server.py"]
