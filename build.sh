#!/usr/bin/env bash
# Build script for Render deployment
pip install -r requirements.txt
python -c "import app; app.init_db(); print('DB initialized successfully')"
