#!/usr/bin/env bash
set -e

echo "====================================================================="
echo " Brightloop Subscription Management Platform — Launcher (UNIX)"
echo " Odoo Hackathon Kochi"
echo "====================================================================="

# 1. Copy .env.example to .env if missing
if [ ! -f ".env" ]; then
    echo "[1/4] Creating .env from .env.example..."
    cp .env.example .env
else
    echo "[1/4] Existing .env detected."
fi

# 2. Virtual environment setup
if [ ! -f "venv/bin/python" ]; then
    echo "[2/4] Initializing Python virtual environment in ./venv..."
    python3 -m venv venv || python -m venv venv
else
    echo "[2/4] Python virtual environment ready."
fi

# 3. Dependencies
echo "[3/4] Checking and installing dependencies..."
./venv/bin/pip install -q -r requirements.txt

# 4. Database initialization and seeding check
if [ ! -f "brightloop.db" ]; then
    echo "[4/4] First boot: Initializing schema and seeding demo catalog..."
    ./venv/bin/python seed.py
else
    echo "[4/4] Database brightloop.db detected."
fi

echo ""
echo "====================================================================="
echo " SUCCESS: Brightloop is starting on http://localhost:8000"
echo " - Web Application: http://localhost:8000"
echo " - Interactive API Docs: http://localhost:8000/docs"
echo ""
echo " Default Demo Credentials:"
echo "   Administrator : admin@brightloop.com / Admin@12345"
echo "   Billing Staff : staff@brightloop.com / Staff@12345"
echo "   Customer Demo : alex@acme.com        / Customer@12345"
echo "====================================================================="
echo ""

# Single worker is required because SSE in-process event bus runs in-memory
exec ./venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1
