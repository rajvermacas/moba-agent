#!/bin/bash

# MOBA Server Startup Script
# This script starts the FastAPI server for the MOBA agent

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting MOBA Server...${NC}"

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}❌ Poetry not found. Please install Poetry first: https://python-poetry.org/docs/#installation${NC}"
    exit 1
fi

# Check if pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ pyproject.toml not found. This project requires Poetry configuration.${NC}"
    exit 1
fi

# Install dependencies using Poetry
echo -e "${YELLOW}📦 Installing dependencies with Poetry...${NC}"
poetry lock
poetry install

# Create logs directory if it doesn't exist
mkdir -p logs

# Set Python path to include src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Default configuration
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-"8001"}
LOG_LEVEL=${LOG_LEVEL:-"info"}

echo -e "${GREEN}🌐 Server will be available at: http://localhost:${PORT}${NC}"
echo -e "${GREEN}📝 Logs will be written to: logs/moba_server.log${NC}"
echo -e "${GREEN}🔧 Environment: $(poetry run python --version)${NC}"

# Function to handle errors
handle_error() {
    local exit_code=$?
    echo -e "${RED}❌ Error: Server failed to start (Exit code: ${exit_code})${NC}"
    echo -e "${RED}📋 Troubleshooting steps:${NC}"
    echo -e "${YELLOW}   1. Check if port ${PORT} is already in use: lsof -i :${PORT}${NC}"
    echo -e "${YELLOW}   2. Verify src.moba_server.main:app exists and is valid${NC}"
    echo -e "${YELLOW}   3. Check logs/moba_server.log for detailed error messages${NC}"
    echo -e "${YELLOW}   4. Ensure all dependencies are installed: poetry install${NC}"
    echo -e "${YELLOW}   5. Check Python import paths: echo \$PYTHONPATH${NC}"
    exit ${exit_code}
}

# Start the server with error handling
echo -e "${GREEN}▶️  Starting FastAPI server...${NC}"
{
    poetry run python -m uvicorn src.moba_server.main:app \
        --host "${HOST}" \
        --port "${PORT}" \
        --log-level "${LOG_LEVEL}" \
        2>&1 | tee -a logs/moba_server.log
    # --reload
} || handle_error