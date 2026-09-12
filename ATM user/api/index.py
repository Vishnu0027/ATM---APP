"""
Vercel Serverless Function Entry Point for FastAPI Backend.
Exposes the ASGI 'app' instance for @vercel/python runtime.
"""

import os
import sys
from pathlib import Path

# Ensure project root (containing 'backend' directory) is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import the FastAPI application instance
from backend.app.main import app

# Export app for Vercel
__all__ = ["app"]
