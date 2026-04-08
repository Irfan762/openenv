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

# Add src directory to PYTHONPATH
ENV PYTHONPATH=/app/artifacts/openenv-datacleaning/src
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

# Create startup script
RUN echo '#!/bin/sh\n\
set -e\n\
echo "Starting OpenEnv server..."\n\
cd /app\n\
python -m uvicorn openenv_datacleaning.server:app --host 0.0.0.0 --port 7860\n\
' > /start.sh && chmod +x /start.sh

CMD ["/start.sh"]
