FROM python:3.11-slim

WORKDIR /app

# Copy entire project structure
COPY . .

# Install dependencies explicitly from pyproject.toml
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.10.0 \
    openai==1.55.0 \
    requests==2.33.0 \
    pytest==8.0.0 \
    httpx==0.28.0

# Configure Python path to find the openenv_datacleaning package
ENV PYTHONPATH=/app/artifacts/openenv-datacleaning/src:${PYTHONPATH}
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

EXPOSE 7860

# Start server from app root, module is on PYTHONPATH
CMD ["python", "-m", "uvicorn", "openenv_datacleaning.server:app", "--host", "0.0.0.0", "--port", "7860"]
