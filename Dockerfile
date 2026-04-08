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

ENV PYTHONUNBUFFERED=1

EXPOSE 7860

# Use the startup script to ensure proper module loading
CMD ["python", "/app/start_server.py"]
