#!/usr/bin/env python
"""
Startup script for OpenEnv DataCleaning Server
Simply run uvicorn to serve the app installed via pip
"""

import sys

def main():
    try:
        # Import the app from the installed package
        from openenv_datacleaning.server import app
        import uvicorn
        
        # Run the server
        uvicorn.run(
            app,
            host='0.0.0.0',
            port=7860,
            log_level='info',
        )
    except ImportError as e:
        print(f"Import Error: {e}", file=sys.stderr)
        print("Make sure openenv-datacleaning is installed", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
