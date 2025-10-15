# Render Deploy (Quick)
1) Put this `app.py`, `requirements.txt`, `Procfile` into your project WITH your existing `templates/` and `static/`.
2) Push to GitHub.
3) On Render → New → Web Service → pick repo.
   Build: pip install -r requirements.txt
   Start: gunicorn app:app
4) Add Environment Variables:
   ADMIN_USERNAME=DD brothers
   ADMIN_PASSWORD=Ash#1Laddi
   DELETE_PASSWORD=1322420
5) Open your public URL.
