#!/bin/bash
cd /home/sekmet/DEVELOPMENT/x402-PROTOCOL/CELO-HACKATHON/celoflow
source .venv/bin/activate
uv run uvicorn server:app --host 0.0.0.0 --port 8000 --reload 2>&1 | tee agent-server.log
