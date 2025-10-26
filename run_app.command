#!/bin/bash
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip >/dev/null
pip install flask reportlab pillow >/dev/null
python app.py
