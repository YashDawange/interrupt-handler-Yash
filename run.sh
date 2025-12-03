#!/usr/bin/env bash
# Simple helper to run the agent inside a venv (POSIX)
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.template .env 2>/dev/null || true
echo "Make sure to edit .env and set USE_SIMULATION=false for live mode."
python main_agent.py
