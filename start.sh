#!/bin/bash

# Cultura Visualizer - Start Script
# Usage: ./start.sh [dev|prod]
#   dev  - Start frontend and backend in development mode (default)
#   prod - Build frontend and start backend serving the built app

set -e

cd "$(dirname "$0")"

MODE="${1:-dev}"

# Check for .env file
if [ ! -f ".env" ] && [ ! -f "backend/.env" ]; then
    echo "Warning: No .env file found. Make sure environment variables are set."
fi

if [ "$MODE" = "prod" ]; then
    echo "Building frontend..."
    cd frontend
    npm install
    npm run build
    cd ..

    echo "Starting backend (serving built frontend)..."
    source .venv/bin/activate 2>/dev/null || true
    python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
else
    echo "Starting in development mode..."

    # Start backend in background
    echo "Starting backend on http://localhost:8000..."
    (
        source .venv/bin/activate 2>/dev/null || true
        python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    ) &
    BACKEND_PID=$!

    # Give backend time to start
    sleep 2

    # Start frontend
    echo "Starting frontend on http://localhost:5173..."
    (
        cd frontend
        npm run dev
    ) &
    FRONTEND_PID=$!

    # Cleanup on exit
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

    echo ""
    echo "App running:"
    echo "  Frontend: http://localhost:5173"
    echo "  Backend:  http://localhost:8000"
    echo ""
    echo "Press Ctrl+C to stop"

    wait
fi
