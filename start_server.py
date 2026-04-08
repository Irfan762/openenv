#!/usr/bin/env python
"""
Startup script for OpenEnv DataCleaning Server
Ensures proper module path setup before launching uvicorn
"""

import sys
import os

# Detect if running in Docker (check for /app path) or locally
if os.path.exists('/app'):
    # Running in Docker
    app_root = '/app'
    os.chdir(app_root)
else:
    # Running locally - use current directory
    app_root = os.getcwd()

# Add the src directory to Python path
src_path = os.path.join(app_root, 'artifacts', 'openenv-datacleaning', 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Verify imports work
try:
    from openenv_datacleaning.server import app
    print(f"✓ Successfully imported app from openenv_datacleaning.server")
except ImportError as e:
    print(f"✗ Failed to import app: {e}")
    sys.exit(1)

# Launch uvicorn
if __name__ == '__main__':
    import uvicorn
    
    print("Starting OpenEnv DataCleaning Server...")
    print(f"PYTHONPATH={sys.path}")
    print(f"Working directory: {os.getcwd()}")
    
    uvicorn.run(
        app,
        host='0.0.0.0',
        port=7860,
        log_level='info',
        access_log=True
    )
