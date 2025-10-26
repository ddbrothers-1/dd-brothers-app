@echo off
cd %~dp0
if not exist venv (
  python -m venv venv
)
call venv\Scripts\activate
pip install --upgrade pip
pip install flask reportlab pillow
python app.py
pause
