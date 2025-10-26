
DD Brothers Transport Manager - Render Deploy Bundle

1. This folder should be your GitHub repo root.
2. Files required:
   - app.py
   - requirements.txt
   - Procfile
   - templates/ (all html templates)
   - static/style.css , static/dd_logo.png
   - reports/  (empty but must exist so PDFs can be saved)

3. On Render:
   - Runtime: Python 3
   - Start Command: gunicorn app:app
