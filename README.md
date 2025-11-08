# 🛰️ TARS-9 Sentinel – Mission Horizon

**ATEC’25 CyberQuest Project** — Autonomous AI-driven cyber defense for interstellar missions.

## Overview
TARS-9 Sentinel monitors spacecraft telemetry to detect cyber anomalies across AI, comms, propulsion, and life-support. It writes events to an immutable hash-chain log and visualizes system health on a live, space-themed dashboard.

## Features
- Real-time anomaly detection  
- Immutable hash-chain log  
- Automated response protocol  
- Flask dashboard (animated UI)

## Prerequisites
- Python 3.11+ (recommended)

## Setup
```bash
# clone
git clone https://github.com/mhamdiamiin/ATEC25.git
cd ATEC25

# create & activate venv (Windows PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
# python3 -m venv .venv && source .venv/bin/activate

# install deps
pip install -r requirements.txt

#run 
# 1) Generate fresh anomalies + immutable log
python ./src/run.py

# 2) Launch the dashboard
python ./app/app.py
# open http://127.0.0.1:5000
