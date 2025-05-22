#!/bin/bash
# Default port if not set in environment
PORT=${PORT:-8000}

# Create necessary directories
mkdir -p temp
mkdir -p output

# Start the FastAPI application
exec uvicorn main:app --host 0.0.0.0 --port $PORT
