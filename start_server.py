#!/usr/bin/env python
"""
Startup script for OpenEnv DataCleaning Server
Robust module loading that works both locally and in Docker
"""

import sys
import os
import traceback

def main():
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = script_dir if os.path.exists(os.path.join(script_dir, 'artifacts')) else os.getcwd()
    
    # Build the source path
    src_path = os.path.join(repo_root, 'artifacts', 'openenv-datacleaning', 'src')
    
    # Add to sys.path
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    
    try:
        from openenv_datacleaning.server import app
        import uvicorn
        
        uvicorn.run(
            app,
            host='0.0.0.0',
            port=7860,
            log_level='info',
        )
    except ImportError as e:
        print(f"Import Error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
