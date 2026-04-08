FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY . .

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install minimal dependencies directly
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    pydantic==2.10.0 \
    openai==1.55.0 \
    requests==2.33.0

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/artifacts/openenv-datacleaning/src:$PYTHONPATH

EXPOSE 7860

# Run uvicorn with PYTHONPATH set
CMD ["uvicorn", "openenv_datacleaning.server:app", "--host", "0.0.0.0", "--port", "7860"]
