FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY . .

# Install all dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.10.0 \
    openai==1.55.0 \
    requests==2.33.0 \
    pytest==8.0.0 \
    httpx==0.28.0

# Set Python to look for modules in the src directory
ENV PYTHONPATH=/app/artifacts/openenv-datacleaning/src:/app:${PYTHONPATH}
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

# Start server with explicit PYTHONPATH - use exec form to ensure proper signal handling
ENTRYPOINT ["/bin/sh", "-c"]
CMD ["python -m uvicorn openenv_datacleaning.server:app --host 0.0.0.0 --port 7860"]
