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

# Create Python wrapper script that properly handles module loading
RUN cat > /run_server.py << 'EOF'
import sys
import os

# Add the package to path
sys.path.insert(0, '/app/artifacts/openenv-datacleaning/src')
os.chdir('/app')

# Import and run uvicorn
import uvicorn
from openenv_datacleaning.server import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
EOF

# Run the wrapper script
CMD ["python", "/run_server.py"]
